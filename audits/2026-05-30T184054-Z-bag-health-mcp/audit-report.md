# MCP-Server Audit-Report — `bag-health-mcp`

**Audit-Datum:** 2026-05-30
**Skill-Version:** 1.0.0
**Catalog-Version:** v0.5.0 (68 checks)

---

## 1. Executive Summary

Server `bag-health-mcp` wurde gegen 47 anwendbare Best-Practice-Checks geprüft. 5 bestanden, 40 Findings dokumentiert (6 critical, 19 high, 15 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: ARCH-009, CH-005, CH-006, OBS-001, OBS-002, OPS-003, SCALE-002, SCALE-003, SDK-001, SDK-004, SEC-007, SEC-009, SEC-021.

**Production-Readiness:** NO

> ⚠️ **Zwei funktionale Defekte ausserhalb des Katalogs (während der Verifikation gefunden):**
> 1. **HTTP-Modus crasht beim Start.** `server.py:741` ruft `mcp.run(transport="streamable-http", port=port)`. Verifiziert gegen `mcp` 1.27.2 (frischer Install des Pins `mcp[cli]>=1.0.0`): `FastMCP.run()` hat die Signatur `run(transport, mount_path)` und akzeptiert **kein** `port`-Argument → `TypeError` beim Start. Damit crasht der gesamte `--http`-Pfad **und** der Docker-`CMD` (`--http --port 8000`) sofort. Der Cloud-/HTTP-Betrieb funktioniert aktuell nicht. (Betrifft direkt SCALE-001, SDK-001, SEC-016.)
> 2. **Falscher Entry-Point.** `pyproject.toml` `[project.scripts]` `bag-health-mcp = "bag_health_mcp.server:mcp.run"` zeigt auf eine gebundene Methode statt auf eine `main()`-Callable — das Konsolenskript ist nicht sauber aufrufbar.
>
> Beide sind S-Effort-Fixes, aber blockierend für jeden HTTP-/Cloud-Einsatz und sollten vor allen anderen Findings adressiert werden.

---

## 2. Profil-Snapshot

> Hinweis: Kein Notion-Audit-Tracker in dieser Session verfügbar. Das Profil wurde aus dem Repo-Code abgeleitet und mit `validate_profile.py` (exit 0, keine Placeholder/Schema-Fehler) bestätigt. Quelle: `audits/profile.yaml`.

| Feld | Wert | Belegt durch |
|---|---|---|
| Server-Name | `bag-health-mcp` | — |
| Repo-URL | https://github.com/malkreide/bag-health-mcp | — |
| Transport | `dual` (stdio default + streamable-http via `--http`) | server.py:737-743 |
| SDK-Sprache | Python (FastMCP) | server.py:15 |
| Auth-Modell | `none` (IDD API ist öffentlich) | server.py:5-6, README.md:68 |
| Datenklasse | `Public Open Data` (BAG IDD) | — |
| Schreibzugriff | `read-only` (`write_capable=false`) | nur GET + Query-POST |
| Deployment | `local-stdio`, `andere` (Dockerfile/HTTP) | Dockerfile:10-12 |
| Cloud-deployed (derived) | `true` | EXPOSE 8000 |
| Externe Requests | `true` → api.idd.bag.admin.ch | server.py:22,55-64 |
| Filesystem-Tools | `false` | — |
| Kontext | Stadt Zürich / Schulamt / Volksschule | server.py:585-592,724-728 |
| Datenquelle | BAG Infectious Disease Dashboard (IDD), Swiss Open Data | server.py:22 |
| Audit-Datum | 2026-05-30 | — |
| Skill-Version | 1.0.0 | — |
| Catalog-Version | v0.5.0 (68 checks), catalog_hash `091f446b…93c0` | — |

---

## 3. Applicability

### Coverage pro Kategorie (anwendbar / gesamt)

| Kategorie | anwendbar | gesamt | Anteil |
|---|---|---|---|
| ARCH | 11 | 12 | 92% |
| SDK | 4 | 5 | 80% |
| SEC | 15 | 23 | 65% |
| SCALE | 6 | 6 | 100% |
| OBS | 5 | 6 | 83% |
| OPS | 3 | 3 | 100% |
| CH | 3 | 8 | 38% |
| HITL | 0 | 5 | 0% |
| **Total** | **47** | **68** | **69%** |

_Nicht anwendbar (Beispiele): OAuth-/Confused-Deputy- und Session-Hijacking-Checks (`auth_model=none`), HITL/Sampling-Checks (`write_capable=false`, kein Sampling), PII-/DSG-Checks (`Public Open Data`). Nicht-anwendbare Checks erscheinen bewusst gar nicht im Report._

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 3 | 3 | 5 | 0 | 0 |
| CH | 0 | 2 | 1 | 0 | 0 |
| OBS | 0 | 4 | 1 | 0 | 0 |
| OPS | 1 | 1 | 1 | 0 | 0 |
| SCALE | 0 | 5 | 1 | 0 | 0 |
| SDK | 0 | 3 | 1 | 0 | 0 |
| SEC | 1 | 3 | 9 | 2 | 0 |
| **Total** | **5** | **21** | **19** | **2** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| OBS-004 | OBS | critical | partial |
| SEC-004 | SEC | critical | partial |
| SEC-009 | SEC | critical | fail |
| SEC-016 | SEC | critical | partial |
| SEC-019 | SEC | critical | partial |
| ARCH-004 | ARCH | high | partial |
| ARCH-009 | ARCH | high | fail |
| CH-005 | CH | high | fail |
| CH-006 | CH | high | fail |
| OBS-001 | OBS | high | fail |
| OBS-002 | OBS | high | fail |
| OPS-003 | OPS | high | fail |
| SCALE-001 | SCALE | high | partial |
| SCALE-002 | SCALE | high | fail |
| SCALE-003 | SCALE | high | fail |
| SDK-001 | SDK | high | fail |
| SDK-004 | SDK | high | fail |
| SEC-005 | SEC | high | partial |
| SEC-006 | SEC | high | partial |
| SEC-007 | SEC | high | fail |
| SEC-013 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | fail |
| SEC-022 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-008 | ARCH | medium | fail |
| ARCH-011 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | fail |
| CH-004 | CH | medium | partial |
| OBS-003 | OBS | medium | fail |
| OBS-006 | OBS | medium | fail |
| OPS-002 | OPS | medium | partial |
| SCALE-004 | SCALE | medium | fail |
| SCALE-005 | SCALE | medium | fail |
| SCALE-006 | SCALE | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | fail |
| SEC-008 | SEC | medium | partial |

**Gesamt:** 40 Findings

---

## 5. Detail-Findings

### ARCH-002

## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-002` |
| **PDF-Reference** | Sec 2.2 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `src/bag_health_mcp/server.py:173-178 — descriptions well above 100 chars, multi-sentence with usage hints`
- `src/bag_health_mcp/server.py:585-592 — canton_situation description includes anchor query`

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-002` (Tool-Beschreibung mit Use-Case-Tags). Folgendes fehlt / ist unvollständig:

1. No structured <use_case>/<important_notes>/<example> tags in any tool description — fails use-case-tag criterion (>=80% of tools)

### Evidence

- `src/bag_health_mcp/server.py:173-178 — descriptions well above 100 chars, multi-sentence with usage hints`
- `src/bag_health_mcp/server.py:585-592 — canton_situation description includes anchor query`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No structured <use_case>/<important_notes>/<example> tags in any tool description — fails use-case-tag criterion (>=80% of tools)

Detail-Schritte und Code-Pattern siehe `checks/ARCH-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `src/bag_health_mcp/server.py:245-249 — bag_list_series returns {error,hint} not bare empty list`
- `src/bag_health_mcp/server.py:411-417 — error+actionable hint on API failure`
- `src/bag_health_mcp/server.py:676 — canton_situation returns {status:'no_data'}`

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-003` («Not Found» Anti-Pattern: Heuristiken statt leerer Antworten). Folgendes fehlt / ist unvollständig:

1. No fuzzy-match/suggestion mechanism on no-results; no match_type field
2. Empty topic/series returns 'error' string rather than structured heuristic with related suggestions

### Evidence

- `src/bag_health_mcp/server.py:245-249 — bag_list_series returns {error,hint} not bare empty list`
- `src/bag_health_mcp/server.py:411-417 — error+actionable hint on API failure`
- `src/bag_health_mcp/server.py:676 — canton_situation returns {status:'no_data'}`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No fuzzy-match/suggestion mechanism on no-results; no match_type field
2. Empty topic/series returns 'error' string rather than structured heuristic with related suggestions

Detail-Schritte und Code-Pattern siehe `checks/ARCH-003.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-003` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-004

## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-004` |
| **PDF-Reference** | Sec 2.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- src/bag_health_mcp/server.py — no request/transport internals leak into handlers; handlers take only Pydantic input models
- `src/bag_health_mcp/server.py:737-743 — both stdio and streamable-http from one codebase`
- tool business logic identical regardless of transport

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-004` (Inversion of Control: Transport-agnostische Server-Logik). Folgendes fehlt / ist unvollständig:

1. No Pydantic BaseSettings/Settings object; config read ad-hoc from sys.argv (server.py:738-740)
2. No shared lifespan; new httpx.AsyncClient per call via _client() (server.py:55)

### Evidence

- src/bag_health_mcp/server.py — no request/transport internals leak into handlers; handlers take only Pydantic input models
- `src/bag_health_mcp/server.py:737-743 — both stdio and streamable-http from one codebase`
- tool business logic identical regardless of transport

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No Pydantic BaseSettings/Settings object; config read ad-hoc from sys.argv (server.py:738-740)
2. No shared lifespan; new httpx.AsyncClient per call via _client() (server.py:55)

Detail-Schritte und Code-Pattern siehe `checks/ARCH-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-005

## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `src/bag_health_mcp/server.py — no hardcoded keys/passwords/tokens (secret grep clean); API is auth-none (README.md:68,137)`
- `src/bag_health_mcp/server.py:22-24 — only constants are public base URL + User-Agent`
- Dockerfile:1-12 — no ENV secret lines

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-005` (Keine Hardcoded Secrets: Env-Vars / Secret Manager only). Folgendes fehlt / ist unvollständig:

1. No .gitignore (no ignore for .env/secrets)
2. No .env.example
3. No secret-scanning (gitleaks/trufflehog) in CI workflows
4. No Pydantic SecretStr/Settings pattern (moot today, criterion unmet)

### Evidence

- `src/bag_health_mcp/server.py — no hardcoded keys/passwords/tokens (secret grep clean); API is auth-none (README.md:68,137)`
- `src/bag_health_mcp/server.py:22-24 — only constants are public base URL + User-Agent`
- Dockerfile:1-12 — no ENV secret lines

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No .gitignore (no ignore for .env/secrets)
2. No .env.example
3. No secret-scanning (gitleaks/trufflehog) in CI workflows
4. No Pydantic SecretStr/Settings pattern (moot today, criterion unmet)

Detail-Schritte und Code-Pattern siehe `checks/ARCH-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-008

## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-008` |
| **PDF-Reference** | Anhang A2 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- src/bag_health_mcp/server.py — only @mcp.tool used; no @mcp.resource or @mcp.prompt despite read-only/idempotent data tools that are Resource candidates

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-008` (Drei Primitive nutzen: Tools, Resources und Prompts). Folgendes fehlt / ist unvollständig:

1. Server uses only Tools (1 of 3 primitives)
2. No README justification for Tools-only choice

### Evidence

- src/bag_health_mcp/server.py — only @mcp.tool used; no @mcp.resource or @mcp.prompt despite read-only/idempotent data tools that are Resource candidates

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Server uses only Tools (1 of 3 primitives)
2. No README justification for Tools-only choice

Detail-Schritte und Code-Pattern siehe `checks/ARCH-008.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-008` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-009

## Finding: ARCH-009 — Tool Annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-009` |
| **PDF-Reference** | Anhang A5 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- src/bag_health_mcp/server.py — no annotations/readOnlyHint/destructiveHint/idempotentHint/openWorldHint on any tool; all 8 use description= only

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-009` (Tool Annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint). Folgendes fehlt / ist unvollständig:

1. All tools read-only + reach external API (openWorldHint applies) yet no annotations declared; host must treat every call pessimistically
2. No annotations policy table in README/docs

### Evidence

- src/bag_health_mcp/server.py — no annotations/readOnlyHint/destructiveHint/idempotentHint/openWorldHint on any tool; all 8 use description= only

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. All tools read-only + reach external API (openWorldHint applies) yet no annotations declared; host must treat every call pessimistically
2. No annotations policy table in README/docs

Detail-Schritte und Code-Pattern siehe `checks/ARCH-009.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-009` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-011

## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-011` |
| **PDF-Reference** | Anhang A8 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml all present
- src/, tests/, .github/workflows/ all present
- src-layout correct: pyproject.toml:55-56 packages=['src/bag_health_mcp']

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-011` (Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)). Folgendes fehlt / ist unvollständig:

1. 8 tools all in single 743-line server.py, no tools/ split (expects tools/ + server.py <200 lines)
2. README.de.md sections not parallel to README.md

### Evidence

- README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml all present
- src/, tests/, .github/workflows/ all present
- src-layout correct: pyproject.toml:55-56 packages=['src/bag_health_mcp']

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. 8 tools all in single 743-line server.py, no tools/ split (expects tools/ + server.py <200 lines)
2. README.de.md sections not parallel to README.md

Detail-Schritte und Code-Pattern siehe `checks/ARCH-011.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-011` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- `src/bag_health_mcp/server.py:37-48 — FastMCP with no protocol_version pin`
- CHANGELOG.md present in Keep-a-Changelog format

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-012` (protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin). Folgendes fehlt / ist unvollständig:

1. protocolVersion not pinned — relies on SDK default, can break on SDK update
2. CHANGELOG entries reference no MCP spec version
3. No protocol-version/update-policy section in READMEs
4. No dependabot.yml/renovate.json

### Evidence

- `src/bag_health_mcp/server.py:37-48 — FastMCP with no protocol_version pin`
- CHANGELOG.md present in Keep-a-Changelog format

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. protocolVersion not pinned — relies on SDK default, can break on SDK update
2. CHANGELOG entries reference no MCP spec version
3. No protocol-version/update-policy section in READMEs
4. No dependabot.yml/renovate.json

Detail-Schritte und Code-Pattern siehe `checks/ARCH-012.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-012` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### CH-004

## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `CH-004` |
| **PDF-Reference** | Custom (OGD-CH-Richtlinien) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- README.md:138 documents data licence (public domain / OGD)
- README.md:154 / README.de.md:97 repeat source+licence (MIT code, public-domain/OGD data)
- server.py:308,491 emit 'source' field but only passthrough of data.get('source') — no controlled license/provenance
- server.py:714-730 canton_situation return has no source/license field

### Expected Behavior

Erfüllung der Pass-Criteria von `CH-004` (OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution). Folgendes fehlt / ist unvollständig:

1. No controlled license/attribution field in tool responses; no provenance field
2. README declares 'public domain' rather than required CC BY 4.0 attribution; no Datenquellen-&-Lizenzen table
3. Schulamt tool output omits source/license entirely

### Evidence

- README.md:138 documents data licence (public domain / OGD)
- README.md:154 / README.de.md:97 repeat source+licence (MIT code, public-domain/OGD data)
- server.py:308,491 emit 'source' field but only passthrough of data.get('source') — no controlled license/provenance
- server.py:714-730 canton_situation return has no source/license field

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No controlled license/attribution field in tool responses; no provenance field
2. README declares 'public domain' rather than required CC BY 4.0 attribution; no Datenquellen-&-Lizenzen table
3. Schulamt tool output omits source/license entirely

Detail-Schritte und Code-Pattern siehe `checks/CH-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `CH-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### CH-005

## Finding: CH-005 — ISDS Stadt Zürich Schutzbedarfsklasse-Mapping

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `CH-005` |
| **PDF-Reference** | Custom (ISDS-Richtlinie Stadt Zürich) |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No docs/ directory; no isds-klassifikation.md
- No isds/schutzbedarf/vertraulich/integrität/verfügbarkeit/oiz hits in any .md/.py/.toml

### Expected Behavior

Erfüllung der Pass-Criteria von `CH-005` (ISDS Stadt Zürich Schutzbedarfsklasse-Mapping). Folgendes fehlt / ist unvollständig:

1. No ISDS classification document despite stadt_zuerich_context=true (mandatory)
2. No per-Schutzziel ratings with justifications
3. No Massnahmen-Mapping per class; no OIZ sign-off

### Evidence

- No docs/ directory; no isds-klassifikation.md
- No isds/schutzbedarf/vertraulich/integrität/verfügbarkeit/oiz hits in any .md/.py/.toml

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No ISDS classification document despite stadt_zuerich_context=true (mandatory)
2. No per-Schutzziel ratings with justifications
3. No Massnahmen-Mapping per class; no OIZ sign-off

Detail-Schritte und Code-Pattern siehe `checks/CH-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `CH-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### CH-006

## Finding: CH-006 — Schulamt Klassifikationsschema: BUI/Vertraulich/Streng-Vertraulich

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `CH-006` |
| **PDF-Reference** | Custom (Stadt Zürich Klassifikations-Schema) |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No klassifikation/classification document; no docs/ dir
- `No BUI/vertraulich/streng-vertraulich declaration; only README.md:134/README.de.md:93 'aggregated and anonymised at canton level'`
- canton_situation (server.py:593-730) has no k_anonymity/min_class_size/aggregation_threshold control

### Expected Behavior

Erfüllung der Pass-Criteria von `CH-006` (Schulamt Klassifikationsschema: BUI/Vertraulich/Streng-Vertraulich). Folgendes fehlt / ist unvollständig:

1. No BUI/VERT/SVERT classification scheme documented despite schulamt_context=true (mandatory)
2. Highest level not declared; no Massnahmen-Mapping
3. Aggregation-risk not addressed; no documented min-group-size on the aggregating tool

### Evidence

- No klassifikation/classification document; no docs/ dir
- `No BUI/vertraulich/streng-vertraulich declaration; only README.md:134/README.de.md:93 'aggregated and anonymised at canton level'`
- canton_situation (server.py:593-730) has no k_anonymity/min_class_size/aggregation_threshold control

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No BUI/VERT/SVERT classification scheme documented despite schulamt_context=true (mandatory)
2. Highest level not declared; no Massnahmen-Mapping
3. Aggregation-risk not addressed; no documented min-group-size on the aggregating tool

Detail-Schritte und Code-Pattern siehe `checks/CH-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `CH-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-001` |
| **PDF-Reference** | Sec 6.1 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- All tools return plain {error:...} dicts instead of MCP tool-results with isError:true — server.py:246-249,281-284,292-295,410-417,537-541
- No isError flag anywhere; no TextContent usage
- No standardized JSON-RPC error codes in src/
- raise_for_status() at server.py:182,241,296,350,515,568 lets execution-class HTTP failures bubble up as protocol errors
- tests have no execution-error/protocol-error contract test

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-001` (Protocol vs. Execution Errors: korrekte Trennung). Folgendes fehlt / ist unvollständig:

1. Convert app errors (404, not-found, non-200) to tool-results with isError:true
2. Use standardized JSON-RPC codes for genuine protocol errors
3. Add execution-error + protocol-error tests

### Evidence

- All tools return plain {error:...} dicts instead of MCP tool-results with isError:true — server.py:246-249,281-284,292-295,410-417,537-541
- No isError flag anywhere; no TextContent usage
- No standardized JSON-RPC error codes in src/
- raise_for_status() at server.py:182,241,296,350,515,568 lets execution-class HTTP failures bubble up as protocol errors
- tests have no execution-error/protocol-error contract test

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Convert app errors (404, not-found, non-200) to tool-results with isError:true
2. Use standardized JSON-RPC codes for genuine protocol errors
3. Add execution-error + protocol-error tests

Detail-Schritte und Code-Pattern siehe `checks/OBS-001.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-001` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-002` |
| **PDF-Reference** | Sec 6.2 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- FastMCP initialized WITHOUT mask_error_details — server.py:37-48
- Raw upstream body leaked to LLM: server.py:412 'detail': r.text[:500]
- Raw exception leaked: server.py:708 return {error: str(e)}
- Unhandled raise_for_status() (server.py:182,241,296,350,515,542,568) reach FastMCP

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-002` (Mask Error Details: keine Stacktraces / SQL ans LLM). Folgendes fehlt / ist unvollständig:

1. Set mask_error_details=True on FastMCP
2. Remove r.text[:500] and str(e) from returns; log originals server-side only

### Evidence

- FastMCP initialized WITHOUT mask_error_details — server.py:37-48
- Raw upstream body leaked to LLM: server.py:412 'detail': r.text[:500]
- Raw exception leaked: server.py:708 return {error: str(e)}
- Unhandled raise_for_status() (server.py:182,241,296,350,515,542,568) reach FastMCP

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Set mask_error_details=True on FastMCP
2. Remove r.text[:500] and str(e) from returns; log originals server-side only

Detail-Schritte und Code-Pattern siehe `checks/OBS-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No structlog/loguru in pyproject.toml or anywhere
- No logging in src/ — no import logging/logger./structlog
- No bound context (tool name/session_id/correlation_id), no severity levels

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-003` (Structured Logging mit RFC 5424 Severity-Stufen). Folgendes fehlt / ist unvollständig:

1. Add structlog (JSON output)
2. Emit structured logs per tool-call with bound context and >=4 severity levels

### Evidence

- No structlog/loguru in pyproject.toml or anywhere
- No logging in src/ — no import logging/logger./structlog
- No bound context (tool name/session_id/correlation_id), no severity levels

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Add structlog (JSON output)
2. Emit structured logs per tool-call with bound context and >=4 severity levels

Detail-Schritte und Code-Pattern siehe `checks/OBS-003.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-003` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OBS-004

## Finding: OBS-004 — stderr für stdio-Server: stdout reserviert für Protocol

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-004` |
| **PDF-Reference** | Sec 6.3 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No print() statements in src/ (passes hard criterion)
- Transport dual: stdio default (server.py:743) + streamable-http (server.py:741)
- No logging to stdout exists because there is no logging at all

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-004` (stderr für stdio-Server: stdout reserviert für Protocol). Folgendes fehlt / ist unvollständig:

1. No explicit stderr configuration (no logging.basicConfig(stream=sys.stderr))
2. Once logging added (OBS-003), explicitly route to sys.stderr; add CI guard against print()

### Evidence

- No print() statements in src/ (passes hard criterion)
- Transport dual: stdio default (server.py:743) + streamable-http (server.py:741)
- No logging to stdout exists because there is no logging at all

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No explicit stderr configuration (no logging.basicConfig(stream=sys.stderr))
2. Once logging added (OBS-003), explicitly route to sys.stderr; add CI guard against print()

Detail-Schritte und Code-Pattern siehe `checks/OBS-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- is_cloud_deployed=true so check applies (HTTP at server.py:741)
- No opentelemetry/otel anywhere — not in src/ or pyproject.toml
- No TracerProvider/OTLP exporter/HTTPXClientInstrumentor/per-tool spans
- No OTEL_* config

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-006` (OpenTelemetry Distributed Tracing pro Tool-Call). Folgendes fehlt / ist unvollständig:

1. Add OpenTelemetry SDK + OTLP exporter, instrument httpx, wrap each tool in a span (no PII), env-configurable endpoint

### Evidence

- is_cloud_deployed=true so check applies (HTTP at server.py:741)
- No opentelemetry/otel anywhere — not in src/ or pyproject.toml
- No TracerProvider/OTLP exporter/HTTPXClientInstrumentor/per-tool spans
- No OTEL_* config

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Add OpenTelemetry SDK + OTLP exporter, instrument httpx, wrap each tool in a span (no PII), env-configurable endpoint

Detail-Schritte und Code-Pattern siehe `checks/OBS-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OPS-002

## Finding: OPS-002 — Doku-Standard: bilingualer README, ASCII-Diagramm, Limits-Sektion

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OPS-002` |
| **PDF-Reference** | Anhang C2 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Both READMEs exist; CHANGELOG Keep-a-Changelog; CONTRIBUTING present
- Anchor demo query natural-language: README.md:14-30, README.de.md:12-18
- ASCII architecture diagram: README.md:73-80
- Known Limitations >3: README.md:143-148, README.de.md:102-107
- `Tools overview, Installation (uvx+HTTP), Security/Limits: README.md:34-45,84-104,129-139`

### Expected Behavior

Erfüllung der Pass-Criteria von `OPS-002` (Doku-Standard: bilingualer README, ASCII-Diagramm, Limits-Sektion). Folgendes fehlt / ist unvollständig:

1. README.de.md not in section parity: missing ASCII diagram, HTTP/Cloud install, Tools/Topics table, License section
2. No architecture diagram in README.de.md

### Evidence

- Both READMEs exist; CHANGELOG Keep-a-Changelog; CONTRIBUTING present
- Anchor demo query natural-language: README.md:14-30, README.de.md:12-18
- ASCII architecture diagram: README.md:73-80
- Known Limitations >3: README.md:143-148, README.de.md:102-107
- `Tools overview, Installation (uvx+HTTP), Security/Limits: README.md:34-45,84-104,129-139`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. README.de.md not in section parity: missing ASCII diagram, HTTP/Cloud install, Tools/Topics table, License section
2. No architecture diagram in README.de.md

Detail-Schritte und Code-Pattern siehe `checks/OPS-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OPS-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OPS-003` |
| **PDF-Reference** | Anhang C4 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- `No explicit phase declaration in READMEs/CHANGELOG — only README.md:133 'Read-only — no write operations' safety cell`
- No docs/ dir, no roadmap.md
- No phase status table/transition prerequisites
- Server de-facto read-only (write_capable=false) consistent with Phase 1 but undeclared

### Expected Behavior

Erfüllung der Pass-Criteria von `OPS-003` (Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent). Folgendes fehlt / ist unvollständig:

1. Add explicit Phase 1 (read-only wrapper) declaration with status table to both READMEs
2. Add docs/roadmap.md with phase tasks + transition prerequisites

### Evidence

- `No explicit phase declaration in READMEs/CHANGELOG — only README.md:133 'Read-only — no write operations' safety cell`
- No docs/ dir, no roadmap.md
- No phase status table/transition prerequisites
- Server de-facto read-only (write_capable=false) consistent with Phase 1 but undeclared

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Add explicit Phase 1 (read-only wrapper) declaration with status table to both READMEs
2. Add docs/roadmap.md with phase tasks + transition prerequisites

Detail-Schritte und Code-Pattern siehe `checks/OPS-003.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OPS-003` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SCALE-001

## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-001` |
| **PDF-Reference** | Sec 5.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- server.py:737-743 — dual transport, --http -> streamable-http, else stdio
- Dockerfile:11 — CMD runs --http --port 8000, cloud image uses streamable-http
- README.md:99-104 documents --http cloud invocation

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-001` (Streamable HTTP statt stdio für Cloud-Deployments). Folgendes fehlt / ist unvollständig:

1. Transport selection CLI-flag based, not ENV-based (no MCP_TRANSPORT)
2. No deployment manifest sets transport explicitly
3. Host not set to 0.0.0.0 explicitly (relies on FastMCP default)

### Evidence

- server.py:737-743 — dual transport, --http -> streamable-http, else stdio
- Dockerfile:11 — CMD runs --http --port 8000, cloud image uses streamable-http
- README.md:99-104 documents --http cloud invocation

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Transport selection CLI-flag based, not ENV-based (no MCP_TRANSPORT)
2. No deployment manifest sets transport explicitly
3. Host not set to 0.0.0.0 explicitly (relies on FastMCP default)

Detail-Schritte und Code-Pattern siehe `checks/SCALE-001.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-001` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-002` |
| **PDF-Reference** | Sec 5.2 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No sticky-session config: no railway.toml/render.yaml/compose/k8s manifests
- No redis/memcached/session_manager/stick/sessionAffinity anywhere
- server.py:37-48 — FastMCP with no session_manager / shared-state backend; sessions in pod memory only

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-002` (Stateful Load Balancing für Streamable HTTP / SSE). Folgendes fehlt / ist unvollständig:

1. Neither sticky-session nor shared-state session manager implemented
2. No session TTL
3. Cloud-deployed dual transport with in-memory session state breaks on pod switch/restart

### Evidence

- No sticky-session config: no railway.toml/render.yaml/compose/k8s manifests
- No redis/memcached/session_manager/stick/sessionAffinity anywhere
- server.py:37-48 — FastMCP with no session_manager / shared-state backend; sessions in pod memory only

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Neither sticky-session nor shared-state session manager implemented
2. No session TTL
3. Cloud-deployed dual transport with in-memory session state breaks on pod switch/restart

Detail-Schritte und Code-Pattern siehe `checks/SCALE-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**L** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-003` |
| **PDF-Reference** | Sec 5.2 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No HAProxy/NGINX/Ingress config in repo
- No stick-table/Mcp-Session-Id/affinity config
- Repo has only Dockerfile + workflows; no edge-LB layer

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-003` (Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)). Folgendes fehlt / ist unvollständig:

1. No Edge-LB reads Mcp-Session-Id for routing
2. No stick-table/hash, no TTL, no failover
3. is_cloud_deployed + dual transport means check applies and unmet

### Evidence

- No HAProxy/NGINX/Ingress config in repo
- No stick-table/Mcp-Session-Id/affinity config
- Repo has only Dockerfile + workflows; no edge-LB layer

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No Edge-LB reads Mcp-Session-Id for routing
2. No stick-table/hash, no TTL, no failover
3. is_cloud_deployed + dual transport means check applies and unmet

Detail-Schritte und Code-Pattern siehe `checks/SCALE-003.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**L** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-003` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-004` |
| **PDF-Reference** | Sec 5.3 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- Dockerfile:1 — single FROM python:3.12-slim (not multi-stage)
- Dockerfile:7 — pip install -e . in final image
- No USER directive (runs as root); no HEALTHCHECK

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-004` (Containerization mit Multi-Stage-Builds). Folgendes fehlt / ist unvollständig:

1. Not multi-stage
2. Runs as root (no non-root USER)
3. No HEALTHCHECK for LB integration
4. Editable-install/build tooling left in final image

### Evidence

- Dockerfile:1 — single FROM python:3.12-slim (not multi-stage)
- Dockerfile:7 — pip install -e . in final image
- No USER directive (runs as root); no HEALTHCHECK

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Not multi-stage
2. Runs as root (no non-root USER)
3. No HEALTHCHECK for LB integration
4. Editable-install/build tooling left in final image

Detail-Schritte und Code-Pattern siehe `checks/SCALE-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SCALE-005

## Finding: SCALE-005 — MCP-Gateway für Enterprise (Anti-Shadow-MCP)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-005` |
| **PDF-Reference** | Sec 5.3 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No gateway/proxy/allowlist in READMEs or src/
- No tool-allowlist/mcp-policy files
- README.md:99-104 documents direct --http access, project targets Stadt Zürich Schulamt context

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-005` (MCP-Gateway für Enterprise (Anti-Shadow-MCP)). Folgendes fehlt / ist unvollständig:

1. No MCP gateway architecture documented despite Stadt Zürich/Schulamt context
2. No tool allow-list, no SIEM audit-log export, no justification for direct access

### Evidence

- No gateway/proxy/allowlist in READMEs or src/
- No tool-allowlist/mcp-policy files
- README.md:99-104 documents direct --http access, project targets Stadt Zürich Schulamt context

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No MCP gateway architecture documented despite Stadt Zürich/Schulamt context
2. No tool allow-list, no SIEM audit-log export, no justification for direct access

Detail-Schritte und Code-Pattern siehe `checks/SCALE-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**L** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No K8s/compose/railway manifests; no resources/limits anywhere
- Dockerfile:1-13 sets no ulimits, no restart policy, no memory/CPU constraints

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-006` (Resource-Limits per Container (Memory, CPU, FDs)). Folgendes fehlt / ist unvollständig:

1. No memory limit
2. No CPU limit
3. No FD/ulimit config (relevant — httpx.AsyncClient per-call, server.py:55-64)
4. No OOM/restart-policy; is_cloud_deployed so check applies and unmet

### Evidence

- No K8s/compose/railway manifests; no resources/limits anywhere
- Dockerfile:1-13 sets no ulimits, no restart policy, no memory/CPU constraints

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No memory limit
2. No CPU limit
3. No FD/ulimit config (relevant — httpx.AsyncClient per-call, server.py:55-64)
4. No OOM/restart-policy; is_cloud_deployed so check applies and unmet

Detail-Schritte und Code-Pattern siehe `checks/SCALE-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SDK-001

## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-001` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- server.py:37-48 — FastMCP() with NO lifespan= argument
- No @asynccontextmanager/lifespan/AsyncExitStack in src/
- server.py:55-64 _client() returns fresh httpx.AsyncClient; every tool uses 'async with _client()' — new client per call, no pooling
- server.py:710-712 — canton_situation fans out 5+ tasks, each opening 2 clients (~10 fresh clients per call)

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-001` (FastMCP Lifespan via @asynccontextmanager + AsyncExitStack). Folgendes fehlt / ist unvollständig:

1. No @asynccontextmanager lifespan
2. FastMCP constructor missing lifespan=
3. No connection pooling; matches documented fail-pattern (httpx client per call)

### Evidence

- server.py:37-48 — FastMCP() with NO lifespan= argument
- No @asynccontextmanager/lifespan/AsyncExitStack in src/
- server.py:55-64 _client() returns fresh httpx.AsyncClient; every tool uses 'async with _client()' — new client per call, no pooling
- server.py:710-712 — canton_situation fans out 5+ tasks, each opening 2 clients (~10 fresh clients per call)

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No @asynccontextmanager lifespan
2. FastMCP constructor missing lifespan=
3. No connection pooling; matches documented fail-pattern (httpx client per call)

Detail-Schritte und Code-Pattern siehe `checks/SDK-001.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-001` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- pyproject.toml — pydantic>=2.0.0 (v2 satisfied)
- All 8 tools annotate -> dict[str,Any] (acceptable per criteria)
- `Inputs use Pydantic BaseModel with Field/Literal (server.py:91-166)`

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-002` (Pydantic v2 / TypedDict / Dataclass als Tool-Returns). Folgendes fehlt / ist unvollständig:

1. Returns are plain dict[str,Any] not BaseModel/TypedDict — no precise structured output schema in tools/list
2. No consistent response envelope across tools
3. No provenance field; source/source_date only on some tools

### Evidence

- pyproject.toml — pydantic>=2.0.0 (v2 satisfied)
- All 8 tools annotate -> dict[str,Any] (acceptable per criteria)
- `Inputs use Pydantic BaseModel with Field/Literal (server.py:91-166)`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Returns are plain dict[str,Any] not BaseModel/TypedDict — no precise structured output schema in tools/list
2. No consistent response envelope across tools
3. No provenance field; source/source_date only on some tools

Detail-Schritte und Code-Pattern siehe `checks/SDK-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- `No Context/report_progress/ctx. in src/ — no tool declares ctx: Context`
- server.py:593-730 canton_situation runs gather over 5+ series with many round-trips (>2s) but no progress
- server.py:707-708 — errors swallowed into {error:str(e)} not ctx.warning/error
- No FastMCP Context import

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-003` (Context Injection für Progress Reports und Logging). Folgendes fehlt / ist unvollständig:

1. No Context injection in any tool
2. No ctx.report_progress() on the long-running multi-series tool
3. No ctx structured logging to client

### Evidence

- `No Context/report_progress/ctx. in src/ — no tool declares ctx: Context`
- server.py:593-730 canton_situation runs gather over 5+ series with many round-trips (>2s) but no progress
- server.py:707-708 — errors swallowed into {error:str(e)} not ctx.warning/error
- No FastMCP Context import

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No Context injection in any tool
2. No ctx.report_progress() on the long-running multi-series tool
3. No ctx structured logging to client

Detail-Schritte und Code-Pattern siehe `checks/SDK-003.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-003` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-004` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No CORSMiddleware/cors/allow_origins/expose_headers in src/
- server.py:737-743 — HTTP mode calls mcp.run(transport='streamable-http') with no Starlette middleware/CORS
- Dockerfile:11 — server deployed in HTTP mode (cloud), so check applies

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-004` (CORS Mcp-Session-Id Exposure bei HTTP/SSE). Folgendes fehlt / ist unvollständig:

1. No CORS middleware at all
2. Mcp-Session-Id not in expose_headers — browser cross-origin clients cannot read session id, breaking stateful sessions
3. Mcp-Session-Id not in allow_headers; no explicit allow_origins

### Evidence

- No CORSMiddleware/cors/allow_origins/expose_headers in src/
- server.py:737-743 — HTTP mode calls mcp.run(transport='streamable-http') with no Starlette middleware/CORS
- Dockerfile:11 — server deployed in HTTP mode (cloud), so check applies

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No CORS middleware at all
2. Mcp-Session-Id not in expose_headers — browser cross-origin clients cannot read session id, breaking stateful sessions
3. Mcp-Session-Id not in allow_headers; no explicit allow_origins

Detail-Schritte und Code-Pattern siehe `checks/SDK-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-004` |
| **PDF-Reference** | Sec 4.4 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Base URL hardcoded to HTTPS: IDD_BASE='https://api.idd.bag.admin.ch' (server.py:22); all requests via _client() with base_url=IDD_BASE (server.py:55-64)
- No user/LLM-supplied URLs reach the HTTP client — tool args are slugs/Literal enums interpolated into fixed API paths
- No urlparse, no IP blocklist, no 169.254.169.254/metadata blocking, no egress proxy in src/

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-004` (SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting). Folgendes fehlt / ist unvollständig:

1. No explicit HTTPS-scheme enforcement or IP blocklist as required by Pass Criteria — relies solely on hardcoded base_url
2. follow_redirects=True (server.py:63) means a compromised upstream could 30x-redirect to an internal IP; no resolved-IP validation, no DNS pinning

### Evidence

- Base URL hardcoded to HTTPS: IDD_BASE='https://api.idd.bag.admin.ch' (server.py:22); all requests via _client() with base_url=IDD_BASE (server.py:55-64)
- No user/LLM-supplied URLs reach the HTTP client — tool args are slugs/Literal enums interpolated into fixed API paths
- No urlparse, no IP blocklist, no 169.254.169.254/metadata blocking, no egress proxy in src/

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No explicit HTTPS-scheme enforcement or IP blocklist as required by Pass Criteria — relies solely on hardcoded base_url
2. follow_redirects=True (server.py:63) means a compromised upstream could 30x-redirect to an internal IP; no resolved-IP validation, no DNS pinning

Detail-Schritte und Code-Pattern siehe `checks/SEC-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-005` |
| **PDF-Reference** | Sec 4.4 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No code-level DNS pinning (no getaddrinfo, no resolved-IP substitution) in src/
- FastMCP auto-enables inbound DNS-rebinding protection because host defaults to 127.0.0.1 — but this protects the inbound listener, not outbound httpx

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-005` (DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU). Folgendes fehlt / ist unvollständig:

1. No DNS-pinning on the OUTBOUND side (SSRF-relevant direction); follow_redirects=True (server.py:63) re-resolves DNS per request — TOCTOU window if target were attacker-controlled
2. Inbound protection is library-provided incidental, not authored; not the outbound pinning this check requires

### Evidence

- No code-level DNS pinning (no getaddrinfo, no resolved-IP substitution) in src/
- FastMCP auto-enables inbound DNS-rebinding protection because host defaults to 127.0.0.1 — but this protects the inbound listener, not outbound httpx

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No DNS-pinning on the OUTBOUND side (SSRF-relevant direction); follow_redirects=True (server.py:63) re-resolves DNS per request — TOCTOU window if target were attacker-controlled
2. Inbound protection is library-provided incidental, not authored; not the outbound pinning this check requires

Detail-Schritte und Code-Pattern siehe `checks/SEC-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-006

## Finding: SEC-006 — Lokaler Server: stdio-Transport zwingend (Netzwerk-Isolation)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-006` |
| **PDF-Reference** | Sec 4.5 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Default transport is stdio: mcp.run() unless '--http' in sys.argv (server.py:738-743)
- HTTP only via explicit --http flag, not default
- README documents local stdio with Claude Desktop (README.md:86-96); claude_desktop_config.json uses stdio command

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-006` (Lokaler Server: stdio-Transport zwingend (Netzwerk-Isolation)). Folgendes fehlt / ist unvollständig:

1. Cloud/HTTP section has no security warning about network exposure
2. Activation via CLI flag rather than MCP_TRANSPORT env-var (cosmetic vs Pass-Criteria wording)

### Evidence

- Default transport is stdio: mcp.run() unless '--http' in sys.argv (server.py:738-743)
- HTTP only via explicit --http flag, not default
- README documents local stdio with Claude Desktop (README.md:86-96); claude_desktop_config.json uses stdio command

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Cloud/HTTP section has no security warning about network exposure
2. Activation via CLI flag rather than MCP_TRANSPORT env-var (cosmetic vs Pass-Criteria wording)

Detail-Schritte und Code-Pattern siehe `checks/SEC-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-007

## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- Dockerfile has NO USER directive — container runs as root (grep USER/useradd/adduser = zero)
- Single-stage python:3.12-slim, pip install -e ., CMD as root; no readOnlyRootFilesystem, no cap drop, no seccomp
- No k8s/helm securityContext in repo

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-007` (Container-Sandboxing: Docker / chroot mit minimalen Privilegien). Folgendes fehlt / ist unvollständig:

1. None of Pass Criteria met: no USER>=10000, no runAsNonRoot, no readOnlyRootFilesystem, no capabilities.drop, no seccomp
2. is_cloud_deployed=true so hardening expected

### Evidence

- Dockerfile has NO USER directive — container runs as root (grep USER/useradd/adduser = zero)
- Single-stage python:3.12-slim, pip install -e ., CMD as root; no readOnlyRootFilesystem, no cap drop, no seccomp
- No k8s/helm securityContext in repo

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. None of Pass Criteria met: no USER>=10000, no runAsNonRoot, no readOnlyRootFilesystem, no capabilities.drop, no seccomp
2. is_cloud_deployed=true so hardening expected

Detail-Schritte und Code-Pattern siehe `checks/SEC-007.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-007` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-008

## Finding: SEC-008 — Pre-Configuration Consent für Local-Server-Installation

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-008` |
| **PDF-Reference** | Sec 4.5 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No install hooks: hatchling backend, standard [project.scripts] entry-point; no pre/postinstall
- README shows full Claude Desktop config transparently (README.md:86-96)
- `publish.yml uses pypa/gh-action-pypi-publish with id-token: write -> OIDC Trusted Publisher / Sigstore signing`

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-008` (Pre-Configuration Consent für Local-Server-Installation). Folgendes fehlt / ist unvollständig:

1. [project.scripts] 'bag-health-mcp = bag_health_mcp.server:mcp.run' points at a bound method, not a main callable (cosmetic/bug, not security)
2. No Sigstore signature-verification instructions for users in README

### Evidence

- No install hooks: hatchling backend, standard [project.scripts] entry-point; no pre/postinstall
- README shows full Claude Desktop config transparently (README.md:86-96)
- `publish.yml uses pypa/gh-action-pypi-publish with id-token: write -> OIDC Trusted Publisher / Sigstore signing`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. [project.scripts] 'bag-health-mcp = bag_health_mcp.server:mcp.run' points at a bound method, not a main callable (cosmetic/bug, not security)
2. No Sigstore signature-verification instructions for users in README

Detail-Schritte und Code-Pattern siehe `checks/SEC-008.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-008` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-009` |
| **PDF-Reference** | Sec 4.6 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No session handling in code; auth_model=none
- FastMCP streamable-http used with no auth (server.py:741), no OAuth token validation, no user_id, no Mcp-Session-Id binding

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-009` (Session-ID Cryptographic Binding (user_id:session_id)). Folgendes fehlt / ist unvollständig:

1. transport!=stdio-only (dual, HTTP via --http) so check applies
2. No cryptographically secure session-ID bound to validated user; no TTL, no invalidation — none of 6 Pass Criteria met

### Evidence

- No session handling in code; auth_model=none
- FastMCP streamable-http used with no auth (server.py:741), no OAuth token validation, no user_id, no Mcp-Session-Id binding

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. transport!=stdio-only (dual, HTTP via --http) so check applies
2. No cryptographically secure session-ID bound to validated user; no TTL, no invalidation — none of 6 Pass Criteria met

Detail-Schritte und Code-Pattern siehe `checks/SEC-009.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-009` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-013

## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-013` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No secrets used: auth_model=none, IDD API needs no auth (README.md:68); grep os.environ/getenv/API_KEY/SECRET in src/ = zero
- No hardcoded secrets, no .env, no plaintext keys in Dockerfile ENV

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-013` (API-Key-Storage: Secret Manager statt Plain-Text Env-Vars). Folgendes fehlt / ist unvollständig:

1. Public Open Data so no-secret is acceptable per Pass Criteria — BUT no docs/secret-management.md documenting the no-secret/acceptable-risk decision as the criteria require

### Evidence

- No secrets used: auth_model=none, IDD API needs no auth (README.md:68); grep os.environ/getenv/API_KEY/SECRET in src/ = zero
- No hardcoded secrets, no .env, no plaintext keys in Dockerfile ENV

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Public Open Data so no-secret is acceptable per Pass Criteria — BUT no docs/secret-management.md documenting the no-secret/acceptable-risk decision as the criteria require

Detail-Schritte und Code-Pattern siehe `checks/SEC-013.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-013` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-016

## Finding: SEC-016 — 0.0.0.0-Binding-Prevention (NeighborJack)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-016` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- server.py:741 — mcp.run(transport='streamable-http', port=port) sets no host argument
- Verified against mcp 1.27.2 (fresh install of pinned 'mcp[cli]>=1.0.0'): FastMCP default host is '127.0.0.1' (FastMCP('probe').settings.host == '127.0.0.1'); localhost binding also auto-enables TransportSecuritySettings DNS-rebinding protection
- grep for 0.0.0.0 across py/toml/yaml/Dockerfile = zero matches — no explicit all-interfaces binding

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-016` (0.0.0.0-Binding-Prevention (NeighborJack)). Folgendes fehlt / ist unvollständig:

1. Binding relies on the IMPLICIT SDK default rather than an explicit 127.0.0.1 / MCP_HOST configuration; the pin 'mcp[cli]>=1.0.0' is unbounded and earlier SDK versions defaulted host to 0.0.0.0 — latent NeighborJack risk on a downgrade/older lockfile
2. No README note on host binding / local-vs-container differentiation; no warning when a non-localhost host is configured
3. SEPARATE FUNCTIONAL DEFECT: FastMCP.run() signature is run(transport, mount_path) — it does NOT accept port=; server.py:741 raises TypeError at startup, so the --http path (and Dockerfile CMD --http --port 8000) crashes before binding at all

### Evidence

- server.py:741 — mcp.run(transport='streamable-http', port=port) sets no host argument
- Verified against mcp 1.27.2 (fresh install of pinned 'mcp[cli]>=1.0.0'): FastMCP default host is '127.0.0.1' (FastMCP('probe').settings.host == '127.0.0.1'); localhost binding also auto-enables TransportSecuritySettings DNS-rebinding protection
- grep for 0.0.0.0 across py/toml/yaml/Dockerfile = zero matches — no explicit all-interfaces binding

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Binding relies on the IMPLICIT SDK default rather than an explicit 127.0.0.1 / MCP_HOST configuration; the pin 'mcp[cli]>=1.0.0' is unbounded and earlier SDK versions defaulted host to 0.0.0.0 — latent NeighborJack risk on a downgrade/older lockfile
2. No README note on host binding / local-vs-container differentiation; no warning when a non-localhost host is configured
3. SEPARATE FUNCTIONAL DEFECT: FastMCP.run() signature is run(transport, mount_path) — it does NOT accept port=; server.py:741 raises TypeError at startup, so the --http path (and Dockerfile CMD --http --port 8000) crashes before binding at all

Detail-Schritte und Code-Pattern siehe `checks/SEC-016.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-016` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-018` |
| **PDF-Reference** | Sec 3 / Sec 4 (Defense-in-Depth) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Most tools use Pydantic BaseModel input models with constraints: DiseaseDataInput.limit_weeks ge=1,le=600 (server.py:137-143); Literal enums for canton/sex/format/version (server.py:83-88,124-131)

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-018` (Input-Validation an Tool-Boundaries (Pydantic strict / Zod)). Folgendes fehlt / ist unvollständig:

1. bag_get_canton_situation takes raw 'canton: str="ZH"' and 'include_wastewater: bool' (server.py:593-596) — no Field constraints, only manual list check (server.py:601)
2. NO model_config strict=True / extra='forbid' on ANY input model — Pydantic coercion active, unknown fields silently accepted
3. String fields topic/series_id/file have no min/max_length or pattern; age_group free-form str
4. No tests for invalid-input rejection (out-of-range, extra fields)

### Evidence

- Most tools use Pydantic BaseModel input models with constraints: DiseaseDataInput.limit_weeks ge=1,le=600 (server.py:137-143); Literal enums for canton/sex/format/version (server.py:83-88,124-131)

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. bag_get_canton_situation takes raw 'canton: str="ZH"' and 'include_wastewater: bool' (server.py:593-596) — no Field constraints, only manual list check (server.py:601)
2. NO model_config strict=True / extra='forbid' on ANY input model — Pydantic coercion active, unknown fields silently accepted
3. String fields topic/series_id/file have no min/max_length or pattern; age_group free-form str
4. No tests for invalid-input rejection (out-of-range, extra fields)

Detail-Schritte und Code-Pattern siehe `checks/SEC-018.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-018` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-019

## Finding: SEC-019 — Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-019` |
| **PDF-Reference** | Anhang B1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `Read-only/write_capable=false: only GET/query-POST to fetch public data; no send_mail/smtplib/slack/webhook exfiltration sinks`
- httpx.post (server.py:408,659) only target the fixed read API; Public Open Data (README.md:133)

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-019` (Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send). Folgendes fehlt / ist unvollständig:

1. No documented Lethal Trifecta assessment in README/docs (grep trifecta/lethal = none; no docs/ dir)
2. Score effectively safe (<=1 leg) but undocumented, so Pass Criteria not fully met

### Evidence

- `Read-only/write_capable=false: only GET/query-POST to fetch public data; no send_mail/smtplib/slack/webhook exfiltration sinks`
- httpx.post (server.py:408,659) only target the fixed read API; Public Open Data (README.md:133)

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No documented Lethal Trifecta assessment in README/docs (grep trifecta/lethal = none; no docs/ dir)
2. Score effectively safe (<=1 leg) but undocumented, so Pass Criteria not fully met

Detail-Schritte und Code-Pattern siehe `checks/SEC-019.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-019` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No code-layer egress allow-list: grep allowed_domains/allowed_hosts/host_whitelist in src/ = zero
- Outbound relies solely on hardcoded base_url IDD_BASE (server.py:22) with no assert_host_allowed()
- No network-layer egress control (no NetworkPolicy, no Smokescreen) in repo

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-021` (Egress-Allow-List: Code-Layer und Network-Layer). Folgendes fehlt / ist unvollständig:

1. Neither required layer (code-layer allow-list + network-layer egress control) present; tools_make_external_requests + is_cloud_deployed so check applies
2. Hardcoded base_url is implicit single-host restriction, not enforced, bypassable via follow_redirects=True (server.py:63)

### Evidence

- No code-layer egress allow-list: grep allowed_domains/allowed_hosts/host_whitelist in src/ = zero
- Outbound relies solely on hardcoded base_url IDD_BASE (server.py:22) with no assert_host_allowed()
- No network-layer egress control (no NetworkPolicy, no Smokescreen) in repo

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Neither required layer (code-layer allow-list + network-layer egress control) present; tools_make_external_requests + is_cloud_deployed so check applies
2. Hardcoded base_url is implicit single-host restriction, not enforced, bypassable via follow_redirects=True (server.py:63)

Detail-Schritte und Code-Pattern siehe `checks/SEC-021.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-021` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-022` |
| **PDF-Reference** | Anhang B4 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- All tools share consistent 'bag_' prefix giving basic namespace
- CHANGELOG.md lists tools, but no hashes

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-022` (Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull). Folgendes fehlt / ist unvollständig:

1. Namespace uses single 'bag_' prefix, not the required server-identity '<server>__<tool>' double-underscore format preventing cross-server shadowing
2. No tool-definition SHA-256 hash snapshot in CI (ci.yml/publish.yml have no hash step)
3. CHANGELOG has no per-tool hash entries; is_cloud_deployed so check applies

### Evidence

- All tools share consistent 'bag_' prefix giving basic namespace
- CHANGELOG.md lists tools, but no hashes

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Namespace uses single 'bag_' prefix, not the required server-identity '<server>__<tool>' double-underscore format preventing cross-server shadowing
2. No tool-definition SHA-256 hash snapshot in CI (ci.yml/publish.yml have no hash step)
3. CHANGELOG has no per-tool hash entries; is_cloud_deployed so check applies

Detail-Schritte und Code-Pattern siehe `checks/SEC-022.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-022` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **OBS-004** (critical, partial)
3. **SEC-004** (critical, partial)
4. **SEC-009** (critical, fail)
5. **SEC-016** (critical, partial)
6. **SEC-019** (critical, partial)
7. **ARCH-004** (high, partial)
8. **ARCH-009** (high, fail)
9. **CH-005** (high, fail)
10. **CH-006** (high, fail)
11. **OBS-001** (high, fail)
12. **OBS-002** (high, fail)
13. **OPS-003** (high, fail)
14. **SCALE-001** (high, partial)
15. **SCALE-002** (high, fail)
16. **SCALE-003** (high, fail)
17. **SDK-001** (high, fail)
18. **SDK-004** (high, fail)
19. **SEC-005** (high, partial)
20. **SEC-006** (high, partial)
21. **SEC-007** (high, fail)
22. **SEC-013** (high, partial)
23. **SEC-018** (high, partial)
24. **SEC-021** (high, fail)
25. **SEC-022** (high, partial)
26. **ARCH-002** (medium, partial)
27. **ARCH-003** (medium, partial)
28. **ARCH-008** (medium, fail)
29. **ARCH-011** (medium, partial)
30. **ARCH-012** (medium, fail)
31. **CH-004** (medium, partial)
32. **OBS-003** (medium, fail)
33. **OBS-006** (medium, fail)
34. **OPS-002** (medium, partial)
35. **SCALE-004** (medium, fail)
36. **SCALE-005** (medium, fail)
37. **SCALE-006** (medium, fail)
38. **SDK-002** (medium, partial)
39. **SDK-003** (medium, fail)
40. **SEC-008** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `v0.5.0 (68 checks)` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-05-30` |


_Generated by tools/build_report.py — do not edit by hand._
