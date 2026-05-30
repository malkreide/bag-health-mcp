## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- `src/bag_health_mcp/server.py:37-48 — FastMCP with no protocol_version pin`
- CHANGELOG.md present in Keep-a-Changelog format

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-012` (protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin). Folgendes fehlt / ist unvollständig:

1. protocolVersion not pinned — relies on SDK default, can break on SDK update
2. CHANGELOG entries reference no MCP spec version
3. No protocol-version/update-policy section in READMEs
4. No dependabot.yml/renovate.json

### Evidence

- `src/bag_health_mcp/server.py:37-48 — FastMCP with no protocol_version pin`
- CHANGELOG.md present in Keep-a-Changelog format

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. protocolVersion not pinned — relies on SDK default, can break on SDK update
2. CHANGELOG entries reference no MCP spec version
3. No protocol-version/update-policy section in READMEs
4. No dependabot.yml/renovate.json

Detail-Schritte und Code-Pattern siehe `checks/ARCH-012.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-012` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
