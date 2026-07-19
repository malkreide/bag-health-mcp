# Tool-Design — Multi-Source Health Indicators (Phase 2)

> Phase-2-Erweiterung nach der Live-Probe (`docs/probe-*.md`). Baut den Server um
> drei zusätzliche Gesundheitsdaten-Quellen aus: **Versorgungsatlas**, **Obsan**,
> **Sucht Schweiz** (HBSC).

## 1. Inventar der bestehenden Tools

| # | Tool | Zweck |
|---|---|---|
| 1 | `bag_health_mcp__list_diseases` | IDD-Krankheits­themen auflisten |
| 2 | `bag_health_mcp__list_series` | Serien eines Themas auflisten |
| 3 | `bag_health_mcp__get_series_details` | Filter-Metadaten einer Serie |
| 4 | `bag_health_mcp__get_disease_data` | Zeitreihe (Fälle/Inzidenz) abrufen |
| 5 | `bag_health_mcp__list_export_files` | Bulk-Export-Dateien auflisten |
| 6 | `bag_health_mcp__download_export` | Vollständigen Datensatz laden |
| 7 | `bag_health_mcp__get_data_version` | Datenstand des IDD |
| 8 | `bag_health_mcp__get_canton_situation` | Kantons-Lagebild (Schulamt) |

**Bestand: 8 Tools. Budget: 18. Verfügbar: 10.**

## 2. Design-Entscheid — zwei generische Tools statt drei Familien

Statt pro Quelle eine eigene Tool-Familie (was schnell 6–9 Tools kostet und das
Budget belastet), wird **ein generisches Paar** eingeführt, parametrisiert über
`source`:

| # | Neues Tool | Signatur (Kern) |
|---|---|---|
| 9 | `bag_health_mcp__search_health_indicators` | `(source, topic, region, year_from, year_to, language, limit)` |
| 10 | `bag_health_mcp__get_indicator_series` | `(source, indicator_id, region, year_from, year_to, language)` |

`source ∈ {obsan, versorgungsatlas, suchtschweiz}`.

**Ergebnis: 8 + 2 = 10 Tools — Budget (18) eingehalten, 8 Reserve.**

Begründung (entspricht der Vorgabe):
- Einheitliche mentale Landkarte für das LLM: „suchen → Serie holen" gilt für alle
  Quellen. Kein Umlernen pro Quelle.
- Erweiterbar ohne neue Tools: eine vierte Quelle wird ein weiterer `source`-Wert,
  kein zusätzliches Tool.
- Die quellenspezifischen Eigenheiten (Obsan-`/api`, VA-Katalog, HBSC-Spiegel)
  liegen in internen Adaptern (`_health_indicators.py`), nicht in der Tool-Fläche.

## 3. Zugriffsarchitektur je Quelle (aus der Live-Probe)

| Quelle | ARCH | Zugriff im Server |
|---|---|---|
| **Obsan** | A (Live-API) | `sitemap.xml` (Katalog, gecacht) → SSR-Seite `__NEXT_DATA__` (id-Auflösung) → `GET /api/<id>/g/json` (Fallback `/gum/json`). Voll funktionsfähig, mit 95%-CI. |
| **Versorgungsatlas** | C (File-first) | `search/search_<lang>.json` (Katalog, gecacht) für Suche; SSR-Seite für Metadaten/Dimensionen. **Numerische Werte** liegen nur im interaktiven Atlas → `get_indicator_series` liefert Metadaten + Verweis (Graceful Degradation, dokumentierte Grenze). |
| **Sucht Schweiz** | via Obsan | HBSC-Jugendreihen werden von Obsan mit Provenienz gespiegelt → `source='suchtschweiz'` nutzt den Obsan-Pfad, auf das `monam`-Monitoring beschränkt und mit Sucht-Schweiz-Attribution. Der `zahlen-fakten`-Host (Tableau/PDF, bei Probe HTTP 526) wird bewusst nicht angebunden. |

## 4. 🎯 Anchor Demo Query

> «Wie hat sich der Alkoholkonsum bei 15-Jährigen im Kanton Zürich seit 2010
> entwickelt, und wie steht der Kanton im Schweizer Vergleich da?»

Ablauf:
1. `search_health_indicators(source='suchtschweiz', topic='alkohol')`
   → u. a. `monam/alkoholkonsum-alter-11-15`.
2. `get_indicator_series(source='suchtschweiz',
   indicator_id='monam/alkoholkonsum-alter-11-15', region='ZH', year_from=2010)`
   → nationale HBSC-Prävalenz nach Geschlecht, mit 95%-CI, ab 2010.

**Ehrliche Grenze (im Response transparent gemacht):** Die HBSC-Reihen sind
**national, nicht kantonal** (die Stichprobe ist nicht kantonal repräsentativ).
Das Tool gibt daher die Schweizer Reihe zurück **plus** `region_note`, die erklärt,
dass ein „Kanton ZH vs. Schweiz"-Vergleich auf dieser Serie nicht möglich ist.
Der Zeitverlauf seit 2010 für die Schweiz wird vollständig beantwortet.

## 5. Sicherheit & Resilienz (bestehende Leitplanken beibehalten)

- **Egress-Allow-List (SEC-021):** `ALLOWED_HOSTS` um `ind.obsan.admin.ch` und
  `www.versorgungsatlas.ch` erweitert — weiterhin fixe Liste, HTTPS-only, mit
  SSRF-Blocklist und DNS-Pinning (SEC-004/005) unverändert wirksam.
- **Retry mit Backoff:** neuer `_get_with_retry` (2s/4s/8s, nur 5xx/429/Netz),
  Skill-Vorgabe erfüllt; Fehler werden als sichere `ToolError` maskiert (OBS-002).
- **Provenance in jeder Response:** per-Quelle Attribution + Lizenzhinweis
  (kein formales Lizenzfeld an den Objekten → Swiss-OGD-Praxis, Quellenangabe).
- **Caching:** Kataloge (Obsan-Sitemap, VA-Suchindex) mit 6h-TTL in-memory.

## 6. Pflicht-Kennzeichnung (Schulkontext)

Sucht-Schweiz/HBSC-Daten berühren Präventionsthemen im Schulkontext. Beide Tool-
Descriptions **und** jede Response tragen den Hinweis
`aggregate_statistics_notice`:

> Aggregierte Bevölkerungsstatistik (Prävalenzen/Kennzahlen nach
> Alter/Geschlecht/Region) — KEINE individuelle Beratung, Diagnose oder
> Fallbeurteilung, kein Personenbezug.

## 7. Bekannte Grenzen

- Versorgungsatlas: keine maschinenlesbaren Werte (nur Metadaten + Atlas-Link),
  bis die `/data/`-Basis via Headless-Trace fixiert ist (Folgearbeit).
- Obsan: nicht jeder Indikator hat `/g/json`; Fallback auf `/gum/json` implementiert.
- HBSC/Obsan: national, keine Kantonsauflösung (siehe Anchor-Query-Hinweis).
