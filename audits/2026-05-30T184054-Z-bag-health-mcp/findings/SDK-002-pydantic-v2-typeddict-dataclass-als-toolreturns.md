## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- pyproject.toml — pydantic>=2.0.0 (v2 satisfied)
- All 8 tools annotate -> dict[str,Any] (acceptable per criteria)
- `Inputs use Pydantic BaseModel with Field/Literal (server.py:91-166)`

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-002` (Pydantic v2 / TypedDict / Dataclass als Tool-Returns). Folgendes fehlt / ist unvollständig:

1. Returns are plain dict[str,Any] not BaseModel/TypedDict — no precise structured output schema in tools/list
2. No consistent response envelope across tools
3. No provenance field; source/source_date only on some tools

### Evidence

- pyproject.toml — pydantic>=2.0.0 (v2 satisfied)
- All 8 tools annotate -> dict[str,Any] (acceptable per criteria)
- `Inputs use Pydantic BaseModel with Field/Literal (server.py:91-166)`

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Returns are plain dict[str,Any] not BaseModel/TypedDict — no precise structured output schema in tools/list
2. No consistent response envelope across tools
3. No provenance field; source/source_date only on some tools

Detail-Schritte und Code-Pattern siehe `checks/SDK-002.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-002` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
