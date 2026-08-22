"""
bag-health-mcp — Swiss Federal Office of Public Health (BAG)
Infectious Disease Surveillance MCP Server

Data source: IDD API (api.idd.bag.admin.ch)
No authentication required. All data is public.
"""

from __future__ import annotations

import asyncio
import difflib
import ipaddress
import json
import logging
import os
import random
import socket
import sys
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, NoReturn
from urllib.parse import urlsplit

import httpcore
import httpx
from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import __version__

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDD_BASE = "https://api.idd.bag.admin.ch"
# Additional Swiss health-data sources reached by the multi-source indicator
# tools (see docs/tool-design-health-indicators.md). Obsan exposes a clean
# JSON API; Versorgungsatlas a static JSON catalogue + SSR indicator pages.
# Sucht Schweiz's HBSC series are obtained via the Obsan mirror, so no separate
# host is needed for it.
OBSAN_BASE = "https://ind.obsan.admin.ch"
VERSORGUNGSATLAS_BASE = "https://www.versorgungsatlas.ch"
TIMEOUT = 30.0
USER_AGENT = f"bag-health-mcp/{__version__} (https://github.com/malkreide/bag-health-mcp)"


# ---------------------------------------------------------------------------
# Runtime configuration (ARCH-004)
# ---------------------------------------------------------------------------
#
# Transport-agnostic config object: the server logic reads settings from this
# object, not ad-hoc from os.environ / sys.argv. Values come from MCP_* env vars
# (or their defaults). main() builds one instance and uses it to wire up
# logging, transport and binding.


class Settings(BaseSettings):
    """Runtime configuration, sourced from ``MCP_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="MCP_", extra="ignore")

    transport: str = ""  # "http"/"streamable-http" | "stdio" | "" (fall back to --http)
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    # SEC-009: shared-secret bearer token for the HTTP transport. When set, HTTP
    # requests must present "Authorization: Bearer <token>"; when empty, no auth
    # is enforced (suitable for stdio/local; HTTP should set this or sit behind a
    # gateway). The server itself reaches only public data — this gates *who may
    # invoke it*, not data sensitivity.
    auth_token: str = ""
    # SDK-004: comma-separated CORS allow-list for browser MCP clients. Empty =
    # no cross-origin access. Never a wildcard.
    cors_origins: str = ""
    # SEC-005: comma-separated Host allow-list for the HTTP transport — the
    # names this server is reachable under, e.g. "bag.example.ch:8000". This is
    # the *inbound* counterpart to the module-level ``ALLOWED_HOSTS`` below,
    # which is the egress allow-list and is not configurable. Empty on a
    # non-local bind leaves the check off (the gateway-fronted default, see
    # ``build_transport_security``).
    allowed_hosts: str = ""

    def wants_http(self, *, http_flag: bool) -> bool:
        """Whether to serve over Streamable HTTP (vs. stdio), SCALE-001.

        ``MCP_TRANSPORT`` wins when set; otherwise the ``--http`` CLI flag.
        """
        t = self.transport.strip().lower()
        if t:
            return t in {"http", "streamable-http", "streamable_http"}
        return http_flag

    @property
    def is_local_bind(self) -> bool:
        return self.host in ("127.0.0.1", "::1", "localhost")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


# Code-layer egress allow-list (SEC-021): the only hosts this server may ever
# talk to are the BAG IDD API plus the two additional public health-data hosts
# used by the indicator tools, derived from their base URLs so there is a single
# source of truth. Enforced on every outbound request — including redirect hops —
# by the egress guard below, and only over HTTPS (SEC-004 scheme enforcement).
ALLOWED_HOSTS = frozenset(
    h
    for h in (
        urlsplit(IDD_BASE).hostname,
        urlsplit(OBSAN_BASE).hostname,
        urlsplit(VERSORGUNGSATLAS_BASE).hostname,
    )
    if h
)
ALLOWED_SCHEMES = frozenset({"https"})

# Logs go to stderr (stdout is reserved for the stdio JSON-RPC channel).
logger = logging.getLogger("bag_health_mcp")

# ---------------------------------------------------------------------------
# Structured logging (OBS-003 / OBS-004)
# ---------------------------------------------------------------------------
#
# OBS-004: stdout is the stdio JSON-RPC transport, so every log line must go to
# stderr — a stray print/handler on stdout would corrupt the protocol stream.
# OBS-003: emit one JSON object per line with an RFC 5424 severity, so log
# aggregators can parse and filter by level.

# Python logging level -> RFC 5424 severity (keyword, numeric code).
_RFC5424_SEVERITY: dict[int, tuple[str, int]] = {
    logging.CRITICAL: ("crit", 2),
    logging.ERROR: ("err", 3),
    logging.WARNING: ("warning", 4),
    logging.INFO: ("info", 6),
    logging.DEBUG: ("debug", 7),
}


class JsonLogFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object (OBS-003).

    Includes an RFC 5424 severity keyword and numeric code alongside the Python
    level name, plus exception text when present. Reserved/internal record
    attributes are skipped; any structured fields passed via ``extra=`` are
    merged in.
    """

    _RESERVED = frozenset(logging.makeLogRecord({}).__dict__.keys()) | {
        "message",
        "asctime",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        severity, severity_code = _RFC5424_SEVERITY.get(record.levelno, ("info", 6))
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "severity": severity,
            "severity_code": severity_code,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Merge any caller-provided structured fields (logger.x(..., extra={...})).
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def _configure_logging(level: str | int | None = None) -> None:
    """Attach a stderr JSON handler to the package logger (OBS-003/OBS-004).

    Idempotent: a second call replaces the handler rather than stacking another.
    The level comes from ``level``, else ``MCP_LOG_LEVEL`` (default ``INFO``).
    ``propagate`` is disabled so records are not also emitted by the root logger
    (which could reach stdout). Called from :func:`main`; library importers keep
    full control of their own logging config.
    """
    resolved = level if level is not None else os.environ.get("MCP_LOG_LEVEL", "INFO")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLogFormatter())
    handler.set_name("bag_health_mcp_json")

    # Drop any handler we previously installed so repeated calls stay idempotent.
    for existing in list(logger.handlers):
        if existing.get_name() == "bag_health_mcp_json":
            logger.removeHandler(existing)
    logger.addHandler(handler)
    logger.setLevel(resolved)
    logger.propagate = False


# ---------------------------------------------------------------------------
# Distributed tracing (OBS-006)
# ---------------------------------------------------------------------------
#
# OpenTelemetry is an *optional* dependency. Tracing stays a complete no-op
# unless (a) the opentelemetry packages are installed (the `telemetry` extra)
# and (b) an OTLP endpoint is configured via the standard OTEL_* env vars. With
# no provider configured, ``trace.get_tracer`` returns the API's no-op tracer,
# so the per-tool span wrapper and the client instrumentation cost nothing.
#
# Spans carry only the tool name and error class — never arguments, cantons or
# upstream data — so no PII or surveillance content is exported (OBS-002).

try:  # optional: present only with the `telemetry` extra
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import Status as _OtelStatus
    from opentelemetry.trace import StatusCode as _OtelStatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by the base (no-extra) install
    _OTEL_AVAILABLE = False

# Set to True by _configure_tracing() once a real provider is wired up; gates the
# httpx client instrumentation so we don't instrument when tracing is off.
_tracing_enabled = False


def _tracer() -> Any:
    """Return the OTel tracer, or ``None`` when telemetry isn't available.

    Even when available but unconfigured, the returned tracer is OTel's no-op
    tracer, so wrapping a tool in a span is essentially free.
    """
    if not _OTEL_AVAILABLE:
        return None
    return _otel_trace.get_tracer("bag_health_mcp")


def _configure_tracing() -> bool:
    """Wire up an OTLP exporter if telemetry is available and configured.

    Enabled only when the opentelemetry packages are installed *and* an endpoint
    is set (``OTEL_EXPORTER_OTLP_ENDPOINT`` or the traces-specific variant) — the
    standard OTel convention. Returns whether tracing was enabled. Idempotent and
    safe to call when telemetry is absent (returns False, no error).
    """
    global _tracing_enabled
    if not _OTEL_AVAILABLE:
        return False
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if not endpoint:
        return False

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = os.environ.get("OTEL_SERVICE_NAME", "bag-health-mcp")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    _otel_trace.set_tracer_provider(provider)
    _tracing_enabled = True
    logger.info("OpenTelemetry tracing enabled", extra={"otel_endpoint": endpoint})
    return True


def _traced(fn: Any) -> Any:
    """Wrap an async tool in a span named ``tool/<name>`` (OBS-006).

    No-op overhead when tracing is unconfigured (the no-op tracer). The span
    records only the tool name and, on failure, the error class — never tool
    arguments or upstream data (OBS-002). Re-raises so error handling is
    unchanged.
    """
    import functools

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        tracer = _tracer()
        if tracer is None:
            return await fn(*args, **kwargs)
        with tracer.start_as_current_span(f"tool/{fn.__name__}") as span:
            span.set_attribute("mcp.tool.name", fn.__name__)
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                span.set_attribute("mcp.tool.is_error", True)
                span.set_attribute("mcp.tool.error_type", type(exc).__name__)
                span.set_status(_OtelStatus(_OtelStatusCode.ERROR))
                raise

    return wrapper


def _instrument_client(client: httpx.AsyncClient) -> None:
    """Instrument the pooled client for per-request HTTP spans, if tracing is on.

    Instruments only this client instance (not global httpx), so nothing happens
    unless tracing was enabled by :func:`_configure_tracing`.
    """
    if not (_OTEL_AVAILABLE and _tracing_enabled):
        return
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor.instrument_client(client)
    except Exception as exc:  # pragma: no cover - defensive; never break startup
        logger.warning("could not instrument httpx client for tracing: %r", exc)


# Swiss cantons (incl. FL = Liechtenstein as BAG tracks it)
CANTONS = [
    "AG",
    "AI",
    "AR",
    "BE",
    "BL",
    "BS",
    "FR",
    "GE",
    "GL",
    "GR",
    "JU",
    "LU",
    "NE",
    "NW",
    "OW",
    "SG",
    "SH",
    "SO",
    "SZ",
    "TG",
    "TI",
    "UR",
    "VD",
    "VS",
    "ZG",
    "ZH",
    "FL",
    "all",
]

# Data classification (CH-006, Stadt Zürich Schulamt scheme).
# All data served is public BAG IDD Open Government Data, already aggregated and
# anonymised at canton level by the BAG by law, with small cells suppressed at
# source. It is therefore "Öffentlich / BUI" (not VERTRAULICH/STRENG VERTRAULICH).
# See docs/datenklassifikation-schulamt.md.
DATA_CLASSIFICATION = "ÖFFENTLICH / BUI"
# The smallest geographic granularity this server ever exposes is the canton.
# It never re-aggregates below what the upstream OGD API returns, so it cannot
# create a finer-grained (re-identifying) view; this documents that floor and is
# surfaced on the aggregating overview tool for transparency. It is not a
# re-suppression threshold — the BAG already suppresses small cells at source.
MIN_AGGREGATION_LEVEL = "canton"

# Disease-topic taxonomy: which known IDD topics fall in each category. Used both
# to categorise bag_health_mcp__list_diseases output and to serve the bag://disease-categories
# reference resource, so the two never drift (single source of truth).
DISEASE_CATEGORIES: dict[str, set[str]] = {
    "respiratory": {
        "acute_respiratory_infection",
        "influenza",
        "influenza-like_illness",
        "respiratory_pathogens",
        "covid19",
    },
    "enteric": {
        "campylobacteriosis",
        "salmonellosis",
        "ehec",
        "listeriosis",
        "hepatitis_a",
        "hepatitis_e",
        "shigellosis",
        "cholera",
        "typhoidParatyphoidFever",
        "trichinellosis",
        "botulism",
        "qFever",
    },
    "sti_and_bloodborne": {
        "hiv",
        "aids",
        "syphilis",
        "gonorrhea",
        "chlamydiosis",
        "hepatitis_b",
        "hepatitis_c",
    },
    "vaccine_preventable": {
        "measles",
        "rubella",
        "pertussis",
        "diphtheria",
        "tetanus",
        "haemophilusInfluenzae",
        "ipd",
        "meningo",
        "herpesZoster",
        "postZosterNeuralgia",
    },
    "vector_borne": {
        "lyme_borreliosis",
        "tick-borne_encephalitis",
        "dengueFever",
        "malaria",
        "westnileFever",
        "chikungunya",
        "zika",
        "yellowFever",
        "hanta",
        "tularemia",
    },
}

# ---------------------------------------------------------------------------
# HTTP client lifespan (SDK-001)
# ---------------------------------------------------------------------------
#
# A single pooled httpx.AsyncClient is opened for the server's whole lifetime
# and shared across every tool, instead of opening a new client (new TCP/TLS
# connection) per call. Its lifetime is owned by the MCPServer lifespan below;
# an AsyncExitStack manages teardown so additional async resources can be added
# later with the same guaranteed-cleanup semantics.

# Process-wide pooled client, owned by ``lifespan``. ``None`` whenever no
# lifespan is running; in that case ``_client`` falls back to a per-call client
# (see below), so this global is only ever the lifespan-managed instance.
_shared_client: httpx.AsyncClient | None = None


class EgressNotAllowed(Exception):
    """Raised when an outbound request targets a non-allow-listed host/scheme.

    Carries only safe, non-sensitive text; the offending URL is logged
    server-side by the guard, never surfaced to the model (OBS-002).
    """


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True if an IP must never be contacted (SSRF blocklist, SEC-004).

    Blocks private, loopback, link-local (incl. the 169.254.169.254 cloud
    metadata endpoint), reserved, multicast and unspecified addresses — every
    range that should be unreachable from a server that only talks to a public
    API.
    """
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def _resolve_host(host: str) -> list[str]:
    """Resolve ``host`` to its IP addresses (overridable in tests).

    Pulled out as a module-level function so unit tests can substitute a stub
    and avoid real DNS. A literal IP resolves to itself without a lookup.
    """
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


async def _assert_egress_allowed(url: httpx.URL) -> None:
    """Enforce the egress allow-list, HTTPS, and IP blocklist on a URL.

    Three layers (SEC-021 / SEC-004):
      1. scheme must be https;
      2. host must be in ALLOWED_HOSTS;
      3. the host must resolve only to public IPs — if DNS returns a private,
         loopback, link-local (e.g. cloud metadata), reserved, multicast or
         unspecified address, the request is refused. This covers the case the
         host-name allow-list alone cannot: an allowed host that resolves (or is
         rebound) to an internal address.
    Raises :class:`EgressNotAllowed`; the raw URL/IPs are logged, not returned.
    """
    if url.scheme not in ALLOWED_SCHEMES or url.host not in ALLOWED_HOSTS:
        logger.warning("blocked egress to disallowed target: %s", url)
        raise EgressNotAllowed(
            f"refused to contact a non-allow-listed endpoint ({url.scheme} host); "
            "this server may only reach its allow-listed public data hosts "
            "(BAG IDD, Obsan, Versorgungsatlas)"
        )

    host = url.host
    try:
        addresses = await _resolve_host(host)
    except OSError as exc:
        logger.warning("egress DNS resolution failed for %s: %r", host, exc)
        raise EgressNotAllowed(
            "could not resolve the BAG IDD API host; refusing the request"
        ) from exc

    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr.split("%", 1)[0])  # strip IPv6 zone id
        except ValueError:
            logger.warning("egress: unparseable resolved address %r for %s", addr, host)
            raise EgressNotAllowed("host resolved to an unparseable address; refused")
        if _is_disallowed_ip(ip):
            logger.warning("blocked egress: host %s resolved to disallowed IP %s", host, ip)
            raise EgressNotAllowed(
                "the target host resolved to a non-public address; refused as a "
                "possible SSRF attempt"
            )


async def _egress_guard(request: httpx.Request) -> None:
    """httpx request event-hook: validate every hop, including redirects.

    Registered on the client so it fires for the initial request *and* each
    redirect target, closing the follow_redirects bypass flagged by SEC-004.
    Validates scheme, host allow-list, and resolved IP blocklist.

    Note this is the *first* of two checks. It runs before the connection is
    established and gives a fast, early rejection, but on its own it is subject
    to a DNS resolve-vs-connect TOCTOU race: the address it validates may differ
    from the one httpcore later connects to. :class:`_PinningBackend` closes that
    window by validating and connecting to the *same* address (SEC-005).
    """
    await _assert_egress_allowed(request.url)


class _PinningBackend(httpcore.AsyncNetworkBackend):
    """Network backend that pins outbound TCP to a validated IP (SEC-005).

    DNS rebinding / TOCTOU defence on the *outbound* side: the egress hook
    validates a URL before connecting, but DNS could resolve differently between
    that check and the actual socket connect. This backend resolves the host
    once, rejects the connection if *any* resolved address is non-public
    (:func:`_is_disallowed_ip`), and then connects to that exact validated IP —
    so the address checked is the address dialled, with no second lookup.

    TLS still uses the original hostname for SNI/cert validation: httpcore calls
    ``start_tls(server_hostname=...)`` separately from ``connect_tcp``, so
    pinning the connect address does not weaken certificate checking.

    Wraps the pool's default backend; a literal-IP host is validated directly
    without a DNS lookup. ``connect_unix_socket`` is refused outright — this
    server only ever speaks to a remote HTTPS API.
    """

    def __init__(self, inner: httpcore.AsyncNetworkBackend) -> None:
        self._inner = inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            ipaddress.ip_address(host)
            candidates = [host]  # already an IP literal; no lookup needed
        except ValueError:
            try:
                candidates = await _resolve_host(host)
            except OSError as exc:
                logger.warning("egress DNS resolution failed for %s: %r", host, exc)
                raise EgressNotAllowed(
                    "could not resolve the BAG IDD API host; refusing the request"
                ) from exc

        pinned: str | None = None
        for addr in candidates:
            stripped = addr.split("%", 1)[0]  # strip IPv6 zone id
            try:
                ip = ipaddress.ip_address(stripped)
            except ValueError:
                logger.warning("egress: unparseable resolved address %r for %s", addr, host)
                raise EgressNotAllowed("host resolved to an unparseable address; refused")
            if _is_disallowed_ip(ip):
                logger.warning("blocked egress: host %s resolved to disallowed IP %s", host, ip)
                raise EgressNotAllowed(
                    "the target host resolved to a non-public address; refused as a "
                    "possible SSRF attempt"
                )
            if pinned is None:
                pinned = stripped

        # Connect to the exact address we just validated (no re-resolution).
        return await self._inner.connect_tcp(
            pinned,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        raise EgressNotAllowed("unix-socket egress is not permitted")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def _new_client() -> httpx.AsyncClient:
    # The pinning backend (SEC-005) sits below httpx's transport layer: it owns
    # the actual DNS + connect, so the address validated is the address dialled.
    transport = httpx.AsyncHTTPTransport()
    transport._pool._network_backend = _PinningBackend(transport._pool._network_backend)
    return httpx.AsyncClient(
        base_url=IDD_BASE,
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        # Redirects stay enabled for legitimate same-host hops, but every hop is
        # re-validated by the egress guard, so a redirect to an internal host
        # can no longer be followed (SEC-004 / SEC-021).
        follow_redirects=True,
        event_hooks={"request": [_egress_guard]},
        transport=transport,
    )


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[dict[str, Any]]:
    """Open one pooled httpx.AsyncClient for the server's lifetime (SDK-001).

    The client is also exposed in the lifespan context (``http_client``) for
    inspection / future Context injection. ``AsyncExitStack`` guarantees the
    client — and any further resources entered on the stack — are closed on
    shutdown even if startup of a later resource fails.
    """
    global _shared_client
    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(_new_client())
        _instrument_client(client)  # per-request HTTP spans when tracing is on (OBS-006)
        _shared_client = client
        logger.info("opened shared httpx client for %s", server.name)
        try:
            yield {"http_client": client}
        finally:
            _shared_client = None
            logger.info("closed shared httpx client for %s", server.name)


# ---------------------------------------------------------------------------
# MCPServer setup
# ---------------------------------------------------------------------------

# SEP-2549, Spec 2026-07-28: die auflistenden Methoden tragen `ttlMs` und
# `cacheScope`. Das SDK setzt beides auf «sofort veraltet, nie geteilt» — ein
# Server ohne `cache_hints` verhaelt sich also nicht neutral, sondern laesst
# jeden Client bei jeder Verbindung neu auflisten, fuer Listen, die beim Import
# feststehen und sich zur Laufzeit des Prozesses nicht aendern koennen.
#
# `public` folgt aus der Sache, nicht aus Bequemlichkeit: die 10 Tools werden
# per Dekorator beim Import registriert, es gibt keine Filterung nach Aufrufer.
# Sobald eine Liste vom Aufrufer abhaengt, muss der Scope im selben Commit auf
# `private` wechseln.
#
# `resources/read` und `prompts/get` stehen bewusst nicht dabei: das waere eine
# Zusicherung ueber den INHALT statt ueber das Verzeichnis.
LIST_CACHE_TTL_MS = 300_000

CACHE_HINTS = {
    "tools/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "resources/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "resources/templates/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "prompts/list": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
    "server/discover": CacheHint(ttl_ms=LIST_CACHE_TTL_MS, scope="public"),
}

mcp = MCPServer(
    name="bag-health-mcp",
    cache_hints=CACHE_HINTS,
    instructions=(
        "Access Swiss Federal Office of Public Health (BAG) infectious disease "
        "surveillance data via the IDD API. Covers 51 pathogens including "
        "influenza, COVID-19, measles, tuberculosis, wastewater surveillance, "
        "and more. Data is updated weekly every Wednesday. "
        "Use bag_health_mcp__list_diseases first to discover available topics, then "
        "bag_health_mcp__get_series_details to understand available filters, then "
        "bag_health_mcp__get_disease_data to retrieve time-series values."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Error handling (OBS-001 / OBS-002)
# ---------------------------------------------------------------------------
#
# Protocol vs. execution errors are kept separate:
#   * Protocol errors (unknown tool, malformed request, schema-invalid params)
#     are raised by the MCP SDK itself with standard JSON-RPC error codes — we
#     never fabricate those.
#   * Execution errors (upstream non-200, not-found, unreachable API, malformed
#     series_id) are signalled with ``_fail`` below, which raises ``ToolError``.
#     The SDK converts a raised ToolError into a tool *result* with
#     ``isError: true`` (not a protocol error), so the model gets a clear,
#     actionable message it can recover from.
#
# Raw upstream detail (status bodies, exception text, URLs) is logged
# server-side only and never placed in the returned message (OBS-002).


def _fail(message: str, *, detail: str | None = None) -> NoReturn:
    """Raise an execution-class error as an MCP tool result (``isError: true``).

    ``message`` must be safe to expose to the model; ``detail`` (optional) holds
    the raw upstream cause and is logged to stderr only.
    """
    if detail:
        logger.warning("tool execution error: %s | detail=%s", message, detail)
    raise ToolError(message)


def _suggest(query: str, candidates: list[str], *, n: int = 3) -> list[str]:
    """Return up to ``n`` candidates closest to ``query`` (ARCH-003).

    Turns an empty/not-found result into an actionable heuristic ("did you
    mean …") instead of a dead end. Matching is case-insensitive and also
    catches substring/prefix overlaps that ``difflib`` alone can miss (e.g. a
    user passing a parent topic that prefixes several real slugs).
    """
    if not query or not candidates:
        return []
    q = query.lower()
    scored = difflib.get_close_matches(q, [c.lower() for c in candidates], n=n, cutoff=0.5)
    lower_to_orig: dict[str, str] = {}
    for c in candidates:  # keep first original spelling per lowercase key
        lower_to_orig.setdefault(c.lower(), c)
    out = [lower_to_orig[s] for s in scored if s in lower_to_orig]
    # Add substring matches not already covered (stable order, capped at n).
    for c in candidates:
        if len(out) >= n:
            break
        if q in c.lower() and c not in out:
            out.append(c)
    return out[:n]


def _fail_not_found(label: str, query: str, candidates: list[str], hint: str) -> NoReturn:
    """Raise a not-found ToolError enriched with fuzzy suggestions (ARCH-003).

    Keeps the OBS-001 contract (not-found is an execution error → isError:true)
    but, instead of a bare "not found", appends "Did you mean …" when close
    matches exist, so the model can self-correct without a blind retry.
    """
    suggestions = _suggest(query, candidates)
    msg = f"{label} '{query}' not found."
    if suggestions:
        msg += " Did you mean: " + ", ".join(suggestions) + "?"
    msg += f" {hint}"
    _fail(msg)


def _ensure_ok(r: httpx.Response, *, context: str) -> None:
    """Raise a safe ToolError if an upstream response is not a 2xx success."""
    if r.is_success:
        return
    _fail(
        f"BAG IDD API returned error {r.status_code} while {context}. "
        "Verify your parameters with bag_health_mcp__get_series_details or retry later.",
        detail=r.text[:500],
    )


# ---------------------------------------------------------------------------
# HTTP client accessor
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield an httpx client for a tool call (connection pooling, SDK-001).

    Under the server :func:`lifespan` this yields the process-wide pooled client
    and does **not** close it on exit — its lifetime is owned by the lifespan, so
    connections are reused across calls. With no lifespan active (a unit test
    calling a tool directly) it falls back to a per-call client that is created
    and closed here, matching the pre-pooling behaviour. Call sites keep using
    ``async with _client() as c:`` unchanged.
    """
    if _shared_client is not None:
        yield _shared_client
    else:
        async with _new_client() as client:
            yield client


async def _get(
    client: httpx.AsyncClient, url: str, *, context: str, allow_404: bool = False
) -> httpx.Response:
    """GET ``url``, converting transport/HTTP failures into safe ToolErrors.

    When ``allow_404`` is set, a 404 response is returned to the caller so it can
    render a domain-specific not-found message; every other non-2xx status and
    any transport error raises via :func:`_fail`.
    """
    try:
        r = await client.get(url)
    except EgressNotAllowed as exc:
        _fail(f"Request blocked: {exc}.")
    except httpx.HTTPError as exc:
        _fail(
            f"Could not reach the BAG IDD API while {context}. "
            "The upstream service may be temporarily unavailable; retry later.",
            detail=repr(exc),
        )
    if allow_404 and r.status_code == 404:
        return r
    _ensure_ok(r, context=context)
    return r


# --- Retry policy (ARCH-014) -------------------------------------------------
# Three questions: *what* is retried, *how fast*, and *how long*. The first is
# settled in `_get_with_retry` (4xx except 429 fails fast); these settle the
# other two.

# Exponential-backoff base (seconds); overridden to 0 in tests so retry paths
# run instantly. Attempt N waits RETRY_BACKOFF_BASE * 2**(N-1) before jitter —
# 2s, 4s, 8s. (The exponent used to be N, which made the real ladder 4/8/16s
# while this comment said 2/4/8. The comment was right about the intent.)
RETRY_BACKOFF_BASE = 2.0
RETRY_ATTEMPTS = 4  # 1 initial + 3 retries

# Ceiling on the WHOLE call — every attempt and every wait together. An attempt
# count is not a bound: four attempts against an upstream that takes the full
# TIMEOUT (30s) to give up is two minutes inside one tool call, and
# RETRY_ATTEMPTS never says so. The anchor is measured: the Python MCP SDK
# ships MCP_DEFAULT_TIMEOUT = 30.0, so 25s leaves headroom for framing and
# parsing. Past the caller's timeout nobody is listening — the work continues,
# the load lands on the source, and the result goes nowhere.
RETRY_TOTAL_BUDGET = 25.0

# Ceiling for a single wait. Bounds the exponential ladder, and bounds a
# `Retry-After` the source is entitled to send but we are not obliged to sit
# through.
RETRY_MAX_DELAY = 20.0

# Jitter spread. Without it every client that hit the same outage retries in
# lockstep, and the load returns as a wave exactly when the source recovers —
# the retry storm extends the outage it was meant to bridge.
RETRY_JITTER_SPREAD = 0.5  # exponential delays land in [0.5x, 1.5x]

# Applied on top of a `Retry-After`, deliberately one-sided: the source told us
# when to come back, so later is polite and earlier ignores the value read.
RETRY_AFTER_JITTER = 0.25  # lands in [1.0x, 1.25x]

# Statuses that carry a meaningful `Retry-After` (RFC 9110 section 10.2.3). A
# 429 or 503 is the source answering the very question the curve is guessing
# at; reading the header elsewhere means honouring a number never about waiting.
RETRY_AFTER_STATUSES = frozenset({429, 503})

# Indirection so tests can zero the wait without patching `asyncio.sleep`
# itself. A `monkeypatch.setattr(server.asyncio, "sleep", ...)` looks local and
# is not — `server.asyncio` *is* the stdlib module, so it would disable sleeping
# for the whole process, including foreign tests that use it to yield to the
# event loop and would then measure nothing while staying green.
_sleep = asyncio.sleep


def _parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Seconds to wait per the response's ``Retry-After``, or ``None``.

    RFC 9110 section 10.2.3 allows two forms — delta-seconds (``120``) and an
    HTTP-date. Both appear in the wild, so both are read. Anything unparseable
    yields ``None`` and the caller falls back to its own curve: a malformed
    header must not become a crash on the error path, which is the one path
    already going badly.
    """
    if resp is None or resp.status_code not in RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("retry-after") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:  # RFC 9110 dates are GMT; a naive one means UTC
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())  # past date -> now


def _retry_delay(attempt: int, resp: httpx.Response | None) -> float:
    """Seconds to wait before ``attempt`` (1-based for the first retry).

    The cap wraps the jitter and not the other way round. ``min(cap, base) *
    jitter`` and ``min(cap, base * jitter)`` both contain a cap and a jitter;
    only the second is bounded — a value capped at 20s and then multiplied by
    up to 1.5 lands at 30s, and the constant would claim a ceiling it does not
    hold. That ordering shipped in six portfolio servers.
    """
    hinted = _parse_retry_after(resp)
    if hinted is not None:
        return min(hinted * (1.0 + random.random() * RETRY_AFTER_JITTER), RETRY_MAX_DELAY)
    return min(
        RETRY_BACKOFF_BASE
        * 2 ** (attempt - 1)
        * (1.0 - RETRY_JITTER_SPREAD + random.random() * 2 * RETRY_JITTER_SPREAD),
        RETRY_MAX_DELAY,
    )


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    context: str,
    allow_404: bool = False,
) -> httpx.Response:
    """GET with exponential backoff for transient failures (resilience default).

    Retries up to :data:`RETRY_ATTEMPTS` times on network errors and 5xx/429
    responses. Each wait is jittered (2s/4s/8s into [0.5x, 1.5x]) and capped at
    :data:`RETRY_MAX_DELAY`; a ``Retry-After`` on a 429 or 503 beats our curve.
    A 4xx other than 429 is not retried — it will not fix itself.

    The whole call is bounded by :data:`RETRY_TOTAL_BUDGET` seconds of wall
    clock, enforced with ``asyncio.timeout``. The httpx ``TIMEOUT`` is *not* a
    budget: it bounds each operation and its read timeout restarts with every
    chunk, so a slowly trickling response outlives any ceiling without a single
    read expiring.

    On ``allow_404`` a 404 is returned to the caller (for domain not-found
    messages). After the final attempt a safe ToolError is raised; raw upstream
    detail is logged server-side only (OBS-002).

    Used by the multi-source indicator tools, whose upstreams (Obsan dynamic JSON,
    the Versorgungsatlas static store) can return transient 5xx under load — the
    skill's non-negotiable retry default.
    """
    last_detail: str | None = None
    last_response: httpx.Response | None = None
    deadline = time.monotonic() + RETRY_TOTAL_BUDGET
    for attempt in range(RETRY_ATTEMPTS):
        if attempt > 0:
            delay = _retry_delay(attempt, last_response)
            # A wait that outlasts the budget is a wait for nobody: the caller
            # has given up by the time it ends. Stop instead of sleeping.
            if delay >= deadline - time.monotonic():
                break
            await _sleep(delay)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # `asyncio.timeout` is the wall-clock deadline the budget promises;
            # the httpx TIMEOUT stays alongside it as the per-operation bound.
            async with asyncio.timeout(remaining):
                r = await client.get(url)
        except EgressNotAllowed as exc:
            _fail(f"Request blocked: {exc}.")
        except TimeoutError as exc:  # the budget is gone, not just this try
            last_detail = repr(exc)
            logger.warning("fetch budget spent (%s) attempt %d", context, attempt)
            break
        except httpx.HTTPError as exc:
            last_detail = repr(exc)
            last_response = None
            logger.warning("transient fetch error (%s) attempt %d: %r", context, attempt, exc)
            continue
        if allow_404 and r.status_code == 404:
            return r
        if r.is_success:
            return r
        # Non-2xx: retry only transient classes (5xx, 429).
        if r.status_code >= 500 or r.status_code == 429:
            last_detail = r.text[:500]
            last_response = r  # carries a Retry-After the source may have sent
            logger.warning(
                "transient upstream %s while %s (attempt %d)",
                r.status_code,
                context,
                attempt,
            )
            continue
        # Permanent client error — do not retry.
        _ensure_ok(r, context=context)
    _fail(
        f"Upstream source unreachable while {context} after {RETRY_ATTEMPTS} attempts. "
        "The service may be temporarily unavailable; retry later.",
        detail=last_detail,
    )


async def _post(client: httpx.AsyncClient, url: str, *, json: Any, context: str) -> httpx.Response:
    """POST ``json`` to ``url``, converting transport errors into safe ToolErrors.

    The response is returned without status validation so callers can branch on
    specific codes; transport failures (DNS, connect, timeout) raise.
    """
    try:
        return await client.post(url, json=json)
    except EgressNotAllowed as exc:
        _fail(f"Request blocked: {exc}.")
    except httpx.HTTPError as exc:
        _fail(
            f"Could not reach the BAG IDD API while {context}. "
            "The upstream service may be temporarily unavailable; retry later.",
            detail=repr(exc),
        )


def _fmt_isoweek(x: int) -> str:
    """Convert IDD isoweek int (e.g. 202413) → '2024-W13'."""
    s = str(x)
    if len(s) == 6:
        return f"{s[:4]}-W{s[4:]}"
    return str(x)


def _fmt_year(x: int) -> str:
    return str(x)


# ---------------------------------------------------------------------------
# Input/output models (SEC-018 / SDK-002 / CH-004)
# ---------------------------------------------------------------------------
#
# Defined in _models.py; re-exported here so existing imports
# (from bag_health_mcp.server import DiseaseDataInput, ...) keep working.
from bag_health_mcp._models import (  # noqa: E402,F401
    AGGREGATE_STATISTICS_NOTICE,
    DATA_ATTRIBUTION,
    DATA_LICENSE,
    INDICATOR_LICENSE,
    OBSAN_ATTRIBUTION,
    SUCHTSCHWEIZ_ATTRIBUTION,
    VERSORGUNGSATLAS_ATTRIBUTION,
    CantonCode,
    CantonDiseaseData,
    CantonDiseaseStatus,
    CantonSeries,
    CantonSituationOutput,
    DataSetsInput,
    DataVersionInput,
    DataVersionOutput,
    DiseaseDataInput,
    DiseaseDataOutput,
    DiseaseDataPoint,
    DiseaseDataSummary,
    DownloadExportOutput,
    ExportDownloadInput,
    ExportFilesInput,
    GetIndicatorSeriesInput,
    HealthSource,
    IndicatorSearchOutput,
    IndicatorSeriesOutput,
    IndicatorSeriesPoint,
    IndicatorSummary,
    Language,
    ListDiseasesInput,
    ListDiseasesOutput,
    ListExportFilesOutput,
    ListSeriesOutput,
    Provenance,
    SearchHealthIndicatorsInput,
    SeriesDetailsInput,
    SeriesDetailsOutput,
)

# ---------------------------------------------------------------------------
# HTTP auth + CORS (SEC-009 / SDK-004)
# ---------------------------------------------------------------------------


class _BearerAuthMiddleware:
    """ASGI middleware enforcing a shared-secret bearer token (SEC-009).

    Requests must carry ``Authorization: Bearer <token>``; otherwise 401. The
    health/liveness path is exempt so probes work without the secret. Comparison
    is constant-time. Only installed when a token is configured.
    """

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self._token = token

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        provided = headers.get(b"authorization", b"").decode()
        import hmac

        expected = f"Bearer {self._token}"
        if not hmac.compare_digest(provided, expected):
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"text/plain"), (b"www-authenticate", b"Bearer")],
                }
            )
            await send({"type": "http.response.body", "body": b"unauthorized"})
            return
        await self.app(scope, receive, send)


def build_transport_security(settings: Settings) -> Any:
    """Host/Origin allow-list for the HTTP transport (SEC-005).

    The inbound counterpart to the outbound DNS pinning in ``_new_client``:
    that one decides where this server may *talk to*, this one under which name
    it may be *addressed*. A DNS-rebinding attack turns a browser on the
    operator's network into a client, so a bearer token does not cover it — the
    attacking page carries a valid one by construction.

    Three cases, in the order they are decided:

    - ``MCP_ALLOWED_HOSTS`` set — that list, port-exact, plus loopback so
      container health checks keep working.
    - local bind, no list — loopback only. This is what the SDK auto-enables
      for a loopback ``host``; making it explicit means the same protection no
      longer depends on the SDK's inference from the bind address.
    - non-local bind, no list — ``None``, i.e. the check stays off, and
      ``main()`` says so in its warning. That is the documented gateway-fronted
      deployment (SEC-016), where the gateway terminates and validates Host.

    The last case is deliberately not "guess a list": on ``0.0.0.0`` the
    reachable name is unknowable here, and a guessed allow-list rejects the
    very deployment it is meant to protect — HTTP 421 on every request.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    port = settings.port
    loopback = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    configured = settings.allowed_host_list
    if configured:
        hosts = set(configured) | loopback
    elif settings.is_local_bind:
        hosts = loopback | {f"{settings.host}:{port}"}
    else:
        return None

    # Configured CORS origins must pass the transport check too, otherwise the
    # server rejects precisely the browser clients CORS was opened for. A
    # wildcard is not expressible here — origins are compared literally.
    origins = {o for o in settings.cors_origin_list if o != "*"}
    origins |= {f"http://{h}" for h in hosts}
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(origins),
    )


# Die Header, nach denen Spec 2026-07-28 eine Streamable-HTTP-Anfrage routet —
# in der Schreibweise des SDK (`mcp.shared.inbound`). Ein Browser darf einen
# nicht safelisteten Header gar nicht erst senden, wenn der Server ihn nicht in
# `Access-Control-Allow-Headers` nennt: ohne sie stirbt jede Cross-Origin-
# Anfrage am Preflight, vor dem ersten MCP-Byte. stdio- und Python-Clients
# kennen keinen Preflight und merken davon nichts — deshalb fiel es nicht auf.
#
# `Mcp-Param-*` fehlt bewusst: CORS kennt keinen Praefix-Wildcard, und kein
# Tool-Schema dieses Servers traegt eine `x-mcp-header`-Annotation.
CORS_ROUTING_HEADERS = ["Mcp-Method", "Mcp-Name", "Mcp-Protocol-Version"]


def build_http_app(settings: Settings) -> Any:
    """Build the Streamable-HTTP ASGI app with optional auth + CORS.

    - Bearer-token auth is applied when ``settings.auth_token`` is set (SEC-009).
    - CORS is applied when ``settings.cors_origins`` is non-empty, exposing the
      ``Mcp-Session-Id`` header browser clients need for stateful sessions
      (SDK-004). Origins are an explicit allow-list — never a wildcard.

    ``host`` is handed to the SDK rather than left at its default because the
    SDK derives its DNS-rebinding protection from it; leaving it out would mean
    a loopback allow-list on a ``0.0.0.0`` bind, and HTTP 421 for every real
    request. The allow-list itself is passed explicitly (SEC-005) rather than
    inferred — see :func:`build_transport_security`.
    """
    app = mcp.streamable_http_app(
        host=settings.host,
        transport_security=build_transport_security(settings),
    )
    if settings.auth_token:
        app = _BearerAuthMiddleware(app, settings.auth_token)
        logger.info("HTTP bearer-token authentication enabled")
    origins = settings.cors_origin_list
    if origins:
        from starlette.middleware.cors import CORSMiddleware

        app = CORSMiddleware(
            app,
            allow_origins=origins,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "Mcp-Session-Id",
                "Authorization",
                "Content-Type",
                *CORS_ROUTING_HEADERS,
            ],
            expose_headers=["Mcp-Session-Id"],
        )
        logger.info("CORS enabled for origins: %s", ", ".join(origins))
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Console-script / module entry point.

    Runtime configuration is read into a :class:`Settings` object from ``MCP_*``
    environment variables (ARCH-004), keeping the server logic transport- and
    source-agnostic. Transport is selected by ``MCP_TRANSPORT`` (``http`` or
    ``stdio``) when set — the recommended way for container/cloud deployments —
    otherwise by the ``--http`` CLI flag; the default is stdio. For HTTP, host
    and port come from ``MCP_HOST`` / ``MCP_PORT`` (``--port`` overrides). The
    host defaults to ``127.0.0.1`` so a local HTTP server is not exposed to the
    network; container deployments opt into all-interface binding explicitly by
    setting ``MCP_HOST=0.0.0.0`` (see Dockerfile).
    """
    settings = Settings()
    _configure_logging(settings.log_level)
    _configure_tracing()  # no-op unless telemetry installed + OTEL endpoint set
    if settings.wants_http(http_flag="--http" in sys.argv):
        # --port is a CLI-only override (not an env var) for local convenience.
        if "--port" in sys.argv:
            settings.port = int(sys.argv[sys.argv.index("--port") + 1])
        if not settings.is_local_bind and not settings.allowed_host_list:
            # NeighborJack awareness (SEC-016): binding beyond localhost exposes
            # the server on the network; that should only happen in an isolated,
            # gateway-fronted deployment. Without MCP_ALLOWED_HOSTS the Host
            # check is off as well (SEC-005), so the gateway is the only thing
            # validating Host — say that rather than let it be inferred.
            logger.warning(
                "binding HTTP server to non-localhost host %s with no "
                "MCP_ALLOWED_HOSTS — Host/Origin validation is left to the "
                "gateway in front of it; set MCP_ALLOWED_HOSTS to the names "
                "this server is reachable under to enforce it here too",
                settings.host,
                extra={"bind_host": settings.host},
            )
        elif not settings.is_local_bind:
            logger.info(
                "binding HTTP server to non-localhost host %s with a Host allow-list of %s",
                settings.host,
                ", ".join(settings.allowed_host_list),
                extra={"bind_host": settings.host},
            )
        if settings.auth_token or settings.cors_origin_list:
            # Serve the auth/CORS-wrapped ASGI app ourselves (SEC-009/SDK-004).
            import uvicorn

            uvicorn.run(
                build_http_app(settings),
                host=settings.host,
                port=settings.port,
                log_config=None,  # keep our JSON logging on stderr (OBS-004)
            )
        else:
            # No auth/CORS configured: let the SDK run the server. Since mcp
            # 2.x the bind address is a run() kwarg — MCPServer.settings no
            # longer carries host/port, so passing them here is the only way
            # to bind anywhere other than the SDK default of 127.0.0.1:8000.
            # transport_security travels the same way; run() forwards it to the
            # same app builder, so both HTTP paths get the identical allow-list
            # rather than only the auth/CORS one.
            mcp.run(
                transport="streamable-http",
                host=settings.host,
                port=settings.port,
                transport_security=build_transport_security(settings),
            )
    else:
        mcp.run()


# ---------------------------------------------------------------------------
# Tool / resource / prompt registration (ARCH-011)
# ---------------------------------------------------------------------------
#
# The tools, resources and prompts live in _tools.py (split out for size). This
# import — placed at the end, after mcp and all the helpers above are defined —
# registers them on ``mcp`` and is required for the import-time side effect. The
# tool functions are re-exported so existing imports
# (from bag_health_mcp.server import bag_get_disease_data, ...) keep working.
from bag_health_mcp import _tools  # noqa: E402

READ_ONLY = _tools.READ_ONLY
bag_list_diseases = _tools.bag_list_diseases
bag_list_series = _tools.bag_list_series
bag_get_series_details = _tools.bag_get_series_details
bag_get_disease_data = _tools.bag_get_disease_data
bag_list_export_files = _tools.bag_list_export_files
bag_download_export = _tools.bag_download_export
bag_get_data_version = _tools.bag_get_data_version
bag_get_canton_situation = _tools.bag_get_canton_situation

# Multi-source health-indicator tools (Obsan / Versorgungsatlas / Sucht Schweiz).
# Imported after _tools so all shared helpers exist; registers 2 more tools.
from bag_health_mcp import _health_indicators  # noqa: E402

bag_search_health_indicators = _health_indicators.bag_search_health_indicators
bag_get_indicator_series = _health_indicators.bag_get_indicator_series


if __name__ == "__main__":
    main()
