## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-011` |
| **PDF-Reference** | Anhang A8 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml all present
- src/, tests/, .github/workflows/ all present
- src-layout correct: pyproject.toml:55-56 packages=['src/bag_health_mcp']

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-011` (Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)). Folgendes fehlt / ist unvollständig:

1. 8 tools all in single 743-line server.py, no tools/ split (expects tools/ + server.py <200 lines)
2. README.de.md sections not parallel to README.md

### Evidence

- README.md, README.de.md, CHANGELOG.md, LICENSE, pyproject.toml all present
- src/, tests/, .github/workflows/ all present
- src-layout correct: pyproject.toml:55-56 packages=['src/bag_health_mcp']

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. 8 tools all in single 743-line server.py, no tools/ split (expects tools/ + server.py <200 lines)
2. README.de.md sections not parallel to README.md

Detail-Schritte und Code-Pattern siehe `checks/ARCH-011.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-011` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
