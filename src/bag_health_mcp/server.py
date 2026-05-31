"""
bag-health-mcp — Swiss Federal Office of Public Health (BAG)
Infectious Disease Surveillance MCP Server

Data source: IDD API (api.idd.bag.admin.ch)
No authentication required. All data is public.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import socket
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Literal, NoReturn
from urllib.parse import urlsplit

import httpcore
import httpx
from mcp.server.fastmcp import FastMCP
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

# Swiss cantons (incl. FL = Liechtenstein as BAG tracks it)
CANTONS = [
    "AG","AI","AR","BE","BL","BS","FR","GE","GL","GR",
    "JU","LU","NE","NW","OW","SG","SH","SO","SZ","TG",
    "TI","UR","VD","VS","ZG","ZH","FL","all",
]

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
async def bag_list_diseases(params: ListDiseasesInput) -> dict[str, Any]:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/sets", context="listing disease topics")
        all_sets: list[str] = r.json()

    topics: set[str] = {s.split("/")[0] for s in all_sets}

    # Categorise for readability
    respiratory = {t for t in topics if t in {
        "acute_respiratory_infection", "influenza", "influenza-like_illness",
        "respiratory_pathogens", "covid19",
    }}
    enteric = {t for t in topics if t in {
        "campylobacteriosis", "salmonellosis", "ehec", "listeriosis",
        "hepatitis_a", "hepatitis_e", "shigellosis", "cholera",
        "typhoidParatyphoidFever", "trichinellosis", "botulism", "qFever",
    }}
    sti_blood = {t for t in topics if t in {
        "hiv", "aids", "syphilis", "gonorrhea", "chlamydiosis",
        "hepatitis_b", "hepatitis_c",
    }}
    vaccine_prev = {t for t in topics if t in {
        "measles", "rubella", "pertussis", "diphtheria", "tetanus",
        "haemophilusInfluenzae", "ipd", "meningo", "herpesZoster",
        "postZosterNeuralgia",
    }}
    vector_borne = {t for t in topics if t in {
        "lyme_borreliosis", "tick-borne_encephalitis", "dengueFever",
        "malaria", "westnileFever", "chikungunya", "zika", "yellowFever",
        "hanta", "tularemia",
    }}
    wastewater = {t for t in topics if "wastewater" in t}
    other = topics - respiratory - enteric - sti_blood - vaccine_prev - vector_borne - wastewater

    return {
        "total_topics": len(topics),
        "data_version": "see bag_get_data_version",
        "categories": {
            "respiratory": sorted(respiratory),
            "enteric": sorted(enteric),
            "sti_and_bloodborne": sorted(sti_blood),
            "vaccine_preventable": sorted(vaccine_prev),
            "vector_borne": sorted(vector_borne),
            "wastewater_surveillance": sorted(wastewater),
            "other": sorted(other),
        },
        "usage": (
            "Use a topic slug with bag_list_series(topic=...) "
            "to see available data series."
        ),
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "List all available data series for a specific disease topic. "
    "Each series is identified by 'topic/chapter/aggregation/temporality'. "
    "Returns series IDs to use with bag_get_series_details and bag_get_disease_data."
))
async def bag_list_series(params: DataSetsInput) -> dict[str, Any]:
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

    return {
        "topic": params.topic,
        "total_series": len(topic_sets),
        "chapters": {ch: sorted(series) for ch, series in sorted(chapters.items())},
        "series_ids": sorted(topic_sets),
        "usage": (
            "Use a series_id with bag_get_series_details to see available "
            "filter values (canton, age_group, sex, type), then "
            "bag_get_disease_data to fetch the time series."
        ),
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "Get metadata and available filter values for a specific data series. "
    "Shows which canton, age group, sex, and other dimensions are available. "
    "Always call this before bag_get_disease_data to know valid filter options."
))
async def bag_get_series_details(params: SeriesDetailsInput) -> dict[str, Any]:
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

    return {
        "series_id": params.series_id,
        "source": data.get("source"),
        "source_date": data.get("sourceDate"),
        "version": data.get("version"),
        "available_filters": filters,
        "cantons": filters.get("canton", []),
        "age_groups": (
            filters.get("agegroup_ili_ari")
            or filters.get("agegroup_oblig")
            or filters.get("agegroup")
            or []
        ),
        "sex_options": filters.get("sex", []),
        "note": (
            "Use these filter values in bag_get_disease_data. "
            "Use 'all' for any aggregated dimension."
        ),
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "Fetch time-series surveillance data for a disease from the BAG IDD. "
    "Returns weekly or yearly case counts, incidence rates, or other metrics. "
    "Data updated every Wednesday. "
    "Example: Influenza incidence per 100k population in Zurich by week."
))
async def bag_get_disease_data(params: DiseaseDataInput) -> dict[str, Any]:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        _fail("series_id must be 'topic/chapter/aggregation/temporality'.")
    topic, chapter, aggregation, temporality = parts

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

    result_series: list[dict[str, Any]] = []

    if isinstance(values, dict):
        # grouped by canton
        for canton_key, points in values.items():
            if not isinstance(points, list):
                continue
            # Take last N points
            recent = points[-params.limit_weeks:]
            series_points = [
                {
                    "period": fmt_period(p["x"]),
                    "value": p.get("y"),
                    "trend": p.get("properties", {}).get("trend"),
                    "data_complete": p.get("properties", {}).get("dataComplete"),
                }
                for p in recent
                if p.get("y") is not None
            ]
            if series_points:
                result_series.append({
                    "canton": canton_key,
                    "data_points": len(series_points),
                    "series": series_points,
                })
    elif isinstance(values, list):
        recent = values[-params.limit_weeks:]
        result_series = [
            {
                "period": fmt_period(p["x"]),
                "value": p.get("y"),
                "trend": p.get("properties", {}).get("trend"),
            }
            for p in recent
            if p.get("y") is not None
        ]

    # Summary stats for canton=all case
    summary: dict[str, Any] = {}
    if params.canton == "ZH" or params.canton != "all":
        matching = next(
            (s for s in result_series if isinstance(s, dict) and s.get("canton") == params.canton),
            None,
        )
        if matching:
            pts = matching["series"]
            if pts:
                last = pts[-1]
                summary = {
                    "canton": params.canton,
                    "latest_period": last["period"],
                    "latest_value": last["value"],
                    "trend": last.get("trend"),
                    "data_points_returned": len(pts),
                }

    return {
        "series_id": params.series_id,
        "topic": topic,
        "aggregation": aggregation,
        "temporality": temporality,
        "source": data.get("source"),
        "source_date": data.get("sourceDate"),
        "data_version": data.get("version"),
        "filters_applied": body,
        "summary": summary,
        "results": result_series,
        "interpretation": (
            f"Values represent '{aggregation}' ({chapter}) for '{topic}'. "
            "Period format: YYYY-Www for weekly, YYYY for yearly. "
            "'incValue' = incidence per 100'000 population. "
            "'value' = absolute case count."
        ),
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "List all available export file names from the BAG IDD. "
    "These are complete datasets (CSV/JSON) per disease, "
    "e.g. INFLUENZA_oblig, COVID19_wastewater_sequencing, MEASLES_oblig. "
    "Use with bag_download_export to get raw data files."
))
async def bag_list_export_files(params: ExportFilesInput) -> dict[str, Any]:
    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/export/{params.version}/files",
            context="listing export files",
        )
        files: list[str] = r.json()

    return {
        "version": params.version,
        "total_files": len(files),
        "files": sorted(files),
        "usage": (
            "Use bag_download_export(file='INFLUENZA_oblig', format='csv') "
            "to download the raw dataset."
        ),
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "Download a complete export dataset from the BAG IDD as CSV or JSON. "
    "Returns the raw data content for a specific disease file. "
    "Useful for bulk analysis. Files are updated weekly."
))
async def bag_download_export(params: ExportDownloadInput) -> dict[str, Any]:
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

    return {
        "file": params.file,
        "format": params.format,
        "size_bytes": len(content),
        "rows": len(lines) - 1 if lines else None,
        "preview": content[:3000],
        "note": (
            "Full data returned in 'preview' (truncated at 3000 chars). "
            "For large datasets, use the IDD web interface at idd.bag.admin.ch."
        ),
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "Get the current data version of the BAG IDD. "
    "Returns the date of the last data update (format YYYYMMDD). "
    "IDD is updated every Wednesday."
))
async def bag_get_data_version(params: DataVersionInput) -> dict[str, Any]:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/version", context="fetching data version")
        data = r.json()

    version_str = data.get("name", "")
    # Parse YYYYMMDD
    if len(version_str) == 8:
        formatted = f"{version_str[:4]}-{version_str[4:6]}-{version_str[6:]}"
    else:
        formatted = version_str

    return {
        "version": version_str,
        "date": formatted,
        "note": "IDD is updated every Wednesday. Data reflects the state as of this date.",
    }


@mcp.tool(annotations=READ_ONLY, description=(
    "Get a public health situation overview for a specific canton or Switzerland. "
    "Combines current incidence data for key school-relevant diseases "
    "(influenza, measles, norovirus proxy via acute_respiratory_infection) "
    "with trend information. Designed for school authorities and "
    "city administration Public Health Reporting. "
    "Anchor query: 'Was ist die aktuelle Grippesituation im Kanton Zürich?'"
))
async def bag_get_canton_situation(
    canton: str = "ZH",
    include_wastewater: bool = False,
) -> dict[str, Any]:
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
    results: dict[str, Any] = {"canton": canton_up, "diseases": {}}

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

    async def _fetch_series(name: str, series_id: str) -> tuple[str, Any]:
        # This aggregates several independent series into one overview. A failure
        # of a single series is reported inline as that series' status and never
        # fails the whole overview (which would be the wrong granularity); the
        # tool call itself still succeeds. Raw causes are logged server-side.
        parts = series_id.split("/")
        if len(parts) != 4:
            return name, {"status": "unavailable"}
        topic, chapter, aggregation, temporality = parts

        is_yearly = "year" in temporality

        try:
            async with _client() as c:
                dr = await c.get(
                    f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details"
                )
                if dr.status_code != 200:
                    return name, {"status": "series_not_found"}
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
                    return name, {"status": "data_unavailable"}
                data = r.json()

            values = data.get("values", {})
            canton_data: list[dict] = []

            if isinstance(values, dict):
                canton_data = values.get(canton_up, [])
            elif isinstance(values, list):
                canton_data = values

            if not canton_data:
                return name, {"status": "no_data", "source_date": data.get("sourceDate")}

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

            return name, {
                "latest_period": period_fmt,
                "latest_value": latest.get("y"),
                "unit": "incidence per 100'000" if "incValue" in aggregation else "absolute count",
                "trend": trend,
                "change_vs_prev_period_pct": change_pct,
                "source_date": data.get("sourceDate"),
                "series": [
                    {
                        "period": _fmt_isoweek(p["x"]) if not is_yearly else _fmt_year(p["x"]),
                        "value": p.get("y"),
                    }
                    for p in recent if p.get("y") is not None
                ],
            }
        except (EgressNotAllowed, httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            # Don't surface the raw exception to the model — log it server-side
            # and report a stable, generic per-series status (OBS-002). An egress
            # block fails this series closed; the guard already logged the target.
            logger.warning("canton_situation series '%s' failed: %r", name, exc)
            return name, {"status": "unavailable"}

    tasks = [_fetch_series(name, sid) for name, sid in school_relevant.items()]
    fetched = await asyncio.gather(*tasks)

    for name, data in fetched:
        results["diseases"][name] = data

    results["note"] = (
        f"Situation overview for canton {canton_up}. "
        "incValue = incidence per 100'000 population. "
        "Data from BAG Infectious Disease Dashboard, updated weekly. "
        "For outbreak assessment, compare to 5-year mean using series "
        "ending in 'valueMean5y'."
    )
    results["school_relevance"] = (
        "Influenza and ARI spikes correlate with school outbreak risk. "
        "Measles: single case = potential outbreak in low-vaccination schools. "
        "Pertussis: high risk for unvaccinated infants (siblings of school children)."
    )

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Console-script / module entry point.

    Default transport is stdio. Pass ``--http`` (optionally ``--port N``) to
    serve over Streamable HTTP. Host and port can also be configured via the
    ``MCP_HOST`` / ``MCP_PORT`` environment variables. The host defaults to
    ``127.0.0.1`` so a local HTTP server is not exposed to the network;
    container deployments opt into all-interface binding explicitly by setting
    ``MCP_HOST=0.0.0.0`` (see Dockerfile).
    """
    if "--http" in sys.argv:
        if "--port" in sys.argv:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        else:
            port = int(os.environ.get("MCP_PORT", "8000"))
        # FastMCP.run() accepts no host/port kwargs — configure them on the
        # instance settings, which the Streamable HTTP runner (uvicorn) reads.
        mcp.settings.host = os.environ.get("MCP_HOST", "127.0.0.1")
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
