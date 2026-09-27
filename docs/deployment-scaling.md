# Deployment & scaling guide — bag-health-mcp

Reference guidance for running the server over **Streamable HTTP** in a
cloud/cluster setting. The concrete manifests are Kubernetes (matching the
existing `deploy/networkpolicy.yaml`), but the principles map to any
orchestrator — adapt them to your platform. Covers audit findings
**SCALE-001, -002, -003, -005, -006**.

> These are **reference templates**, not a turnkey production configuration.
> Review image pinning, replica count, resource sizing and ingress class before
> use.

---

## 1. Transport selection (SCALE-001)

Use **Streamable HTTP** for cloud deployments and select it via the
**`MCP_TRANSPORT`** environment variable rather than a CLI flag, so the choice
lives in your deployment manifest:

| Variable | Values | Default |
|----------|--------|---------|
| `MCP_TRANSPORT` | `http` (= streamable-http) / `stdio` | unset → falls back to `--http` flag, else stdio |
| `MCP_HOST` | bind address | `127.0.0.1` (set `0.0.0.0` in a container) |
| `MCP_PORT` | port | `8000` |

`MCP_TRANSPORT` takes precedence over the `--http` flag. See
`deploy/deployment.yaml` for the env block. `stdio` remains the default for
local/Claude-Desktop use.

---

## 2. No session affinity needed (SCALE-002, SCALE-003)

The server is **sessionless over HTTP in both protocol eras**, so any replica can
answer any request and a plain round-robin load balancer is enough:

| Client speaks | Session | What the LB must do |
|---|---|---|
| `2026-07-28` (per-request envelope) | none — the revision has no session | nothing |
| `2025-11-25` and earlier (`initialize` handshake) | none — `STATELESS_HTTP = True` in `server.py` | nothing |

The first row is the spec itself: a `2026-07-28` request is one self-contained
POST, no `initialize` before it, no `Mcp-Session-Id` after it. The second row is
a choice this server makes (`stateless_http=True`): the SDK then builds a
throwaway per-request session for handshake-era clients instead of holding one
in pod memory.

That choice costs the legacy leg its server-to-client channels outside a
response — server-initiated requests (sampling, roots, push elicitation) and
standalone notifications. This server uses none of them: no tool asks the client
anything, the tool/resource/prompt lists are fixed at import, and protocol
logging is gone (deprecated in `2026-07-28`, SEP-2577). **Progress still
arrives** — it travels on the response stream of the tool call itself. All of
this is measured in `tests/test_spec_2026_07_28.py`, including the case that
matters here: a handshake on one app instance, the tool call on a second one.

> Earlier versions of this guide required client-IP affinity or
> `Mcp-Session-Id` header routing (HAProxy stick-table, NGINX
> `upstream-hash-by`). Both are unnecessary now and have been removed from
> `deploy/deployment.yaml`; leaving them in place is harmless but skews load.
>
> Revisit this section the day a tool needs to ask the client something
> (`Resolve(...)` / `InputRequiredResult`) or to push list changes: that is the
> point where `STATELESS_HTTP` has to be decided again, and where
> `request_state_security=` (shared keys across replicas) and a shared
> `subscriptions=` bus come in.

---

## 3. Resource limits (SCALE-006)

Always set per-container CPU/memory **requests and limits** so a single pod
can't exhaust the node, and so the scheduler can place pods sensibly. The server
is lightweight (an async HTTP proxy to one upstream API); starting point in
`deploy/deployment.yaml`:

```yaml
resources:
  requests: { cpu: "50m",  memory: "128Mi" }
  limits:   { cpu: "500m", memory: "256Mi" }
```

Tune from observed usage. The container also runs **non-root** with a read-only
root filesystem and all capabilities dropped (see the `securityContext` blocks).

---

## 4. MCP gateway / access control (SCALE-005)

For an enterprise / Stadt-Zürich context, prefer **not** exposing the server
directly. Front it with an MCP gateway (or API gateway) that provides:

- **Authentication & authorization** in front of the (unauthenticated) server —
  the server itself reaches only public OGD data, but *who may invoke it* should
  be controlled at the edge.
- A **tool allow-list** if only a subset of the 10 tools should be reachable in a
  given deployment.
- **Audit-log export to a SIEM** — the server emits structured JSON logs on
  stderr (OBS-003) and optional OpenTelemetry traces (OBS-006); ship both to
  your central logging/SIEM from the gateway and the pod.
- A single **egress chokepoint**, complementing the code-layer egress allow-list
  (SEC-021) and the `NetworkPolicy`.

This keeps the server a thin, read-only data adapter while policy, authN/Z and
auditing live in a controlled gateway layer (anti-"shadow MCP").

> **TODO (Betrieb/OIZ):** choose the concrete gateway product and SIEM target
> for your environment; the above is the required shape, not a product decision
> I can make for you.

---

## 5. Apply

```bash
kubectl apply -f deploy/networkpolicy.yaml   # egress control (SEC-021)
kubectl apply -f deploy/deployment.yaml      # Deployment + Service (this guide)
# then an Ingress/LB of your choice — no session routing needed (§2)
```

See also: [`docs/isds-klassifikation.md`](isds-klassifikation.md) (ISDS) and
[`docs/datenklassifikation-schulamt.md`](datenklassifikation-schulamt.md)
(data classification).
