"""Tests for the multi-source health-indicator tools.

Covers the happy path, the Obsan /g -> /gum fallback, Versorgungsatlas graceful
degradation, the retry-with-backoff path (503 then 200) and a clean network-error
failure. Run unit tests: pytest -m "not live".
"""

import re

import httpx
import pytest
import respx
from fixture_data import fixture_json, fixture_text, internal_id
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


# --- fixtures ---------------------------------------------------------------
#
# Aufgezeichnet statt ausgedacht. Herkunft, Datum, Auswahlregel und SHA-256 je
# Datei stehen in tests/fixtures/PROVENANCE.md; neu aufzeichnen mit
# `python scripts/record_fixtures.py`.
#
# Was der Wechsel zutage gefoerdert hat, steht im CHANGELOG. Kurz: Die alte
# SITEMAP-Fixture bestand aus `/de/indicator/...`-URLs — die Quelle liefert
# davon **keine einzige**. Deutsch kommt sprachneutral, ohne Sprachsegment.
# Der Zweig, ueber den damit jedes deutsche Ergebnis laeuft, war ungetestet.

SITEMAP = fixture_text("obsan_sitemap.xml")
OBSAN_PAGE = fixture_text("obsan_page.html")
OBSAN_PAGE_NO_SERIES = fixture_text("obsan_page_no_series.html")
OBSAN_API = fixture_json("obsan_api_g.json")
OBSAN_API_GUM = fixture_json("obsan_api_gum.json")

# Aus der Fixture gelesen, nicht danebengeschrieben: eine Kopie waere eine
# zweite Stelle, an der die Angabe falsch sein kann.
INTERNAL = internal_id("obsan_page.html")
INTERNAL_NO_SERIES = internal_id("obsan_page_no_series.html")
INDICATOR_ID = "obsan/suizid-und-suizidhilfe"
NO_SERIES_ID = "obsan/lebenserwartung"

VA_SEARCH = fixture_json("va_search_de.json")
VA_AD = fixture_json("va_ad.json")
VA_RZ = fixture_json("va_rz.json")
VA_AG = fixture_json("va_ag.json")


# --- Obsan / suchtschweiz --------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_obsan_search_happy():
    respx.get(f"{OBSAN}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    out = await srv.bag_search_health_indicators(
        SearchHealthIndicatorsInput(source="obsan", topic="suizid", language="de")
    )
    # Der Treffer kommt aus einem sprachneutralen Sitemap-Eintrag — der Form,
    # in der die Quelle Deutsch tatsaechlich ausliefert.
    assert out.total_matches == 1
    assert out.indicators[0].indicator_id == INDICATOR_ID
    # safeguard label present in every response
    assert "Aggregierte Bevölkerungsstatistik" in out.aggregate_statistics_notice


@pytest.mark.asyncio
@respx.mock
async def test_suchtschweiz_scoped_to_monam_with_attribution():
    respx.get(f"{OBSAN}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    out = await srv.bag_search_health_indicators(
        SearchHealthIndicatorsInput(source="suchtschweiz", topic="", language="de")
    )
    # Die obsan/*-Eintraege fallen raus, die monam/*-Eintraege bleiben.
    # Die Nicht-Leerheit ist Teil der Zusicherung: `all(...)` ueber einer leeren
    # Liste ist wahr, und ein Test, der so besteht, prueft nichts.
    assert out.indicators, "keine monam-Indikatoren — die Zusicherung waere leer wahr"
    assert all(i.indicator_id.startswith("monam/") for i in out.indicators)
    assert "HBSC" in out.provenance.attribution


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_resolves_path_and_filters_years():
    respx.get(f"{OBSAN}/de/indicator/{INDICATOR_ID}").mock(
        return_value=httpx.Response(200, text=OBSAN_PAGE)
    )
    respx.get(f"{OBSAN}/api/{INTERNAL}/g/json").mock(
        return_value=httpx.Response(200, json=OBSAN_API)
    )
    year_from = 2020
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(
            source="obsan",
            indicator_id=INDICATOR_ID,
            region="ZH",
            year_from=year_from,
            language="de",
        )
    )
    assert out.title.startswith("Suizid")
    # Erwartung aus der Fixture abgeleitet, nicht hingeschrieben: eine feste
    # Zahl waere beim naechsten Aufzeichnen falsch, ohne dass sich etwas
    # Gepruefte geaendert haette.
    expected = [p for p in OBSAN_API["data"] if p["year"] >= year_from]
    assert out.total_points == len(expected)
    assert min(p.year for p in out.points) >= year_from
    assert out.points[0].value_lower_ci == expected[0]["value_lci"]
    # canton requested but indicator is national -> explanatory note
    assert out.region == "CH"
    assert "ZH" in out.region_note and "cantonally representative" in out.region_note
    assert out.provenance.data_version == OBSAN_API["version"]


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_falls_back_to_gum_variant():
    respx.get(f"{OBSAN}/api/_500/g/json").mock(return_value=httpx.Response(404))
    respx.get(f"{OBSAN}/api/_500/gum/json").mock(
        return_value=httpx.Response(200, json=OBSAN_API_GUM)
    )
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id="_500", language="de")
    )
    assert out.total_points == len(OBSAN_API_GUM["data"])


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_retries_then_succeeds():
    # first call 503 (transient), retry returns 200
    respx.get(f"{OBSAN}/api/_777/g/json").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=OBSAN_API)]
    )
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id="_777", language="de")
    )
    assert out.total_points == len(OBSAN_API["data"])


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
    # Erwartung aus der Fixture abgeleitet. Die Quelle fuehrt drei Aspekte von
    # `_003` und zwei von `_006` — die handgeschriebene Fixture kannte je einen,
    # also hat nie ein Test mehrere Aspekte desselben Indikators gesehen.
    expected = {
        f"{e['id']}/{e['aspect']}"
        for e in VA_SEARCH
        if "impfung" in (e["topic"] + e["title"]).lower()
    }
    assert expected, "Fixture enthaelt kein Impfungs-Thema — Auswahlregel pruefen"
    assert out.total_matches == len(expected)
    assert {i.indicator_id for i in out.indicators} == expected
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
    zh = sorted((r for r in VA_RZ if r.get("region_name") == "ZH"), key=lambda r: r["year"])
    ch = {r["year"]: r["var1"] for r in VA_RZ if r.get("region_name") == "CH"}
    assert zh and ch, "Fixture ohne ZH- oder CH-Zeilen — Auswahlregel pruefen"

    assert out.values_available is True
    assert out.region == "ZH"
    assert out.total_points == len(zh)  # ZH only (CH filtered out)
    assert out.points[0].year == zh[0]["year"] and out.points[0].value == zh[0]["var1"]
    assert out.points[0].value_lower_ci == zh[0]["lci1"]
    assert out.title == "MMR-Impfungen"
    assert out.unit and "costs" in out.unit
    # canton-vs-Switzerland comparison from the latest shared year
    latest = zh[-1]
    assert f"ZH={latest['var1']}" in out.region_note
    assert f"CH={ch[latest['year']]}" in out.region_note
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
    ch = sorted((r for r in VA_RZ if r.get("region_name") == "CH"), key=lambda r: r["year"])
    assert out.region == "CH"
    assert out.region_note is None
    assert [p.value for p in out.points] == [r["var1"] for r in ch]


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
    # Aus der Fixture abgeleitet: die Altersreihe traegt eine Zeile je
    # Altersklasse und Jahr, nicht die zwei der erfundenen Vorgaengerin.
    assert out.total_points == len(VA_AG)
    assert out.points[0].category_id == VA_AG[0]["ageclass"]  # age class


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


@pytest.mark.asyncio
@respx.mock
async def test_german_results_ride_on_the_language_neutral_catalogue_entries():
    """Deutsch kommt ohne Sprachsegment — und genau das war ungetestet.

    Gemessen am 2026-08-07 fuehrt die Obsan-Sitemap 285 `fr`, 223 `it`, 41 `en`
    und 285 sprachneutrale Eintraege — und **keine einzige** `/de/`-URL. Die
    neutralen tragen die deutschen Slugs. Jedes deutsche Suchergebnis laeuft
    damit ueber den `lang == ""`-Zweig von `_obsan_catalogue`.

    Die alte, handgeschriebene Fixture bestand ausschliesslich aus
    `/de/indicator/...`-URLs: eine Form, die die Quelle nicht produziert. Sie
    hat den einzigen Zweig, der in der Wirklichkeit traegt, nie beruehrt.

    Diese Zusicherung haelt beides fest — dass die aufgezeichnete Fixture die
    Form der Quelle behaelt, und dass die Suche darauf antwortet. Ohne den
    ersten Teil bestuende sie auch wieder mit `/de/`-URLs, und dann waere sie
    genau der Test, den sie ersetzt.
    """
    assert "/de/indicator/" not in SITEMAP, (
        "Die Fixture traegt wieder /de/-URLs — die Quelle liefert davon keine. "
        "Neu aufzeichnen mit `python scripts/record_fixtures.py`."
    )
    assert re.search(r"admin\.ch/indicator/", SITEMAP), (
        "Kein sprachneutraler Eintrag in der Fixture — dann prueft dieser Test "
        "den Zweig nicht, um den es geht"
    )

    respx.get(f"{OBSAN}/sitemap.xml").mock(return_value=httpx.Response(200, text=SITEMAP))
    out = await srv.bag_search_health_indicators(
        SearchHealthIndicatorsInput(source="obsan", topic="suizid", language="de")
    )
    assert out.total_matches == 1
    assert out.indicators[0].indicator_id == INDICATOR_ID
