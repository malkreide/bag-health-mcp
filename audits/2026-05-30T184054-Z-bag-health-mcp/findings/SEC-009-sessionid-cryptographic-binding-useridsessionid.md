## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-009` |
| **PDF-Reference** | Sec 4.6 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No session handling in code; auth_model=none
- FastMCP streamable-http used with no auth (server.py:741), no OAuth token validation, no user_id, no Mcp-Session-Id binding

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-009` (Session-ID Cryptographic Binding (user_id:session_id)). Folgendes fehlt / ist unvollständig:

1. transport!=stdio-only (dual, HTTP via --http) so check applies
2. No cryptographically secure session-ID bound to validated user; no TTL, no invalidation — none of 6 Pass Criteria met

### Evidence

- No session handling in code; auth_model=none
- FastMCP streamable-http used with no auth (server.py:741), no OAuth token validation, no user_id, no Mcp-Session-Id binding

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. transport!=stdio-only (dual, HTTP via --http) so check applies
2. No cryptographically secure session-ID bound to validated user; no TTL, no invalidation — none of 6 Pass Criteria met

Detail-Schritte und Code-Pattern siehe `checks/SEC-009.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-009` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
