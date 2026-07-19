# Security posture — bag-health-mcp

Concise statements of the server's security-relevant design decisions, for audit
and review. Companion to the ISDS and data-classification docs.

---

## 1. Lethal Trifecta assessment (SEC-019)

The "lethal trifecta" for tool-using agents is the simultaneous presence of all
three of:

1. **access to private/sensitive data**,
2. **exposure to untrusted content**, and
3. **the ability to externally communicate / act** (exfiltration or state
   change).

An agent server is dangerous when it holds **all three legs**. This server holds
**at most one**, so the combination cannot arise:

| Leg | Present? | Why |
|-----|----------|-----|
| Private/sensitive data | **No** | Only public Swiss Open Government Data, aggregated/anonymised (BAG IDD at canton level; Obsan/Versorgungsatlas/Sucht-Schweiz HBSC indicators are population aggregates by age/sex/region). No personal data, no secrets, no internal systems. |
| Untrusted content | Partially | Upstream API responses are parsed, but never executed; raw bodies/exceptions are never surfaced to the model (OBS-002). |
| Exfiltration / external action / write | **No** | The server is **strictly read-only**. Outbound calls go only to a **fixed allow-list of three public data hosts** (`api.idd.bag.admin.ch`, `ind.obsan.admin.ch`, `www.versorgungsatlas.ch`), enforced on every hop (egress allow-list + IP-blocklist + DNS-pinning, SEC-004/005/021). No write tools, no send/email/exec, no arbitrary destination. |

**Conclusion:** ≤ 1 leg → the lethal-trifecta risk does **not** apply. The
read-vs-write/send separation is structural: there are no write or
communication tools to separate out, and outbound egress is pinned to a fixed
allow-list of public data hosts. Should write-capable tools ever be added (see
[roadmap](roadmap.md)), they must run in a **separate server/process** from any
component handling untrusted content, and this assessment must be redone.

---

## 2. Secret management (SEC-013)

**The server uses no secrets.** It accesses the BAG IDD API, which is public
Open Government Data requiring **no authentication and no API key**.

- No API keys, tokens, passwords or credentials exist in code, config or
  environment (verified: zero secret references in `src/`).
- Therefore no secret store / secret manager is required.
- CI runs **gitleaks** secret-scanning on every push (ARCH-005) as a guard
  against secrets being introduced accidentally; dependencies are pinned and
  Dependabot-monitored.

This "no-secret" posture is an explicit, accepted design decision documented
here per the audit's pass-criteria — not an oversight. If the system is ever
extended to a data source that requires credentials, those **must** be sourced
from a secret manager / injected secret (never committed, never a plaintext env
default), and this document updated.

---

## 3. Network exposure (SEC-006 / SEC-016)

- **Default transport is stdio** (no network surface) for local/desktop use.
- For HTTP, the server binds to **`127.0.0.1` by default**; all-interface
  binding (`0.0.0.0`) is an **explicit opt-in** via `MCP_HOST`, intended only
  for network-isolated container/cluster deployments behind a gateway and a
  `NetworkPolicy` (see [`deploy/`](../deploy/)). Binding to a non-localhost host
  is logged as a warning at startup (NeighborJack awareness).
- The server serves only public data, so data sensitivity does not require
  authentication. **Who may invoke it** can still be controlled:
  - **In-server (SEC-009):** set `MCP_AUTH_TOKEN` to require an
    `Authorization: Bearer <token>` on every HTTP request (401 otherwise),
    compared in constant time. Unset = no auth (stdio/local). This is a
    shared-secret gate, not a per-user identity system.
  - **CORS (SDK-004):** `MCP_CORS_ORIGINS` is an explicit origin allow-list
    (never a wildcard) for browser MCP clients; the `Mcp-Session-Id` header is
    exposed so stateful sessions work.
  - For real per-user identity/authorisation, front the server with an edge
    gateway (see the [deployment & scaling guide](deployment-scaling.md)).

---

*See also: [`isds-klassifikation.md`](isds-klassifikation.md),
[`datenklassifikation-schulamt.md`](datenklassifikation-schulamt.md),
[`deployment-scaling.md`](deployment-scaling.md).*
