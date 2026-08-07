# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-07** von den Live-Quellen `https://ind.obsan.admin.ch` und `https://www.versorgungsatlas.ch`, unveraendert bis auf die je Datei dokumentierte Auswahl.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden — die Datei sieht gleich aus, und niemand weiss,
ob sie den Stand von gestern zeigt oder den von vor drei
Schema-Wechseln. Das Datum macht diesen Abstand zu einer lesbaren Zahl.

**Es sind Ausschnitte, keine Vollabzuege.** Die Auswahlregel steht je
Datei dabei. Eine Fixture belegt damit die *Form* der Antwort und
einen datierten Ausschnitt ihres Inhalts — nicht den Bestand. Aussagen
ueber Vollstaendigkeit gehoeren in Live-Tests.

## `obsan_sitemap.xml`

- **Quelle:** `https://ind.obsan.admin.ch/sitemap.xml`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** XML-Huelle unveraendert plus die 4 <url>-Bloecke der getesteten Indikatoren (von 994 insgesamt)
- **Groesse:** 647 B
- **SHA-256:** `a459bbd01af0e489e96be8344c3fde1c4279a032c45f2c672c31cfafa700d950`

## `obsan_page.html`

- **Quelle:** `https://ind.obsan.admin.ch/de/indicator/obsan/suizid-und-suizidhilfe`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** nur der __NEXT_DATA__-Block; das umgebende Markup liest der Server nie
- **Groesse:** 9124 B
- **SHA-256:** `2c4e0057e8fa54d828a90383571a1391ee0be6d81bbe8a9eaa37c23e868c5856`

## `obsan_api_g.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_010/g/json`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** vollstaendig, Indikator obsan/suizid-und-suizidhilfe (intern _010)
- **Groesse:** 39608 B
- **SHA-256:** `7fdc0a1842a53bee821d01d8602b38723e025f16ab67ee45a976d203c05bf115`

## `obsan_api_gum.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_010/gum/json`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** vollstaendig, Indikator obsan/suizid-und-suizidhilfe (intern _010)
- **Groesse:** 109017 B
- **SHA-256:** `88823ee583daa0a24f17906bb736f1b0d1ef521f619bc4d2e113da4dbfa00d6b`

## `obsan_page_no_series.html`

- **Quelle:** `https://ind.obsan.admin.ch/de/indicator/obsan/lebenserwartung`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** nur der __NEXT_DATA__-Block; Indikator ohne Serie (intern _001, /g und /gum je 404)
- **Groesse:** 4848 B
- **SHA-256:** `ca5429ac4d788f2f55314424da6790f8cfd85a522d6caa59b633072c3cac0372`

## `va_search_de.json`

- **Quelle:** `https://www.versorgungsatlas.ch/search/search_de.json`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** alle Aspekte von _003 plus die ersten zwei fremden Eintraege (5 von 285)
- **Groesse:** 14567 B
- **SHA-256:** `a84dec373d9a3bc911b22f649747f1a53d1d44121c4b6a68103f561e7ea5edb2`

## `va_ad.json`

- **Quelle:** `https://www.versorgungsatlas.ch/data/_003b_ad.json`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** vollstaendig
- **Groesse:** 17041 B
- **SHA-256:** `f83d27ec162f2edd0fe9a4ac9c2b96961b670ebe1a01120fe9acacb85a1f57a1`

## `va_rz.json`

- **Quelle:** `https://www.versorgungsatlas.ch/data/_003b_rz.json`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** die letzten zwei Jahrgaenge ([2023, 2024]) — 54 von 270 Zeilen
- **Groesse:** 15696 B
- **SHA-256:** `bb819f416d35e250d6551612b0e8bc81e71fe47889155f5f38e4d4f731cbbb99`

## `va_ag.json`

- **Quelle:** `https://www.versorgungsatlas.ch/data/_003b_ag.json`
- **Aufgezeichnet:** 2026-08-07
- **Auswahl:** die letzten zwei Jahrgaenge ([2023, 2024]) — 18 von 90 Zeilen
- **Groesse:** 3083 B
- **SHA-256:** `bc718cba39615dd271ca312ccb124ec803d732295359a541c21724fcdd52271d`
