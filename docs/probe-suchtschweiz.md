# Live-Probe — Sucht Schweiz (Zahlen & Fakten / HBSC)

> **Phase-1-Befund** gemäss Skill `mcp-data-source-probe`, Schritt 1.
> Durchgeführt am **2026-07-19**. Alle Zahlen live verifiziert.

## Kurzfazit

| Feld | Wert |
|---|---|
| **Empfehlung** | ⚠️ **Nicht direkt über `zahlen-fakten.suchtschweiz.ch`.** Bevorzugt **Obsan-API** (re-publiziert die HBSC-Reihen als sauberes JSON, siehe `probe-obsan.md`). Direkter Weg = Tableau-Public-Extraktion (fragil) oder HBSC-PDF-Factsheets (nicht maschinenlesbar). |
| **Offizielles REST-API** | Nein. Datenvisualisierung läuft über **Tableau Public**; Rohtabellen nur als PDF-Factsheets. |
| **Auth** | Keine — aber Tableau-Public-Datenexport ist durch **AWS WAF (Captcha)** geschützt. |
| **Verfügbarkeit bei Probe** | `zahlen-fakten.suchtschweiz.ch` liefert über unser Egress durchgängig **HTTP 526** (Cloudflare „Invalid SSL certificate" / Origin nicht erreichbar). Reproduzierbar über curl **und** WebFetch. |

---

## Basis-URLs

| Zweck | URL | Status bei Probe |
|---|---|---|
| Zahlen-&-Fakten-Portal | `https://zahlen-fakten.suchtschweiz.ch/` | ❌ **HTTP 526** (TLS-Terminierung ok, Cloudflare-Origin-Fehler) |
| Charts (Hauptsite) | `https://www.suchtschweiz.ch/zahlen-und-fakten/alkohol/alkohol-grafiken/` | ✅ 200 — bettet **Tableau Public** ein |
| Chart-Backend | `https://public.tableau.com/…/AL/ALC01DE … ALC11DEa/Tableaudebord1` | ✅ 200 (Bild/Embed); Datenexport WAF-geschützt |
| Tableau-Workbook-Meta | `https://public.tableau.com/profile/api/single_workbook/ALC01DE` | ✅ 200 JSON (`allowDataAccess:true`) |
| HBSC-Factsheets | `https://www.suchtschweiz.ch/wp-content/uploads/…/HBSC_2022_factsheet_Substances_DE.pdf` | ✅ 200 (PDF) |

## Beispiel-Payload (gekürzt)

**Tableau-Embed** auf der Grafik-Seite (`<param>`-Block):
```html
<param name='host_url'      value='https%3A%2F%2Fpublic.tableau.com%2F'>
<param name='name'          value='ALC01DE/Tableaudebord1'>
<param name='static_image'  value='https://public.tableau.com/static/images/AL/ALC01DE/Tableaudebord1/1.png'>
<param name='language'      value='de-DE'>
```
Workbooks: `ALC01DE`, `ALC02DE`, … `ALC08DE_…`, `ALC10DEa`, `ALC11DEa` (Suffixe = Republish-Versionen).

**Tableau-Workbook-Metadaten** — `GET /profile/api/single_workbook/ALC01DE`:
```json
{
  "showInProfile": true,
  "allowDataAccess": true,   "warnDataAccess": false,
  "id": 3807869, "ownerId": 491277,
  "firstPublishDate": 1512727953372, "lastPublishDate": 1720801837420,
  "luid": "f662872a-84dd-4eba-b3a0-c762b9f45efb"
}
```
`allowDataAccess:true` → der Autor erlaubt Datendownload grundsätzlich. Der eigentliche
Summary-/Crosstab-Export (`.../vizql/…/export`) erfordert jedoch eine **vizql-Bootstrap-Session** und
stösst auf `.csv`-Direktpfaden auf **AWS WAF (`captcha-sdk.awswaf.com`)** → fragil, bot-geschützt.

**Dieselben Daten sauber via Obsan** — `GET https://ind.obsan.admin.ch/api/_330/g/json`:
```json
{"title": {"de": "Prävalenz des Alkoholkonsums, nach Geschlecht"},
 "source": {"de": "Sucht Schweiz – Studie «HBSC»"},
 "value": {"de": "Anteil der 11- bis 15-Jährigen in %"},
 "data": [{"year": 2010, "value": 27.61, "value_lci": 25.61, "value_uci": 29.70, "sex_id": 20}, …]}
```

## Befund-Tabelle

| Endpoint | HTTP | Status | Bemerkung |
|---|---|---|---|
| `zahlen-fakten.suchtschweiz.ch/` | 526 | ❌ nicht erreichbar | Cloudflare-Origin-Fehler, mehrfach reproduziert (curl + WebFetch) |
| `suchtschweiz.ch/…/alkohol-grafiken/` | 200 | ✅ | 222 KB HTML, Tableau-Embeds |
| `public.tableau.com/profile/api/single_workbook/ALC01DE` | 200 | ✅ | JSON, `allowDataAccess:true` |
| `public.tableau.com/views/ALC01DE/Tableaudebord1.csv` | 404→WAF | ⚠️ | AWS-WAF-Captcha-Seite statt CSV |
| HBSC-Factsheet-PDF | 200 | ✅ | menschenlesbar, nicht maschinen-tauglich |
| Obsan `/api/_330/g/json` (dieselben HBSC-Zahlen) | 200 | ✅ | **empfohlener Zugangsweg** |

**Fundstück (Known finding):** Die „seriöse Schweizer NGO bietet immer einen Dump"-Faustregel greift
hier **nicht** direkt — Sucht Schweiz publiziert Zahlen nur als Tableau-Public-Dashboards + PDF-Factsheets.
Der maschinenlesbare Ausweg ist, dass **Obsan (Bund) die HBSC-Reihen als offizielle JSON-Indikatoren
weiterführt** (Quelle „Sucht Schweiz – HBSC" im Payload ausgewiesen). Metapher: *Die Rohdaten stehen im
Schaufenster (Tableau), aber die Ladentür ist der Nebeneingang beim Bund (Obsan).*

## Reality-Check gegen Homepage

Homepage bewirbt HBSC-Zeitreihen zum Substanzkonsum Jugendlicher (11–15 J.). Live bestätigt: Die Reihen
existieren, sind aber in Tableau gekapselt. Die inhaltlich identischen Zahlen (Prävalenz Alkoholkonsum
11–15 J., **2006–2022**, nach Geschlecht, mit 95%-CI) sind über Obsan `_330` 1:1 abrufbar → Reality-Check
über den Obsan-Spiegel bestanden.

## Aktualisierungsfrequenz

**HBSC-Erhebung alle 4 Jahre** (seit 1986; letzte Welle **2022**, publiziert 2023; nächste ~2026).
Tableau-Dashboards werden pro Welle neu publiziert (`lastPublishDate` 2024 im Workbook-Meta).
Keine unterjährige Aktualisierung.

## Lizenz

Keine explizite Lizenz an den Datenobjekten. Sucht Schweiz ist eine Stiftung; HBSC wird im Auftrag von
BAG/Kantonen durchgeführt. **Attribution zwingend**: „Sucht Schweiz – HBSC" (+ Erhebungsjahr). Bei Bezug
über Obsan zusätzlich „Obsan". Formale Nutzungsbedingungen vor Implementierung klären.

## Rate-Limit-Verhalten

`zahlen-fakten`-Host bei Probe komplett aus (526) → kein Test möglich. Tableau Public (`public.tableau.com`)
hat **aktiven Bot-Schutz (AWS WAF)** — automatisierte Datenextraktion ist nicht rate-stabil und wird
teils mit Captcha geblockt. Genau der Grund, den fragilen Direktweg zu meiden.

## Präventions-/Schulkontext — Kennzeichnungspflicht

HBSC-Alkohol-/Substanzdaten berühren Präventionsthemen im Schulkontext. Jede spätere Tool-Description
**muss** klarstellen: Es handelt sich um **aggregierte Bevölkerungsstatistik** (nationale Prävalenzen
nach Alter/Geschlecht, mit Konfidenzintervallen) — **nicht um individuelle Beratung, Diagnose oder
Fallbezug**. Kein Personenbezug, keine Kanton-/Schul-/Klassenauflösung.

## Empfehlung

**Nicht implementierbar über den offiziellen `zahlen-fakten`-Host** (bei Probe 526; Daten ohnehin nur
Tableau/PDF). **Empfohlener Weg: die HBSC-Reihen über die Obsan-API beziehen** (`probe-obsan.md`) — sauberes
JSON, viersprachig, mit CI und amtlicher Provenienz. Tableau-Public-Extraktion nur als letzter Ausweg für
Reihen, die Obsan **nicht** spiegelt — dann als eigenständige, WAF-tolerante Dump-Routine mit `dump_status()`
und klarer Graceful Degradation, **nicht** als Live-Tool.
