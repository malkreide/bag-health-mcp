# Roadmap — phase architecture (OPS-003)

This server follows a **read-only-first** phase architecture: capabilities are
introduced in stages, with each stage gated on prerequisites being met before
the next is enabled. Write/mutating capabilities are deliberately deferred.

## Phase status

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1 — Read-only wrapper** | Read-only access to public Swiss health data: the BAG IDD API (list/inspect diseases & series, time-series data, canton overview, exports, data version) plus a multi-source indicator layer (Obsan, Versorgungsatlas, Sucht-Schweiz/HBSC — search + series). 10 tools, all `readOnlyHint=true`; egress pinned to a fixed 3-host allow-list. | ✅ **Active** |
| **Phase 2 — Enrichment / analysis** *(planned)* | Read-only value-adds: outbreak heuristics, 5-year-mean comparison, cross-series correlation. Still no writes. | ⏳ Not started |
| **Phase 3 — Write / send capabilities** *(not planned)* | Any mutating or outbound-communicating tool (e.g. alerting, report delivery). | ⛔ Deferred — see prerequisites |

## Why read-only first

Keeping the server strictly read-only avoids the "lethal trifecta" entirely (see
[`security-posture.md`](security-posture.md)): with no write/send leg, exposure
to untrusted upstream content cannot lead to exfiltration or unwanted action.

## Prerequisites before enabling any write/send phase

A future Phase 3 must **not** be added to this server process. Before any
write- or communication-capable tool ships, all of the following are required:

1. **Server separation** — write/send tools run in a **separate server/process**
   from anything handling untrusted content (no single server holds read +
   untrusted-content + write/send together).
2. **AuthN/Z** — an authenticated, authorised caller model (today the server is
   unauthenticated by design; writes require identity + permissions, fronted by
   the MCP gateway).
3. **Re-classification** — redo the ISDS Schutzbedarfs- and Schulamt
   data-classification analyses; writes likely raise Integrität/Vertraulichkeit.
4. **Audit trail** — mutating actions logged to a SIEM with actor + before/after.
5. **Lethal-trifecta re-assessment** documented and signed off.

Until these are met, the server stays Phase 1 / read-only.
