## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-022` |
| **PDF-Reference** | Anhang B4 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- All tools share consistent 'bag_' prefix giving basic namespace
- CHANGELOG.md lists tools, but no hashes

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-022` (Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull). Folgendes fehlt / ist unvollständig:

1. Namespace uses single 'bag_' prefix, not the required server-identity '<server>__<tool>' double-underscore format preventing cross-server shadowing
2. No tool-definition SHA-256 hash snapshot in CI (ci.yml/publish.yml have no hash step)
3. CHANGELOG has no per-tool hash entries; is_cloud_deployed so check applies

### Evidence

- All tools share consistent 'bag_' prefix giving basic namespace
- CHANGELOG.md lists tools, but no hashes

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Namespace uses single 'bag_' prefix, not the required server-identity '<server>__<tool>' double-underscore format preventing cross-server shadowing
2. No tool-definition SHA-256 hash snapshot in CI (ci.yml/publish.yml have no hash step)
3. CHANGELOG has no per-tool hash entries; is_cloud_deployed so check applies

Detail-Schritte und Code-Pattern siehe `checks/SEC-022.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-022` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
