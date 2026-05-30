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
