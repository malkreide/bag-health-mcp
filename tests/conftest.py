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
def stub_dns(monkeypatch):
    """Resolve any host to a fixed public IP unless a test overrides this.

    Prevents the egress guard from performing real DNS during unit tests.
    """
    async def _fake_resolve(host: str) -> list[str]:
        return [PUBLIC_IP]

    monkeypatch.setattr(server, "_resolve_host", _fake_resolve)
    return monkeypatch
