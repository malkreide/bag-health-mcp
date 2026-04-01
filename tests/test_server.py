"""
Tests for bag-health-mcp server.
Run unit tests: pytest -m "not live"
Run live tests: pytest -m live --timeout=30
"""

import httpx
import pytest
import respx

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
    result = await bag_list_series(DataSetsInput(topic="unknown_disease"))
    assert "error" in result


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
    result = await bag_get_series_details(
        SeriesDetailsInput(series_id="influenza/cases")  # only 2 parts
    )
    assert "error" in result


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
