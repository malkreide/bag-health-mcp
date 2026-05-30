## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-005` |
| **PDF-Reference** | Sec 4.4 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No code-level DNS pinning (no getaddrinfo, no resolved-IP substitution) in src/
- FastMCP auto-enables inbound DNS-rebinding protection because host defaults to 127.0.0.1 — but this protects the inbound listener, not outbound httpx

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-005` (DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU). Folgendes fehlt / ist unvollständig:

1. No DNS-pinning on the OUTBOUND side (SSRF-relevant direction); follow_redirects=True (server.py:63) re-resolves DNS per request — TOCTOU window if target were attacker-controlled
2. Inbound protection is library-provided incidental, not authored; not the outbound pinning this check requires

### Evidence

- No code-level DNS pinning (no getaddrinfo, no resolved-IP substitution) in src/
- FastMCP auto-enables inbound DNS-rebinding protection because host defaults to 127.0.0.1 — but this protects the inbound listener, not outbound httpx

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No DNS-pinning on the OUTBOUND side (SSRF-relevant direction); follow_redirects=True (server.py:63) re-resolves DNS per request — TOCTOU window if target were attacker-controlled
2. Inbound protection is library-provided incidental, not authored; not the outbound pinning this check requires

Detail-Schritte und Code-Pattern siehe `checks/SEC-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
