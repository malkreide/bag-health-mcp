"""
Tests for bag-health-mcp server.
Run unit tests: pytest -m "not live"
Run live tests: pytest -m live --timeout=30
"""

import sys

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from bag_health_mcp.server import (
    DATA_ATTRIBUTION,
    DATA_LICENSE,
    IDD_BASE,
    CantonDiseaseData,
    CantonDiseaseStatus,
    CantonSeries,
    DataSetsInput,
    DataVersionInput,
    DataVersionOutput,
    DiseaseDataInput,
    ExportFilesInput,
    ListDiseasesInput,
    SeriesDetailsInput,
    _fmt_isoweek,
    bag_get_canton_situation,
    bag_get_data_version,
    bag_get_disease_data,
    bag_get_series_details,
    bag_list_diseases,
    bag_list_export_files,
    bag_list_series,
)

# ---------------------------------------------------------------------------
# Unit: helpers
# ---------------------------------------------------------------------------

def test_fmt_isoweek_6digit():
    assert _fmt_isoweek(202413) == "2024-W13"

def test_fmt_isoweek_passthrough():
    assert _fmt_isoweek(2024) == "2024"


# ---------------------------------------------------------------------------
# Unit: mocked API
# ---------------------------------------------------------------------------

MOCK_SETS = [
    "influenza/cases/incValue/iso_week",
    "influenza/cases/value/iso_week",
    "influenza/cases/incValue/year",
    "measles/cases/incValue/year",
    "measles/cases/value/year",
    "covid19/cases/incValue/iso_week",
    "acute_respiratory_infection/consultations/incValue/iso_week",
    "wastewater_viral_load/NA/value/date",
]

MOCK_DETAILS = {
    "identifier": "influenza/cases/incValue/iso_week",
    "source": "mandatory_reporting_system",
    "sourceDate": "2026-03-24",
    "version": "20260325",
    "properties": {
        "canton": {"allValue": "all", "possibleValues": ["ZH", "BE", "all"]},
        "georegion": {"allValue": None, "possibleValues": ["canton", "CHFL"]},
        "sex": {"allValue": "all", "possibleValues": ["male", "female", "all"]},
        "agegroup": {"allValue": None, "possibleValues": ["agegroup_ili_ari"]},
        "agegroup_ili_ari": {"allValue": "all", "possibleValues": ["0 - 4", "all"]},
        "type": {"allValue": "all", "possibleValues": ["A", "B", "all"]},
    },
    "availableSeriesConfigurations": [],
}

MOCK_DATA = {
    "source": "mandatory_reporting_system",
    "sourceDate": "2026-03-24",
    "version": "20260325",
    "values": {
        "ZH": [
            {"x": 202601, "y": 3.2, "properties": {"dataComplete": "TRUE", "trend": "increasing"}},
            {"x": 202602, "y": 4.1, "properties": {"dataComplete": "TRUE", "trend": "increasing"}},
            {"x": 202603, "y": 5.7, "properties": {"dataComplete": "TRUE", "trend": "stable"}},
        ],
        "BE": [
            {"x": 202601, "y": 2.1, "properties": {"dataComplete": "TRUE", "trend": "stable"}},
        ],
    },
}


@pytest.mark.asyncio
@respx.mock
async def test_bag_list_diseases():
    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )
    result = await bag_list_diseases(ListDiseasesInput())
    assert result.total_topics > 0
    cats = result.categories
    assert "respiratory" in cats
    assert "influenza" in cats["respiratory"]


@pytest.mark.asyncio
@respx.mock
async def test_bag_list_series_found():
    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )
    result = await bag_list_series(DataSetsInput(topic="influenza"))
    assert result.topic == "influenza"
    assert result.total_series == 3
    assert "cases" in result.chapters


@pytest.mark.asyncio
@respx.mock
async def test_bag_list_series_not_found():
    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )
    # Unknown topic is an execution error: raised as ToolError -> isError:true.
    with pytest.raises(ToolError) as exc:
        await bag_list_series(DataSetsInput(topic="unknown_disease"))
    assert "bag_list_diseases" in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_bag_get_series_details_ok():
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))

    result = await bag_get_series_details(
        SeriesDetailsInput(series_id="influenza/cases/incValue/iso_week")
    )
    assert result.series_id == "influenza/cases/incValue/iso_week"
    assert "ZH" in result.cantons
    assert result.provenance.source_date == "2026-03-24"


@pytest.mark.asyncio
@respx.mock
async def test_bag_get_series_details_invalid_format():
    with pytest.raises(ToolError) as exc:
        await bag_get_series_details(
            SeriesDetailsInput(series_id="influenza/cases")  # only 2 parts
        )
    assert "topic/chapter/aggregation/temporality" in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_bag_get_disease_data_zh():
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(200, json=MOCK_DATA))

    result = await bag_get_disease_data(
        DiseaseDataInput(
            series_id="influenza/cases/incValue/iso_week",
            canton="ZH",
        )
    )
    assert result.topic == "influenza"
    assert result.provenance.source_date == "2026-03-24"
    # ZH has 3 data points
    zh_results = [r for r in result.results
                  if isinstance(r, CantonSeries) and r.canton == "ZH"]
    assert len(zh_results) > 0
    assert zh_results[0].data_points == 3


@pytest.mark.asyncio
@respx.mock
async def test_disease_data_api_error_does_not_leak_body():
    """On an upstream error the tool raises a ToolError (-> isError:true,
    OBS-001) whose message carries only the status code and a generic hint —
    never the raw upstream body (OBS-002)."""
    secret_body = "INTERNAL-STACKTRACE secret upstream detail 0xDEADBEEF"
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(500, text=secret_body))

    with pytest.raises(ToolError) as exc:
        await bag_get_disease_data(
            DiseaseDataInput(series_id="influenza/cases/incValue/iso_week", canton="ZH")
        )
    message = str(exc.value)
    assert "500" in message
    assert secret_body not in message


@pytest.mark.asyncio
@respx.mock
async def test_bag_get_data_version():
    respx.get(f"{IDD_BASE}/api/v1/data/version").mock(
        return_value=httpx.Response(200, json={"name": "20260325"})
    )
    result = await bag_get_data_version(DataVersionInput())
    assert result.version == "20260325"
    assert result.date == "2026-03-25"


@pytest.mark.asyncio
@respx.mock
async def test_bag_list_export_files():
    respx.get(f"{IDD_BASE}/api/v1/export/latest/files").mock(
        return_value=httpx.Response(200, json=["INFLUENZA_oblig", "COVID19_oblig"])
    )
    result = await bag_list_export_files(ExportFilesInput())
    assert result.total_files == 2
    assert "INFLUENZA_oblig" in result.files


# ---------------------------------------------------------------------------
# Live tests (require network, skip in CI)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_list_diseases():
    result = await bag_list_diseases(ListDiseasesInput())
    assert result.total_topics >= 40
    assert "influenza" in result.categories["respiratory"]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_data_version():
    result = await bag_get_data_version(DataVersionInput())
    assert len(result.version) == 8
    assert result.version.startswith("2026") or result.version.startswith("2025")


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_influenza_zh():
    """Anchor demo query: Grippesituation Kanton Zürich."""
    result = await bag_get_disease_data(
        DiseaseDataInput(
            series_id="influenza/cases/incValue/iso_week",
            canton="ZH",
            limit_weeks=26,
        )
    )
    assert result.topic == "influenza"
    assert len(result.results) > 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_canton_situation():
    result = await bag_get_canton_situation(canton="ZH")
    assert result.canton == "ZH"
    assert "influenza" in result.diseases


# ---------------------------------------------------------------------------
# Unit: entry point / transport selection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_tools_declare_readonly_annotations():
    """Every tool is read-only, idempotent and open-world (ARCH-009)."""
    from bag_health_mcp.server import mcp

    tools = await mcp.list_tools()
    assert len(tools) == 8
    for t in tools:
        ann = t.annotations
        assert ann is not None, f"{t.name} has no annotations"
        assert ann.readOnlyHint is True, t.name
        assert ann.destructiveHint is False, t.name
        assert ann.idempotentHint is True, t.name
        assert ann.openWorldHint is True, t.name


def test_main_stdio_default(monkeypatch):
    """Without --http, main() runs the default stdio transport."""
    from bag_health_mcp import server

    called = {}
    monkeypatch.setattr(sys, "argv", ["bag-health-mcp"])
    monkeypatch.setattr(server.mcp, "run", lambda *a, **k: called.update(args=a, kwargs=k))
    server.main()
    # stdio = run() with no transport argument
    assert called == {"args": (), "kwargs": {}}


def test_main_http_sets_settings_and_no_port_kwarg(monkeypatch):
    """--http must configure host/port on settings and call run() WITHOUT a
    port kwarg (regression guard: FastMCP.run() raises TypeError on port=)."""
    from bag_health_mcp import server

    called = {}
    monkeypatch.setattr(sys, "argv", ["bag-health-mcp", "--http", "--port", "9001"])
    monkeypatch.delenv("MCP_HOST", raising=False)
    monkeypatch.setattr(server.mcp, "run", lambda *a, **k: called.update(args=a, kwargs=k))
    server.main()
    assert called["kwargs"] == {"transport": "streamable-http"}
    assert "port" not in called["kwargs"]
    assert server.mcp.settings.port == 9001
    assert server.mcp.settings.host == "127.0.0.1"  # safe default, no MCP_HOST


def test_main_http_respects_mcp_host_env(monkeypatch):
    """Container deployments set MCP_HOST=0.0.0.0 to bind all interfaces."""
    from bag_health_mcp import server

    monkeypatch.setattr(sys, "argv", ["bag-health-mcp", "--http"])
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "8123")
    monkeypatch.setattr(server.mcp, "run", lambda *a, **k: None)
    server.main()
    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 8123


# ---------------------------------------------------------------------------
# OBS-001: protocol vs. execution error contract (in-memory client roundtrip)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_execution_error_surfaces_as_tool_result_iserror():
    """An upstream failure must reach the model as a tool RESULT with
    isError:true (execution error) — not as a JSON-RPC protocol error — and
    must not leak the raw upstream body (OBS-001 + OBS-002)."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    secret_body = "INTERNAL upstream stacktrace 0xDEADBEEF"
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(500, text=secret_body))

    async with connect(mcp._mcp_server) as client:
        result = await client.call_tool(
            "bag_get_disease_data",
            {"params": {"series_id": "influenza/cases/incValue/iso_week", "canton": "ZH"}},
        )

    assert result.isError is True
    text = " ".join(getattr(c, "text", "") for c in result.content)
    assert "500" in text
    assert secret_body not in text


@pytest.mark.asyncio
@respx.mock
async def test_not_found_surfaces_as_tool_result_iserror():
    """A semantic not-found (unknown topic) is an execution error: isError:true
    with an actionable hint, not an empty success result (ARCH-003/OBS-001)."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )

    async with connect(mcp._mcp_server) as client:
        result = await client.call_tool(
            "bag_list_series", {"params": {"topic": "unknown_disease"}}
        )

    assert result.isError is True
    text = " ".join(getattr(c, "text", "") for c in result.content)
    assert "bag_list_diseases" in text


@pytest.mark.asyncio
async def test_schema_invalid_params_are_protocol_errors():
    """Schema-invalid params (bad enum) are genuine protocol errors handled by
    the SDK with isError:true at the protocol boundary — validated before any
    tool body runs (no upstream call mocked, so a leak here would be a bug)."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    async with connect(mcp._mcp_server) as client:
        result = await client.call_tool(
            "bag_get_disease_data",
            {"params": {"series_id": "influenza/cases/incValue/iso_week",
                        "canton": "NOT_A_CANTON"}},
        )

    assert result.isError is True


@pytest.mark.asyncio
@respx.mock
async def test_successful_call_is_not_iserror():
    """A normal successful call must report isError:false (regression guard so
    the execution-error path doesn't bleed into the happy path)."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(200, json=MOCK_DATA))

    async with connect(mcp._mcp_server) as client:
        result = await client.call_tool(
            "bag_get_disease_data",
            {"params": {"series_id": "influenza/cases/incValue/iso_week", "canton": "ZH"}},
        )

    assert result.isError is False


# ---------------------------------------------------------------------------
# SDK-001: lifespan-managed shared httpx client (connection pooling)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lifespan_shares_single_pooled_client():
    """The lifespan opens ONE pooled client shared across tools; exiting the
    per-call _client() context must not close it, and the lifespan shutdown
    must close it (SDK-001)."""
    from bag_health_mcp import server

    async with server.lifespan(server.mcp) as ctx:
        pooled = ctx["http_client"]
        # Every _client() acquisition yields the same pooled instance ...
        async with server._client() as a, server._client() as b:
            assert a is b is pooled
        # ... and exiting the _client() context does NOT close it.
        assert pooled.is_closed is False

    # Lifespan shutdown closes the pooled client and clears the module slot.
    assert pooled.is_closed is True
    assert server._shared_client is None


@pytest.mark.asyncio
@respx.mock
async def test_tools_reuse_pooled_client_under_lifespan():
    """Two tool calls within one lifespan must reuse the same client object
    (no client-per-call), and still work end to end."""
    from bag_health_mcp import server

    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )

    async with server.lifespan(server.mcp) as ctx:
        pooled = ctx["http_client"]
        r1 = await bag_list_diseases(ListDiseasesInput())
        r2 = await bag_list_series(DataSetsInput(topic="influenza"))
        # Both calls ran against the single pooled client.
        assert server._shared_client is pooled
        assert r1.total_topics > 0
        assert r2.topic == "influenza"


# ---------------------------------------------------------------------------
# SEC-021 / SEC-004: egress allow-list + HTTPS enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assert_egress_allows_idd_host():
    """The configured BAG IDD host over HTTPS (resolving to a public IP) is OK."""
    from bag_health_mcp.server import _assert_egress_allowed

    await _assert_egress_allowed(httpx.URL("https://api.idd.bag.admin.ch/api/v1/data/version"))


@pytest.mark.asyncio
async def test_assert_egress_blocks_other_host():
    """Any host outside the allow-list is refused (SEC-021)."""
    from bag_health_mcp.server import EgressNotAllowed, _assert_egress_allowed

    with pytest.raises(EgressNotAllowed):
        await _assert_egress_allowed(httpx.URL("https://evil.example.com/steal"))


@pytest.mark.asyncio
async def test_assert_egress_blocks_internal_ip_host():
    """The cloud metadata endpoint as a literal host is refused (not allow-listed)."""
    from bag_health_mcp.server import EgressNotAllowed, _assert_egress_allowed

    with pytest.raises(EgressNotAllowed):
        await _assert_egress_allowed(httpx.URL("http://169.254.169.254/latest/meta-data"))


@pytest.mark.asyncio
async def test_assert_egress_blocks_non_https_scheme():
    """Plain HTTP to the allowed host is still refused (SEC-004 scheme enforce)."""
    from bag_health_mcp.server import EgressNotAllowed, _assert_egress_allowed

    with pytest.raises(EgressNotAllowed):
        await _assert_egress_allowed(httpx.URL("http://api.idd.bag.admin.ch/api/v1/data/version"))


@pytest.mark.asyncio
async def test_assert_egress_blocks_allowed_host_resolving_to_private_ip(monkeypatch):
    """SEC-004 IP-blocklist: even the allow-listed host is refused if DNS returns
    a private/internal address (SSRF via a poisoned/rebound record)."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import EgressNotAllowed, _assert_egress_allowed

    async def _resolve_internal(host: str) -> list[str]:
        return ["169.254.169.254"]

    monkeypatch.setattr(server, "_resolve_host", _resolve_internal)
    with pytest.raises(EgressNotAllowed):
        await _assert_egress_allowed(httpx.URL("https://api.idd.bag.admin.ch/api/v1/data/version"))


@pytest.mark.asyncio
async def test_assert_egress_blocks_when_any_resolved_ip_is_private(monkeypatch):
    """If a host resolves to a mix of public and private IPs, fail closed —
    a public answer must not mask an internal one."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import EgressNotAllowed, _assert_egress_allowed

    async def _resolve_mixed(host: str) -> list[str]:
        return ["93.184.216.34", "10.0.0.5"]

    monkeypatch.setattr(server, "_resolve_host", _resolve_mixed)
    with pytest.raises(EgressNotAllowed):
        await _assert_egress_allowed(httpx.URL("https://api.idd.bag.admin.ch/api/v1/data/version"))


@pytest.mark.asyncio
async def test_assert_egress_blocks_on_dns_failure(monkeypatch):
    """A resolution failure fails closed (no request proceeds on unknown IP)."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import EgressNotAllowed, _assert_egress_allowed

    async def _resolve_fail(host: str) -> list[str]:
        raise OSError("temporary DNS failure")

    monkeypatch.setattr(server, "_resolve_host", _resolve_fail)
    with pytest.raises(EgressNotAllowed):
        await _assert_egress_allowed(httpx.URL("https://api.idd.bag.admin.ch/api/v1/data/version"))


@pytest.mark.asyncio
@respx.mock
async def test_redirect_to_internal_host_is_blocked_no_leak():
    """A compromised-upstream 30x redirect to an internal host must be blocked
    on the redirect hop and must not leak the internal response (SEC-004)."""
    secret = "SECRET-METADATA-TOKEN"
    respx.get(f"{IDD_BASE}/api/v1/data/version").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/x"})
    )
    # Even if the attacker stands up a listener, the guard fires before this
    # response can be consumed:
    respx.get("http://169.254.169.254/x").mock(
        return_value=httpx.Response(200, text=secret)
    )

    with pytest.raises(ToolError) as exc:
        await bag_get_data_version(DataVersionInput())
    assert secret not in str(exc.value)


@pytest.mark.asyncio
async def test_new_client_registers_egress_guard():
    """The pooled client is built with the egress guard wired as a request hook
    so every request (and redirect hop) is validated."""
    from bag_health_mcp.server import _egress_guard, _new_client

    client = _new_client()
    try:
        assert _egress_guard in client.event_hooks["request"]
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# SEC-005: outbound DNS-pinning network backend (TOCTOU)
# ---------------------------------------------------------------------------
#
# These exercise the _PinningBackend directly with a fake inner backend, because
# respx intercepts ABOVE the network backend (verified) and so never reaches it.

class _FakeStream:
    pass


class _RecordingInner:
    """Stand-in inner network backend that records the address it is asked to
    dial instead of opening a real socket."""

    def __init__(self):
        self.connected_to = None

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connected_to = (host, port)
        return _FakeStream()

    async def connect_unix_socket(self, *a, **k):  # pragma: no cover - not used
        raise AssertionError("unix socket should never be reached")

    async def sleep(self, seconds):  # pragma: no cover
        return None


@pytest.mark.asyncio
async def test_new_client_installs_pinning_backend():
    """The pooled client's connection pool uses the SEC-005 pinning backend."""
    from bag_health_mcp.server import _new_client, _PinningBackend

    client = _new_client()
    try:
        backend = client._transport._pool._network_backend
        assert isinstance(backend, _PinningBackend)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pinning_backend_connects_to_validated_public_ip(monkeypatch):
    """The backend resolves the host once and dials the exact validated IP
    (no second lookup) — closing the resolve-vs-connect TOCTOU window."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import _PinningBackend

    async def _resolve(host):
        return ["93.184.216.34"]

    monkeypatch.setattr(server, "_resolve_host", _resolve)
    inner = _RecordingInner()
    backend = _PinningBackend(inner)

    stream = await backend.connect_tcp("api.idd.bag.admin.ch", 443)

    assert stream is not None
    # Dialled the resolved IP, not the hostname (proves the pin).
    assert inner.connected_to == ("93.184.216.34", 443)


@pytest.mark.asyncio
async def test_pinning_backend_blocks_private_resolution(monkeypatch):
    """If the host resolves to an internal IP, the backend refuses to connect
    at all (the inner backend is never dialled)."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import EgressNotAllowed, _PinningBackend

    async def _resolve(host):
        return ["169.254.169.254"]

    monkeypatch.setattr(server, "_resolve_host", _resolve)
    inner = _RecordingInner()
    backend = _PinningBackend(inner)

    with pytest.raises(EgressNotAllowed):
        await backend.connect_tcp("api.idd.bag.admin.ch", 443)
    assert inner.connected_to is None


@pytest.mark.asyncio
async def test_pinning_backend_validates_literal_ip_without_dns(monkeypatch):
    """A literal-IP host is validated directly (no DNS) and a private one is
    refused; a public one is dialled as-is."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import EgressNotAllowed, _PinningBackend

    async def _resolve_should_not_run(host):  # pragma: no cover
        raise AssertionError("resolver must not run for a literal IP")

    monkeypatch.setattr(server, "_resolve_host", _resolve_should_not_run)

    inner = _RecordingInner()
    backend = _PinningBackend(inner)
    with pytest.raises(EgressNotAllowed):
        await backend.connect_tcp("169.254.169.254", 80)
    assert inner.connected_to is None

    inner2 = _RecordingInner()
    backend2 = _PinningBackend(inner2)
    await backend2.connect_tcp("8.8.8.8", 443)
    assert inner2.connected_to == ("8.8.8.8", 443)


@pytest.mark.asyncio
async def test_pinning_backend_fails_closed_on_dns_error(monkeypatch):
    """A resolution failure raises EgressNotAllowed; nothing is dialled."""
    import bag_health_mcp.server as server
    from bag_health_mcp.server import EgressNotAllowed, _PinningBackend

    async def _resolve(host):
        raise OSError("temporary DNS failure")

    monkeypatch.setattr(server, "_resolve_host", _resolve)
    inner = _RecordingInner()
    backend = _PinningBackend(inner)

    with pytest.raises(EgressNotAllowed):
        await backend.connect_tcp("api.idd.bag.admin.ch", 443)
    assert inner.connected_to is None


@pytest.mark.asyncio
async def test_pinning_backend_refuses_unix_socket():
    """Unix-socket egress is refused outright (only remote HTTPS is allowed)."""
    from bag_health_mcp.server import EgressNotAllowed, _PinningBackend

    backend = _PinningBackend(_RecordingInner())
    with pytest.raises(EgressNotAllowed):
        await backend.connect_unix_socket("/var/run/whatever.sock")


@pytest.mark.asyncio
@respx.mock
async def test_canton_situation_degrades_on_egress_block_no_leak():
    """If a per-series fetch hits a blocked redirect, that series fails closed
    (status 'unavailable') instead of crashing the whole overview or leaking
    the internal response (SEC-004/SEC-021 + OBS-002)."""
    respx.get(url__regex=r".*/details$").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/x"})
    )
    respx.route().mock(return_value=httpx.Response(200, text="LEAK-MUST-NOT-APPEAR"))

    result = await bag_get_canton_situation(canton="ZH")

    assert result.canton == "ZH"
    # Every series failed closed as a status (not data), all 'unavailable'.
    assert all(isinstance(v, CantonDiseaseStatus) and v.status == "unavailable"
               for v in result.diseases.values())
    assert "LEAK-MUST-NOT-APPEAR" not in repr(result)


# ---------------------------------------------------------------------------
# SEC-018: strict input validation at tool boundaries
# ---------------------------------------------------------------------------

from pydantic import ValidationError  # noqa: E402


def test_input_models_accept_real_world_values():
    """Constraints must not reject any legitimate IDD value."""
    from bag_health_mcp.server import (
        DataSetsInput,
        DiseaseDataInput,
        ExportDownloadInput,
        SeriesDetailsInput,
    )

    for topic in ["influenza", "covid19", "tick-borne_encephalitis",
                  "acute_respiratory_infection", "wastewater_viral_load"]:
        DataSetsInput(topic=topic)
    for sid in ["influenza/cases/incValue/iso_week",
                "wastewater_viral_load/NA/value/date"]:
        SeriesDetailsInput(series_id=sid)
    for age in ["0 - 4", "5 - 14", "65+"]:
        DiseaseDataInput(series_id="influenza/cases/incValue/iso_week", age_group=age)
    for f in ["INFLUENZA_oblig", "COVID19_wastewater_sequencing"]:
        ExportDownloadInput(file=f)


def test_input_models_forbid_extra_fields():
    """extra='forbid' rejects unexpected fields (SEC-018)."""
    from bag_health_mcp.server import DataSetsInput

    with pytest.raises(ValidationError):
        DataSetsInput(topic="influenza", unexpected="x")


def test_input_models_are_strict_no_coercion():
    """strict=True refuses silent type coercion (e.g. str where int declared)."""
    from bag_health_mcp.server import DiseaseDataInput

    with pytest.raises(ValidationError):
        DiseaseDataInput.model_validate(
            {"series_id": "influenza/cases/incValue/iso_week", "limit_weeks": "26"}
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"topic": "../../etc/passwd"},   # path traversal
        {"topic": "a/b"},                # slash not allowed in a topic slug
        {"topic": "a" * 65},             # over max_length
        {"topic": ""},                   # under min_length
    ],
)
def test_topic_rejects_malicious_or_oversized(kwargs):
    from bag_health_mcp.server import DataSetsInput

    with pytest.raises(ValidationError):
        DataSetsInput(**kwargs)


def test_series_id_rejects_injection_chars():
    from bag_health_mcp.server import SeriesDetailsInput

    with pytest.raises(ValidationError):
        SeriesDetailsInput(series_id="influenza;rm -rf /")


def test_export_file_rejects_path_chars():
    from bag_health_mcp.server import ExportDownloadInput

    with pytest.raises(ValidationError):
        ExportDownloadInput(file="../secret")


@pytest.mark.asyncio
async def test_input_schema_advertises_constraints():
    """The advertised JSON inputSchema must carry the pattern/length limits and
    forbid extra properties, so invalid args are refused at the protocol layer."""
    import json

    from bag_health_mcp.server import mcp

    tools = {t.name: t for t in await mcp.list_tools()}
    blob = json.dumps(tools["bag_get_disease_data"].inputSchema)
    assert "pattern" in blob
    assert "maxLength" in blob
    assert '"additionalProperties": false' in blob


# ---------------------------------------------------------------------------
# OBS-003 / OBS-004: structured JSON logging on stderr
# ---------------------------------------------------------------------------

import io as _io  # noqa: E402
import json as _json  # noqa: E402
import logging as _logging  # noqa: E402


def test_json_log_formatter_emits_valid_json_with_rfc5424_severity():
    """Each record renders as one JSON object carrying an RFC 5424 severity."""
    from bag_health_mcp.server import JsonLogFormatter

    fmt = JsonLogFormatter()
    rec = _logging.LogRecord(
        name="bag_health_mcp", level=_logging.WARNING, pathname=__file__,
        lineno=1, msg="careful %s", args=("now",), exc_info=None,
    )
    obj = _json.loads(fmt.format(rec))
    assert obj["message"] == "careful now"
    assert obj["level"] == "WARNING"
    assert obj["severity"] == "warning"
    assert obj["severity_code"] == 4
    assert obj["logger"] == "bag_health_mcp"
    assert "timestamp" in obj


def test_json_log_formatter_merges_extra_and_exception():
    """extra= fields are merged and exceptions captured as text."""
    from bag_health_mcp.server import JsonLogFormatter

    fmt = JsonLogFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        rec = _logging.LogRecord(
            name="bag_health_mcp", level=_logging.ERROR, pathname=__file__,
            lineno=1, msg="failed", args=(), exc_info=sys.exc_info(),
        )
        rec.request_id = "abc123"  # as logger.error(..., extra={"request_id": ...})
    obj = _json.loads(fmt.format(rec))
    assert obj["request_id"] == "abc123"
    assert "ValueError" in obj["exception"]
    assert obj["severity_code"] == 3


def test_configure_logging_writes_json_to_stderr(monkeypatch):
    """_configure_logging sends JSON records to stderr (OBS-004: stdout is the
    stdio protocol channel)."""
    import bag_health_mcp.server as server

    cap = _io.StringIO()
    monkeypatch.setattr(sys, "stderr", cap)
    server._configure_logging("DEBUG")
    try:
        server.logger.info("hello")
    finally:
        for h in list(server.logger.handlers):
            if h.get_name() == "bag_health_mcp_json":
                server.logger.removeHandler(h)

    line = cap.getvalue().strip().splitlines()[-1]
    obj = _json.loads(line)
    assert obj["message"] == "hello"
    assert obj["severity"] == "info"


def test_configure_logging_is_idempotent_and_no_propagate():
    """Repeated calls keep exactly one handler and disable propagation so
    records never reach the root logger (which could hit stdout)."""
    import bag_health_mcp.server as server

    try:
        server._configure_logging("INFO")
        server._configure_logging("INFO")
        server._configure_logging("INFO")
        handlers = [h for h in server.logger.handlers
                    if h.get_name() == "bag_health_mcp_json"]
        assert len(handlers) == 1
        assert server.logger.propagate is False
        assert server.logger.level == _logging.INFO
    finally:
        for h in list(server.logger.handlers):
            if h.get_name() == "bag_health_mcp_json":
                server.logger.removeHandler(h)
        server.logger.propagate = True


def test_configure_logging_honors_env_level(monkeypatch):
    """Level falls back to MCP_LOG_LEVEL when not passed explicitly."""
    import bag_health_mcp.server as server

    monkeypatch.setenv("MCP_LOG_LEVEL", "ERROR")
    try:
        server._configure_logging()
        assert server.logger.level == _logging.ERROR
    finally:
        for h in list(server.logger.handlers):
            if h.get_name() == "bag_health_mcp_json":
                server.logger.removeHandler(h)


def test_main_configures_logging(monkeypatch):
    """main() installs the structured logging handler on startup."""
    import bag_health_mcp.server as server

    monkeypatch.setattr(sys, "argv", ["bag-health-mcp"])
    monkeypatch.setattr(server.mcp, "run", lambda *a, **k: None)
    try:
        server.main()
        handlers = [h for h in server.logger.handlers
                    if h.get_name() == "bag_health_mcp_json"]
        assert len(handlers) == 1
    finally:
        for h in list(server.logger.handlers):
            if h.get_name() == "bag_health_mcp_json":
                server.logger.removeHandler(h)
        server.logger.propagate = True


# ---------------------------------------------------------------------------
# SDK-002: typed output models + provenance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_tool_returns_typed_output_model():
    """A tool returns its Pydantic output model instance, not a bare dict."""
    respx.get(f"{IDD_BASE}/api/v1/data/version").mock(
        return_value=httpx.Response(200, json={"name": "20260325"})
    )
    result = await bag_get_data_version(DataVersionInput())
    assert isinstance(result, DataVersionOutput)


@pytest.mark.asyncio
@respx.mock
async def test_every_output_carries_attribution_provenance():
    """Every tool output exposes provenance with the data attribution (CH-004)."""
    respx.get(f"{IDD_BASE}/api/v1/data/version").mock(
        return_value=httpx.Response(200, json={"name": "20260325"})
    )
    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )
    v = await bag_get_data_version(DataVersionInput())
    d = await bag_list_diseases(ListDiseasesInput())
    assert v.provenance.attribution == DATA_ATTRIBUTION
    assert d.provenance.attribution == DATA_ATTRIBUTION
    # CH-004: a controlled licence accompanies the attribution on every output.
    assert v.provenance.license == DATA_LICENSE
    assert d.provenance.license == DATA_LICENSE
    assert "attribution required" in v.provenance.license
    # data_version tool also pins the version into provenance
    assert v.provenance.data_version == "20260325"


@pytest.mark.asyncio
async def test_all_tools_advertise_output_schema():
    """Every tool exposes a non-null outputSchema in tools/list (SDK-002)."""
    from bag_health_mcp.server import mcp

    tools = await mcp.list_tools()
    assert len(tools) == 8
    for t in tools:
        assert t.outputSchema is not None, f"{t.name} has no outputSchema"


@pytest.mark.asyncio
@respx.mock
async def test_call_through_client_yields_structured_content():
    """An in-memory client call returns structuredContent with provenance."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    respx.get(f"{IDD_BASE}/api/v1/data/version").mock(
        return_value=httpx.Response(200, json={"name": "20260325"})
    )
    async with connect(mcp._mcp_server) as client:
        result = await client.call_tool("bag_get_data_version", {"params": {}})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["version"] == "20260325"
    assert "provenance" in result.structuredContent


@pytest.mark.asyncio
@respx.mock
async def test_disease_data_results_are_typed_union():
    """Canton-grouped results are CantonSeries of typed DiseaseDataPoints, and
    the summary is a typed model populated from them (SDK-002)."""
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(200, json=MOCK_DATA))

    result = await bag_get_disease_data(
        DiseaseDataInput(series_id="influenza/cases/incValue/iso_week", canton="ZH")
    )
    zh = next(r for r in result.results
              if isinstance(r, CantonSeries) and r.canton == "ZH")
    assert zh.series[0].period  # typed DiseaseDataPoint
    assert result.summary.canton == "ZH"
    assert result.summary.data_points_returned == 3
    assert result.provenance.data_version == "20260325"


@pytest.mark.asyncio
@respx.mock
async def test_canton_situation_returns_typed_disease_data():
    """A successful canton overview yields typed CantonDiseaseData entries."""
    respx.get(url__regex=r".*/details$").mock(
        return_value=httpx.Response(200, json=MOCK_DETAILS)
    )
    respx.post(url__regex=r"/api/v1/data/[^/]+/[^/]+/[^/]+/[^/]+$").mock(
        return_value=httpx.Response(200, json=MOCK_DATA)
    )

    result = await bag_get_canton_situation(canton="ZH")
    assert result.canton == "ZH"
    flu = result.diseases["influenza"]
    assert isinstance(flu, CantonDiseaseData)
    assert flu.latest_value is not None


@pytest.mark.asyncio
async def test_license_advertised_in_output_schema():
    """CH-004: the controlled licence field is part of every tool's outputSchema
    (so reuse terms are discoverable from tools/list, not just at call time)."""
    import json

    from bag_health_mcp.server import mcp

    for t in await mcp.list_tools():
        blob = json.dumps(t.outputSchema)
        assert "license" in blob, f"{t.name} outputSchema lacks license"
        assert "attribution" in blob, f"{t.name} outputSchema lacks attribution"


# ---------------------------------------------------------------------------
# ARCH-008: all three MCP primitives (tools, resources, prompts)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_server_exposes_resources_and_prompts():
    """The server uses all three primitives, not tools only (ARCH-008)."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    async with connect(mcp._mcp_server) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

    assert len(tools.tools) == 8
    uris = {str(r.uri) for r in resources.resources}
    assert {
        "bag://reference/cantons",
        "bag://reference/disease-categories",
        "bag://reference/data-licence",
    } <= uris
    names = {p.name for p in prompts.prompts}
    assert {"canton_situation_brief", "outbreak_check"} <= names


@pytest.mark.asyncio
async def test_reference_resources_are_readable_json():
    """Each reference resource returns valid JSON reference data."""
    import json

    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import CANTONS, DATA_LICENSE, DISEASE_CATEGORIES, mcp

    async with connect(mcp._mcp_server) as client:
        cantons = json.loads(
            (await client.read_resource("bag://reference/cantons")).contents[0].text
        )
        cats = json.loads(
            (await client.read_resource("bag://reference/disease-categories"))
            .contents[0].text
        )
        lic = json.loads(
            (await client.read_resource("bag://reference/data-licence")).contents[0].text
        )

    assert cantons["cantons"] == CANTONS
    assert set(cats) == set(DISEASE_CATEGORIES)
    assert lic["license"] == DATA_LICENSE


@pytest.mark.asyncio
async def test_prompts_render_with_arguments():
    """Prompts render the workflow text and interpolate their arguments."""
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from bag_health_mcp.server import mcp

    async with connect(mcp._mcp_server) as client:
        brief = await client.get_prompt("canton_situation_brief", {"canton": "BE"})
        outbreak = await client.get_prompt(
            "outbreak_check", {"disease": "measles", "canton": "ZH"}
        )

    brief_text = brief.messages[0].content.text
    assert "BE" in brief_text
    assert "bag_get_canton_situation" in brief_text
    outbreak_text = outbreak.messages[0].content.text
    assert "measles" in outbreak_text
    assert "bag_get_disease_data" in outbreak_text


def test_disease_categories_taxonomy_is_source_of_truth():
    """bag_list_diseases categorises against the shared DISEASE_CATEGORIES map."""
    from bag_health_mcp.server import DISEASE_CATEGORIES

    # Sanity: the taxonomy covers the well-known school-relevant topics.
    assert "influenza" in DISEASE_CATEGORIES["respiratory"]
    assert "measles" in DISEASE_CATEGORIES["vaccine_preventable"]
    assert "wastewater_surveillance" not in DISEASE_CATEGORIES  # matched by substring


# ---------------------------------------------------------------------------
# SDK-003: Context injection (progress + structured logging)
# ---------------------------------------------------------------------------

class _RecordingCtx:
    """Minimal stand-in for FastMCP Context capturing log/progress calls."""

    def __init__(self):
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.progress: list[tuple[float, float | None]] = []

    async def info(self, message, **extra):
        self.infos.append(message)

    async def warning(self, message, **extra):
        self.warnings.append(message)

    async def report_progress(self, progress, total=None, message=None):
        self.progress.append((progress, total))


def test_context_param_not_in_input_schema():
    """The injected ctx must not appear as a tool argument (SDK-003)."""
    import asyncio
    import json

    from bag_health_mcp.server import mcp

    async def _get():
        return {t.name: t for t in await mcp.list_tools()}

    tools = asyncio.get_event_loop().run_until_complete(_get()) if False else None
    # Use a fresh loop run to avoid interfering with pytest-asyncio.
    tools = asyncio.run(_get())
    for name in ("bag_get_disease_data", "bag_get_canton_situation"):
        blob = json.dumps(tools[name].inputSchema)
        assert '"ctx"' not in blob
        assert "Context" not in blob


@pytest.mark.asyncio
@respx.mock
async def test_disease_data_reports_progress_and_logs():
    """bag_get_disease_data emits info logs and 0→1→2 progress via Context."""
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(200, json=MOCK_DATA))

    ctx = _RecordingCtx()
    result = await bag_get_disease_data(
        DiseaseDataInput(series_id="influenza/cases/incValue/iso_week", canton="ZH"),
        ctx=ctx,
    )
    assert result.topic == "influenza"
    assert len(ctx.infos) >= 2
    assert ctx.progress[0] == (0, 2)
    assert ctx.progress[-1] == (2, 2)


@pytest.mark.asyncio
@respx.mock
async def test_canton_situation_reports_progress_per_series():
    """The fan-out reports progress as each series completes (SDK-003)."""
    respx.get(url__regex=r".*/details$").mock(
        return_value=httpx.Response(200, json=MOCK_DETAILS)
    )
    respx.post(url__regex=r"/api/v1/data/[^/]+/[^/]+/[^/]+/[^/]+$").mock(
        return_value=httpx.Response(200, json=MOCK_DATA)
    )

    ctx = _RecordingCtx()
    result = await bag_get_canton_situation(canton="ZH", ctx=ctx)
    n = len(result.diseases)
    assert n >= 5
    # One progress event per completed series, ending at n/n.
    assert ctx.progress[-1] == (n, n)
    assert len(ctx.progress) == n


@pytest.mark.asyncio
@respx.mock
async def test_canton_situation_warns_client_on_degraded_series():
    """A blocked/failed series is reported to the client via ctx.warning, and
    still degrades closed without leaking (SDK-003 + OBS-002)."""
    respx.get(url__regex=r".*/details$").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/x"})
    )
    respx.get("http://169.254.169.254/x").mock(
        return_value=httpx.Response(200, text="LEAK-MUST-NOT-APPEAR")
    )

    ctx = _RecordingCtx()
    result = await bag_get_canton_situation(canton="ZH", ctx=ctx)
    assert len(ctx.warnings) == len(result.diseases)
    assert all(isinstance(v, CantonDiseaseStatus) and v.status == "unavailable"
               for v in result.diseases.values())
    assert "LEAK-MUST-NOT-APPEAR" not in repr(result)
    assert all("LEAK-MUST-NOT-APPEAR" not in w for w in ctx.warnings)


@pytest.mark.asyncio
@respx.mock
async def test_tools_still_work_without_context():
    """ctx is optional: a direct call with no Context behaves as before."""
    respx.get(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week/details"
    ).mock(return_value=httpx.Response(200, json=MOCK_DETAILS))
    respx.post(
        f"{IDD_BASE}/api/v1/data/influenza/cases/incValue/iso_week"
    ).mock(return_value=httpx.Response(200, json=MOCK_DATA))

    result = await bag_get_disease_data(
        DiseaseDataInput(series_id="influenza/cases/incValue/iso_week", canton="ZH")
    )
    assert result.topic == "influenza"
