## Finding: CH-006 — Schulamt Klassifikationsschema: BUI/Vertraulich/Streng-Vertraulich

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `CH-006` |
| **PDF-Reference** | Custom (Stadt Zürich Klassifikations-Schema) |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No klassifikation/classification document; no docs/ dir
- `No BUI/vertraulich/streng-vertraulich declaration; only README.md:134/README.de.md:93 'aggregated and anonymised at canton level'`
- canton_situation (server.py:593-730) has no k_anonymity/min_class_size/aggregation_threshold control

### Expected Behavior

Erfüllung der Pass-Criteria von `CH-006` (Schulamt Klassifikationsschema: BUI/Vertraulich/Streng-Vertraulich). Folgendes fehlt / ist unvollständig:

1. No BUI/VERT/SVERT classification scheme documented despite schulamt_context=true (mandatory)
2. Highest level not declared; no Massnahmen-Mapping
3. Aggregation-risk not addressed; no documented min-group-size on the aggregating tool

### Evidence

- No klassifikation/classification document; no docs/ dir
- `No BUI/vertraulich/streng-vertraulich declaration; only README.md:134/README.de.md:93 'aggregated and anonymised at canton level'`
- canton_situation (server.py:593-730) has no k_anonymity/min_class_size/aggregation_threshold control

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No BUI/VERT/SVERT classification scheme documented despite schulamt_context=true (mandatory)
2. Highest level not declared; no Massnahmen-Mapping
3. Aggregation-risk not addressed; no documented min-group-size on the aggregating tool

Detail-Schritte und Code-Pattern siehe `checks/CH-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `CH-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
