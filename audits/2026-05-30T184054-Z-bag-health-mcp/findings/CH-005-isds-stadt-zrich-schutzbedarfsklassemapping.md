## Finding: CH-005 — ISDS Stadt Zürich Schutzbedarfsklasse-Mapping

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `CH-005` |
| **PDF-Reference** | Custom (ISDS-Richtlinie Stadt Zürich) |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No docs/ directory; no isds-klassifikation.md
- No isds/schutzbedarf/vertraulich/integrität/verfügbarkeit/oiz hits in any .md/.py/.toml

### Expected Behavior

Erfüllung der Pass-Criteria von `CH-005` (ISDS Stadt Zürich Schutzbedarfsklasse-Mapping). Folgendes fehlt / ist unvollständig:

1. No ISDS classification document despite stadt_zuerich_context=true (mandatory)
2. No per-Schutzziel ratings with justifications
3. No Massnahmen-Mapping per class; no OIZ sign-off

### Evidence

- No docs/ directory; no isds-klassifikation.md
- No isds/schutzbedarf/vertraulich/integrität/verfügbarkeit/oiz hits in any .md/.py/.toml

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No ISDS classification document despite stadt_zuerich_context=true (mandatory)
2. No per-Schutzziel ratings with justifications
3. No Massnahmen-Mapping per class; no OIZ sign-off

Detail-Schritte und Code-Pattern siehe `checks/CH-005.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `CH-005` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
