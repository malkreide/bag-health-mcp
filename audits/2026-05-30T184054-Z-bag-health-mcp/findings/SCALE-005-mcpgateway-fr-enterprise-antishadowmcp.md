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
