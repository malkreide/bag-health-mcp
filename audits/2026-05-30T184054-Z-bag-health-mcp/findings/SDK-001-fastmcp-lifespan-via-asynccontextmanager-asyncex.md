## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SDK-001` |
| **PDF-Reference** | Sec 3.1 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- server.py:37-48 — FastMCP() with NO lifespan= argument
- No @asynccontextmanager/lifespan/AsyncExitStack in src/
- server.py:55-64 _client() returns fresh httpx.AsyncClient; every tool uses 'async with _client()' — new client per call, no pooling
- server.py:710-712 — canton_situation fans out 5+ tasks, each opening 2 clients (~10 fresh clients per call)

### Expected Behavior

Erfüllung der Pass-Criteria von `SDK-001` (FastMCP Lifespan via @asynccontextmanager + AsyncExitStack). Folgendes fehlt / ist unvollständig:

1. No @asynccontextmanager lifespan
2. FastMCP constructor missing lifespan=
3. No connection pooling; matches documented fail-pattern (httpx client per call)

### Evidence

- server.py:37-48 — FastMCP() with NO lifespan= argument
- No @asynccontextmanager/lifespan/AsyncExitStack in src/
- server.py:55-64 _client() returns fresh httpx.AsyncClient; every tool uses 'async with _client()' — new client per call, no pooling
- server.py:710-712 — canton_situation fans out 5+ tasks, each opening 2 clients (~10 fresh clients per call)

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No @asynccontextmanager lifespan
2. FastMCP constructor missing lifespan=
3. No connection pooling; matches documented fail-pattern (httpx client per call)

Detail-Schritte und Code-Pattern siehe `checks/SDK-001.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SDK-001` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
