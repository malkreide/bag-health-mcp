"""
bag-health-mcp — Swiss Federal Office of Public Health (BAG)
Infectious Disease Surveillance MCP Server

Data source: IDD API (api.idd.bag.admin.ch)
No authentication required. All data is public.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import socket
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal, NoReturn
from urllib.parse import urlsplit

import httpcore
import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDD_BASE = "https://api.idd.bag.admin.ch"
TIMEOUT = 30.0
USER_AGENT = "bag-health-mcp/0.1.0 (https://github.com/malkreide/bag-health-mcp)"

# Code-layer egress allow-list (SEC-021): the only host this server may ever
# talk to is the BAG IDD API, derived from IDD_BASE so there is a single source
# of truth. Enforced on every outbound request — including redirect hops — by
# the egress guard below, and only over HTTPS (SEC-004 scheme enforcement).
ALLOWED_HOSTS = frozenset({urlsplit(IDD_BASE).hostname or ""})
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

    _RESERVED = frozenset(
        logging.makeLogRecord({}).__dict__.keys()
    ) | {"message", "asctime", "taskName"}

    def format(self, record: logging.LogRecord) -> str:
        severity, severity_code = _RFC5424_SEVERITY.get(
            record.levelno, ("info", 6)
        )
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
    "AG","AI","AR","BE","BL","BS","FR","GE","GL","GR",
    "JU","LU","NE","NW","OW","SG","SH","SO","SZ","TG",
    "TI","UR","VD","VS","ZG","ZH","FL","all",
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
# to categorise bag_list_diseases output and to serve the bag://disease-categories
# reference resource, so the two never drift (single source of truth).
DISEASE_CATEGORIES: dict[str, set[str]] = {
    "respiratory": {
        "acute_respiratory_infection", "influenza", "influenza-like_illness",
        "respiratory_pathogens", "covid19",
    },
    "enteric": {
        "campylobacteriosis", "salmonellosis", "ehec", "listeriosis",
        "hepatitis_a", "hepatitis_e", "shigellosis", "cholera",
        "typhoidParatyphoidFever", "trichinellosis", "botulism", "qFever",
    },
    "sti_and_bloodborne": {
        "hiv", "aids", "syphilis", "gonorrhea", "chlamydiosis",
        "hepatitis_b", "hepatitis_c",
    },
    "vaccine_preventable": {
        "measles", "rubella", "pertussis", "diphtheria", "tetanus",
        "haemophilusInfluenzae", "ipd", "meningo", "herpesZoster",
        "postZosterNeuralgia",
    },
    "vector_borne": {
        "lyme_borreliosis", "tick-borne_encephalitis", "dengueFever",
        "malaria", "westnileFever", "chikungunya", "zika", "yellowFever",
        "hanta", "tularemia",
    },
}

# ---------------------------------------------------------------------------
# HTTP client lifespan (SDK-001)
# ---------------------------------------------------------------------------
#
# A single pooled httpx.AsyncClient is opened for the server's whole lifetime
# and shared across every tool, instead of opening a new client (new TCP/TLS
# connection) per call. Its lifetime is owned by the FastMCP lifespan below;
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
            "this server may only reach the BAG IDD API"
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
            logger.warning(
                "blocked egress: host %s resolved to disallowed IP %s", host, ip
            )
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
                logger.warning(
                    "blocked egress: host %s resolved to disallowed IP %s", host, ip
                )
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
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
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
# FastMCP setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="bag-health-mcp",
    instructions=(
        "Access Swiss Federal Office of Public Health (BAG) infectious disease "
        "surveillance data via the IDD API. Covers 51 pathogens including "
        "influenza, COVID-19, measles, tuberculosis, wastewater surveillance, "
        "and more. Data is updated weekly every Wednesday. "
        "Use bag_list_diseases first to discover available topics, then "
        "bag_get_series_details to understand available filters, then "
        "bag_get_disease_data to retrieve time-series values."
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


def _ensure_ok(r: httpx.Response, *, context: str) -> None:
    """Raise a safe ToolError if an upstream response is not a 2xx success."""
    if r.is_success:
        return
    _fail(
        f"BAG IDD API returned error {r.status_code} while {context}. "
        "Verify your parameters with bag_get_series_details or retry later.",
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


async def _post(
    client: httpx.AsyncClient, url: str, *, json: Any, context: str
) -> httpx.Response:
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
# Input models
# ---------------------------------------------------------------------------

Language = Literal["de", "fr", "it", "en"]
CantonCode = Literal[
    "AG","AI","AR","BE","BL","BS","FR","GE","GL","GR",
    "JU","LU","NE","NW","OW","SG","SH","SO","SZ","TG",
    "TI","UR","VD","VS","ZG","ZH","FL","all",
]


class _StrictInput(BaseModel):
    """Base for every tool input (SEC-018).

    ``strict=True`` disables silent type coercion (a string is not accepted where
    an int is declared, etc.) and ``extra='forbid'`` rejects unexpected fields.
    Both propagate into the JSON inputSchema advertised to clients, so invalid
    arguments are refused at the protocol boundary before any tool body runs.
    Free-form string fields that flow into upstream URL paths additionally carry
    length and pattern constraints below.
    """

    model_config = ConfigDict(strict=True, extra="forbid")


# Slugs (topic, export file) and series ids only ever contain these characters in
# the real IDD API; constraining them caps unbounded user input before it reaches
# a URL path (SEC-018). Series ids are 'topic/chapter/aggregation/temporality'.
_SLUG_PATTERN = r"^[A-Za-z0-9_-]+$"
_SERIES_ID_PATTERN = r"^[A-Za-z0-9_/-]+$"
_AGE_GROUP_PATTERN = r"^[0-9 +-]+$"


class ListDiseasesInput(_StrictInput):
    pass


class DataSetsInput(_StrictInput):
    topic: str = Field(
        min_length=1,
        max_length=64,
        pattern=_SLUG_PATTERN,
        description=(
            "Disease topic slug, e.g. 'influenza', 'covid19', 'measles'. "
            "Use bag_list_diseases to get valid values."
        ),
    )


class SeriesDetailsInput(_StrictInput):
    series_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SERIES_ID_PATTERN,
        description=(
            "Full series identifier in format 'topic/chapter/aggregation/temporality', "
            "e.g. 'influenza/cases/incValue/iso_week'. "
            "Use bag_list_series to discover available series for a topic."
        ),
    )


class DiseaseDataInput(_StrictInput):
    series_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SERIES_ID_PATTERN,
        description=(
            "Full series identifier, e.g. 'influenza/cases/incValue/iso_week'. "
            "Use bag_get_series_details to check available filters."
        ),
    )
    canton: CantonCode = Field(
        default="all",
        description="Canton abbreviation or 'all' for Switzerland-wide data.",
    )
    sex: Literal["male", "female", "all"] = Field(
        default="all",
        description="Sex filter. Use 'all' for aggregated data.",
    )
    age_group: str | None = Field(
        default=None,
        max_length=32,
        pattern=_AGE_GROUP_PATTERN,
        description=(
            "Age group filter if the series supports it, "
            "e.g. '0 - 4', '5 - 14', '15 - 29', '30 - 64', '65+'. "
            "Leave None for aggregated data."
        ),
    )
    limit_weeks: int = Field(
        default=104,
        ge=1,
        le=600,
        description="Maximum number of data points to return (default 104 = ~2 years).",
    )


class ExportFilesInput(_StrictInput):
    version: Literal["latest", "archived"] = Field(
        default="latest",
        description="'latest' for current data, 'archived' for historical snapshots.",
    )


class ExportDownloadInput(_StrictInput):
    file: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SLUG_PATTERN,
        description=(
            "File name from bag_list_export_files, e.g. 'INFLUENZA_oblig', "
            "'COVID19_wastewater_sequencing'."
        ),
    )
    format: Literal["csv", "json"] = Field(
        default="csv",
        description="Export format.",
    )


class DataVersionInput(_StrictInput):
    pass


# ---------------------------------------------------------------------------
# Output models (SDK-002)
# ---------------------------------------------------------------------------
#
# Tools return typed Pydantic models rather than bare dict[str, Any], so FastMCP
# advertises a precise outputSchema in tools/list and emits structuredContent.
# Every output carries a shared Provenance block (consistent envelope) naming the
# data source and licence attribution; the loose source/source_date/version
# fields the dicts used are folded into it.

DATA_ATTRIBUTION = (
    "Federal Office of Public Health FOPH — Infectious Disease Dashboard (IDD); "
    "open data via opendata.swiss"
)
# BAG IDD is published on opendata.swiss as federal Open Government Data under
# "free use — source attribution required" terms (the Swiss OGD equivalent of
# CC BY): reuse is permitted provided the source is cited (CH-004).
DATA_LICENSE = (
    "opendata.swiss Open Government Data — free use, source attribution "
    "required (Swiss OGD terms, CC BY-equivalent). Cite: "
    "Federal Office of Public Health FOPH, Infectious Disease Dashboard (IDD)."
)


class Provenance(BaseModel):
    """Where a result came from, attached to every tool output (SDK-002/CH-004).

    Carries the upstream source/date/version plus a controlled licence and
    attribution string so every response states how the data may be reused.
    """

    source: str | None = None
    source_date: str | None = None
    data_version: str | None = None
    attribution: str = DATA_ATTRIBUTION
    license: str = DATA_LICENSE


class ListDiseasesOutput(BaseModel):
    total_topics: int
    categories: dict[str, list[str]]
    usage: str
    provenance: Provenance = Field(default_factory=Provenance)


class ListSeriesOutput(BaseModel):
    topic: str
    total_series: int
    chapters: dict[str, list[str]]
    series_ids: list[str]
    usage: str
    provenance: Provenance = Field(default_factory=Provenance)


class SeriesDetailsOutput(BaseModel):
    series_id: str
    available_filters: dict[str, list[str]]
    cantons: list[str]
    age_groups: list[str]
    sex_options: list[str]
    note: str
    provenance: Provenance = Field(default_factory=Provenance)


class DiseaseDataPoint(BaseModel):
    period: str
    value: float | None = None
    trend: str | None = None
    data_complete: str | None = None


class CantonSeries(BaseModel):
    canton: str
    data_points: int
    series: list[DiseaseDataPoint]


class DiseaseDataSummary(BaseModel):
    canton: str | None = None
    latest_period: str | None = None
    latest_value: float | None = None
    trend: str | None = None
    data_points_returned: int | None = None


class DiseaseDataOutput(BaseModel):
    series_id: str
    topic: str
    aggregation: str
    temporality: str
    filters_applied: dict[str, str]
    summary: DiseaseDataSummary
    # Canton-grouped responses yield CantonSeries; flat responses yield bare
    # DiseaseDataPoints — the union preserves both existing shapes.
    results: list[CantonSeries | DiseaseDataPoint]
    interpretation: str
    provenance: Provenance = Field(default_factory=Provenance)


class ListExportFilesOutput(BaseModel):
    version: str
    total_files: int
    files: list[str]
    usage: str
    provenance: Provenance = Field(default_factory=Provenance)


class DownloadExportOutput(BaseModel):
    file: str
    format: str
    size_bytes: int
    rows: int | None
    preview: str
    note: str
    provenance: Provenance = Field(default_factory=Provenance)


class DataVersionOutput(BaseModel):
    version: str
    date: str
    note: str
    provenance: Provenance = Field(default_factory=Provenance)


class CantonDiseaseStatus(BaseModel):
    """A school-relevant series that could not be resolved for this canton."""

    status: str
    source_date: str | None = None


class CantonDiseaseData(BaseModel):
    """A school-relevant series with current data for this canton."""

    latest_period: str | None = None
    latest_value: float | None = None
    unit: str | None = None
    trend: str | None = None
    change_vs_prev_period_pct: float | None = None
    source_date: str | None = None
    series: list[DiseaseDataPoint] = Field(default_factory=list)


class CantonSituationOutput(BaseModel):
    canton: str
    diseases: dict[str, CantonDiseaseStatus | CantonDiseaseData]
    note: str
    school_relevance: str
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

# Every tool only reads from the public BAG IDD API: no mutations (read-only),
# safe to repeat (idempotent), and reaches an external system (open world).
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


@mcp.tool(annotations=READ_ONLY, description=(
    "List all 51 disease topics available in the BAG Infectious Disease Dashboard (IDD). "
    "Returns the topic slug needed for other tools, grouped by category "
    "(respiratory, enteric, STI, vector-borne, wastewater). "
    "Start here to discover what data is available."
))
@_traced
async def bag_list_diseases(params: ListDiseasesInput) -> ListDiseasesOutput:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/sets", context="listing disease topics")
        all_sets: list[str] = r.json()

    topics: set[str] = {s.split("/")[0] for s in all_sets}

    # Categorise for readability against the shared taxonomy. Wastewater is
    # matched by substring; whatever is left over lands in 'other'.
    categories: dict[str, list[str]] = {}
    classified: set[str] = set()
    for name, members in DISEASE_CATEGORIES.items():
        present = {t for t in topics if t in members}
        categories[name] = sorted(present)
        classified |= present
    wastewater = {t for t in topics if "wastewater" in t}
    categories["wastewater_surveillance"] = sorted(wastewater)
    classified |= wastewater
    categories["other"] = sorted(topics - classified)

    return ListDiseasesOutput(
        total_topics=len(topics),
        categories=categories,
        usage=(
            "Use a topic slug with bag_list_series(topic=...) "
            "to see available data series."
        ),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "List all available data series for a specific disease topic. "
    "Each series is identified by 'topic/chapter/aggregation/temporality'. "
    "Returns series IDs to use with bag_get_series_details and bag_get_disease_data."
))
@_traced
async def bag_list_series(params: DataSetsInput) -> ListSeriesOutput:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/sets", context="listing data series")
        all_sets: list[str] = r.json()

    topic_sets = [s for s in all_sets if s.startswith(f"{params.topic}/")]
    if not topic_sets:
        _fail(
            f"Topic '{params.topic}' not found. "
            "Use bag_list_diseases to see valid topic slugs."
        )

    # Parse structure
    chapters: dict[str, list[str]] = {}
    for s in topic_sets:
        parts = s.split("/")
        if len(parts) == 4:
            chapter = parts[1]
            agg_temp = f"{parts[2]}/{parts[3]}"
            chapters.setdefault(chapter, []).append(agg_temp)

    return ListSeriesOutput(
        topic=params.topic,
        total_series=len(topic_sets),
        chapters={ch: sorted(series) for ch, series in sorted(chapters.items())},
        series_ids=sorted(topic_sets),
        usage=(
            "Use a series_id with bag_get_series_details to see available "
            "filter values (canton, age_group, sex, type), then "
            "bag_get_disease_data to fetch the time series."
        ),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "Get metadata and available filter values for a specific data series. "
    "Shows which canton, age group, sex, and other dimensions are available. "
    "Always call this before bag_get_disease_data to know valid filter options."
))
@_traced
async def bag_get_series_details(params: SeriesDetailsInput) -> SeriesDetailsOutput:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        _fail(
            "series_id must be in format 'topic/chapter/aggregation/temporality', "
            "e.g. 'influenza/cases/incValue/iso_week'."
        )
    topic, chapter, aggregation, temporality = parts

    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details",
            context=f"fetching details for '{params.series_id}'",
            allow_404=True,
        )
        if r.status_code == 404:
            _fail(
                f"Series '{params.series_id}' not found. "
                "Use bag_list_series(topic=...) to discover valid series."
            )
        data = r.json()

    props = data.get("properties", {})
    # Summarise
    filters: dict[str, list[str]] = {}
    for key, val in props.items():
        if isinstance(val, dict):
            filters[key] = val.get("possibleValues", [])

    return SeriesDetailsOutput(
        series_id=params.series_id,
        available_filters=filters,
        cantons=filters.get("canton", []),
        age_groups=(
            filters.get("agegroup_ili_ari")
            or filters.get("agegroup_oblig")
            or filters.get("agegroup")
            or []
        ),
        sex_options=filters.get("sex", []),
        note=(
            "Use these filter values in bag_get_disease_data. "
            "Use 'all' for any aggregated dimension."
        ),
        provenance=Provenance(
            source=data.get("source"),
            source_date=data.get("sourceDate"),
            data_version=data.get("version"),
        ),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "Fetch time-series surveillance data for a disease from the BAG IDD. "
    "Returns weekly or yearly case counts, incidence rates, or other metrics. "
    "Data updated every Wednesday. "
    "Example: Influenza incidence per 100k population in Zurich by week."
))
@_traced
async def bag_get_disease_data(
    params: DiseaseDataInput, ctx: Context | None = None
) -> DiseaseDataOutput:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        _fail("series_id must be 'topic/chapter/aggregation/temporality'.")
    topic, chapter, aggregation, temporality = parts

    # This tool makes two round-trips (details, then data); surface progress and
    # structured logging to the client when a Context is injected (SDK-003).
    if ctx:
        await ctx.info(f"Resolving filters for '{params.series_id}'")
        await ctx.report_progress(progress=0, total=2)

    # Build filter body based on series details
    async with _client() as c:
        # Fetch details to build correct filter
        dr = await _get(
            c,
            f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details",
            context=f"fetching details for '{params.series_id}'",
            allow_404=True,
        )
        if dr.status_code == 404:
            _fail(
                f"Series not found: {params.series_id}. "
                "Use bag_list_series to find valid series_ids."
            )
        details = dr.json()

    props = details.get("properties", {})
    georegion_options = props.get("georegion", {}).get("possibleValues", [])

    # Determine georegion
    if params.canton == "all":
        if "CHFL" in georegion_options:
            georegion = "CHFL"
        elif "country" in georegion_options:
            georegion = "country"
        else:
            georegion = georegion_options[0] if georegion_options else "canton"
    else:
        georegion = "canton"

    # Build filter body
    body: dict[str, str] = {}
    if "georegion" in props:
        body["georegion"] = georegion
    if "canton" in props:
        body["canton"] = params.canton
    if "CHFL" in props and params.canton == "all":
        body["CHFL"] = "all"
        body.pop("canton", None)
    if "sex" in props:
        body["sex"] = params.sex
    if "country" in props and params.canton == "all":
        body["country"] = "CH"

    # Age group handling
    agegroup_key = None
    for key in ["agegroup_ili_ari", "agegroup_oblig", "agegroup"]:
        if key in props:
            agegroup_key = key
            break

    if agegroup_key:
        ag_options = props[agegroup_key].get("possibleValues", ["all"])
        if params.age_group and params.age_group in ag_options:
            body[agegroup_key] = params.age_group
            if "agegroup" in props and agegroup_key != "agegroup":
                body["agegroup"] = agegroup_key
        else:
            all_val = props[agegroup_key].get("allValue", "all")
            body[agegroup_key] = all_val if all_val else (ag_options[0] if ag_options else "all")
            if "agegroup" in props and agegroup_key != "agegroup":
                body["agegroup"] = agegroup_key

    # Determine groupBy param
    group_by = "canton" if params.canton == "all" else None

    # Fetch data
    if ctx:
        await ctx.info(f"Fetching time series for '{params.series_id}'")
        await ctx.report_progress(progress=1, total=2)
    async with _client() as c:
        url = f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}"
        if group_by:
            url += f"?groupBy={group_by}"
        r = await _post(c, url, json=body, context=f"fetching data for '{params.series_id}'")
        if r.status_code != 200:
            # Surface the status only — never the raw upstream response body,
            # which can leak internal details into the model context (OBS-002).
            _fail(
                f"BAG IDD API error {r.status_code} while fetching "
                f"'{params.series_id}'. Use bag_get_series_details to verify "
                "valid filter values, then retry with adjusted parameters.",
                detail=r.text[:500],
            )
        data = r.json()

    values = data.get("values", {})

    # Normalise to list of {period, value, canton?, ...}
    is_weekly = "week" in temporality or "iso_week" in temporality or "date" in temporality

    def fmt_period(x: int | str) -> str:
        if isinstance(x, int):
            return _fmt_isoweek(x) if is_weekly else _fmt_year(x)
        return str(x)

    result_series: list[CantonSeries | DiseaseDataPoint] = []

    if isinstance(values, dict):
        # grouped by canton
        for canton_key, points in values.items():
            if not isinstance(points, list):
                continue
            # Take last N points
            recent = points[-params.limit_weeks:]
            series_points = [
                DiseaseDataPoint(
                    period=fmt_period(p["x"]),
                    value=p.get("y"),
                    trend=p.get("properties", {}).get("trend"),
                    data_complete=p.get("properties", {}).get("dataComplete"),
                )
                for p in recent
                if p.get("y") is not None
            ]
            if series_points:
                result_series.append(CantonSeries(
                    canton=canton_key,
                    data_points=len(series_points),
                    series=series_points,
                ))
    elif isinstance(values, list):
        recent = values[-params.limit_weeks:]
        result_series = [
            DiseaseDataPoint(
                period=fmt_period(p["x"]),
                value=p.get("y"),
                trend=p.get("properties", {}).get("trend"),
            )
            for p in recent
            if p.get("y") is not None
        ]

    # Summary stats for canton=all case
    summary = DiseaseDataSummary()
    if params.canton == "ZH" or params.canton != "all":
        matching = next(
            (s for s in result_series
             if isinstance(s, CantonSeries) and s.canton == params.canton),
            None,
        )
        if matching and matching.series:
            last = matching.series[-1]
            summary = DiseaseDataSummary(
                canton=params.canton,
                latest_period=last.period,
                latest_value=last.value,
                trend=last.trend,
                data_points_returned=len(matching.series),
            )

    if ctx:
        await ctx.report_progress(progress=2, total=2)

    return DiseaseDataOutput(
        series_id=params.series_id,
        topic=topic,
        aggregation=aggregation,
        temporality=temporality,
        filters_applied=body,
        summary=summary,
        results=result_series,
        interpretation=(
            f"Values represent '{aggregation}' ({chapter}) for '{topic}'. "
            "Period format: YYYY-Www for weekly, YYYY for yearly. "
            "'incValue' = incidence per 100'000 population. "
            "'value' = absolute case count."
        ),
        provenance=Provenance(
            source=data.get("source"),
            source_date=data.get("sourceDate"),
            data_version=data.get("version"),
        ),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "List all available export file names from the BAG IDD. "
    "These are complete datasets (CSV/JSON) per disease, "
    "e.g. INFLUENZA_oblig, COVID19_wastewater_sequencing, MEASLES_oblig. "
    "Use with bag_download_export to get raw data files."
))
@_traced
async def bag_list_export_files(params: ExportFilesInput) -> ListExportFilesOutput:
    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/export/{params.version}/files",
            context="listing export files",
        )
        files: list[str] = r.json()

    return ListExportFilesOutput(
        version=params.version,
        total_files=len(files),
        files=sorted(files),
        usage=(
            "Use bag_download_export(file='INFLUENZA_oblig', format='csv') "
            "to download the raw dataset."
        ),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "Download a complete export dataset from the BAG IDD as CSV or JSON. "
    "Returns the raw data content for a specific disease file. "
    "Useful for bulk analysis. Files are updated weekly."
))
@_traced
async def bag_download_export(params: ExportDownloadInput) -> DownloadExportOutput:
    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/export/latest/{params.file}/{params.format}",
            context=f"downloading export '{params.file}'",
            allow_404=True,
        )
        if r.status_code == 404:
            _fail(
                f"File '{params.file}' not found. "
                "Use bag_list_export_files to see available files."
            )

    content = r.text
    lines = content.split("\n") if params.format == "csv" else []

    return DownloadExportOutput(
        file=params.file,
        format=params.format,
        size_bytes=len(content),
        rows=len(lines) - 1 if lines else None,
        preview=content[:3000],
        note=(
            "Full data returned in 'preview' (truncated at 3000 chars). "
            "For large datasets, use the IDD web interface at idd.bag.admin.ch."
        ),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "Get the current data version of the BAG IDD. "
    "Returns the date of the last data update (format YYYYMMDD). "
    "IDD is updated every Wednesday."
))
@_traced
async def bag_get_data_version(params: DataVersionInput) -> DataVersionOutput:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/version", context="fetching data version")
        data = r.json()

    version_str = data.get("name", "")
    # Parse YYYYMMDD
    if len(version_str) == 8:
        formatted = f"{version_str[:4]}-{version_str[4:6]}-{version_str[6:]}"
    else:
        formatted = version_str

    return DataVersionOutput(
        version=version_str,
        date=formatted,
        note="IDD is updated every Wednesday. Data reflects the state as of this date.",
        provenance=Provenance(source_date=formatted, data_version=version_str),
    )


@mcp.tool(annotations=READ_ONLY, description=(
    "Get a public health situation overview for a specific canton or Switzerland. "
    "Combines current incidence data for key school-relevant diseases "
    "(influenza, measles, norovirus proxy via acute_respiratory_infection) "
    "with trend information. Designed for school authorities and "
    "city administration Public Health Reporting. "
    "Anchor query: 'Was ist die aktuelle Grippesituation im Kanton Zürich?'"
))
@_traced
async def bag_get_canton_situation(
    canton: str = "ZH",
    include_wastewater: bool = False,
    ctx: Context | None = None,
) -> CantonSituationOutput:
    """
    High-level situational awareness tool combining multiple series.
    Optimised for Schulamt / Kreisschulbehörde use cases.
    """
    if canton.upper() not in [c for c in CANTONS if c != "all"]:
        _fail(
            f"Unknown canton '{canton}'. Valid cantons: "
            + ", ".join(c for c in CANTONS if c != "all")
        )

    canton_up = canton.upper()

    # Key disease series for schools
    school_relevant = {
        "influenza": "influenza/cases/incValue/iso_week",
        "influenza_like_illness": "acute_respiratory_infection/consultations/incValue/iso_week",
        "measles": "measles/cases/incValue/year",
        "pertussis": "pertussis/cases/incValue/iso_week",
        "covid19": "covid19/cases/incValue/iso_week",
    }
    if include_wastewater:
        school_relevant["wastewater_covid19"] = "wastewater_viral_load/NA/value/date"

    async def _fetch_series(
        name: str, series_id: str
    ) -> tuple[str, CantonDiseaseStatus | CantonDiseaseData]:
        # This aggregates several independent series into one overview. A failure
        # of a single series is reported inline as that series' status and never
        # fails the whole overview (which would be the wrong granularity); the
        # tool call itself still succeeds. Raw causes are logged server-side.
        parts = series_id.split("/")
        if len(parts) != 4:
            return name, CantonDiseaseStatus(status="unavailable")
        topic, chapter, aggregation, temporality = parts

        is_yearly = "year" in temporality

        try:
            async with _client() as c:
                dr = await c.get(
                    f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details"
                )
                if dr.status_code != 200:
                    return name, CantonDiseaseStatus(status="series_not_found")
                details = dr.json()

            props = details.get("properties", {})
            body: dict[str, str] = {}
            georegion_options = props.get("georegion", {}).get("possibleValues", [])

            if "georegion" in props:
                body["georegion"] = "canton" if "canton" in georegion_options else georegion_options[0]
            if "canton" in props:
                body["canton"] = canton_up
            if "sex" in props:
                body["sex"] = "all"
            if "country" in props:
                body["country"] = "CH"
            for key in ["agegroup_ili_ari", "agegroup_oblig"]:
                if key in props:
                    all_val = props[key].get("allValue", "all")
                    body[key] = all_val or "all"
                    if "agegroup" in props:
                        body["agegroup"] = key
                    break

            async with _client() as c:
                r = await c.post(
                    f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}",
                    json=body,
                )
                if r.status_code != 200:
                    return name, CantonDiseaseStatus(status="data_unavailable")
                data = r.json()

            values = data.get("values", {})
            canton_data: list[dict] = []

            if isinstance(values, dict):
                canton_data = values.get(canton_up, [])
            elif isinstance(values, list):
                canton_data = values

            if not canton_data:
                return name, CantonDiseaseStatus(
                    status="no_data", source_date=data.get("sourceDate")
                )

            recent = canton_data[-8:]  # last 8 periods
            latest = recent[-1]
            prev = recent[-2] if len(recent) >= 2 else None

            trend = latest.get("properties", {}).get("trend")
            period_fmt = (
                _fmt_isoweek(latest["x"]) if not is_yearly else _fmt_year(latest["x"])
            )

            change_pct: float | None = None
            if prev and prev.get("y") and latest.get("y") is not None:
                if prev["y"] != 0:
                    change_pct = round(((latest["y"] - prev["y"]) / prev["y"]) * 100, 1)

            return name, CantonDiseaseData(
                latest_period=period_fmt,
                latest_value=latest.get("y"),
                unit="incidence per 100'000" if "incValue" in aggregation else "absolute count",
                trend=trend,
                change_vs_prev_period_pct=change_pct,
                source_date=data.get("sourceDate"),
                series=[
                    DiseaseDataPoint(
                        period=_fmt_isoweek(p["x"]) if not is_yearly else _fmt_year(p["x"]),
                        value=p.get("y"),
                    )
                    for p in recent if p.get("y") is not None
                ],
            )
        except (EgressNotAllowed, httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            # Don't surface the raw exception to the model — log it server-side
            # and report a stable, generic per-series status (OBS-002). An egress
            # block fails this series closed; the guard already logged the target.
            logger.warning("canton_situation series '%s' failed: %r", name, exc)
            if ctx:
                # Tell the client this series degraded (no raw cause — OBS-002).
                await ctx.warning(f"Series '{name}' unavailable; continuing.")
            return name, CantonDiseaseStatus(status="unavailable")

    # Fan out over the series, reporting progress as each completes. The overview
    # makes 5+ (2 round-trips each) calls and can take a few seconds, so a
    # long-running client gets incremental progress (SDK-003).
    total = len(school_relevant)
    if ctx:
        await ctx.info(f"Building situation overview for canton {canton_up} "
                       f"({total} series)")
    tasks = [
        asyncio.ensure_future(_fetch_series(name, sid))
        for name, sid in school_relevant.items()
    ]
    diseases: dict[str, CantonDiseaseStatus | CantonDiseaseData] = {}
    done = 0
    for coro in asyncio.as_completed(tasks):
        name, value = await coro
        diseases[name] = value
        done += 1
        if ctx:
            await ctx.report_progress(progress=done, total=total)

    return CantonSituationOutput(
        canton=canton_up,
        diseases=diseases,
        note=(
            f"Situation overview for canton {canton_up}. "
            "incValue = incidence per 100'000 population. "
            "Data from BAG Infectious Disease Dashboard, updated weekly. "
            "For outbreak assessment, compare to 5-year mean using series "
            "ending in 'valueMean5y'. "
            f"Classification: {DATA_CLASSIFICATION}; data is aggregated at "
            f"'{MIN_AGGREGATION_LEVEL}' level (public OGD, small cells suppressed "
            "at source by the BAG) — no finer-grained or personal data is exposed."
        ),
        school_relevance=(
            "Influenza and ARI spikes correlate with school outbreak risk. "
            "Measles: single case = potential outbreak in low-vaccination schools. "
            "Pertussis: high risk for unvaccinated infants (siblings of school children)."
        ),
    )


# ---------------------------------------------------------------------------
# Resources (ARCH-008)
# ---------------------------------------------------------------------------
#
# Static reference data is exposed as MCP Resources, not tools: it is fixed,
# read-only and needs no arguments or upstream call, so a Resource (which a host
# can fetch and cache) is the right primitive. Live, parameterised surveillance
# data stays behind Tools.

@mcp.resource(
    "bag://reference/cantons",
    name="swiss_cantons",
    description="The Swiss canton codes accepted by the tools (incl. FL and 'all').",
    mime_type="application/json",
)
def cantons_resource() -> str:
    """The canton allow-list as JSON — reference data for building tool calls."""
    return json.dumps({"cantons": CANTONS})


@mcp.resource(
    "bag://reference/disease-categories",
    name="disease_categories",
    description=(
        "The disease-topic taxonomy: known IDD topic slugs grouped by category. "
        "Static reference; use bag_list_diseases for what the live API currently "
        "serves."
    ),
    mime_type="application/json",
)
def disease_categories_resource() -> str:
    return json.dumps(
        {name: sorted(members) for name, members in DISEASE_CATEGORIES.items()}
    )


@mcp.resource(
    "bag://reference/data-licence",
    name="data_licence",
    description="Data source, attribution and licence terms for the BAG IDD data.",
    mime_type="application/json",
)
def data_licence_resource() -> str:
    return json.dumps(
        {"attribution": DATA_ATTRIBUTION, "license": DATA_LICENSE, "source_api": IDD_BASE}
    )


# ---------------------------------------------------------------------------
# Prompts (ARCH-008)
# ---------------------------------------------------------------------------
#
# Prompts package the recommended multi-tool workflows as reusable, parameterised
# templates a host can surface to the user (e.g. as slash-commands).

@mcp.prompt(
    name="canton_situation_brief",
    title="Canton public-health situation brief",
    description=(
        "Draft a structured public-health situation brief for a Swiss canton "
        "(Schulamt / city-administration use case)."
    ),
)
def canton_situation_brief(canton: str = "ZH") -> str:
    return (
        f"Erstelle einen kurzen Public-Health-Lagebericht für den Kanton {canton}.\n\n"
        "Vorgehen:\n"
        f"1. Rufe bag_get_canton_situation(canton=\"{canton}\") auf.\n"
        "2. Fasse je Krankheit den aktuellen Stand, den Trend und die "
        "Veränderung zur Vorperiode zusammen.\n"
        "3. Hebe schulrelevante Risiken hervor (Influenza/ARI-Spitzen, "
        "Masern-Einzelfälle, Pertussis).\n"
        "4. Nenne Datenstand und Quelle (provenance) am Ende.\n"
        "Antworte auf Deutsch, prägnant, für eine Schulbehörde."
    )


@mcp.prompt(
    name="outbreak_check",
    title="Disease outbreak check",
    description="Check whether a given disease is currently elevated in Switzerland.",
)
def outbreak_check(disease: str = "measles", canton: str = "all") -> str:
    return (
        f"Prüfe, ob bei '{disease}' aktuell ein Ausbruch bzw. eine erhöhte "
        f"Aktivität im Gebiet '{canton}' vorliegt.\n\n"
        "Vorgehen:\n"
        f"1. bag_list_series(topic=\"{disease}\") um eine geeignete Serie zu finden.\n"
        "2. bag_get_series_details(series_id=...) für gültige Filter.\n"
        f"3. bag_get_disease_data(series_id=..., canton=\"{canton}\") für die "
        "Zeitreihe.\n"
        "4. Bewerte den Trend; vergleiche – wenn verfügbar – mit dem 5-Jahres-"
        "Mittel (Serien mit 'valueMean5y').\n"
        "Gib eine klare Einschätzung (erhöht / normal / unklar) mit Datenstand "
        "und Quelle."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _select_http() -> bool:
    """Decide whether to serve over Streamable HTTP (vs. stdio).

    Selection order (SCALE-001): the ``MCP_TRANSPORT`` env var wins when set
    (``http``/``streamable-http`` → HTTP, ``stdio`` → stdio), which is what
    container/cloud deployment manifests should set; otherwise the ``--http``
    CLI flag is honoured for local/back-compat use. Default is stdio.
    """
    transport_env = os.environ.get("MCP_TRANSPORT", "").strip().lower()
    if transport_env:
        return transport_env in {"http", "streamable-http", "streamable_http"}
    return "--http" in sys.argv


def main() -> None:
    """Console-script / module entry point.

    Transport is selected by the ``MCP_TRANSPORT`` env var (``http`` or
    ``stdio``) when set — the recommended way for container/cloud deployments —
    otherwise by the ``--http`` CLI flag; the default is stdio. For HTTP, host
    and port come from ``MCP_HOST`` / ``MCP_PORT`` (or ``--port``). The host
    defaults to ``127.0.0.1`` so a local HTTP server is not exposed to the
    network; container deployments opt into all-interface binding explicitly by
    setting ``MCP_HOST=0.0.0.0`` (see Dockerfile).
    """
    _configure_logging()
    _configure_tracing()  # no-op unless telemetry installed + OTEL endpoint set
    if _select_http():
        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        else:
            port = int(os.environ.get("MCP_PORT", "8000"))
        # FastMCP.run() accepts no host/port kwargs — configure them on the
        # instance settings, which the Streamable HTTP runner (uvicorn) reads.
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        if host not in ("127.0.0.1", "::1", "localhost"):
            # NeighborJack awareness (SEC-016): binding beyond localhost exposes
            # the server on the network; that should only happen in an isolated,
            # gateway-fronted deployment.
            logger.warning(
                "binding HTTP server to non-localhost host %s — ensure this is "
                "an intended, network-isolated deployment behind a gateway",
                host,
                extra={"bind_host": host},
            )
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
