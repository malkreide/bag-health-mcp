## Finding: SEC-016 — 0.0.0.0-Binding-Prevention (NeighborJack)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-016` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- server.py:741 — mcp.run(transport='streamable-http', port=port) sets no host argument
- Verified against mcp 1.27.2 (fresh install of pinned 'mcp[cli]>=1.0.0'): FastMCP default host is '127.0.0.1' (FastMCP('probe').settings.host == '127.0.0.1'); localhost binding also auto-enables TransportSecuritySettings DNS-rebinding protection
- grep for 0.0.0.0 across py/toml/yaml/Dockerfile = zero matches — no explicit all-interfaces binding

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-016` (0.0.0.0-Binding-Prevention (NeighborJack)). Folgendes fehlt / ist unvollständig:

1. Binding relies on the IMPLICIT SDK default rather than an explicit 127.0.0.1 / MCP_HOST configuration; the pin 'mcp[cli]>=1.0.0' is unbounded and earlier SDK versions defaulted host to 0.0.0.0 — latent NeighborJack risk on a downgrade/older lockfile
2. No README note on host binding / local-vs-container differentiation; no warning when a non-localhost host is configured
3. SEPARATE FUNCTIONAL DEFECT: FastMCP.run() signature is run(transport, mount_path) — it does NOT accept port=; server.py:741 raises TypeError at startup, so the --http path (and Dockerfile CMD --http --port 8000) crashes before binding at all

### Evidence

- server.py:741 — mcp.run(transport='streamable-http', port=port) sets no host argument
- Verified against mcp 1.27.2 (fresh install of pinned 'mcp[cli]>=1.0.0'): FastMCP default host is '127.0.0.1' (FastMCP('probe').settings.host == '127.0.0.1'); localhost binding also auto-enables TransportSecuritySettings DNS-rebinding protection
- grep for 0.0.0.0 across py/toml/yaml/Dockerfile = zero matches — no explicit all-interfaces binding

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Binding relies on the IMPLICIT SDK default rather than an explicit 127.0.0.1 / MCP_HOST configuration; the pin 'mcp[cli]>=1.0.0' is unbounded and earlier SDK versions defaulted host to 0.0.0.0 — latent NeighborJack risk on a downgrade/older lockfile
2. No README note on host binding / local-vs-container differentiation; no warning when a non-localhost host is configured
3. SEPARATE FUNCTIONAL DEFECT: FastMCP.run() signature is run(transport, mount_path) — it does NOT accept port=; server.py:741 raises TypeError at startup, so the --http path (and Dockerfile CMD --http --port 8000) crashes before binding at all

Detail-Schritte und Code-Pattern siehe `checks/SEC-016.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-016` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
