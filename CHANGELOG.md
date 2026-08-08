# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Behoben — der Obsan-Client fragte nach zwei von sieben Schnitten

Der letzte Eintrag hielt fest, dass der Katalog mehr Indikatoren anbietet, als
das Serien-Tool ausliefern kann: von 12 Stichproben hatten nur 3 eine Reihe, 9
gaben auf `/g/json` **und** `/gum/json` je 404. Das war die Messung. Der Schluss
daraus war meiner, und er war falsch.

**Sie haben keine Reihe, die der Client fragt.** Eine Obsan-Indikatorseite
deklariert in `props.pageProps.jsonLDs.links.od3.<id>`, welche API-Varianten es
zu ihr gibt — samt vollstaendiger `apiUrl` je Variante. Der Client hat diese
Liste nie gelesen. Er hat zwei feste Endungen geraten.

Am 2026-08-08 ueber 60 sprachneutrale Indikatoren gemessen
(`tests/fixtures/obsan_variant_census.json`):

| Schnitt | Bedeutung | vorhanden bei |
|---|---|---|
| `kg` | nach Kantonen | **50** von 60 |
| `ag` | nach Altersklasse | 49 |
| `sd` | nach sozialer Lage | 24 |
| `gum` | Verteilung nach Segmenten | 9 |
| `agum` | Verteilung nach Altersklasse | 5 |
| `g` | national | **3** |
| `bg` | weiterer Schnitt | 1 |

**49 von 60** haben weder `g` noch `gum` — die beiden einzigen, die der Client
fragte. Gar keine Variante haben **8**. Die Differenz sind **41 Indikatoren mit
Daten, die der Server fuer nicht vorhanden erklaerte.** Der haeufigste Schnitt
ist der kantonale; der einzige, den der Client verlaesslich fragte, ist der
seltenste.

`obsan/lebenserwartung` stand im letzten Eintrag als Beispiel fuer «keine
Serie». Er hat 4374 Datenpunkte, kantonal, seit 1998 — hinter einer Adresse, die
nie jemand abgefragt hat.

**Was jetzt geschieht:**

- Die Seite wird gelesen. `_obsan_resolve` liefert `(interne id, deklarierte
  Varianten)`; die Reihenfolge `g → kg → ag → sd → gum → agum → bg` waehlt aus
  dem, was es gibt, statt zu raten. Wird eine Region angefragt, geht `kg` voran.
- **Kantonale Obsan-Reihen sind damit erreichbar.** `region='ZH'` liefert den
  Kanton, ohne Region den nationalen Wert (BFS-Nummer 0, den `kg` mitfuehrt).
  Die Tool-Beschreibungen behaupteten bisher das Gegenteil («obsan indicators
  are national»); fuer 50 von 60 stimmte das nicht.
- **Der gelieferte Schnitt wird benannt** (`variant`, `variants_available`).
  Vorher rutschte `gum` still als Ersatz fuer `g` durch — `g` ist bei `_010`
  eine standardisierte Rate, `gum` eine Verteilung in %. Zwei Groessen, ein
  Feld, kein Hinweis. Sie sind keine schlechteren Kopien voneinander.
- **Die Legende kommt aus dem Payload.** Obsan liefert zu jeder Dimension eine
  uebersetzte `codes`-Tabelle. Vorher stand hier ein fester Satz («category
  breakdown (see source remarks)») — derselbe fuer einen Indikator, der nach
  Suizid vs. Suizidhilfe geteilt ist, wie fuer einen nach Lebenserwartung bei
  Geburt vs. bei 65. Dazu die `remarks` der Quelle als `note`.
- **Kantonsnummern werden geprueft, nicht geglaubt.** Die BFS-Zuordnung steht im
  Code und wird bei jedem Aufruf gegen die `kanton_nr.codes` des Payloads
  gehalten. Weicht sie ab, bricht der Aufruf ab. Ein falsch zugeordneter Kanton
  ist die unangenehmste Form von falsch: vollstaendig, plausibel, und ueber
  woanders.
- **Gepoolte Jahresspannen brechen nichts mehr.** `"1998-02"` ist 1998–2002, ein
  5-Jahresmittel. Diese Form kommt nur in Schnitten vor, die der Client nie
  holte; in ein `int`-Feld gelegt wirft sie einen Validierungsfehler mitten im
  Werkzeugaufruf. Sie behaelt jetzt ihr Etikett in `period`, ihr erstes Jahr
  steht in `year`, und der Jahresfilter rechnet damit. Ebenso `n` als
  Gleitkommazahl (durchschnittliche Faelle pro Jahr).
- **Wo es wirklich keine Reihe gibt — 8 von 60 —, sagt der Aufruf das.** Ein
  leeres Ergebnis liest sich wie eine Aussage ueber die Welt und waere eine ueber
  den Client.
- Die Suche behauptet nicht mehr «mostly national». Die Sitemap traegt URLs und
  sonst nichts; welche Schnitte es gibt, weiss erst der Serien-Aufruf.

**Aufgezeichnet dazu:** `obsan_api_kg.json` (gepoolte Spannen),
`obsan_api_kg_only.json` (der Indikator ohne `g`/`gum`),
`obsan_api_kg_sparse.json` (nicht fuer alle Kantone publiziert),
`obsan_page_cantonal_only.html`, `obsan_page_no_variants.html` und die Erhebung
`obsan_variant_census.json`. Die Zahl oben ist damit kein Satz in einer
Commit-Nachricht, sondern eine datierte Messung, die man wiederholen kann.

**Gegenprobe gefuehrt:** Mit dem alten Verhalten — Varianten-Liste ignoriert,
`g`/`gum` geraten — fallen sechs der neuen Tests. Zwei `@pytest.mark.live`-Tests
halten die Annahme ausserdem gegen den echten Host.

**Und eine Korrektur an einer eigenen Notiz:** Der letzte Eintrag behauptete,
`pytest -m live` sammle hier null Tests ein. Das stimmt nicht. `test_server.py`
ruft auf Modulebene `importorskip("opentelemetry.sdk.trace")` auf — ohne die
OTel-Extras faellt die ganze Datei weg, Live-Tests inklusive. CI installiert sie
und sammelt sechs. Gemessen wurde eine lokale Umgebung, berichtet wurde ueber
das Repository.

### Hinzugefuegt — die Fixtures sind aufgezeichnet, nicht mehr ausgedacht

Jeder Payload dieser Suite war ein Literal im Testmodul, keiner je von der
Quelle geholt. Dazu kommt: Der einzige `@pytest.mark.live`-Test ist
uebersprungen — `pytest -m live` sammelt hier **null** Tests ein. Nichts in
diesem Repo hat seine Annahmen je gegen die echten Hosts gehalten.

Neu: **`scripts/record_fixtures.py`** zeichnet von `ind.obsan.admin.ch` und
`www.versorgungsatlas.ch` auf und schreibt `tests/fixtures/*` samt
`PROVENANCE.md` mit Quelle, **Aufzeichnungsdatum**, Auswahlregel und SHA-256 je
Datei. Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden.

**Was der Wechsel aufgedeckt hat — drei Befunde:**

1. **Die Sitemap-Fixture beschrieb eine Form, die es nicht gibt.** Sie bestand
   aus vier `/de/indicator/...`-URLs. Die Quelle liefert davon **keine
   einzige**: gemessen 285 `fr`, 223 `it`, 41 `en` und 285 **sprachneutrale**
   Eintraege, und die neutralen tragen die deutschen Slugs. Deutsch kommt ohne
   Sprachsegment. Jedes deutsche Suchergebnis laeuft damit ueber den
   `lang == ""`-Zweig — den kein Test je beruehrt hat. Der Code selbst ist in
   Ordnung; ungetestet war er trotzdem. Neu festgehalten von
   `test_german_results_ride_on_the_language_neutral_catalogue_entries`, und
   die Gegenprobe ist gefuehrt: Mit auf `/de/` zurueckgedrehter Fixture faellt
   genau dieser Test.

2. **Der Katalog listet weit mehr, als das Serien-Tool liefern kann.** In einer
   Stichprobe von 12 sprachneutralen Indikatoren hatten nur **3** ueberhaupt
   eine Serie — 9 gaben auf `/g/json` **und** `/gum/json` 404. Der Mehrheitsfall
   liegt jetzt als eigene Fixture (`obsan_page_no_series.html`) vor; das
   Aufzeichnungsskript prueft beim Lauf nach, dass er weiterhin 404 ist.
   **Nicht behoben:** Dass die Suche Indikatoren anbietet, die das Serien-Tool
   nicht ausliefert, bleibt offen — das ist eine Verhaltensaenderung und
   gehoert in einen eigenen PR.

3. **Die Versorgungsatlas-Fixture unterschlug die Aspekte.** Die Quelle fuehrt
   drei Aspekte von `_003` (a/b/c) und zwei von `_006`; die handgeschriebene
   Fixture kannte je einen. Kein Test hat je mehrere Aspekte desselben
   Indikators gesehen — wofuer das Feld `aspect` gerade da ist.

**Ein Test bestand leer und tut es nicht mehr.** Die Sucht-Schweiz-Eingrenzung
assertiert `all(id.startswith("monam/") …)`; ueber einer leeren Liste ist das
wahr. Die Fixture enthaelt jetzt einen `monam`-Eintrag, und die Nicht-Leerheit
ist Teil der Zusicherung.

Erwartungen werden durchgehend **aus der Fixture abgeleitet** statt
hingeschrieben — Punktzahlen, Jahre, Regionen. Eine feste Zahl waere beim
naechsten Aufzeichnen falsch, ohne dass sich etwas Geprueftes geaendert haette.

Der Rahmen dazu steht im Skill [`mcp-data-fidelity`](https://github.com/malkreide/mcp-data-fidelity-skill)
unter Regel 5 und im Katalog-Check `OPS-009`.


### Changed

- **Retry policy against the upstream: spread, obedient and time-bounded
  (`ARCH-014`).** A portfolio run of the audit catalogue on 2026-08-07 read
  `_get_with_retry` by hand. What it retries was already right — network errors
  and 5xx/429, fail fast on any other 4xx. The other two questions the check
  asks were unanswered.

  | Property | Before | Now |
  |---|---|---|
  | Jitter | none — a fixed exponential ladder | spread into `[0.5x, 1.5x]` |
  | `Retry-After` | not read | read (both RFC 9110 forms), and it beats our curve |
  | Cap on a single wait | none | `RETRY_MAX_DELAY`, applied **after** the jitter |
  | Wall-clock budget | none | `RETRY_TOTAL_BUDGET = 25.0` on `asyncio.timeout` |
  | Ladder | 4s / 8s / 16s | 2s / 4s / 8s, as the comment always claimed |

  **A deterministic ladder is a retry storm.** Every client that hits the same
  outage comes back at the same moment, and the load returns as a wave exactly
  when the source recovers — the retry extends the outage it was meant to
  bridge. Obsan and the Versorgungsatlas are shared, unfunded infrastructure;
  this is the difference between a guest and a load.

  **`TIMEOUT` was never a budget.** httpx bounds each *operation* and its read
  timeout restarts with every chunk, so a slowly trickling response outlives
  any ceiling without a single read expiring. Four attempts against an upstream
  that takes the full 30s to give up is two minutes inside one tool call, and
  `RETRY_ATTEMPTS = 4` never said so. The 25s budget hangs off `asyncio.timeout`
  and sits below the MCP SDK's 30s default, so the server stops working before
  the caller stops listening.

  **The ladder was off by one.** `RETRY_BACKOFF_BASE * 2**attempt` with
  `attempt` starting at 1 gives 4s/8s/16s, while the docstring and the comment
  above the constant both said 2s/4s/8s. The exponent is now `attempt - 1` and
  a test pins the first wait, so the code and the prose agree.

### Added

- **Tests for the retry path (`tests/test_retry_policy.py`).** It had none. The
  properties that were already correct — 5xx/429 and network errors retried,
  other 4xx not — are pinned alongside the new ones, so a later edit cannot
  lose them quietly. Counter-checks were run against all six properties; see
  the pull request.

### Added

- **Host/Origin allow-list for the HTTP transport (`MCP_ALLOWED_HOSTS`,
  SEC-005).** Comma-separated and **port-exact** — the names this server is
  reachable under, e.g. `bag.example.ch:8000`. Anything else is answered with
  421. Loopback stays allowed so container health checks keep working, and
  configured `MCP_CORS_ORIGINS` are folded into the transport's origin list;
  otherwise the transport would reject precisely the browser clients CORS
  opened the door for. A `*` origin is not copied across, since origins are
  compared literally.

  This is the inbound counterpart to the existing outbound egress allow-list:
  that one decides where this server may talk *to*, this one under which name it
  may be *addressed*. It is independent of `MCP_AUTH_TOKEN` — the token answers
  *who* is asking, the Host check *under which name* the server is addressed,
  and a DNS-rebinding attack runs in a browser that already holds a valid token.
  A test pins that: a valid `Bearer` still gets 421 for a foreign Host.

  **No behaviour change without the variable.** On a localhost bind the list is
  now stated explicitly instead of being inferred by the SDK from the bind
  address — same protection, no longer dependent on that inference. On a
  non-localhost bind it stays off, as before, and the startup warning now says
  so rather than leaving it to be inferred. It is deliberately not guessed: on
  `0.0.0.0` the reachable name is unknowable in-process, and a guessed list
  would reject the very deployment it is meant to protect.

  Both HTTP paths carry it: the auth/CORS-wrapped app served by uvicorn, and the
  SDK-served path via `mcp.run()` — `run()` forwards `transport_security` to the
  same app builder. Otherwise enabling the allow-list would have silently
  depended on whether auth or CORS happened to be configured.

  13 new tests, the load-bearing one being right hostname / wrong port —
  `evil.example.com` alone proves little, because a fallback loopback policy
  rejects it too.

## [0.3.0] - 2026-07-30

### Fixed

- **The User-Agent reports the actual package version again.** The published
  `0.2.3` sent `bag-health-mcp/0.1.0` to every upstream — the version string was
  hardcoded and had been left behind by earlier bumps. The version now comes
  from the package metadata, so it can no longer drift from the package.

### Added
- **Multi-source health indicators (2 new tools, 10 total — budget of 18 kept).**
  A single generic tool pair spans three additional Swiss health-data providers
  via a `source` parameter, instead of three source-specific tool families:
  - `bag_health_mcp__search_health_indicators(source, topic, region, year_from, year_to, …)`
  - `bag_health_mcp__get_indicator_series(source, indicator_id, region, year_from, year_to, …)`
  - Sources: **Obsan** (`ind.obsan.admin.ch`) via its clean JSON API
    `/api/<id>/g/json` (fallback `/gum/json`) — the workhorse, with 95% confidence
    intervals; **Versorgungsatlas** via its static catalogue `search/search_<lang>.json`
    (search) plus the per-aspect data files `/data/<id><aspect>_{ad,rz,ag}.json` — the
    `_rz` file returns a **cantonal** year/value series (26 cantons + a `CH` national
    total, with 95% CIs and a canton-vs-CH ratio), with a national age-group fallback
    (`_ag`); **Sucht Schweiz** HBSC youth series through Obsan's official mirror (the
    `zahlen-fakten` host serves only Tableau/PDF and was unreachable at probe time).
  - Anchor demo query: *«Wie hat sich der Alkoholkonsum bei 15-Jährigen … seit 2010
    entwickelt …»* — answered at national level; a `region_note` states honestly
    that HBSC has no cantonal breakdown.
  - Every response and both tool descriptions carry an `aggregate_statistics_notice`:
    aggregated population statistics, **not** individual advice (school-context safeguard).
- Live-probe notes for all three sources under `docs/probe-*.md` and the design
  rationale under `docs/tool-design-health-indicators.md`.

### Changed
- **Migrated to the `mcp` Python SDK 2.x** (`mcp[cli]>=2.0.0,<3`, was `>=1.28.1,<2`).
  Protocol-wise this is a no-op for existing clients (ARCH-012): the `initialize`
  handshake still negotiates at most `2025-11-25`, exactly as under 1.x. 2.x adds
  the `2026-07-28` "modern" revision, which is *not* reachable through the
  handshake and only applies to clients using the new modern path — verified
  against a live server (stdio negotiated `2025-11-25`). Breaking changes handled:
  - Server API moved from `mcp.server.fastmcp` to `mcp.server.mcpserver`;
    `FastMCP` is now `MCPServer`. No compatibility shim exists, so the package no
    longer imports under `mcp` 1.x — hence the hard `>=2.0.0` floor.
  - `MCPServer.settings` no longer carries `host`/`port`. The bind address is a
    `run()` kwarg, so `main()` passes host/port explicitly. `Settings` is a
    pydantic v2 model, so a leftover `mcp.settings.host = ...` raises
    `ValueError: "Settings" object has no field "host"` — loud, but only once
    the HTTP path actually executes, so it surfaces in CI for a server whose
    HTTP path is tested and at first HTTP startup for one whose isn't. A
    regression test asserts both the absence of the fields and the raise.
  - `mcp_types` 2.x renamed every model attribute to snake_case
    (`inputSchema` → `input_schema`, `isError` → `is_error`,
    `readOnlyHint` → `read_only_hint`, …). The **wire format is unchanged** —
    these are pydantic aliases — so the SEC-022 tool-definition hashes in
    `tool-hashes.json` are byte-identical before and after the migration.
  - `mcp.shared.memory.create_connected_server_and_client_session` was removed;
    the in-process test client is now `mcp.client.Client(mcp)`.
  - `streamable_http_app()` takes the bind host directly and auto-enables
    DNS-rebinding protection (Host/Origin allow-list) on a localhost bind — an
    inbound complement to the existing outbound DNS pinning (SEC-005). Non-local
    binds are unaffected and stay gateway-fronted (SEC-016).
  - Note: `ctx.info`/`ctx.warning` (SDK-003) now emit an `MCPDeprecationWarning`
    — SEP-2577 deprecates the server-to-client logging capability in the
    `2026-07-28` revision. The calls still work and have no replacement API, so
    the behaviour is unchanged; `ctx.report_progress` is unaffected.
- Egress allow-list (SEC-021) extended to `ind.obsan.admin.ch` and
  `www.versorgungsatlas.ch` (still a fixed HTTPS-only list with SSRF blocklist and
  DNS pinning); added `_get_with_retry` (exponential backoff 2s/4s/8s on 5xx/429/network)
  as the resilience default for the new upstreams.

### Known findings
- Obsan: not every indicator exposes `/g/json`; the server falls back to `/gum/json`.
- Versorgungsatlas: the value-file scheme was pinned via a headless network trace —
  `/data/<id><aspect>_{ad,rz,ag}.json` (the earlier `_kt` guess was wrong only in the
  third token). Files are served at the web root and fetch fine over `httpx`; the trace
  itself needed a direct connection because Chromium's `CONNECT` through the egress
  proxy reset. Cantonal values are now returned by `get_indicator_series`.

## [0.2.0] - 2026-05-31

This release lands the full remediation of a 40-point security/quality audit
(~20 PRs) on top of 0.1.0. It contains one **breaking change** (tool namespace
rename) — see below.

### Changed
- **BREAKING — tool namespace (SEC-022 #1):** all 8 tools are renamed from the
  `bag_*` prefix to the server-identity `bag_health_mcp__*` double-underscore
  format, preventing cross-server tool shadowing. Update client configurations
  that reference the old names:
  - `bag_list_diseases` → `bag_health_mcp__list_diseases`
  - `bag_list_series` → `bag_health_mcp__list_series`
  - `bag_get_series_details` → `bag_health_mcp__get_series_details`
  - `bag_get_disease_data` → `bag_health_mcp__get_disease_data`
  - `bag_get_canton_situation` → `bag_health_mcp__get_canton_situation`
  - `bag_list_export_files` → `bag_health_mcp__list_export_files`
  - `bag_download_export` → `bag_health_mcp__download_export`
  - `bag_get_data_version` → `bag_health_mcp__get_data_version`

### Added
- **Tool-definition hash pinning (SEC-022, rug-pull guard):** each tool's
  contract (name + description + input/output schema) is SHA-256-hashed and
  pinned in [`tool-hashes.json`](tool-hashes.json); CI fails on unacknowledged
  drift. Current truncated hashes (full values in the snapshot):
  - `bag_health_mcp__download_export`: `6317b4c45403fdaa…`
  - `bag_health_mcp__get_canton_situation`: `febc4225cdef1019…`
  - `bag_health_mcp__get_data_version`: `907ae6beaa4b4e38…`
  - `bag_health_mcp__get_disease_data`: `bc62ff4e955a24df…`
  - `bag_health_mcp__get_series_details`: `c7d41efa9c4d84e5…`
  - `bag_health_mcp__list_diseases`: `c927ae355fbd08cd…`
  - `bag_health_mcp__list_export_files`: `19f030929a8a873d…`
  - `bag_health_mcp__list_series`: `914bb949d3774be4…`

  Regenerate after an intentional tool change with
  `python scripts/tool_hashes.py --write`.

### Security
- **Egress hardening (SEC-004/005/021):** outbound traffic is restricted to the
  single allow-listed BAG IDD host with a resolved-IP blocklist and a
  DNS-pinning network backend that closes the TOCTOU/DNS-rebinding gap between
  resolution and connect.
- **Optional bearer-token auth (SEC-009):** set `MCP_AUTH_TOKEN` to require an
  `Authorization: Bearer <token>` header on every HTTP request (401 otherwise),
  compared in constant time. Unset = no auth (stdio/local unchanged).
- **Strict input validation (SEC-018):** all tool inputs are validated with
  strict Pydantic models.
- **Lethal-trifecta assessment (SEC-019)** documented: the server is strictly
  read-only and holds at most one of the three legs (see
  `docs/security-posture.md`).
- Dependency hash-pinning and gitleaks secret-scanning in CI (ARCH-005).

### Added
- **CORS support (SDK-004):** `MCP_CORS_ORIGINS` is an explicit origin
  allow-list (never a wildcard) for browser MCP clients; exposes the
  `Mcp-Session-Id` header for stateful sessions. Unset = no CORS.
- **Fully typed tool outputs (SDK-002)** with provenance metadata.
- **Structured JSON logging (OBS-001)** on stderr; raw upstream
  bodies/exceptions are never surfaced to the model (OBS-002).
- **Optional OpenTelemetry tracing** via the new `telemetry` extra and the
  standard `OTEL_*` environment variables.
- Hardened non-root multi-stage container plus Kubernetes `NetworkPolicy` and
  `Deployment` manifests under `deploy/`.
- Compliance/posture docs: ISDS classification, data classification, security
  posture, roadmap, and deployment & scaling guide under `docs/`.

### Changed
- **Module split (ARCH-011):** `server.py` is split into `_models.py` (Pydantic
  models) and `_tools.py` (tools/resources/prompts); `server.py` retains the
  infrastructure. No behaviour change.
- Error-contract and not-found handling consolidated (ARCH-002/003/004).

### New environment variables
- `MCP_TRANSPORT` — `stdio` (default) or `streamable-http`
- `MCP_HOST` / `MCP_PORT` — HTTP bind (default `127.0.0.1`)
- `MCP_LOG_LEVEL` — structured-log level
- `MCP_AUTH_TOKEN` — optional bearer-token gate (unset = no auth)
- `MCP_CORS_ORIGINS` — comma-separated CORS allow-list (unset = no CORS)

## [0.1.0] - 2026-04-01

### Added
- Initial release with BAG Infectious Disease Dashboard (IDD) integration
- **8 Tools**: `bag_list_diseases`, `bag_list_series`, `bag_get_series_details`, `bag_get_disease_data`, `bag_get_canton_situation`, `bag_list_export_files`, `bag_download_export`, `bag_get_data_version`
- 51 pathogens across 6 categories (respiratory, enteric, STI/bloodborne, vaccine-preventable, vector-borne, wastewater)
- Canton-level situational overview for school authorities
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
- Bilingual documentation (DE/EN)
- Unit and live integration tests (mocked HTTP via respx)
