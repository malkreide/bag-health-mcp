## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-002` |
| **PDF-Reference** | Sec 6.2 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- FastMCP initialized WITHOUT mask_error_details — server.py:37-48
- Raw upstream body leaked to LLM: server.py:412 'detail': r.text[:500]
- Raw exception leaked: server.py:708 return {error: str(e)}
- Unhandled raise_for_status() (server.py:182,241,296,350,515,542,568) reach FastMCP

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-002` (Mask Error Details: keine Stacktraces / SQL ans LLM). Folgendes fehlt / ist unvollständig:

1. Set mask_error_details=True on FastMCP
2. Remove r.text[:500] and str(e) from returns; log originals server-side only

### Evidence

- FastMCP initialized WITHOUT mask_error_details — server.py:37-48
- Raw upstream body leaked to LLM: server.py:412 'detail': r.text[:500]
- Raw exception leaked: server.py:708 return {error: str(e)}
- Unhandled raise_for_status() (server.py:182,241,296,350,515,542,568) reach FastMCP

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Set mask_error_details=True on FastMCP
2. Remove r.text[:500] and str(e) from returns; log originals server-side only

Detail-Schritte und Code-Pattern siehe `checks/OBS-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
