## Finding: SEC-006 — Lokaler Server: stdio-Transport zwingend (Netzwerk-Isolation)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-006` |
| **PDF-Reference** | Sec 4.5 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Default transport is stdio: mcp.run() unless '--http' in sys.argv (server.py:738-743)
- HTTP only via explicit --http flag, not default
- README documents local stdio with Claude Desktop (README.md:86-96); claude_desktop_config.json uses stdio command

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-006` (Lokaler Server: stdio-Transport zwingend (Netzwerk-Isolation)). Folgendes fehlt / ist unvollständig:

1. Cloud/HTTP section has no security warning about network exposure
2. Activation via CLI flag rather than MCP_TRANSPORT env-var (cosmetic vs Pass-Criteria wording)

### Evidence

- Default transport is stdio: mcp.run() unless '--http' in sys.argv (server.py:738-743)
- HTTP only via explicit --http flag, not default
- README documents local stdio with Claude Desktop (README.md:86-96); claude_desktop_config.json uses stdio command

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Cloud/HTTP section has no security warning about network exposure
2. Activation via CLI flag rather than MCP_TRANSPORT env-var (cosmetic vs Pass-Criteria wording)

Detail-Schritte und Code-Pattern siehe `checks/SEC-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
