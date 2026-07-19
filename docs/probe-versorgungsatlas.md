# Live-Probe — Versorgungsatlas (Schweizer Atlas der Gesundheitsversorgung)

> **Phase-1-Befund** gemäss Skill `mcp-data-source-probe`, Schritt 1.
> Durchgeführt am **2026-07-19**. Alle Zahlen live verifiziert.

## Kurzfazit

| Feld | Wert |
|---|---|
| **Empfehlung** | ✅ **ARCH B/C — File/Dump-first** (statischer JSON-Filestore der Next.js-App). |
| **Offizielles REST-API** | Nein. `versorgungsatlas.ch` ist eine Next.js-SSG-App (**gleicher Vendor wie Obsan** — geteilter Chunk `363-…`). |
| **Auth** | Keine. Öffentlich. |
| **Rate-Limit** | Keines beobachtet (statische Assets). |
| **Offene Frage** | Der numerische **Daten-Filestore** (`/data/…json`) antwortet am Web-Root mit `404` → exakte Base/Rewrite muss per Headless-Fetch fixiert werden (siehe „Offener Punkt"). Katalog + volle Indikator-Metadaten sind **jetzt schon** direkt abrufbar. |

---

## Basis-URLs

| Zweck | URL | Status |
|---|---|---|
| **Katalog** (alle Indikatoren) | `https://www.versorgungsatlas.ch/search/search_{de,fr,en}.json` | ✅ **200**, ~710 KB, **124 Indikatoren / 285 Aspekte** |
| Indikator-Seite (SSR) | `https://www.versorgungsatlas.ch/indicator/<id>/<aspect>` | ✅ 200 — `__NEXT_DATA__` enthält volle Metadaten |
| Sitemap | `https://www.versorgungsatlas.ch/sitemap.xml` | ✅ 200, 889 `<loc>` |
| Daten-Filestore (aus JS-Quelle) | `/data/${id}${aspect}_${geo}.json` | ⚠️ Pattern aus Code bestätigt, am Root `404` |
| Geometrie | `/geo/${id}.geojson` · Definition `/def/${id}.json` · Text `/md/${id}_${aspect}.md` | ⚠️ analog, Base offen |

Die URL-Bildung ist im Client-Bundle wörtlich belegt:
```js
function t(e,n,r){return `/data/${e}${n}_${r}.json`}   // Daten (id, aspect, geo)
function o(e){return `/search/search_${e}.json`}        // Katalog (e = Sprache)
function d(e){return `/geo/${e}.geojson`}                // Geometrie
function l(e){return `/def/${e}.json`}                   // Definition
function s(e,n){return `/md/${e}_${n}.md`}               // Beschreibungstext
```

## Beispiel-Payload (gekürzt)

**Katalog** — `GET /search/search_de.json` (Array):
```json
[
  {
    "id": "_003", "aspect": "b",
    "title": "MMR-Impfungen", "aspect_title": "bei Kindern bis 15 Jahre",
    "topic": "Impfungen", "group_terms": "Pädiatrie", "search_terms": "",
    "description": "Die MMR-Impfung ist eine Kombinationsimpfung …",
    "remark": "Der Impfplan wurde 2019 … (siehe Downloadbereich: Indikatorendefinition)"
  }
]
```

**Indikator-Metadaten** — `__NEXT_DATA__` von `/indicator/_003/b` (`props.pageProps.indicator`):
```json
{
  "id": "_003",
  "labels": {"de": "MMR-Impfungen", "fr": "Vaccins ROR", "en": "MMR vaccinations"},
  "domain_id": 14, "hasData": true,
  "groups": {"de": ["Pädiatrie"]},
  "links":  {"de": "* [Schweizerischer Impfplan (BAG)](…)"},
  "aspects": [
    {"aspect_id": "b", "subtitle": {"de": "bei Kindern bis 15 Jahre"},
     "geos": ["kt"], "sex_def": 0, "digits": 1, "layout": "noSZ", "hasAG": true}
  ],
  "prevs": {"de": "_302"}, "nexts": {"de": "_006"}
}
```
→ Der Aspekt trägt `geos: ["kt"]` (**kt = Kanton**), `hasAG` (Altersgruppen), `sex_def`.
Damit sind Raumeinheit + Dimensionen je Indikator **maschinell auslesbar**, bevor die Werte geladen werden.

## Befund-Tabelle

| Endpoint | HTTP | Status | Records | Bemerkung |
|---|---|---|---|---|
| `/search/search_de.json` | 200 | ✅ funktioniert | 285 Aspekte / 124 IDs | vollständiger Katalog, DE/FR/EN |
| `/sitemap.xml` | 200 | ✅ funktioniert | 889 locs | Indikator-Pfade `indicator/_003/a` … |
| `/indicator/_003/b` (`__NEXT_DATA__`) | 200 | ✅ funktioniert | 1 (mit `aspects[]`) | SSR-Metadaten inkl. `geos`, `hasAG` |
| `/data/_003b_kt.json` (+ Varianten) | 404 | ⚠️ leer | – | Pattern korrekt, Base/Rewrite offen |
| `/geo/_003.geojson`, `/def/_003.json`, `/md/_003_b.md` | 404 | ⚠️ leer | – | analog — nicht am Web-Root |
| `/robots.txt` | 404 | ❌ | – | keiner vorhanden |
| `/api/_003/…` (Obsan-Muster) | 404 | ❌ | – | VA nutzt **nicht** Obsans `/api/`-Backend |

**Fundstück (Known finding):** Obwohl `/search/search_de.json` als echte statische Datei am Web-Root
ausgeliefert wird, liefern `/data/`, `/def/`, `/geo/`, `/md/` durchgängig die SPA-`404`-Seite — trotz
korrekt rekonstruiertem Datei-Token (`id`+`aspect`+`geo`, z. B. `_003b_kt`) und Referer/XHR-Headern.
Das deutet auf einen **separaten Asset-Base / Rewrite** (assetPrefix) oder Auslieferung nur im
SPA-Runtime-Kontext. Für die exakte Werte-URL ist ein **Headless-Browser-Trace** (Network-Tab) nötig —
bewusst nicht Teil dieser Live-Probe (Phase 1). Der **Katalog und die vollen Metadaten je Indikator
sind ohne diesen Schritt vollständig zugänglich.**

## Reality-Check gegen Homepage

Homepage bewirbt „> 100 Indikatoren". Live: `search_de.json` enthält **124 eindeutige IDs / 285
Aspekte** — bestätigt und leicht darüber. Keine Diskrepanz.

## Aktualisierungsfrequenz

Nicht am API-Payload ablesbar. Versorgungsatlas ist ein **jährlich aktualisierter** Atlas auf Basis
des Tarifpool (SASIS AG / santésuisse–curafutura-Abrechnungsdaten). Genaue Kadenz + Datenstand aus
`/p/method` bzw. dem Downloadbereich verifizieren und im README festhalten. `buildId` (`aggXvCnUtYPKk-46Knv67`
bei Probe) markiert das jeweilige Deployment.

## Lizenz

**Kooperationsprojekt BAG + Obsan.** Keine CC-Lizenz auf `/p/about` / `/p/method` sichtbar. VA stellt
je Indikator eine „Indikatorendefinition" im Downloadbereich bereit; Nutzungsbedingungen dort und im
Impressum prüfen. Bis zur Klärung: konservativ als „© BAG/Obsan, Nutzung mit Quellenangabe" behandeln,
**Attribution je Indikator** (Titel + „Versorgungsatlas Schweiz, BAG/Obsan") mitführen.

## Rate-Limit-Verhalten

Statischer Filestore (der Katalog ist eine grosse JSON-Datei) → kein Rate-Limit beobachtet.
Empfehlung: Katalog + Metadaten lokal cachen (ein Fetch deckt alle 124 Indikatoren ab), Backoff-Retry
für transiente 5xx.

## Empfehlung

**ARCH C (Dump-first) mit File-Layer**: Den Katalog `/search/search_<lang>.json` **einmal ziehen und
cachen** (deckt Discovery + Suche vollständig ab), Metadaten je Indikator aus `__NEXT_DATA__` der
`/indicator/<id>/<aspect>`-Seite. Für die **numerischen Werte** ist ein Folge-Schritt nötig
(Headless-Network-Trace, um die `/data/`-Base zu fixieren) — dieser gehört in Phase 2, nicht in die
Live-Probe. **Nicht blockiert**, aber der Werte-Layer ist noch nicht 1:1 per `curl` reproduziert.
