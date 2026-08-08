#!/usr/bin/env python3
"""Records the unit-test fixtures from the live upstream sources.

    python scripts/record_fixtures.py

WHY THIS EXISTS. A hand-written mock encodes its author's assumption and can
therefore never refute it: production code and fixture come from the same head,
the same hour, the same reading of the docs. Where both are wrong, both are
wrong together, and the suite stays green forever.

This repository had no protection against that at all: every payload was a
literal in the test module, none of them recorded. (A note from 2026-08-07 said
``pytest -m live`` collects zero tests here. That was wrong, and worth saying so:
``test_server.py`` calls ``importorskip("opentelemetry.sdk.trace")`` at module
level, so a machine without the OTel extras skips the whole file, live tests
included. CI installs them and collects six.)

The written fixtures are **excerpts**, never full dumps: the Obsan sitemap is
148 KB and the Versorgungsatlas catalogue 710 KB. Each selection rule is small,
deterministic and recorded in ``tests/fixtures/PROVENANCE.md`` next to the
retrieval date -- without the date, "recorded" becomes indistinguishable from
"invented" after two years, because the file looks the same either way.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

OBSAN = "https://ind.obsan.admin.ch"
VA = "https://www.versorgungsatlas.ch"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# The indicator the tests exercise. Its internal id is resolved from the live
# page rather than hard-coded: the page carries it in __NEXT_DATA__, and that
# is exactly the lookup the server performs.
#
# Drei Indikatoren, drei Faelle -- und die Faelle sind der eigentliche Fund:
#
#   INDICATOR             hat `g`, den nationalen Schnitt (3 von 60 haben ihn)
#   CANTONAL_INDICATOR    hat NUR `kg`, den kantonalen. Am 2026-08-07 stand er
#                         hier als NO_SERIES_INDICATOR -- weil `/g` und `/gum`
#                         404 gaben und der Client nur diese beiden fragte.
#                         Er hat 4374 Datenpunkte. Die Aussage «9 von 12
#                         Indikatoren haben keine Serie» war meine eigene, und
#                         sie war falsch: sie haben keine, die der Client fragt.
#   NO_VARIANT_INDICATOR  hat wirklich keine Variante. Diesen Fall gibt es --
#                         8 von 60 -- und er ist der einzige, in dem «keine
#                         Serie» stimmt.
INDICATOR = "obsan/suizid-und-suizidhilfe"
CANTONAL_INDICATOR = "obsan/lebenserwartung"
NO_VARIANT_INDICATOR = "obsan/osteoporose"
# Ein zweiter kantonaler Schnitt, und zwar ein LUECKENHAFTER: nicht jeder
# Indikator wird fuer jeden Kanton publiziert. Ohne diese Fixture liesse sich
# der Zweig «dieser Kanton kommt hier nicht vor» nur gegen einen erfundenen
# Payload pruefen -- also gegen dieselbe Annahme, die er absichern soll.
SPARSE_CANTONAL_INDICATOR = "obsan/starke-koerperliche-beschwerden"
VA_ITEM = ("_003", "b")

# Umfang der Variantenerhebung (siehe `_census`). Die ersten N sprachneutralen
# Eintraege in Sitemap-Reihenfolge -- ein Zuschnitt, dem man sonst zu Recht
# misstraut. Hier traegt er, weil die Sitemap nach Themenpfad sortiert ist und
# nicht danach, welche Schnitte ein Indikator veroeffentlicht; und weil die
# Erhebung abbricht, wenn ihr genau die auffaelligen Faelle fehlen.
CENSUS_SAMPLE = 60

# Kept from the sitemap -- and this list is a finding in itself.
#
# The previous hand-written fixture contained four `/de/indicator/...` URLs.
# The live sitemap contains **none**: measured 2026-08-07 it lists 285 `fr`,
# 223 `it`, 41 `en` and 285 language-NEUTRAL entries -- and the neutral ones
# carry the German slugs (`.../indicator/obsan/lebenserwartung`). German is
# served as the canonical form, without a language segment.
#
# So the old fixture exercised a shape the source never produces and never
# exercised the one it always produces: every German result rides on the
# `lang == ""` branch of `_obsan_catalogue`, which no unit test touched.
SITEMAP_KEEP = (
    "/indicator/obsan/suizid-und-suizidhilfe",  # neutral == Deutsch, mit `g`
    "/indicator/obsan/lebenserwartung",  # neutral, nur `kg` (kantonal)
    "/indicator/obsan/osteoporose",  # neutral, gar keine Variante
    # Ein `monam`-Eintrag ist Pflicht und kein Beiwerk: Der Test zur
    # Sucht-Schweiz-Eingrenzung assertiert `all(id.startswith("monam/") …)`.
    # Ueber einer leeren Liste ist das wahr — ohne diesen Eintrag bestuende er
    # leer und pruefte nichts (Regel 5: ein Test, der die Bedingung herstellt,
    # unter der der Fehler nicht auftreten kann).
    "/indicator/monam/episodisch-risikoreicher-alkoholkonsum-alter-15",
    "/fr/indicator/obsan/esperance-de-vie",  # dieselbe Sache auf fr
)


_NEXT_DATA_RE = re.compile(r"__NEXT_DATA__[^>]*>(.*?)</script>", re.S)
_NEUTRAL_IND_RE = re.compile(r"https?://[^/]+/indicator/([a-z0-9_]+)/([a-z0-9-]+)$", re.I)


def _page_props(client: httpx.Client, path: str) -> tuple[str, dict, str]:
    """``(internal_id, declared_variants, next_data_json)`` for an indicator page."""
    url = f"{OBSAN}/de/indicator/{path}"
    r = client.get(url)
    r.raise_for_status()
    m = _NEXT_DATA_RE.search(r.text)
    if not m:
        raise SystemExit(f"{url}: no __NEXT_DATA__ block -- page rebuilt?")
    props = json.loads(m.group(1))["props"]["pageProps"]
    internal = props["id"]
    od3 = ((props.get("jsonLDs") or {}).get("links") or {}).get("od3") or {}
    return internal, (od3.get(internal) or {}), m.group(1)


def _census(client: httpx.Client, xml: str) -> dict:
    """Count which API variants the catalogue's indicators actually publish.

    This exists because the number it produces is the whole finding, and a
    number in a commit message ages into an assertion nobody can check. Here it
    is a recording like any other: dated, re-runnable, with its selection rule
    written down. Re-run it and the claim either survives or it does not.

    The client used to ask for `/g/json` and, on 404, `/gum/json` -- and for
    most indicators the source publishes neither, while publishing plenty else.
    """
    neutral: list[tuple[str, str]] = []
    for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml):
        m = _NEUTRAL_IND_RE.match(loc.strip())
        if m:
            neutral.append((m.group(1), m.group(2)))

    counts: dict[str, int] = {}
    without_g_or_gum = 0
    without_any = 0
    with_kg = 0
    sample = neutral[:CENSUS_SAMPLE]
    for topic, slug in sample:
        _internal, variants, _raw = _page_props(client, f"{topic}/{slug}")
        for suffix in variants:
            counts[suffix] = counts.get(suffix, 0) + 1
        if not variants:
            without_any += 1
        if not ({"g", "gum"} & set(variants)):
            without_g_or_gum += 1
        if "kg" in variants:
            with_kg += 1
        print(f"    {topic}/{slug:<52} {sorted(variants)}")

    # Eine Erhebung, in der die auffaelligen Faelle fehlen, belegt nichts: sie
    # koennte auch aus einer Welt stammen, in der es sie nicht gibt. Dann lieber
    # abbrechen als eine Zahl schreiben, die niemanden mehr stutzig macht.
    if not without_any:
        raise SystemExit(
            "Erhebung ohne einen einzigen variantenlosen Indikator -- entweder "
            "hat die Quelle nachgeliefert oder der Zuschnitt trifft ihn nicht "
            "mehr. CENSUS_SAMPLE pruefen."
        )
    if not without_g_or_gum:
        raise SystemExit(
            "Erhebung, in der jeder Indikator `g` oder `gum` hat -- dann waere "
            "die alte Abfrage richtig gewesen. Zuschnitt und Quelle pruefen."
        )
    return {
        "sitemap_language_neutral_indicators": len(neutral),
        "sampled": len(sample),
        "sample_rule": (
            f"die ersten {CENSUS_SAMPLE} sprachneutralen Indikator-URLs in Sitemap-Reihenfolge"
        ),
        "variant_counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "without_g_or_gum": without_g_or_gum,
        "without_any_variant": without_any,
        "with_cantonal_cut": with_kg,
    }


def _excerpt_cantonal(rows: list[dict]) -> tuple[list[dict], str]:
    """Shorten a ``kg`` payload without losing what makes it a ``kg`` payload.

    Two things have to survive, and «die ersten N Zeilen» keeps neither: the
    full time series for at least one canton next to the national total (a
    canton-vs-Switzerland comparison needs both, over the same years), and the
    complete canton list (so «this canton is not published here» stays a
    question the fixture can answer). Hence: everything for BFS 0 and 1, plus
    the two most recent years for every canton.
    """
    years = sorted({row.get("year") for row in rows if row.get("year") is not None})
    recent = set(years[-2:])
    kept = [row for row in rows if row.get("kanton_nr") in (0, 1) or row.get("year") in recent]
    return kept, (
        f"alle Jahrgaenge fuer Schweiz (0) und Zuerich (1) plus die zwei "
        f"juengsten Jahrgaenge ({sorted(recent)}) fuer jeden Kanton"
    )


def _excerpt_sitemap(xml: str) -> tuple[str, str]:
    """Keep the envelope and the <url> blocks the tests rely on."""
    blocks = re.findall(r"<url>.*?</url>", xml, re.S)
    kept = [b for b in blocks if any(k in b for k in SITEMAP_KEEP)]
    if len(kept) < len(SITEMAP_KEEP):
        raise SystemExit(
            f"sitemap: only {len(kept)} of {len(SITEMAP_KEEP)} indicator URLs "
            "still present -- the catalogue moved, adjust SITEMAP_KEEP"
        )
    # The namespace on <urlset> is kept verbatim. The server parses with a
    # regex over the raw text, so it does not matter today -- but a fixture
    # that quietly drops it would hide the day someone switches to an XML
    # parser and the namespace starts to matter.
    head = xml[: xml.index("<url>")]
    return head + "\n".join(kept) + "\n</urlset>\n", (
        f"XML-Huelle unveraendert plus die {len(kept)} <url>-Bloecke der "
        f"getesteten Indikatoren (von {len(blocks)} insgesamt)"
    )


def record() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries: list[dict] = []

    def write(name: str, text: str, url: str, rule: str) -> None:
        (FIXTURES / name).write_text(text, encoding="utf-8")
        entries.append(
            {
                "name": name,
                "url": url,
                "rule": rule,
                "bytes": len(text.encode("utf-8")),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
        print(f"ok  {name:<26} {len(text.encode('utf-8')):>7} B")

    with httpx.Client(timeout=90.0, follow_redirects=True) as c:
        # 1) Obsan catalogue.
        r = c.get(f"{OBSAN}/sitemap.xml")
        r.raise_for_status()
        r_sitemap_text = r.text
        text, rule = _excerpt_sitemap(r_sitemap_text)
        write("obsan_sitemap.xml", text, f"{OBSAN}/sitemap.xml", rule)

        # 1b) Which cuts the catalogue actually publishes. The whole finding.
        print("  Variantenerhebung ...")
        census = _census(c, r_sitemap_text)
        write(
            "obsan_variant_census.json",
            json.dumps(census, ensure_ascii=False, indent=2) + "\n",
            f"{OBSAN}/de/indicator/<topic>/<slug> ({census['sampled']} Seiten)",
            census["sample_rule"] + "; gezaehlt werden die in `jsonLDs.links.od3` "
            "deklarierten API-Varianten je Indikator",
        )

        def page(path: str, name: str, note: str) -> tuple[str, dict]:
            """Record an indicator page and return ``(internal_id, variants)``."""
            internal, variants, raw = _page_props(c, path)
            # Only the script block is kept: the surrounding 31 KB of markup is
            # noise the server never reads, and it would churn the diff on every
            # unrelated redesign.
            write(
                name,
                '<html><body><script id="__NEXT_DATA__" type="application/json">'
                + raw
                + "</script></body></html>\n",
                f"{OBSAN}/de/indicator/{path}",
                f"nur der __NEXT_DATA__-Block; {note} (intern {internal}, "
                f"Varianten {sorted(variants) or 'keine'})",
            )
            return internal, variants

        # 2) An indicator that does have the national `g` cut -- 3 of 60 do.
        internal, variants = page(INDICATOR, "obsan_page.html", "nationaler Schnitt vorhanden")
        if "g" not in variants:
            raise SystemExit(
                f"{INDICATOR}: kein `g` mehr deklariert (nur {sorted(variants)}). "
                "Dann testet die Fixture den nationalen Zweig nicht mehr -- "
                "INDICATOR auf einen Indikator mit `g` umstellen."
            )

        # 3) Its data endpoints. Recorded from the URLs the PAGE declares, not
        #    from a suffix guessed here -- that guess was the bug.
        for suffix in ("g", "gum"):
            url = variants[suffix]["apiUrl"]
            r = c.get(url)
            r.raise_for_status()
            write(
                f"obsan_api_{suffix}.json",
                json.dumps(r.json(), ensure_ascii=False, indent=2) + "\n",
                url,
                f"vollstaendig, Indikator {INDICATOR} (intern {internal}), "
                f"Variante `{suffix}` wie von der Seite deklariert",
            )

        # 3a) Und sein kantonaler Schnitt -- derselbe Indikator, andere Zahlen.
        #     Er traegt ausserdem die gepoolten Jahresspannen ("1998-02" ist
        #     1998-2002, kein Februar): eine Form, die kein Fixture je enthielt,
        #     weil sie in `g` und `gum` nicht vorkommt. In ein int-Feld gelegt
        #     wirft sie einen Validierungsfehler, den niemand kommen sieht.
        url = variants["kg"]["apiUrl"]
        r = c.get(url)
        r.raise_for_status()
        payload_pooled = r.json()
        total_pooled = len(payload_pooled.get("data", []))
        pooled = [row for row in payload_pooled["data"] if isinstance(row.get("year"), str)]
        if not pooled:
            raise SystemExit(
                f"{INDICATOR}: keine gepoolte Jahresspanne mehr in `kg` — dann "
                "prueft die Fixture den `period`-Zweig nicht mehr."
            )
        payload_pooled["data"], pooled_rule = _excerpt_cantonal(payload_pooled["data"])
        write(
            "obsan_api_kg.json",
            json.dumps(payload_pooled, ensure_ascii=False, indent=2) + "\n",
            url,
            f"Indikator {INDICATOR} (intern {internal}) — {pooled_rule}, "
            f"{len(payload_pooled['data'])} von {total_pooled} Zeilen; die "
            "Jahresangaben sind gepoolte Spannen ('1998-02' = 1998-2002)",
        )

        # 3b) Der Mehrheitsfall: kein `g`, kein `gum` -- und trotzdem Daten.
        internal_kg, variants_kg = page(
            CANTONAL_INDICATOR,
            "obsan_page_cantonal_only.html",
            "weder `g` noch `gum`, dafuer der kantonale Schnitt",
        )
        if set(variants_kg) != {"kg"}:
            raise SystemExit(
                f"{CANTONAL_INDICATOR}: Varianten sind {sorted(variants_kg)}, "
                "erwartet genau {'kg'}. Genau darum geht diese Fixture -- ein "
                "Indikator, den die alte Abfrage fuer leer hielt. Neuen suchen."
            )
        for suffix in ("g", "gum"):
            probe = c.get(f"{OBSAN}/api/{internal_kg}/{suffix}/json")
            if probe.status_code != 404:
                raise SystemExit(
                    f"{CANTONAL_INDICATOR}: /{suffix}/json antwortet "
                    f"{probe.status_code}, nicht 404 — dann belegt die Fixture "
                    "den Fund nicht mehr, Auswahl pruefen"
                )
        url = variants_kg["kg"]["apiUrl"]
        r = c.get(url)
        r.raise_for_status()
        payload_kg = r.json()
        total_kg = len(payload_kg.get("data", []))
        payload_kg["data"], kg_rule = _excerpt_cantonal(payload_kg["data"])
        write(
            "obsan_api_kg_only.json",
            json.dumps(payload_kg, ensure_ascii=False, indent=2) + "\n",
            url,
            f"Indikator {CANTONAL_INDICATOR} (intern {internal_kg}) — {kg_rule}, "
            f"{len(payload_kg['data'])} von {total_kg} Zeilen. Diese {total_kg} "
            "Punkte lagen hinter einer Adresse, die der Client nie abgefragt hat",
        )

        # 3b') Derselbe Schnitt, aber luekenhaft besetzt.
        internal_sparse, variants_sparse, _ = _page_props(c, SPARSE_CANTONAL_INDICATOR)
        url = variants_sparse["kg"]["apiUrl"]
        r = c.get(url)
        r.raise_for_status()
        payload_sparse = r.json()
        present = {row.get("kanton_nr") for row in payload_sparse.get("data", [])}
        missing = sorted(set(range(1, 27)) - present)
        if not missing:
            raise SystemExit(
                f"{SPARSE_CANTONAL_INDICATOR}: inzwischen fuer alle 26 Kantone "
                "publiziert. Dann belegt die Fixture den Luecken-Fall nicht mehr "
                "— einen anderen luekenhaften Indikator waehlen."
            )
        total_sparse = len(payload_sparse.get("data", []))
        newest = max(row["year"] for row in payload_sparse["data"] if row.get("year"))
        payload_sparse["data"] = [r_ for r_ in payload_sparse["data"] if r_.get("year") == newest]
        write(
            "obsan_api_kg_sparse.json",
            json.dumps(payload_sparse, ensure_ascii=False, indent=2) + "\n",
            url,
            f"Indikator {SPARSE_CANTONAL_INDICATOR} (intern {internal_sparse}) — "
            f"der juengste Jahrgang ({newest}) fuer jeden publizierten Kanton, "
            f"{len(payload_sparse['data'])} von {total_sparse} Zeilen. Der "
            "Indikator wird nicht fuer alle Kantone publiziert; es fehlen die "
            f"BFS-Nummern {missing}, und genau das haelt diese Fixture fest",
        )

        # 3c) Und der Fall, in dem «keine Serie» wirklich stimmt: 8 von 60.
        _internal_none, variants_none = page(
            NO_VARIANT_INDICATOR,
            "obsan_page_no_variants.html",
            "gar keine Variante deklariert",
        )
        if variants_none:
            raise SystemExit(
                f"{NO_VARIANT_INDICATOR}: deklariert jetzt {sorted(variants_none)}. "
                "Die Quelle hat nachgeliefert -- einen anderen variantenlosen "
                "Indikator aus obsan_variant_census.json waehlen."
            )

        # 4) Versorgungsatlas catalogue -- 285 entries upstream, excerpt here.
        url = f"{VA}/search/search_de.json"
        r = c.get(url)
        r.raise_for_status()
        catalogue = r.json()
        item_id, aspect = VA_ITEM
        # Alle Aspekte von `item_id` — die Quelle fuehrt davon drei (a/b/c),
        # die handgeschriebene Fixture kannte nur einen. Dazu die ersten zwei
        # Eintraege mit ANDERER id, sonst trennt die Themenfilterung nichts und
        # ein Suchtest bestuende, weil ohnehin alles passt.
        others = [e for e in catalogue if e.get("id") != item_id][:2]
        kept = [e for e in catalogue if e.get("id") == item_id] + others
        seen, unique = set(), []
        for e in kept:
            key = (e.get("id"), e.get("aspect"))
            if key not in seen:
                seen.add(key)
                unique.append(e)
        write(
            "va_search_de.json",
            json.dumps(unique, ensure_ascii=False, indent=2) + "\n",
            url,
            f"alle Aspekte von {item_id} plus die ersten zwei fremden Eintraege "
            f"({len(unique)} von {len(catalogue)})",
        )

        # 5) The three data files behind one catalogue entry.
        for suffix in ("ad", "rz", "ag"):
            url = f"{VA}/data/{item_id}{aspect}_{suffix}.json"
            r = c.get(url)
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, list):
                # Regional and age series run to tens of thousands of rows.
                # Two years is enough to exercise the trend path and keeps the
                # file readable -- which a fixture has to be.
                years = sorted({row.get("year") for row in payload if row.get("year")})
                keep_years = set(years[-2:])
                excerpt = [r_ for r_ in payload if r_.get("year") in keep_years]
                rule = (
                    f"die letzten zwei Jahrgaenge ({sorted(keep_years)}) — "
                    f"{len(excerpt)} von {len(payload)} Zeilen"
                )
            else:
                excerpt, rule = payload, "vollstaendig"
            write(
                f"va_{suffix}.json",
                json.dumps(excerpt, ensure_ascii=False, indent=2) + "\n",
                url,
                rule,
            )

    _write_provenance(recorded_at, entries)
    print(f"\nPROVENANCE.md written, recording date {recorded_at}")
    return 0


def _write_provenance(recorded_at: str, entries: list[dict]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}** von den Live-Quellen "
        f"`{OBSAN}` und `{VA}`, unveraendert bis auf die je Datei "
        "dokumentierte Auswahl.",
        "",
        "Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht",
        "mehr zu unterscheiden — die Datei sieht gleich aus, und niemand weiss,",
        "ob sie den Stand von gestern zeigt oder den von vor drei",
        "Schema-Wechseln. Das Datum macht diesen Abstand zu einer lesbaren Zahl.",
        "",
        "**Es sind Ausschnitte, keine Vollabzuege.** Die Auswahlregel steht je",
        "Datei dabei. Eine Fixture belegt damit die *Form* der Antwort und",
        "einen datierten Ausschnitt ihres Inhalts — nicht den Bestand. Aussagen",
        "ueber Vollstaendigkeit gehoeren in Live-Tests.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}`",
            "",
            f"- **Quelle:** `{e['url']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Auswahl:** {e['rule']}",
            f"- **Groesse:** {e['bytes']} B",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(record())
    except httpx.HTTPError as exc:  # a failed recording must not write half a set
        print(f"ERROR: upstream unreachable: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
