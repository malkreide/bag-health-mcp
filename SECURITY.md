# Security Policy

**[🇩🇪 Deutsche Version](SECURITY.de.md)**

This server is part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide).

---

## Reporting a Vulnerability

Please report security vulnerabilities **privately** — do not open a public issue
for security problems.

- Use [GitHub Security Advisories](https://github.com/malkreide/bag-health-mcp/security/advisories/new)
  (preferred), or
- contact the maintainer directly.

Please include:
- A description of the vulnerability and its impact
- Steps to reproduce (proof of concept if possible)
- Affected version / commit

We aim to acknowledge reports within a few days and to coordinate a fix and
disclosure timeline with you.

---

## Supported Versions

This is a Phase 1 (read-only) server under active development. Security fixes are
applied to the latest released version on [PyPI](https://pypi.org/project/bag-health-mcp/)
and the `main` branch. Pin to a specific released version or git tag for
production deployments.

---

## Security Model

The server follows a **public-data-only, read-only** design:

- **No authentication / no secrets** — it accesses only public Swiss Open
  Government Data APIs (BAG IDD, Obsan, Versorgungsatlas), which require no API key
  or credentials. Sucht-Schweiz/HBSC series are obtained via the Obsan mirror.
- **Read-only operations** — every tool performs HTTPS `GET`/`POST`-query requests
  only; there are no write, send or execute capabilities.
- **No personal data** — all data is aggregated/anonymised at source: BAG IDD at
  canton level with small cells suppressed; the indicator sources are population
  aggregates by age/sex/region.
- **Egress allow-list** — the server only ever contacts a fixed allow-list of three
  public data hosts (`api.idd.bag.admin.ch`, `ind.obsan.admin.ch`,
  `www.versorgungsatlas.ch`), HTTPS-only, enforced on every request including
  redirect hops (SSRF protection), with a network-layer companion policy in
  [`deploy/networkpolicy.yaml`](deploy/networkpolicy.yaml).
- **Network exposure** — the default stdio transport has no network surface; HTTP
  binds to `127.0.0.1` by default and only binds all interfaces on explicit
  opt-in (`MCP_HOST=0.0.0.0`) for network-isolated deployments.

### Lethal-trifecta assessment

The server holds **at most one** of the three legs (private data, untrusted
content, exfiltration capability), so the prompt-injection-to-exfiltration chain
cannot close. Full assessment, secret-management decision and network-exposure
notes are in [`docs/security-posture.md`](docs/security-posture.md).

For deployment hardening (gateway, resource limits, `NetworkPolicy`), see the
[deployment & scaling guide](docs/deployment-scaling.md).
