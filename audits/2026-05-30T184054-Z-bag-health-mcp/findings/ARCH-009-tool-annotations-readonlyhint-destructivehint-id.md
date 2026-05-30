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
