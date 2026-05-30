## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-005` |
| **PDF-Reference** | Sec 2.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `src/bag_health_mcp/server.py — no hardcoded keys/passwords/tokens (secret grep clean); API is auth-none (README.md:68,137)`
- `src/bag_health_mcp/server.py:22-24 — only constants are public base URL + User-Agent`
- Dockerfile:1-12 — no ENV secret lines

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-005` (Keine Hardcoded Secrets: Env-Vars / Secret Manager only). Folgendes fehlt / ist unvollständig:

1. No .gitignore (no ignore for .env/secrets)
2. No .env.example
3. No secret-scanning (gitleaks/trufflehog) in CI workflows
4. No Pydantic SecretStr/Settings pattern (moot today, criterion unmet)

### Evidence

- `src/bag_health_mcp/server.py — no hardcoded keys/passwords/tokens (secret grep clean); API is auth-none (README.md:68,137)`
- `src/bag_health_mcp/server.py:22-24 — only constants are public base URL + User-Agent`
- Dockerfile:1-12 — no ENV secret lines

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No .gitignore (no ignore for .env/secrets)
2. No .env.example
3. No secret-scanning (gitleaks/trufflehog) in CI workflows
4. No Pydantic SecretStr/Settings pattern (moot today, criterion unmet)

Detail-Schritte und Code-Pattern siehe `checks/ARCH-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
