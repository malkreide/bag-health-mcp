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
