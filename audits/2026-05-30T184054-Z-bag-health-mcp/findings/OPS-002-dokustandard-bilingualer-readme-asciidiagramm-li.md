## Finding: OPS-002 — Doku-Standard: bilingualer README, ASCII-Diagramm, Limits-Sektion

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OPS-002` |
| **PDF-Reference** | Anhang C2 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Both READMEs exist; CHANGELOG Keep-a-Changelog; CONTRIBUTING present
- Anchor demo query natural-language: README.md:14-30, README.de.md:12-18
- ASCII architecture diagram: README.md:73-80
- Known Limitations >3: README.md:143-148, README.de.md:102-107
- `Tools overview, Installation (uvx+HTTP), Security/Limits: README.md:34-45,84-104,129-139`

### Expected Behavior

Erfüllung der Pass-Criteria von `OPS-002` (Doku-Standard: bilingualer README, ASCII-Diagramm, Limits-Sektion). Folgendes fehlt / ist unvollständig:

1. README.de.md not in section parity: missing ASCII diagram, HTTP/Cloud install, Tools/Topics table, License section
2. No architecture diagram in README.de.md

### Evidence

- Both READMEs exist; CHANGELOG Keep-a-Changelog; CONTRIBUTING present
- Anchor demo query natural-language: README.md:14-30, README.de.md:12-18
- ASCII architecture diagram: README.md:73-80
- Known Limitations >3: README.md:143-148, README.de.md:102-107
- `Tools overview, Installation (uvx+HTTP), Security/Limits: README.md:34-45,84-104,129-139`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. README.de.md not in section parity: missing ASCII diagram, HTTP/Cloud install, Tools/Topics table, License section
2. No architecture diagram in README.de.md

Detail-Schritte und Code-Pattern siehe `checks/OPS-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OPS-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
