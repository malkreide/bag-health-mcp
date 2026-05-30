## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-004` |
| **PDF-Reference** | Sec 5.3 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- Dockerfile:1 — single FROM python:3.12-slim (not multi-stage)
- Dockerfile:7 — pip install -e . in final image
- No USER directive (runs as root); no HEALTHCHECK

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-004` (Containerization mit Multi-Stage-Builds). Folgendes fehlt / ist unvollständig:

1. Not multi-stage
2. Runs as root (no non-root USER)
3. No HEALTHCHECK for LB integration
4. Editable-install/build tooling left in final image

### Evidence

- Dockerfile:1 — single FROM python:3.12-slim (not multi-stage)
- Dockerfile:7 — pip install -e . in final image
- No USER directive (runs as root); no HEALTHCHECK

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Not multi-stage
2. Runs as root (no non-root USER)
3. No HEALTHCHECK for LB integration
4. Editable-install/build tooling left in final image

Detail-Schritte und Code-Pattern siehe `checks/SCALE-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
