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
    IDD_BASE,
    DataSetsInput,
    DataVersionInput,
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
    assert result["total_topics"] > 0
    cats = result["categories"]
    assert "respiratory" in cats
    assert "influenza" in cats["respiratory"]


@pytest.mark.asyncio
@respx.mock
async def test_bag_list_series_found():
    respx.get(f"{IDD_BASE}/api/v1/data/sets").mock(
        return_value=httpx.Response(200, json=MOCK_SETS)
    )
    result = await bag_list_series(DataSetsInput(topic="influenza"))
    assert result["topic"] == "influenza"
    assert result["total_series"] == 3
    assert "cases" in result["chapters"]


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
    assert result["series_id"] == "influenza/cases/incValue/iso_week"
    assert "ZH" in result["cantons"]
    assert result["source_date"] == "2026-03-24"


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
    assert result["topic"] == "influenza"
    assert result["source_date"] == "2026-03-24"
    # ZH has 3 data points
    zh_results = [r for r in result["results"] if isinstance(r, dict) and r.get("canton") == "ZH"]
    assert len(zh_results) > 0
    assert zh_results[0]["data_points"] == 3


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
    assert result["version"] == "20260325"
    assert result["date"] == "2026-03-25"


@pytest.mark.asyncio
@respx.mock
async def test_bag_list_export_files():
    respx.get(f"{IDD_BASE}/api/v1/export/latest/files").mock(
        return_value=httpx.Response(200, json=["INFLUENZA_oblig", "COVID19_oblig"])
    )
    result = await bag_list_export_files(ExportFilesInput())
    assert result["total_files"] == 2
    assert "INFLUENZA_oblig" in result["files"]


# ---------------------------------------------------------------------------
# Live tests (require network, skip in CI)
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_list_diseases():
    result = await bag_list_diseases(ListDiseasesInput())
    assert result["total_topics"] >= 40
    assert "influenza" in result["categories"]["respiratory"]


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_data_version():
    result = await bag_get_data_version(DataVersionInput())
    assert len(result["version"]) == 8
    assert result["version"].startswith("2026") or result["version"].startswith("2025")


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
    assert "error" not in result
    assert result["topic"] == "influenza"
    assert len(result["results"]) > 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_canton_situation():
    result = await bag_get_canton_situation(canton="ZH")
    assert result["canton"] == "ZH"
    assert "influenza" in result["diseases"]


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
        assert r1["total_topics"] > 0
        assert r2["topic"] == "influenza"
