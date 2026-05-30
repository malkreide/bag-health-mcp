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
