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
