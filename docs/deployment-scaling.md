# Deployment & scaling guide — bag-health-mcp

Reference guidance for running the server over **Streamable HTTP** in a
cloud/cluster setting. The concrete manifests are Kubernetes (matching the
existing `deploy/networkpolicy.yaml`), but the principles map to any
orchestrator — adapt them to your platform. Covers audit findings
**SCALE-001, -002, -003, -005, -006**.

> These are **reference templates**, not a turnkey production configuration.
> Review image pinning, replica count, resource sizing, ingress class, and your
> LB's session-routing capabilities before use.

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

## 2. Session affinity (SCALE-002, SCALE-003)

Streamable HTTP / SSE sessions are held **in pod memory** (FastMCP has no shared
session backend). With more than one replica, a client's requests must keep
reaching the **same pod** for the life of its session, or the session breaks on
a pod switch. Two options, simplest first:

**(a) Service-level client-IP affinity** — in `deploy/deployment.yaml`:

```yaml
spec:
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600   # ≥ your longest session
```

Works without any LB cookie/header support. Caveat: clients behind a shared NAT
egress IP land on the same pod (coarse balancing).

**(b) `Mcp-Session-Id` header routing at an edge LB** — more precise; routes by
the MCP session id the protocol already sends. Sketches:

*HAProxy stick-table:*
```haproxy
backend mcp
  balance roundrobin
  stick-table type string len 64 size 100k expire 60m
  stick on req.hdr(Mcp-Session-Id)
  server s1 10.0.0.1:8000 check
  server s2 10.0.0.2:8000 check
```

*NGINX Ingress (consistent hash on the header):*
```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"
```

Pick (a) for small/internal deployments; (b) when you run a dedicated edge LB or
need failover semantics. Either way, set a session **TTL** (≥ expected session
length) so stale entries expire.

> A fully stateless horizontal scale-out would require a shared session store
> (e.g. Redis) behind FastMCP, which the SDK does not provide out of the box —
> out of scope here; affinity is the pragmatic answer for this workload.

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
# then an Ingress/LB of your choice for Mcp-Session-Id routing (§2b), if used
```

See also: [`docs/isds-klassifikation.md`](isds-klassifikation.md) (ISDS) and
[`docs/datenklassifikation-schulamt.md`](datenklassifikation-schulamt.md)
(data classification).
