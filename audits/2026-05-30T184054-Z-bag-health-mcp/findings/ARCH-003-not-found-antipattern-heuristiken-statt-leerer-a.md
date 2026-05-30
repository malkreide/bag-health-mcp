## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-003` |
| **PDF-Reference** | Sec 2.2 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `src/bag_health_mcp/server.py:245-249 — bag_list_series returns {error,hint} not bare empty list`
- `src/bag_health_mcp/server.py:411-417 — error+actionable hint on API failure`
- `src/bag_health_mcp/server.py:676 — canton_situation returns {status:'no_data'}`

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-003` («Not Found» Anti-Pattern: Heuristiken statt leerer Antworten). Folgendes fehlt / ist unvollständig:

1. No fuzzy-match/suggestion mechanism on no-results; no match_type field
2. Empty topic/series returns 'error' string rather than structured heuristic with related suggestions

### Evidence

- `src/bag_health_mcp/server.py:245-249 — bag_list_series returns {error,hint} not bare empty list`
- `src/bag_health_mcp/server.py:411-417 — error+actionable hint on API failure`
- `src/bag_health_mcp/server.py:676 — canton_situation returns {status:'no_data'}`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No fuzzy-match/suggestion mechanism on no-results; no match_type field
2. Empty topic/series returns 'error' string rather than structured heuristic with related suggestions

Detail-Schritte und Code-Pattern siehe `checks/ARCH-003.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-003` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
