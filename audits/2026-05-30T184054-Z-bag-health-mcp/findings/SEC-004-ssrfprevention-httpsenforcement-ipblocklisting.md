## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-004` |
| **PDF-Reference** | Sec 4.4 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Base URL hardcoded to HTTPS: IDD_BASE='https://api.idd.bag.admin.ch' (server.py:22); all requests via _client() with base_url=IDD_BASE (server.py:55-64)
- No user/LLM-supplied URLs reach the HTTP client — tool args are slugs/Literal enums interpolated into fixed API paths
- No urlparse, no IP blocklist, no 169.254.169.254/metadata blocking, no egress proxy in src/

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-004` (SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting). Folgendes fehlt / ist unvollständig:

1. No explicit HTTPS-scheme enforcement or IP blocklist as required by Pass Criteria — relies solely on hardcoded base_url
2. follow_redirects=True (server.py:63) means a compromised upstream could 30x-redirect to an internal IP; no resolved-IP validation, no DNS pinning

### Evidence

- Base URL hardcoded to HTTPS: IDD_BASE='https://api.idd.bag.admin.ch' (server.py:22); all requests via _client() with base_url=IDD_BASE (server.py:55-64)
- No user/LLM-supplied URLs reach the HTTP client — tool args are slugs/Literal enums interpolated into fixed API paths
- No urlparse, no IP blocklist, no 169.254.169.254/metadata blocking, no egress proxy in src/

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No explicit HTTPS-scheme enforcement or IP blocklist as required by Pass Criteria — relies solely on hardcoded base_url
2. follow_redirects=True (server.py:63) means a compromised upstream could 30x-redirect to an internal IP; no resolved-IP validation, no DNS pinning

Detail-Schritte und Code-Pattern siehe `checks/SEC-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
