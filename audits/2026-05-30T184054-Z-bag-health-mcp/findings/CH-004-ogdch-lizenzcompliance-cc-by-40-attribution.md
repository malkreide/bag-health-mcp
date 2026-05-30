## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `CH-004` |
| **PDF-Reference** | Custom (OGD-CH-Richtlinien) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- README.md:138 documents data licence (public domain / OGD)
- README.md:154 / README.de.md:97 repeat source+licence (MIT code, public-domain/OGD data)
- server.py:308,491 emit 'source' field but only passthrough of data.get('source') — no controlled license/provenance
- server.py:714-730 canton_situation return has no source/license field

### Expected Behavior

Erfüllung der Pass-Criteria von `CH-004` (OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution). Folgendes fehlt / ist unvollständig:

1. No controlled license/attribution field in tool responses; no provenance field
2. README declares 'public domain' rather than required CC BY 4.0 attribution; no Datenquellen-&-Lizenzen table
3. Schulamt tool output omits source/license entirely

### Evidence

- README.md:138 documents data licence (public domain / OGD)
- README.md:154 / README.de.md:97 repeat source+licence (MIT code, public-domain/OGD data)
- server.py:308,491 emit 'source' field but only passthrough of data.get('source') — no controlled license/provenance
- server.py:714-730 canton_situation return has no source/license field

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No controlled license/attribution field in tool responses; no provenance field
2. README declares 'public domain' rather than required CC BY 4.0 attribution; no Datenquellen-&-Lizenzen table
3. Schulamt tool output omits source/license entirely

Detail-Schritte und Code-Pattern siehe `checks/CH-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `CH-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
