"""Shared test fixtures for bag-health-mcp.

The egress guard (SEC-004) resolves the target host on every request and blocks
non-public IPs. To keep unit tests hermetic — no real DNS, deterministic — an
autouse fixture stubs the module-level resolver so the allowed host resolves to
a fixed public IP. Tests that exercise the IP blocklist override the stub.
"""

import pytest

import bag_health_mcp.server as server

# A stable, routable public IP used as the default stubbed resolution result.
PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def stub_dns(request, monkeypatch):
    """Resolve any host to a fixed public IP unless a test overrides this.

    Prevents the egress guard from performing real DNS during unit tests.

    Live tests are exempt. They exist to ask the real source, and a stubbed
    resolver makes exactly that impossible: the pinning backend (SEC-005) dials
    the address the resolver hands it, so every live test connected to
    ``PUBLIC_IP`` carrying the real host's SNI. On an ordinary network that
    hangs until the timeout; behind a proxy that routes by hostname it *passes*
    — and a passing test that never reached the source is worse than none,
    because it is read as proof it cannot give.
    """
    if "live" in request.keywords:
        return None

    async def _fake_resolve(host: str) -> list[str]:
        return [PUBLIC_IP]

    monkeypatch.setattr(server, "_resolve_host", _fake_resolve)
    return monkeypatch
