"""Tests for the retry policy against the upstream (ARCH-014).

The retry path had no tests at all before this file: a portfolio run on
2026-08-07 read the loop by hand and found no jitter, no `Retry-After`, and no
time bound. The loop *was* correct about what it retries — network errors and
5xx/429, fail fast on other 4xx — and those two properties are pinned here too,
so a later edit cannot lose them quietly.

Every property has a counter-check: the previous implementation is the honest
thing to measure against, because it was in production until this branch.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ToolError

import bag_health_mcp.server as srv

URL = "https://example.test/data.json"


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    """Zero the wait without disabling `asyncio.sleep` for the process.

    Patched on `srv._sleep`. `monkeypatch.setattr(srv.asyncio, "sleep", ...)`
    would look local and reach the stdlib module — every test that uses
    `asyncio.sleep` to yield to the event loop would then measure nothing and
    stay green. `test_the_no_backoff_fixture_leaves_asyncio_sleep_alone` guards
    the seam.
    """

    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(srv, "_sleep", _instant)


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers)


# --- Retry-After: read at all, and both RFC 9110 forms -----------------------


def test_retry_after_reads_delta_seconds():
    assert srv._parse_retry_after(_resp(429, "120")) == 120.0


def test_retry_after_reads_an_http_date():
    when = datetime.now(UTC) + timedelta(seconds=60)
    got = srv._parse_retry_after(_resp(503, format_datetime(when, usegmt=True)))
    assert got is not None
    assert 55 <= got <= 61


def test_retry_after_treats_a_past_date_as_now():
    when = datetime.now(UTC) - timedelta(hours=1)
    assert srv._parse_retry_after(_resp(503, format_datetime(when, usegmt=True))) == 0.0


def test_retry_after_reads_a_naive_date_as_gmt_not_local():
    when = datetime.now(UTC) + timedelta(seconds=30)
    got = srv._parse_retry_after(_resp(503, when.strftime("%a, %d %b %Y %H:%M:%S")))
    assert got is not None
    assert 25 <= got <= 31


@pytest.mark.parametrize("raw", ["", "   ", "soon", "not-a-date"])
def test_an_unreadable_retry_after_falls_back_instead_of_crashing(raw):
    # The error path is the one already going badly; a malformed header there
    # must not become a second failure.
    assert srv._parse_retry_after(_resp(429, raw)) is None


def test_retry_after_is_ignored_where_it_means_nothing():
    assert srv._parse_retry_after(_resp(500, "120")) is None
    assert srv._parse_retry_after(None) is None


# --- Jitter, and the cap that has to come after it ---------------------------


def test_the_exponential_delay_is_spread_not_deterministic():
    draws = {srv._retry_delay(1, None) for _ in range(50)}
    assert len(draws) > 1, "a lockstep backoff returns as a wave when the source recovers"


def test_the_ladder_starts_where_the_docstring_says():
    # The exponent used to be `attempt` rather than `attempt - 1`, so the real
    # first wait was 4s while every comment said 2s.
    draws = [srv._retry_delay(1, None) for _ in range(50)]
    assert all(1.0 <= d <= 3.0 for d in draws), (min(draws), max(draws))


def test_a_retry_after_delay_is_spread_one_sided():
    draws = [srv._retry_delay(1, _resp(429, "10")) for _ in range(50)]
    assert len(set(draws)) > 1
    assert all(10.0 <= d <= 12.5 for d in draws), sorted(draws)[:3]


def test_the_cap_is_a_real_bound_not_a_midpoint():
    # Jitter is random — one draw proves nothing.
    for attempt in range(1, 9):
        for _ in range(25):
            assert srv._retry_delay(attempt, None) <= srv.RETRY_MAX_DELAY
            assert srv._retry_delay(attempt, _resp(429, "86400")) <= srv.RETRY_MAX_DELAY


def test_capping_before_the_jitter_would_not_have_been_a_bound():
    """Counter-check for the cap ordering, so the test above is known to fail.

    `min(cap, base) * jitter` reads correctly and is not a bound: it multiplies
    an already-capped value by up to 1.5. That ordering shipped in six
    portfolio servers.
    """
    broken = min(srv.RETRY_BACKOFF_BASE * 2**7, srv.RETRY_MAX_DELAY) * 1.5
    assert broken > srv.RETRY_MAX_DELAY


# --- What is retried (pinning what was already right) ------------------------


@respx.mock
async def test_a_503_is_retried_and_the_retry_after_is_honoured(monkeypatch):
    seen: list[float] = []

    async def _record(seconds: float) -> None:
        seen.append(seconds)

    monkeypatch.setattr(srv, "_sleep", _record)
    respx.get(URL).mock(side_effect=[_resp(503, "7"), httpx.Response(200, json={})])
    async with httpx.AsyncClient() as client:
        r = await srv._get_with_retry(client, URL, context="testing")
    assert r.status_code == 200
    assert seen and 7.0 <= seen[0] <= 8.75, seen


@respx.mock
async def test_a_network_error_is_retried():
    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError("refused"), httpx.Response(200, json={})]
    )
    async with httpx.AsyncClient() as client:
        r = await srv._get_with_retry(client, URL, context="testing")
    assert r.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_a_404_is_not_retried():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ToolError):
            await srv._get_with_retry(client, URL, context="testing")
    assert route.call_count == 1, "a fourth attempt does not turn a 404 into a 200"


@respx.mock
async def test_attempts_are_bounded():
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ToolError):
            await srv._get_with_retry(client, URL, context="testing")
    assert route.call_count == srv.RETRY_ATTEMPTS


# --- The budget, measured on the wall clock ----------------------------------


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline(monkeypatch):
    """The assertion a fake clock cannot refute.

    A clock that only advances when something sleeps cannot disprove a claim
    about *real* time: the code that ignores the wall clock never sleeps, so no
    time passes and the broken version stays green. This test sleeps for real —
    deliberately, and it is the only one here that does.
    """
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 0.05)

    async def _slow(request):
        await asyncio.sleep(0.30)
        return httpx.Response(200)

    respx.get(URL).mock(side_effect=_slow)
    started = time.monotonic()
    async with httpx.AsyncClient() as client:
        with pytest.raises(ToolError):
            await srv._get_with_retry(client, URL, context="testing")
    assert time.monotonic() - started < 0.25, "the per-operation TIMEOUT is not a budget"


@respx.mock
async def test_a_wait_that_would_outlast_the_budget_is_not_taken(monkeypatch):
    # Sleeping past the caller's deadline buys nothing and costs the source a
    # request. The loop stops instead of taking the wait.
    monkeypatch.setattr(srv, "RETRY_TOTAL_BUDGET", 1.0)
    monkeypatch.setattr(srv, "_retry_delay", lambda *_a, **_k: 999.0)
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    async with httpx.AsyncClient() as client:
        with pytest.raises(ToolError):
            await srv._get_with_retry(client, URL, context="testing")
    assert route.call_count == 1


# --- The seam, and why it is not `asyncio.sleep` -----------------------------


async def test_the_no_backoff_fixture_leaves_asyncio_sleep_alone():
    """Guards the seam the autouse fixture patches.

    `monkeypatch.setattr(srv.asyncio, "sleep", ...)` would look local and reach
    the stdlib module, disabling sleeping for the whole process — including
    foreign tests that use it to yield to the event loop, which then measure
    nothing and stay green. That is how a concurrency check broke in
    `srgssr-mcp` without turning red.
    """
    started = time.monotonic()
    await asyncio.sleep(0.05)
    assert time.monotonic() - started >= 0.04, "asyncio.sleep is disabled process-wide"


# --- Exactly one level retries -----------------------------------------------


def test_no_second_retrying_level_underneath_the_loop():
    """Transport retries multiply with the loop rather than adding to it.

    `AsyncHTTPTransport(retries=2)` under a loop of 4 is 3 x 4 attempts, not
    3 + 4 — and neither number appears anywhere in the code. httpx defaults to
    0; this reads the value off the built client rather than off the source
    text, so it stays true no matter how the transport is spelled.
    """
    client = srv._new_client()
    assert client._transport._pool._retries == 0
