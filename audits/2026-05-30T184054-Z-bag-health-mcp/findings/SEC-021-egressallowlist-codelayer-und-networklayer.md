## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No code-layer egress allow-list: grep allowed_domains/allowed_hosts/host_whitelist in src/ = zero
- Outbound relies solely on hardcoded base_url IDD_BASE (server.py:22) with no assert_host_allowed()
- No network-layer egress control (no NetworkPolicy, no Smokescreen) in repo

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-021` (Egress-Allow-List: Code-Layer und Network-Layer). Folgendes fehlt / ist unvollständig:

1. Neither required layer (code-layer allow-list + network-layer egress control) present; tools_make_external_requests + is_cloud_deployed so check applies
2. Hardcoded base_url is implicit single-host restriction, not enforced, bypassable via follow_redirects=True (server.py:63)

### Evidence

- No code-layer egress allow-list: grep allowed_domains/allowed_hosts/host_whitelist in src/ = zero
- Outbound relies solely on hardcoded base_url IDD_BASE (server.py:22) with no assert_host_allowed()
- No network-layer egress control (no NetworkPolicy, no Smokescreen) in repo

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Neither required layer (code-layer allow-list + network-layer egress control) present; tools_make_external_requests + is_cloud_deployed so check applies
2. Hardcoded base_url is implicit single-host restriction, not enforced, bypassable via follow_redirects=True (server.py:63)

Detail-Schritte und Code-Pattern siehe `checks/SEC-021.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-021` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
