## Finding: OBS-004 — stderr für stdio-Server: stdout reserviert für Protocol

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-004` |
| **PDF-Reference** | Sec 6.3 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- No print() statements in src/ (passes hard criterion)
- Transport dual: stdio default (server.py:743) + streamable-http (server.py:741)
- No logging to stdout exists because there is no logging at all

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-004` (stderr für stdio-Server: stdout reserviert für Protocol). Folgendes fehlt / ist unvollständig:

1. No explicit stderr configuration (no logging.basicConfig(stream=sys.stderr))
2. Once logging added (OBS-003), explicitly route to sys.stderr; add CI guard against print()

### Evidence

- No print() statements in src/ (passes hard criterion)
- Transport dual: stdio default (server.py:743) + streamable-http (server.py:741)
- No logging to stdout exists because there is no logging at all

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No explicit stderr configuration (no logging.basicConfig(stream=sys.stderr))
2. Once logging added (OBS-003), explicitly route to sys.stderr; add CI guard against print()

Detail-Schritte und Code-Pattern siehe `checks/OBS-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
