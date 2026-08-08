# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-08** von den Live-Quellen `https://ind.obsan.admin.ch` und `https://www.versorgungsatlas.ch`, unveraendert bis auf die je Datei dokumentierte Auswahl.

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
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** XML-Huelle unveraendert plus die 6 <url>-Bloecke der getesteten Indikatoren (von 994 insgesamt)
- **Groesse:** 888 B
- **SHA-256:** `9444178aa1fa31329bcbd91e9960548347c27abfb9ae04f992669976757b9910`

## `obsan_variant_census.json`

- **Quelle:** `https://ind.obsan.admin.ch/de/indicator/<topic>/<slug> (60 Seiten)`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** die ersten 60 sprachneutralen Indikator-URLs in Sitemap-Reihenfolge; gezaehlt werden die in `jsonLDs.links.od3` deklarierten API-Varianten je Indikator
- **Groesse:** 357 B
- **SHA-256:** `43a61bcc4af3961d02f3f97010048172225762d5a3e7ce48ac614b121c38a872`

## `obsan_page.html`

- **Quelle:** `https://ind.obsan.admin.ch/de/indicator/obsan/suizid-und-suizidhilfe`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** nur der __NEXT_DATA__-Block; nationaler Schnitt vorhanden (intern _010, Varianten ['ag', 'g', 'gum', 'kg'])
- **Groesse:** 9124 B
- **SHA-256:** `139774fe601e081b3b3fa19a7e8ae584e332bb2bfa27e582bc10ef6f6c1e26fa`

## `obsan_api_g.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_010/g/json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** vollstaendig, Indikator obsan/suizid-und-suizidhilfe (intern _010), Variante `g` wie von der Seite deklariert
- **Groesse:** 39608 B
- **SHA-256:** `4c3c8069f4ee70bf594e3c78d4e3ece03271ba73782adefbbeda2a65fe723796`

## `obsan_api_gum.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_010/gum/json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** vollstaendig, Indikator obsan/suizid-und-suizidhilfe (intern _010), Variante `gum` wie von der Seite deklariert
- **Groesse:** 109017 B
- **SHA-256:** `69383e723e1b0fba62c33b1f80346260312ae5464d9dae2f9c6300fd07343fe8`

## `obsan_api_kg.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_010/kg/json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** Indikator obsan/suizid-und-suizidhilfe (intern _010) — alle Jahrgaenge fuer Schweiz (0) und Zuerich (1) plus die zwei juengsten Jahrgaenge (['2019-23', '2020-24']) fuer jeden Kanton, 569 von 3283 Zeilen; die Jahresangaben sind gepoolte Spannen ('1998-02' = 1998-2002)
- **Groesse:** 158495 B
- **SHA-256:** `b53932c115297be02ff1d5dc498425c3e00bf1e356f28174f31f1302b8974053`

## `obsan_page_cantonal_only.html`

- **Quelle:** `https://ind.obsan.admin.ch/de/indicator/obsan/lebenserwartung`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** nur der __NEXT_DATA__-Block; weder `g` noch `gum`, dafuer der kantonale Schnitt (intern _001, Varianten ['kg'])
- **Groesse:** 4848 B
- **SHA-256:** `1c584bb1e60c1a2c9bdbcd3e4453e89e2912b026882b94f36726db1854ed1a35`

## `obsan_api_kg_only.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_001/kg/json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** Indikator obsan/lebenserwartung (intern _001) — alle Jahrgaenge fuer Schweiz (0) und Zuerich (1) plus die zwei juengsten Jahrgaenge ([2023, 2024]) fuer jeden Kanton, 624 von 4374 Zeilen. Diese 4374 Punkte lagen hinter einer Adresse, die der Client nie abgefragt hat
- **Groesse:** 136645 B
- **SHA-256:** `129f46be3ebcd28414f428f7a0695a7b3ca1101c451db0e62f41deb97834438e`

## `obsan_api_kg_sparse.json`

- **Quelle:** `https://ind.obsan.admin.ch/api/_003/kg/json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** Indikator obsan/starke-koerperliche-beschwerden (intern _003) — der juengste Jahrgang (2022) fuer jeden publizierten Kanton, 57 von 315 Zeilen. Der Indikator wird nicht fuer alle Kantone publiziert; es fehlen die BFS-Nummern [8, 14, 16], und genau das haelt diese Fixture fest
- **Groesse:** 28177 B
- **SHA-256:** `71dd853892612b465a26d14f4f2e6f0fcb126d28f53a8ab7da88abafb1ccf46a`

## `obsan_page_no_variants.html`

- **Quelle:** `https://ind.obsan.admin.ch/de/indicator/obsan/osteoporose`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** nur der __NEXT_DATA__-Block; gar keine Variante deklariert (intern _069, Varianten keine)
- **Groesse:** 1125 B
- **SHA-256:** `5c88003e8d3bf45d975a5017f8a6734c15ef9b5e763aa68c66cc7efebfc3ae83`

## `va_search_de.json`

- **Quelle:** `https://www.versorgungsatlas.ch/search/search_de.json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** alle Aspekte von _003 plus die ersten zwei fremden Eintraege (5 von 285)
- **Groesse:** 14567 B
- **SHA-256:** `a84dec373d9a3bc911b22f649747f1a53d1d44121c4b6a68103f561e7ea5edb2`

## `va_ad.json`

- **Quelle:** `https://www.versorgungsatlas.ch/data/_003b_ad.json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** vollstaendig
- **Groesse:** 17041 B
- **SHA-256:** `f83d27ec162f2edd0fe9a4ac9c2b96961b670ebe1a01120fe9acacb85a1f57a1`

## `va_rz.json`

- **Quelle:** `https://www.versorgungsatlas.ch/data/_003b_rz.json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** die letzten zwei Jahrgaenge ([2023, 2024]) — 54 von 270 Zeilen
- **Groesse:** 15696 B
- **SHA-256:** `bb819f416d35e250d6551612b0e8bc81e71fe47889155f5f38e4d4f731cbbb99`

## `va_ag.json`

- **Quelle:** `https://www.versorgungsatlas.ch/data/_003b_ag.json`
- **Aufgezeichnet:** 2026-08-08
- **Auswahl:** die letzten zwei Jahrgaenge ([2023, 2024]) — 18 von 90 Zeilen
- **Groesse:** 3083 B
- **SHA-256:** `bc718cba39615dd271ca312ccb124ec803d732295359a541c21724fcdd52271d`
