## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-013` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No secrets used: auth_model=none, IDD API needs no auth (README.md:68); grep os.environ/getenv/API_KEY/SECRET in src/ = zero
- No hardcoded secrets, no .env, no plaintext keys in Dockerfile ENV

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-013` (API-Key-Storage: Secret Manager statt Plain-Text Env-Vars). Folgendes fehlt / ist unvollständig:

1. Public Open Data so no-secret is acceptable per Pass Criteria — BUT no docs/secret-management.md documenting the no-secret/acceptable-risk decision as the criteria require

### Evidence

- No secrets used: auth_model=none, IDD API needs no auth (README.md:68); grep os.environ/getenv/API_KEY/SECRET in src/ = zero
- No hardcoded secrets, no .env, no plaintext keys in Dockerfile ENV

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Public Open Data so no-secret is acceptable per Pass Criteria — BUT no docs/secret-management.md documenting the no-secret/acceptable-risk decision as the criteria require

Detail-Schritte und Code-Pattern siehe `checks/SEC-013.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-013` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
