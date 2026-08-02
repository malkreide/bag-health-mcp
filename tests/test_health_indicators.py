"""Tests for the multi-source health-indicator tools.

Covers the happy path, the Obsan /g -> /gum fallback, Versorgungsatlas graceful
degradation, the retry-with-backoff path (503 then 200) and a clean network-error
failure. Run unit tests: pytest -m "not live".
"""

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ToolError

import bag_health_mcp.server as srv
from bag_health_mcp import _health_indicators as hi
from bag_health_mcp._models import (
    GetIndicatorSeriesInput,
    SearchHealthIndicatorsInput,
)

OBSAN = srv.OBSAN_BASE
VA = srv.VERSORGUNGSATLAS_BASE


@pytest.fixture(autouse=True)
def _fast_and_fresh(monkeypatch):
    """No real backoff sleeps, and a clean catalogue cache per test."""
    monkeypatch.setattr(srv, "RETRY_BACKOFF_BASE", 0.0)
    hi._clear_cache()
    yield
    hi._clear_cache()


# --- fixtures --------------------------------------------------------------

SITEMAP = f"""<?xml version="1.0"?>
<urlset>
  <url><loc>{OBSAN}</loc></url>
  <url><loc>{OBSAN}/de/indicator/monam/alkoholkonsum-alter-11-15</loc></url>
  <url><loc>{OBSAN}/de/indicator/monam/kosten-des-gesundheitswesens</loc></url>
  <url><loc>{OBSAN}/de/indicator/avos/urologie</loc></url>
  <url><loc>{OBSAN}/fr/indicator/monam/consommation-d-alcool-age-11-15</loc></url>
</urlset>"""


def _page(internal_id: str) -> str:
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        f'{{"props":{{"pageProps":{{"id":"{internal_id}"}}}}}}'
        "</script></body></html>"
    )


OBSAN_API_330 = {
    "title": {"de": "Prävalenz des Alkoholkonsums", "en": "Alcohol prevalence"},
    "source": {"de": "Sucht Schweiz – HBSC"},
    "value": {"de": "Anteil in %"},
    "version": "20260615",
    "last_updated_at": "2023-03-27",
    "data": [
        {"year": 2006, "value": 31.0, "value_lci": 29.1, "value_uci": 33.0, "n": 9700, "sex_id": 0},
        {"year": 2010, "value": 29.8, "value_lci": 27.6, "value_uci": 31.5, "n": 9700, "sex_id": 0},
        {"year": 2022, "value": 23.4, "value_lci": 21.0, "value_uci": 25.0, "n": 9500, "sex_id": 0},
    ],
}

VA_SEARCH = [
    {
        "id": "_003",
        "aspect": "b",
        "title": "MMR-Impfungen",
        "aspect_title": "bei Kindern bis 15 Jahre",
        "topic": "Impfungen",
        "description": "Die MMR-Impfung …",
        "search_terms": "",
        "group_terms": "Pädiatrie",
    },
    {
        "id": "_010",
        "aspect": "a",
        "title": "Diabetes",
        "aspect_title": "Behandlung",
        "topic": "Chronische Krankheiten",
        "description": "…",
        "search_terms": "",
        "group_terms": "",
    },
]

# Versorgungsatlas data files: _ad (definition), _rz (regional incl. CH), _ag (age).
VA_AD = {
    "var1_label": "std_costs",
    "datasource": "Tarifpool",
    "denominator": "Wohnbevölkerung",
    "population": {"de": "Wohnbevölkerung bis 15 Jahre"},
    "version": 20220829,
    "date_export": "05.11.2025",
}
VA_RZ = [
    {
        "year": 2020,
        "region_name": "ZH",
        "var1": 5.0,
        "lci1": 4.9,
        "uci1": 5.1,
        "sex": 0,
        "rr": 1.05,
    },
    {"year": 2020, "region_name": "CH", "var1": 4.8, "lci1": 4.7, "uci1": 4.9, "sex": 0, "rr": 1.0},
    {
        "year": 2021,
        "region_name": "ZH",
        "var1": 5.2,
        "lci1": 5.1,
        "uci1": 5.3,
        "sex": 0,
        "rr": 1.06,
    },
    {"year": 2021, "region_name": "CH", "var1": 4.9, "lci1": 4.8, "uci1": 5.0, "sex": 0, "rr": 1.0},
]
VA_AG = [
    {"year": 2021, "ageclass": 1, "sex": 0, "var1": 3.1, "lci1": 3.0, "uci1": 3.2, "age": "0 - 5"},
    {
        "year": 2021,
        "ageclass": 3,
        "sex": 0,
        "var1": 0.5,
        "lci1": 0.4,
        "uci1": 0.6,
        "age": "11 - 15",
    },
]


# --- Obsan / suchtschweiz --------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_obsan_search_happy():
    respx.get(f"{OBSAN}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    out = await srv.bag_search_health_indicators(
        SearchHealthIndicatorsInput(source="obsan", topic="alkohol", language="de")
    )
    assert out.total_matches == 1
    assert out.indicators[0].indicator_id == "monam/alkoholkonsum-alter-11-15"
    # safeguard label present in every response
    assert "Aggregierte Bevölkerungsstatistik" in out.aggregate_statistics_notice


@pytest.mark.asyncio
@respx.mock
async def test_suchtschweiz_scoped_to_monam_with_attribution():
    respx.get(f"{OBSAN}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    out = await srv.bag_search_health_indicators(
        SearchHealthIndicatorsInput(source="suchtschweiz", topic="", language="de")
    )
    # avos/urologie is filtered out (not monam); only monam indicators remain
    assert all(i.indicator_id.startswith("monam/") for i in out.indicators)
    assert "HBSC" in out.provenance.attribution


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_resolves_path_and_filters_years():
    respx.get(f"{OBSAN}/de/indicator/monam/alkoholkonsum-alter-11-15").mock(
        return_value=httpx.Response(200, text=_page("_330"))
    )
    respx.get(f"{OBSAN}/api/_330/g/json").mock(return_value=httpx.Response(200, json=OBSAN_API_330))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(
            source="suchtschweiz",
            indicator_id="monam/alkoholkonsum-alter-11-15",
            region="ZH",
            year_from=2010,
            language="de",
        )
    )
    assert out.title.startswith("Prävalenz")
    assert out.total_points == 2  # 2006 dropped by year_from=2010
    assert out.points[0].year == 2010
    assert out.points[0].value_lower_ci == 27.6
    # canton requested but indicator is national -> explanatory note
    assert out.region == "CH"
    assert "ZH" in out.region_note and "cantonally representative" in out.region_note
    assert "HBSC" in out.provenance.attribution
    assert out.provenance.data_version == "20260615"


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_falls_back_to_gum_variant():
    respx.get(f"{OBSAN}/api/_500/g/json").mock(return_value=httpx.Response(404))
    respx.get(f"{OBSAN}/api/_500/gum/json").mock(
        return_value=httpx.Response(200, json=OBSAN_API_330)
    )
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id="_500", language="de")
    )
    assert out.total_points == 3


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_retries_then_succeeds():
    # first call 503 (transient), retry returns 200
    respx.get(f"{OBSAN}/api/_777/g/json").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=OBSAN_API_330)]
    )
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id="_777", language="de")
    )
    assert out.total_points == 3


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_network_error_is_clean_toolerror():
    respx.get(f"{OBSAN}/api/_888/g/json").mock(side_effect=httpx.ConnectError("boom"))
    respx.get(f"{OBSAN}/api/_888/gum/json").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(ToolError) as exc:
        await srv.bag_get_indicator_series(
            GetIndicatorSeriesInput(source="obsan", indicator_id="_888", language="de")
        )
    # user-facing message is safe (no raw exception text)
    assert "unreachable" in str(exc.value).lower()
    assert "boom" not in str(exc.value)


# --- Versorgungsatlas ------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_va_search_happy():
    respx.get(f"{VA}/search/search_de.json").mock(return_value=httpx.Response(200, json=VA_SEARCH))
    out = await srv.bag_search_health_indicators(
        SearchHealthIndicatorsInput(source="versorgungsatlas", topic="impfung", language="de")
    )
    assert out.total_matches == 1
    assert out.indicators[0].indicator_id == "_003/b"
    assert out.indicators[0].regional_dimension.startswith("canton")


@pytest.mark.asyncio
@respx.mock
async def test_va_series_cantonal_with_comparison():
    respx.get(f"{VA}/search/search_de.json").mock(return_value=httpx.Response(200, json=VA_SEARCH))
    respx.get(f"{VA}/data/_003b_ad.json").mock(return_value=httpx.Response(200, json=VA_AD))
    respx.get(f"{VA}/data/_003b_rz.json").mock(return_value=httpx.Response(200, json=VA_RZ))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(
            source="versorgungsatlas",
            indicator_id="_003/b",
            region="ZH",
            year_from=2020,
            language="de",
        )
    )
    assert out.values_available is True
    assert out.region == "ZH"
    assert out.total_points == 2  # ZH only (CH filtered out)
    assert out.points[0].year == 2020 and out.points[0].value == 5.0
    assert out.points[0].value_lower_ci == 4.9
    assert out.title == "MMR-Impfungen"
    assert out.unit and "costs" in out.unit
    # canton-vs-Switzerland comparison from the latest shared year (2021)
    assert "ZH=5.2" in out.region_note and "CH=4.9" in out.region_note
    assert "CH" in out.dimensions["regions_available"]


@pytest.mark.asyncio
@respx.mock
async def test_va_series_national_ch():
    respx.get(f"{VA}/search/search_de.json").mock(return_value=httpx.Response(200, json=VA_SEARCH))
    respx.get(f"{VA}/data/_003b_ad.json").mock(return_value=httpx.Response(200, json=VA_AD))
    respx.get(f"{VA}/data/_003b_rz.json").mock(return_value=httpx.Response(200, json=VA_RZ))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="versorgungsatlas", indicator_id="_003/b", language="de")
    )
    assert out.region == "CH"
    assert out.region_note is None
    assert [p.value for p in out.points] == [4.8, 4.9]


@pytest.mark.asyncio
@respx.mock
async def test_va_series_falls_back_to_age_when_no_regional():
    respx.get(f"{VA}/search/search_de.json").mock(return_value=httpx.Response(200, json=VA_SEARCH))
    respx.get(f"{VA}/data/_003b_ad.json").mock(return_value=httpx.Response(200, json=VA_AD))
    respx.get(f"{VA}/data/_003b_rz.json").mock(return_value=httpx.Response(404))
    respx.get(f"{VA}/data/_003b_ag.json").mock(return_value=httpx.Response(200, json=VA_AG))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="versorgungsatlas", indicator_id="_003/b", language="de")
    )
    assert out.values_available is True
    assert out.region == "CH"
    assert out.total_points == 2
    assert out.points[0].category_id == 1  # age class


@pytest.mark.asyncio
@respx.mock
async def test_va_series_unknown_region_fails_cleanly():
    respx.get(f"{VA}/search/search_de.json").mock(return_value=httpx.Response(200, json=VA_SEARCH))
    respx.get(f"{VA}/data/_003b_ad.json").mock(return_value=httpx.Response(200, json=VA_AD))
    respx.get(f"{VA}/data/_003b_rz.json").mock(return_value=httpx.Response(200, json=VA_RZ))
    with pytest.raises(ToolError) as exc:
        await srv.bag_get_indicator_series(
            GetIndicatorSeriesInput(source="versorgungsatlas", indicator_id="_003/b", region="XX")
        )
    assert "not available" in str(exc.value).lower()
