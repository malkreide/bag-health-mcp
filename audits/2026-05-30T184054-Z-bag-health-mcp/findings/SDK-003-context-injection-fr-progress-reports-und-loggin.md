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
