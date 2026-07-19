# Live-Probe — Obsan (Schweizerisches Gesundheitsobservatorium)

> **Phase-1-Befund** gemäss Skill `mcp-data-source-probe`, Schritt 1.
> Durchgeführt am **2026-07-19**. Alle Zahlen live verifiziert.

## Kurzfazit

| Feld | Wert |
|---|---|
| **Empfehlung** | ✅ **ARCH A — Live-API** (undokumentierte, aber stabile JSON-API). Beste Quelle der drei. |
| **Offizielles REST-API** | Nein (nicht beworben) — aber das Indikatoren-Portal `ind.obsan.admin.ch` hat einen sauberen, maschinenlesbaren JSON-Backend. |
| **Auth** | Keine. Rein öffentlich. Phase-1-tauglich. |
| **Rate-Limit** | Keines beobachtet (8 schnelle Calls → alle `200`, < 0.9 s). Apache, keine Rate-Limit-Header. |

---

## Basis-URLs

| Zweck | URL | Format |
|---|---|---|
| Katalog (Sitemap) | `https://ind.obsan.admin.ch/sitemap.xml` | XML, **987 `<loc>`**, davon **827** Indikator-Pfade (inkl. DE/FR/IT/EN-Duplikate) |
| Indikator-Metadaten | `https://ind.obsan.admin.ch/_next/data/<buildId>/<lang>/indicator/<topic>/<slug>.json` | JSON → liefert die interne `id` (z. B. `_330`) |
| **Indikator-Daten** | `https://ind.obsan.admin.ch/api/<id>/g/json` | **JSON mit `data`-Array (year, value, …)** |
| Daten-Variante | `https://ind.obsan.admin.ch/api/<id>/gum/json` | JSON, alternative Ansicht (z. B. Anteile in %) |

`<buildId>` bei Probe: `sq58i2_tpDjCJF2rYRkLW` (aus Next.js `_buildManifest`; ändert sich pro Deployment).
Topics: `monam` (Monitoring Sucht/NCD), `avos`, `pflemo` (Pflegepersonal), `docmo` (Ärzteschaft), `medpsyreg`, u. a.

## Beispiel-Payload (gekürzt) — Indikator `_330`

`GET https://ind.obsan.admin.ch/api/_330/g/json`

```json
{
  "name": "_330_g",
  "title":  {"de": "Prävalenz des Alkoholkonsums, nach Geschlecht", "fr": "…", "it": "…", "en": "…"},
  "source": {"de": "Sucht Schweiz – Studie «Health Behaviour in School-aged Children» (HBSC)"},
  "year":   {"de": "Jahr"},
  "value":  {"de": "Anteil der 11- bis 15-Jährigen in %"},
  "version": "20260615",
  "last_updated_at": "2023-03-27",
  "created_at": "2026-07-19T13:44:52.238Z",
  "remarks": {"de": "… Die Daten sind mit dem 95%-Vertrauensintervall dargestellt …"},
  "data": [
    {"year": 2006, "n": 4850, "value": 29.28, "value_lci": 27.09, "value_uci": 31.56, "sex_id": 20},
    {"year": 2006, "n": 4850, "value": 32.76, "value_lci": 30.71, "value_uci": 34.87, "sex_id": 10},
    {"year": 2006, "n": 9700, "value": 31.06, "value_lci": 29.19, "value_uci": 33.00, "sex_id": 0},
    {"year": 2010, "n": 5002, "value": 27.61, "value_lci": 25.61, "value_uci": 29.70, "sex_id": 20}
  ]
}
```

Beobachtete `data`-Felder: `year`, `value`, `value_lci`/`value_uci` (95%-CI), `n` (Fallzahl),
`sex_id` (0 = Total, 10 / 20 = Geschlechter), `category_id` (bei anderen Indikatoren, z. B. Kostenarten).
Titel/Quelle/Labels konsequent **viersprachig** (de/fr/it/en).

## Befund-Tabelle

| Endpoint | HTTP | Status | Records | Bemerkung |
|---|---|---|---|---|
| `/sitemap.xml` | 200 | ✅ funktioniert | 827 Indikator-Locs | vollständiger Katalog, sprachdupliziert |
| `/_next/data/<b>/…/indicator/monam/alkoholkonsum-alter-11-15.json` | 200 | ✅ | 1 | liefert `id=_330` |
| `/api/_330/g/json` | 200 | ✅ funktioniert | 15 Punkte (2006–2022) | HBSC-Prävalenz, mit CI |
| `/api/_257/g/json` | 200 | ✅ funktioniert | 78 Punkte (ab 2000) | Gesundheitskosten, `category_id` |
| `/api/_405/g/json` | 200 | ✅ funktioniert | 24 Punkte (2001–2024) | Alkoholverkauf pro Kopf (BAG) |
| `/api/_111/g/json` | 404 | ⚠️ leer | – | **nicht jeder Indikator hat `/g/json`** — Variante prüfen (`/gum/json`) |
| `/data/config`, `/data/labels`, `/data/texts/search/…` | 404 | ❌ | – | in JS referenzierte Pfade, am Web-Root nicht erreichbar |

**Fundstück (Known finding):** Der Suffix `/g/json` ist nicht universell. Einige IDs liefern `404`
auf `/g` und exponieren ihre Reihe nur unter `/gum/json` oder mit anderem Suffix. Ein Implementierungs-Tool
muss auf `404` mit Fallback auf die Alternativ-Variante reagieren (nicht als „keine Daten" werten).

## Reality-Check gegen Homepage

`ind.obsan.admin.ch` bewirbt „Indikatoren"-Sammlungen. Die Sitemap listet 827 Indikator-Pfade
(sprachbereinigt Grössenordnung ~200 Indikatoren über alle Topics). Stichproben (`_330`, `_257`,
`_405`) liefern konsistent vollständige Zeitreihen — **keine leeren Arrays**, keine Abweichung
zwischen beworbenem Umfang und tatsächlicher Auslieferung.

## Räumliche Granularität — wichtig für die Anchor-Query

Die Stichprobe zeigt: **MONAM-Indikatoren sind national, dimensioniert nach `sex_id` / `age` /
`category_id` — kein Kantons-Feld.** Die HBSC-Jugendreihe `_330` existiert nur gesamtschweizerisch
(die HBSC-Stichprobe ist nicht kantonal repräsentativ). Ein **„Kanton Zürich vs. Schweiz"-Vergleich
auf Jugend-Alkohol ist mit dieser Quelle nicht abbildbar** — der Schweizer Wert und der Trend seit
2006/2010 hingegen schon. Kantonale Reihen finden sich in anderen Obsan-Topics (z. B.
`monam/…-in-den-kantonen` = Regulierungs-/Gesetzesindikatoren), nicht in den Konsum-Prävalenzen.

Für die Anchor-Query relevant: Obsan **re-publiziert die Sucht-Schweiz-HBSC-Daten** (Quelle im Payload
ausgewiesen) als saubere JSON mit Konfidenzintervallen — damit ist Obsan der bevorzugte Zugangsweg
zu den HBSC-Zahlen (statt Tableau-Scraping bei Sucht Schweiz, siehe `probe-suchtschweiz.md`).

## Aktualisierungsfrequenz

- Pro Indikator: Feld `version` (z. B. `20260615`) und `last_updated_at` (z. B. `2023-03-27`, = HBSC-Welle 2022).
- Frequenz je nach Quellstatistik unterschiedlich (BFS-jährlich bis HBSC alle 4 Jahre). Keine globale Kadenz.
- `created_at` = Request-Zeitpunkt → Payload wird **dynamisch generiert** (nicht statisch gecacht).

## Lizenz

**Kein Lizenzfeld im API-Payload.** Obsan ist Bund/Kantone (admin.ch). Für die zugrunde liegenden
BFS-Statistiken gelten die BFS-Nutzungsbedingungen (freie Nutzung mit Quellenangabe). **Attribution
zwingend**: je Reihe das Feld `source` (viersprachig) plus „Obsan (ind.obsan.admin.ch)" mitführen;
bei HBSC-Reihen zusätzlich „Sucht Schweiz – HBSC". Formale Lizenz vor Implementierung beim Obsan-Impressum
(`https://www.obsan.admin.ch/de/impressum`) verifizieren und im README unter „Lizenz" dokumentieren.

## Rate-Limit-Verhalten

8 aufeinanderfolgende Requests auf `/api/_257/g/json` → alle `200`, 0.48–0.88 s, keine Drosselung.
Server: `Apache/2.4.68 (Debian)`, `HSTS` gesetzt, keine `X-RateLimit-*`-Header, keine `Cache-Control`.
Resilienz-Default (Retry mit Backoff) trotzdem einbauen — die dynamische Generierung kann bei Last 5xx liefern.

## Empfehlung

**ARCH A — Live-API**, `https://ind.obsan.admin.ch/api/<id>/g/json`.
Zusätzlich Katalog per Sitemap + Metadaten per `_next/data`-JSON auflösen und **lokal cachen**
(TTL ~24 h; `buildId` kann wechseln → robust gegen `404` auf `_next/data` re-resolven).
Kein Dump nötig; die API ist vollständig und stabil. `/g/json`↔`/gum/json`-Fallback implementieren.
