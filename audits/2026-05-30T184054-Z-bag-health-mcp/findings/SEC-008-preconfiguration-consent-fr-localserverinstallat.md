## Finding: SEC-008 — Pre-Configuration Consent für Local-Server-Installation

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-008` |
| **PDF-Reference** | Sec 4.5 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No install hooks: hatchling backend, standard [project.scripts] entry-point; no pre/postinstall
- README shows full Claude Desktop config transparently (README.md:86-96)
- `publish.yml uses pypa/gh-action-pypi-publish with id-token: write -> OIDC Trusted Publisher / Sigstore signing`

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-008` (Pre-Configuration Consent für Local-Server-Installation). Folgendes fehlt / ist unvollständig:

1. [project.scripts] 'bag-health-mcp = bag_health_mcp.server:mcp.run' points at a bound method, not a main callable (cosmetic/bug, not security)
2. No Sigstore signature-verification instructions for users in README

### Evidence

- No install hooks: hatchling backend, standard [project.scripts] entry-point; no pre/postinstall
- README shows full Claude Desktop config transparently (README.md:86-96)
- `publish.yml uses pypa/gh-action-pypi-publish with id-token: write -> OIDC Trusted Publisher / Sigstore signing`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. [project.scripts] 'bag-health-mcp = bag_health_mcp.server:mcp.run' points at a bound method, not a main callable (cosmetic/bug, not security)
2. No Sigstore signature-verification instructions for users in README

Detail-Schritte und Code-Pattern siehe `checks/SEC-008.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-008` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
