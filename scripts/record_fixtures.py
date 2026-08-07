#!/usr/bin/env python3
"""Records the unit-test fixtures from the live upstream sources.

    python scripts/record_fixtures.py

WHY THIS EXISTS. A hand-written mock encodes its author's assumption and can
therefore never refute it: production code and fixture come from the same head,
the same hour, the same reading of the docs. Where both are wrong, both are
wrong together, and the suite stays green forever.

This repository had no protection against that at all: every payload was a
literal in the test module, none of them recorded, and the one ``@pytest.mark.live``
test is skipped -- ``pytest -m live`` collects zero tests here. So nothing in
this repo has ever compared its assumptions against the real hosts.

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
# Sprachneutral (== Deutsch) UND mit Datenserie. Beides ist noetig und
# keineswegs selbstverstaendlich: In einer Stichprobe von 12 neutralen
# Indikatoren am 2026-08-07 hatten nur 3 ueberhaupt eine Serie -- 9 gaben auf
# `/g/json` UND `/gum/json` 404. Der Katalog listet also weit mehr, als das
# Serien-Tool ausliefern kann. `NO_SERIES_INDICATOR` haelt genau diesen
# Mehrheitsfall als Fixture fest; vorher testete ihn nichts.
INDICATOR = "obsan/suizid-und-suizidhilfe"
NO_SERIES_INDICATOR = "obsan/lebenserwartung"
VA_ITEM = ("_003", "b")

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
    "/indicator/obsan/suizid-und-suizidhilfe",  # neutral == Deutsch, mit Serie
    "/indicator/obsan/lebenserwartung",  # neutral, OHNE Serie
    # Ein `monam`-Eintrag ist Pflicht und kein Beiwerk: Der Test zur
    # Sucht-Schweiz-Eingrenzung assertiert `all(id.startswith("monam/") …)`.
    # Ueber einer leeren Liste ist das wahr — ohne diesen Eintrag bestuende er
    # leer und pruefte nichts (Regel 5: ein Test, der die Bedingung herstellt,
    # unter der der Fehler nicht auftreten kann).
    "/indicator/monam/episodisch-risikoreicher-alkoholkonsum-alter-15",
    "/fr/indicator/obsan/esperance-de-vie",  # dieselbe Sache auf fr
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
        text, rule = _excerpt_sitemap(r.text)
        write("obsan_sitemap.xml", text, f"{OBSAN}/sitemap.xml", rule)

        # 2) The indicator page, and the internal id the server reads from it.
        page_url = f"{OBSAN}/de/indicator/{INDICATOR}"
        r = c.get(page_url)
        r.raise_for_status()
        match = re.search(r"__NEXT_DATA__[^>]*>(.*?)</script>", r.text, re.S)
        if not match:
            raise SystemExit(f"{page_url}: no __NEXT_DATA__ block -- page rebuilt?")
        internal = json.loads(match.group(1))["props"]["pageProps"]["id"]
        # Only the script block is kept: the surrounding 31 KB of markup is
        # noise the server never reads, and it would churn the diff on every
        # unrelated redesign.
        write(
            "obsan_page.html",
            '<html><body><script id="__NEXT_DATA__" type="application/json">'
            + match.group(1)
            + "</script></body></html>\n",
            page_url,
            "nur der __NEXT_DATA__-Block; das umgebende Markup liest der Server nie",
        )

        # 3) The two data endpoints -- /g is the primary, /gum the fallback.
        for suffix in ("g", "gum"):
            url = f"{OBSAN}/api/{internal}/{suffix}/json"
            r = c.get(url)
            r.raise_for_status()
            write(
                f"obsan_api_{suffix}.json",
                json.dumps(r.json(), ensure_ascii=False, indent=2) + "\n",
                url,
                f"vollstaendig, Indikator {INDICATOR} (intern {internal})",
            )

        # 3b) The majority case: an indicator whose series does not exist.
        page_url = f"{OBSAN}/de/indicator/{NO_SERIES_INDICATOR}"
        r = c.get(page_url)
        r.raise_for_status()
        m2 = re.search(r"__NEXT_DATA__[^>]*>(.*?)</script>", r.text, re.S)
        if not m2:
            raise SystemExit(f"{page_url}: no __NEXT_DATA__ block")
        internal_none = json.loads(m2.group(1))["props"]["pageProps"]["id"]
        write(
            "obsan_page_no_series.html",
            '<html><body><script id="__NEXT_DATA__" type="application/json">'
            + m2.group(1)
            + "</script></body></html>\n",
            page_url,
            f"nur der __NEXT_DATA__-Block; Indikator ohne Serie (intern "
            f"{internal_none}, /g und /gum je 404)",
        )
        for suffix in ("g", "gum"):
            probe = c.get(f"{OBSAN}/api/{internal_none}/{suffix}/json")
            if probe.status_code != 404:
                raise SystemExit(
                    f"{NO_SERIES_INDICATOR}: /{suffix}/json antwortet "
                    f"{probe.status_code}, nicht 404 — die Quelle hat "
                    "nachgeliefert, Fixture-Auswahl pruefen"
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
