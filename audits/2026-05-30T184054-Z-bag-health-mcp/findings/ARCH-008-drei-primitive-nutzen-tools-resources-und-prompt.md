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
