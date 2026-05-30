## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-004` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- No CORSMiddleware/cors/allow_origins/expose_headers in src/
- server.py:737-743 — HTTP mode calls mcp.run(transport='streamable-http') with no Starlette middleware/CORS
- Dockerfile:11 — server deployed in HTTP mode (cloud), so check applies

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-004` (CORS Mcp-Session-Id Exposure bei HTTP/SSE). Folgendes fehlt / ist unvollständig:

1. No CORS middleware at all
2. Mcp-Session-Id not in expose_headers — browser cross-origin clients cannot read session id, breaking stateful sessions
3. Mcp-Session-Id not in allow_headers; no explicit allow_origins

### Evidence

- No CORSMiddleware/cors/allow_origins/expose_headers in src/
- server.py:737-743 — HTTP mode calls mcp.run(transport='streamable-http') with no Starlette middleware/CORS
- Dockerfile:11 — server deployed in HTTP mode (cloud), so check applies

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No CORS middleware at all
2. Mcp-Session-Id not in expose_headers — browser cross-origin clients cannot read session id, breaking stateful sessions
3. Mcp-Session-Id not in allow_headers; no explicit allow_origins

Detail-Schritte und Code-Pattern siehe `checks/SDK-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
