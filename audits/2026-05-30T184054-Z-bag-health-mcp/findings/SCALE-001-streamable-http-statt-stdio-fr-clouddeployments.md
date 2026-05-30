## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SCALE-001` |
| **PDF-Reference** | Sec 5.1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- server.py:737-743 — dual transport, --http -> streamable-http, else stdio
- Dockerfile:11 — CMD runs --http --port 8000, cloud image uses streamable-http
- README.md:99-104 documents --http cloud invocation

### Expected Behavior

Erfüllung der Pass-Criteria von `SCALE-001` (Streamable HTTP statt stdio für Cloud-Deployments). Folgendes fehlt / ist unvollständig:

1. Transport selection CLI-flag based, not ENV-based (no MCP_TRANSPORT)
2. No deployment manifest sets transport explicitly
3. Host not set to 0.0.0.0 explicitly (relies on FastMCP default)

### Evidence

- server.py:737-743 — dual transport, --http -> streamable-http, else stdio
- Dockerfile:11 — CMD runs --http --port 8000, cloud image uses streamable-http
- README.md:99-104 documents --http cloud invocation

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Transport selection CLI-flag based, not ENV-based (no MCP_TRANSPORT)
2. No deployment manifest sets transport explicitly
3. Host not set to 0.0.0.0 explicitly (relies on FastMCP default)

Detail-Schritte und Code-Pattern siehe `checks/SCALE-001.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SCALE-001` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
