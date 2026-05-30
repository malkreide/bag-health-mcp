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
