"""Tests for the multi-source health-indicator tools.

Covers the happy path, the Obsan cut selection (which variant of an indicator
exists, read off its page), Versorgungsatlas graceful degradation, the
retry-with-backoff path (503 then 200) and a clean network-error failure.
Run unit tests: pytest -m "not live"; the live checks: pytest -m live.
"""

import re

import httpx
import pytest
import respx
from fixture_data import declared_variants, fixture_json, fixture_text, internal_id
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
OBSAN_PAGE_KG_ONLY = fixture_text("obsan_page_cantonal_only.html")
OBSAN_PAGE_NO_VARIANTS = fixture_text("obsan_page_no_variants.html")
OBSAN_API = fixture_json("obsan_api_g.json")
OBSAN_API_GUM = fixture_json("obsan_api_gum.json")
OBSAN_API_KG = fixture_json("obsan_api_kg.json")
OBSAN_API_KG_ONLY = fixture_json("obsan_api_kg_only.json")
OBSAN_API_KG_SPARSE = fixture_json("obsan_api_kg_sparse.json")
CENSUS = fixture_json("obsan_variant_census.json")

# Aus der Fixture gelesen, nicht danebengeschrieben: eine Kopie waere eine
# zweite Stelle, an der die Angabe falsch sein kann.
INTERNAL_NO_VARIANTS = internal_id("obsan_page_no_variants.html")
VARIANTS = declared_variants("obsan_page.html")
VARIANTS_KG_ONLY = declared_variants("obsan_page_cantonal_only.html")
INDICATOR_ID = "obsan/suizid-und-suizidhilfe"
KG_ONLY_ID = "obsan/lebenserwartung"
NO_VARIANTS_ID = "obsan/osteoporose"

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
    respx.get(VARIANTS["g"]).mock(return_value=httpx.Response(200, json=OBSAN_API))
    year_from = 2020
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(
            source="obsan",
            indicator_id=INDICATOR_ID,
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
    assert out.region == "CH"
    assert out.variant == "g"
    assert out.variants_available == sorted(VARIANTS)
    assert out.provenance.data_version == OBSAN_API["version"]


# --- Welche Schnitte es gibt, sagt die Seite -------------------------------
#
# Die Erhebung dazu ist selbst aufgezeichnet (obsan_variant_census.json), also
# datiert und nachmessbar — nicht eine Zahl in einer Commit-Nachricht, die
# niemand mehr pruefen kann.


def test_the_two_suffixes_the_client_used_to_ask_for_are_the_rare_ones():
    """Die Begruendung des ganzen Umbaus, als Zusicherung.

    Der Client fragte `/g/json` und, bei 404, `/gum/json` — sonst nichts. Am
    2026-08-08 ueber 60 sprachneutrale Indikatoren gemessen: 49 haben weder das
    eine noch das andere, und nur 8 haben ueberhaupt keine Variante. Die
    Differenz — 41 Indikatoren — sind Reihen, die es gibt und die der Server
    fuer nicht vorhanden erklaerte. Nicht der Katalog war zu grosszuegig, die
    Frage war falsch.
    """
    counts = CENSUS["variant_counts"]
    assert CENSUS["without_g_or_gum"] > CENSUS["sampled"] / 2, (
        "Wenn die Mehrheit `g` oder `gum` haette, waere die alte Abfrage in "
        "Ordnung gewesen — dann diesen Umbau und seine Begruendung pruefen."
    )
    unreachable_before = CENSUS["without_g_or_gum"] - CENSUS["without_any_variant"]
    assert unreachable_before > 0
    assert counts["kg"] > counts.get("g", 0), (
        "Der kantonale Schnitt ist der haeufigste, der nationale der seltenste "
        "— und der Client fragte nur den seltenen."
    )


@pytest.mark.asyncio
@respx.mock
async def test_obsan_series_reads_the_cantonal_cut_the_page_declares():
    """Ein Indikator, den die alte Abfrage fuer leer hielt.

    `obsan/lebenserwartung` deklariert genau eine Variante: `kg`. Auf `/g/json`
    und `/gum/json` — die beiden einzigen, die der Client fragte — antwortet die
    Quelle 404. Er hat trotzdem eine vollstaendige Reihe, kantonal, seit 1998.

    Die Gegenprobe steckt in dem, was hier NICHT gemockt ist: respx laesst keinen
    ungemockten Aufruf durch, also faellt dieser Test, sobald wieder jemand
    `/g/json` fragt. Der Weg ueber die Seite ist damit nicht nur gangbar, sondern
    der einzige, den dieser Test bestehen laesst.
    """
    assert set(VARIANTS_KG_ONLY) == {"kg"}, (
        "Die Fixture deklariert nicht mehr nur `kg` — dann belegt sie den Fund "
        "nicht mehr. Neu aufzeichnen mit `python scripts/record_fixtures.py`."
    )
    respx.get(f"{OBSAN}/de/indicator/{KG_ONLY_ID}").mock(
        return_value=httpx.Response(200, text=OBSAN_PAGE_KG_ONLY)
    )
    respx.get(VARIANTS_KG_ONLY["kg"]).mock(return_value=httpx.Response(200, json=OBSAN_API_KG_ONLY))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id=KG_ONLY_ID, region="ZH", language="de")
    )
    zurich = [p for p in OBSAN_API_KG_ONLY["data"] if p["kanton_nr"] == 1]
    assert zurich, "Fixture ohne Zuercher Zeilen — Auswahlregel pruefen"
    assert out.values_available is True
    assert out.total_points == len(zurich)
    assert out.region == "ZH"
    assert out.variant == "kg"
    assert all(p.canton == "ZH" for p in out.points)
    # Die Legende kommt aus dem Payload, nicht aus einer Tabelle im Server:
    # dieser Indikator ist nach «bei der Geburt» / «bei 65 Jahren» geteilt, und
    # ohne diese Angabe mischt eine Reihe zwei verschiedene Groessen.
    assert "category_id" in out.dimensions
    for code, name in OBSAN_API_KG_ONLY["category_id"]["codes"].items():
        assert f"{code} = {name['de']}" in out.dimensions["category_id"]


@pytest.mark.asyncio
@respx.mock
async def test_obsan_national_total_comes_from_the_cantonal_cut():
    """Ohne Region ist die Schweiz gemeint — und `kg` fuehrt sie als Nummer 0."""
    respx.get(f"{OBSAN}/de/indicator/{KG_ONLY_ID}").mock(
        return_value=httpx.Response(200, text=OBSAN_PAGE_KG_ONLY)
    )
    respx.get(VARIANTS_KG_ONLY["kg"]).mock(return_value=httpx.Response(200, json=OBSAN_API_KG_ONLY))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id=KG_ONLY_ID, language="de")
    )
    national = [p for p in OBSAN_API_KG_ONLY["data"] if p["kanton_nr"] == 0]
    assert national, "Fixture ohne Schweiz-Zeilen — Auswahlregel pruefen"
    assert out.region == "CH"
    assert out.total_points == len(national)
    assert {p.canton_nr for p in out.points} == {0}


@pytest.mark.asyncio
@respx.mock
async def test_obsan_pooled_year_spans_keep_their_label():
    """'1998-02' ist die Spanne 1998-2002, nicht der Februar 1998.

    Diese Form kommt in `g` und `gum` nicht vor, also hat sie bis hierher kein
    Payload getroffen. In ein `int`-Feld gelegt wirft sie einen
    Validierungsfehler mitten im Werkzeugaufruf.
    """
    pooled = [p for p in OBSAN_API_KG["data"] if isinstance(p["year"], str)]
    assert pooled, "Fixture ohne gepoolte Spanne — dann prueft dieser Test nichts"
    respx.get(f"{OBSAN}/de/indicator/{INDICATOR_ID}").mock(
        return_value=httpx.Response(200, text=OBSAN_PAGE)
    )
    respx.get(VARIANTS["kg"]).mock(return_value=httpx.Response(200, json=OBSAN_API_KG))
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(
            source="obsan", indicator_id=INDICATOR_ID, region="ZH", language="de"
        )
    )
    assert out.variant == "kg"
    assert out.points, "keine Punkte — dann sagt der Rest nichts"
    first = next(p for p in OBSAN_API_KG["data"] if p["kanton_nr"] == 1)
    got = out.points[0]
    assert got.period == first["year"]
    assert got.year == int(str(first["year"])[:4])
    assert "period" in out.dimensions


@pytest.mark.asyncio
@respx.mock
async def test_obsan_year_filter_reads_the_start_of_a_pooled_span():
    respx.get(f"{OBSAN}/de/indicator/{INDICATOR_ID}").mock(
        return_value=httpx.Response(200, text=OBSAN_PAGE)
    )
    respx.get(VARIANTS["kg"]).mock(return_value=httpx.Response(200, json=OBSAN_API_KG))
    year_from = 2015
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(
            source="obsan",
            indicator_id=INDICATOR_ID,
            region="ZH",
            year_from=year_from,
            language="de",
        )
    )
    expected = [
        p
        for p in OBSAN_API_KG["data"]
        if p["kanton_nr"] == 1 and int(str(p["year"])[:4]) >= year_from
    ]
    assert expected, "Zuschnitt ohne Zeilen ab 2015 — Auswahlregel pruefen"
    assert out.total_points == len(expected)


@pytest.mark.asyncio
@respx.mock
async def test_obsan_names_a_canton_the_indicator_is_not_published_for():
    """Nicht jeder Indikator erscheint fuer jeden Kanton — und das ist sagbar.

    Der interne Bezeichner wird hier absichtlich direkt uebergeben: dann gibt es
    keine Seite zu lesen, und der Client muss die Varianten abklopfen. Auch
    dieser Weg soll die Luecke benennen statt eine leere Reihe zu liefern.
    """
    published = {p["kanton_nr"] for p in OBSAN_API_KG_SPARSE["data"]}
    missing = sorted(set(range(1, 27)) - published)
    assert missing, "Fixture ohne fehlenden Kanton — dann prueft dieser Test nichts"
    absent = hi._BFS_BY_NUMBER[missing[0]]

    respx.get(f"{OBSAN}/api/_003/kg/json").mock(
        return_value=httpx.Response(200, json=OBSAN_API_KG_SPARSE)
    )
    with pytest.raises(ToolError) as exc:
        await srv.bag_get_indicator_series(
            GetIndicatorSeriesInput(
                source="obsan", indicator_id="_003", region=absent, language="de"
            )
        )
    message = str(exc.value)
    assert absent in message and "not published" in message
    # Und die Antwort sagt, welche es gibt — sonst ist der Fehler eine Sackgasse.
    assert hi._BFS_BY_NUMBER[sorted(published - {0})[0]] in message


@pytest.mark.asyncio
@respx.mock
async def test_obsan_says_so_when_the_indicator_publishes_nothing():
    """Der Fall, in dem «keine Reihe» wirklich stimmt — 8 von 60.

    Er soll benannt werden und nicht als leeres Ergebnis erscheinen: eine leere
    Reihe liest sich wie eine Aussage ueber die Welt und ist eine ueber den
    Client.
    """
    assert not declared_variants("obsan_page_no_variants.html"), (
        "Die Fixture deklariert jetzt Varianten — neu aufzeichnen."
    )
    respx.get(f"{OBSAN}/de/indicator/{NO_VARIANTS_ID}").mock(
        return_value=httpx.Response(200, text=OBSAN_PAGE_NO_VARIANTS)
    )
    with pytest.raises(ToolError) as exc:
        await srv.bag_get_indicator_series(
            GetIndicatorSeriesInput(source="obsan", indicator_id=NO_VARIANTS_ID, language="de")
        )
    assert "no time series" in str(exc.value)
    assert INTERNAL_NO_VARIANTS in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_obsan_distribution_cut_is_named_as_one():
    """`gum` ist eine Verteilung in %, keine schlechtere Rate.

    Frueher rutschte sie stillschweigend als Ersatz fuer `g` durch. Sie traegt
    eine andere Einheit und eine eigene Dimension (`segment_id`), und beides
    steht jetzt in der Antwort.
    """
    respx.get(f"{OBSAN}/api/_500/g/json").mock(return_value=httpx.Response(404))
    respx.get(f"{OBSAN}/api/_500/kg/json").mock(return_value=httpx.Response(404))
    respx.get(f"{OBSAN}/api/_500/ag/json").mock(return_value=httpx.Response(404))
    respx.get(f"{OBSAN}/api/_500/sd/json").mock(return_value=httpx.Response(404))
    respx.get(f"{OBSAN}/api/_500/gum/json").mock(
        return_value=httpx.Response(200, json=OBSAN_API_GUM)
    )
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id="_500", language="de")
    )
    assert out.total_points == len(OBSAN_API_GUM["data"])
    assert out.variant == "gum"
    assert "distribution" in out.interpretation
    assert out.unit == OBSAN_API_GUM["value"]["de"]
    assert [p.segment_id for p in out.points] == [p["segment_id"] for p in OBSAN_API_GUM["data"]]


def test_canton_numbering_is_checked_against_the_source():
    """Die BFS-Nummern werden am Payload geprueft, nicht geglaubt.

    Ein falsch zugeordneter Kanton ist die unangenehmste Form von falsch: die
    Antwort ist vollstaendig, plausibel und handelt von woanders. Sie faellt
    niemandem auf.
    """
    payload = OBSAN_API_KG_ONLY
    for code, (number, name) in hi._BFS_CANTONS.items():
        upstream = payload["kanton_nr"]["codes"].get(str(number))
        if upstream is None:
            continue
        assert upstream["de"] == name, f"{code}: {name!r} hier, {upstream['de']!r} dort"
        assert hi._canton_number(code, payload) == number

    tampered = {"kanton_nr": {"codes": {"1": {"de": "Genf"}}}}
    with pytest.raises(ToolError) as exc:
        hi._canton_number("ZH", tampered)
    assert "Refusing to guess" in str(exc.value)


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


# --- Live ------------------------------------------------------------------
#
# Eine Fixture belegt die *Form* einer Antwort zu einem Datum. Dass die Quelle
# ihre Schnitte weiterhin so ausweist — und dass dieser Indikator sie weiterhin
# hat — belegt nur ein Lauf gegen den echten Host. `pytest -m live`.


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_obsan_publishes_more_cuts_than_g_and_gum():
    """Die Annahme, auf der der ganze Umbau steht, gegen die Quelle gehalten."""
    out = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id=KG_ONLY_ID, language="de")
    )
    assert out.values_available is True
    assert out.total_points > 0
    assert "g" not in out.variants_available and "gum" not in out.variants_available, (
        "Die Quelle liefert fuer diesen Indikator jetzt `g` oder `gum` — dann "
        "war die alte Abfrage fuer ihn richtig, und die Fixture-Auswahl gehoert "
        "geprueft (scripts/record_fixtures.py)."
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_obsan_cantonal_series_differs_from_the_national_one():
    """Kantonal heisst kantonal — sonst waere der Zuschnitt folgenlos."""
    zh = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id=KG_ONLY_ID, region="ZH", language="de")
    )
    ch = await srv.bag_get_indicator_series(
        GetIndicatorSeriesInput(source="obsan", indicator_id=KG_ONLY_ID, language="de")
    )
    assert zh.region == "ZH" and ch.region == "CH"
    assert zh.variant == ch.variant == "kg"
    assert zh.points and ch.points
    assert [p.value for p in zh.points] != [p.value for p in ch.points]
