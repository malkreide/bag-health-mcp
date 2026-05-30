## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- Dockerfile has NO USER directive — container runs as root (grep USER/useradd/adduser = zero)
- Single-stage python:3.12-slim, pip install -e ., CMD as root; no readOnlyRootFilesystem, no cap drop, no seccomp
- No k8s/helm securityContext in repo

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-007` (Container-Sandboxing: Docker / chroot mit minimalen Privilegien). Folgendes fehlt / ist unvollständig:

1. None of Pass Criteria met: no USER>=10000, no runAsNonRoot, no readOnlyRootFilesystem, no capabilities.drop, no seccomp
2. is_cloud_deployed=true so hardening expected

### Evidence

- Dockerfile has NO USER directive — container runs as root (grep USER/useradd/adduser = zero)
- Single-stage python:3.12-slim, pip install -e ., CMD as root; no readOnlyRootFilesystem, no cap drop, no seccomp
- No k8s/helm securityContext in repo

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. None of Pass Criteria met: no USER>=10000, no runAsNonRoot, no readOnlyRootFilesystem, no capabilities.drop, no seccomp
2. is_cloud_deployed=true so hardening expected

Detail-Schritte und Code-Pattern siehe `checks/SEC-007.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-007` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
