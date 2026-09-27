"""Spec 2026-07-28 nativ: kein Handshake, keine Session, kein Protokoll-Logging.

`test_protocol_version.py` pinnt, WELCHE Revisionen das SDK erreicht. Diese
Datei prueft, dass der Server sie auch so spricht, wie 2026-07-28 es meint —
und zwar an den drei Stellen, an denen die Revision das Verhalten aendert:

* **Kein Handshake.** Ein moderner Client ruft ein Tool auf, ohne je
  `initialize` gesendet zu haben, und bekommt eine vollstaendige Antwort samt
  Fortschritt.
* **Keine Session.** Kein Antwort-Header traegt `Mcp-Session-Id`, in keiner
  Aera. Gemessen als das, worauf es im Betrieb ankommt: zwei getrennt gebaute
  Apps stehen fuer zwei Worker, und die zweite beantwortet eine Anfrage, deren
  Vorgeschichte nur die erste kennt.
* **Kein Protokoll-Logging.** SEP-2577 kuendigt `ctx.info`/`ctx.warning` ab.
  Die Wache dafuer steht in `pyproject.toml` (`error::mcp.MCPDeprecationWarning`)
  und greift hier, weil die Tools durch einen echten Client laufen: ein
  zurueckgekehrter `ctx.info` macht den Aufruf zu `is_error`.

Die HTTP-Faelle laufen durch `build_http_app`, nicht durch
`mcp.streamable_http_app()` — geprueft wird, was ausgeliefert wird.
"""

from __future__ import annotations

import json
import pathlib
import tomllib

import httpx
import respx
from mcp import Client
from test_server import MOCK_DATA, MOCK_DETAILS

from bag_health_mcp.server import IDD_BASE, STATELESS_HTTP, Settings, build_http_app, mcp

MODERN = "2026-07-28"
LEGACY = "2025-11-25"
REPO = pathlib.Path(__file__).resolve().parents[1]
SERIES = "influenza/cases/incValue/iso_week"
TOOL = "bag_health_mcp__get_disease_data"
ARGS = {"params": {"series_id": SERIES, "canton": "ZH"}}

_BASE_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": "127.0.0.1:8000",
}


def _mock_idd(router: respx.MockRouter) -> None:
    router.get(f"{IDD_BASE}/api/v1/data/{SERIES}/details").mock(
        return_value=httpx.Response(200, json=MOCK_DETAILS)
    )
    router.post(f"{IDD_BASE}/api/v1/data/{SERIES}").mock(
        return_value=httpx.Response(200, json=MOCK_DATA)
    )


def _messages(response: httpx.Response) -> list[dict]:
    """JSON-RPC-Nachrichten einer Antwort, ob als JSON oder als SSE gerahmt."""
    if response.headers.get("content-type", "").startswith("application/json"):
        return [response.json()]
    return [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def _call_body(meta: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": TOOL, "arguments": ARGS, "_meta": meta},
    }


# ---------------------------------------------------------------------------
# Kein Handshake
# ---------------------------------------------------------------------------


async def test_der_client_landet_ohne_zutun_auf_2026_07_28() -> None:
    """Der SDK-Client probt `server/discover` und faellt nur zurueck, wenn der
    Server aelter ist. Landet er auf der Handshake-Revision, spricht der Server
    2026-07-28 nicht — egal, was die Konstanten sagen."""
    async with Client(mcp) as client:
        assert client.protocol_version == MODERN
        assert client.server_info is not None
        assert client.server_info.name == "bag-health-mcp"


@respx.mock
async def test_ein_tool_laeuft_modern_durch_mit_fortschritt() -> None:
    """Der lasttragende Fall: echter Client, moderne Revision, echtes Tool.

    Faellt der Aufruf mit `is_error`, ist der naheliegende Grund ein
    zurueckgekehrter `ctx.info` — die Deprecation-Wache in `pyproject.toml`
    macht ihn zum Fehler, und der Client sieht «Error executing tool».
    """
    _mock_idd(respx)
    progress: list[tuple[float, float | None]] = []

    async def on_progress(value: float, total: float | None, message: str | None) -> None:
        progress.append((value, total))

    async with Client(mcp) as client:
        assert client.protocol_version == MODERN
        result = await client.call_tool(TOOL, ARGS, progress_callback=on_progress)

    assert not result.is_error, result.content
    assert result.structured_content["topic"] == "influenza"
    assert progress[0] == (0, 2)
    assert progress[-1] == (2, 2)


async def test_das_modell_bekommt_keine_protokoll_logs() -> None:
    """Auch ein Legacy-Client, der Logs ausdruecklich abonniert, bekommt keine.

    Ohne diese Zusicherung koennte ein `ctx.info` zurueckkehren und nur deshalb
    unbemerkt bleiben, weil ein moderner Client ohnehin keine Logs empfaengt.
    """
    received: list[object] = []

    async def on_log(params: object) -> None:
        received.append(params)

    with respx.mock:
        _mock_idd(respx)
        async with Client(mcp, mode="legacy", logging_callback=on_log) as client:
            assert client.protocol_version == LEGACY
            result = await client.call_tool(TOOL, ARGS)

    assert not result.is_error, result.content
    assert received == []


# ---------------------------------------------------------------------------
# Keine Session
# ---------------------------------------------------------------------------


async def _post(app, headers: dict, body: dict) -> httpx.Response:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client:
            return await client.post("/mcp", headers=headers, json=body)


def _app():
    return build_http_app(Settings(auth_token="", cors_origins=""))


def test_der_schalter_steht_auf_sessionlos() -> None:
    """Die HTTP-Tests unten setzen ihn voraus; faellt dieser, lesen sie sich
    wie ein Transportfehler statt wie eine Entscheidung."""
    assert STATELESS_HTTP is True


async def test_modern_ohne_initialize_und_ohne_session() -> None:
    headers = {
        **_BASE_HEADERS,
        "Mcp-Protocol-Version": MODERN,
        "Mcp-Method": "tools/call",
        "Mcp-Name": TOOL,
    }
    meta = {
        "progressToken": "p1",
        "io.modelcontextprotocol/protocolVersion": MODERN,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    with respx.mock(assert_all_called=False) as router:
        router.route(host="127.0.0.1").pass_through()
        _mock_idd(router)
        response = await _post(_app(), headers, _call_body(meta))

    assert response.status_code == 200, response.text
    assert "mcp-session-id" not in response.headers
    messages = _messages(response)
    progress = [m for m in messages if m.get("method") == "notifications/progress"]
    final = [m for m in messages if m.get("id") == 2]
    assert len(progress) == 3
    assert len(final) == 1
    assert not final[0]["result"].get("isError")
    assert final[0]["result"]["structuredContent"]["topic"] == "influenza"
    # serverInfo steht seit 2026-07-28 im `_meta` jedes Resultats (spec #3002)
    assert "bag-health-mcp" in json.dumps(final[0]["result"].get("_meta", {}))


async def test_legacy_braucht_keinen_klebrigen_worker() -> None:
    """Zwei getrennt gebaute Apps stehen fuer zwei Worker hinter einem
    Round-Robin-Balancer. Worker A sieht den Handshake, Worker B den Aufruf.

    Mit Session ginge das nicht: A vergaebe eine `Mcp-Session-Id`, der Client
    schickte sie an B, und B kennte sie nicht — 404 «Session not found». Das
    ist die Gegenprobe, und sie faellt, sobald `STATELESS_HTTP` auf False steht.
    """
    worker_a, worker_b = _app(), _app()

    init = await _post(
        worker_a,
        _BASE_HEADERS,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LEGACY,
                "capabilities": {},
                "clientInfo": {"name": "legacy-client", "version": "1"},
            },
        },
    )
    assert init.status_code == 200, init.text
    assert _messages(init)[0]["result"]["protocolVersion"] == LEGACY

    # Was ein Legacy-Client an B schickt: die Revision, und die Session, falls
    # A eine vergeben hat. Genau diese zweite Zeile macht den Test scharf.
    headers = {**_BASE_HEADERS, "Mcp-Protocol-Version": LEGACY}
    if sid := init.headers.get("mcp-session-id"):
        headers["Mcp-Session-Id"] = sid

    with respx.mock(assert_all_called=False) as router:
        router.route(host="127.0.0.1").pass_through()
        _mock_idd(router)
        call = await _post(worker_b, headers, _call_body({"progressToken": "p1"}))

    assert call.status_code == 200, call.text
    assert "mcp-session-id" not in init.headers
    assert "mcp-session-id" not in call.headers
    messages = _messages(call)
    # Fortschritt ueberlebt die fehlende Session: er laeuft im Stream der
    # Antwort, nicht im eigenstaendigen GET-Kanal, den `stateless_http` kostet.
    assert len([m for m in messages if m.get("method") == "notifications/progress"]) == 3
    final = [m for m in messages if m.get("id") == 2]
    assert final and not final[0]["result"].get("isError")


def test_kein_tool_fragt_beim_client_zurueck() -> None:
    """Sessionlos heisst: kein Server->Client-Kanal ausserhalb der Antwort.
    Das ist nur gratis, solange kein Tool einen braucht.

    Ab 2026-07-28 laeuft eine Rueckfrage als `Resolve`-Parameter oder als
    zurueckgegebenes `InputRequiredResult`; auf einer Legacy-Verbindung ohne
    Session scheitert sie mit `NoBackChannelError`, und zwar als Protokollfehler,
    den das Modell nicht lesen kann. Faellt dieser Test, ist `STATELESS_HTTP`
    im selben Commit neu zu entscheiden.
    """
    tools = mcp._tool_manager.list_tools()
    assert len(tools) == 10
    with_resolvers = [t.name for t in tools if t.resolved_params]
    assert not with_resolvers, with_resolvers

    src = (REPO / "src").rglob("*.py")
    back_channel = ("ctx.elicit", "create_message(", "list_roots(", "InputRequiredResult")
    offenders = [
        f"{path.name}: {needle}"
        for path in src
        for needle in back_channel
        if needle in path.read_text(encoding="utf-8")
    ]
    assert not offenders, offenders


def test_die_deprecation_wache_ist_eingeschaltet() -> None:
    """Die Wache gegen Protokoll-Logging und die uebrigen SEP-2577-Faehigkeiten
    ist eine Zeile Konfiguration. Ohne sie waere `ctx.info` wieder eine
    Warnung, die niemand liest, und die Tool-Tests oben blieben gruen."""
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    filters = config["tool"]["pytest"]["ini_options"].get("filterwarnings", [])
    assert "error::mcp.MCPDeprecationWarning" in filters
