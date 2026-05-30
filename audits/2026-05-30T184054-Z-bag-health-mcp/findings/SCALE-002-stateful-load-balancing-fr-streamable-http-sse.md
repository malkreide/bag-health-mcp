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
