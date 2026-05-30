## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `ARCH-004` |
| **PDF-Reference** | Sec 2.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- src/bag_health_mcp/server.py — no request/transport internals leak into handlers; handlers take only Pydantic input models
- `src/bag_health_mcp/server.py:737-743 — both stdio and streamable-http from one codebase`
- tool business logic identical regardless of transport

### Expected Behavior

Erfüllung der Pass-Criteria von `ARCH-004` (Inversion of Control: Transport-agnostische Server-Logik). Folgendes fehlt / ist unvollständig:

1. No Pydantic BaseSettings/Settings object; config read ad-hoc from sys.argv (server.py:738-740)
2. No shared lifespan; new httpx.AsyncClient per call via _client() (server.py:55)

### Evidence

- src/bag_health_mcp/server.py — no request/transport internals leak into handlers; handlers take only Pydantic input models
- `src/bag_health_mcp/server.py:737-743 — both stdio and streamable-http from one codebase`
- tool business logic identical regardless of transport

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No Pydantic BaseSettings/Settings object; config read ad-hoc from sys.argv (server.py:738-740)
2. No shared lifespan; new httpx.AsyncClient per call via _client() (server.py:55)

Detail-Schritte und Code-Pattern siehe `checks/ARCH-004.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `ARCH-004` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
