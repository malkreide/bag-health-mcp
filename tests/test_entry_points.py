"""Die dokumentierten Startbefehle muessen einen Server hochbringen.

`python -m bag_health_mcp.server` brach bis hierher mit einem zirkulaeren Import
ab (`partially initialized module 'bag_health_mcp._tools' has no attribute
'READ_ONLY'`), waehrend alle Tests gruen waren: sie importieren das Modul,
statt es als `__main__` zu starten. Genau diesen Befehl nennen aber README und
`claude_desktop_config.json`.

Geprueft wird deshalb der echte Start als Unterprozess, ueber stdio, bis zu
einer `tools/list`-Antwort — nicht, ob das Modul importierbar ist.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest
from mcp import Client, StdioServerParameters

REPO = pathlib.Path(__file__).resolve().parents[1]

MODULE_FORMS = [
    ["-m", "bag_health_mcp.server"],  # README, claude_desktop_config.json
    ["-m", "bag_health_mcp"],
]


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(REPO / "src"), env.get("PYTHONPATH", "")) if p
    )
    env.pop("MCP_TRANSPORT", None)  # stdio erzwingen, auch wenn die Umgebung http setzt
    return env


@pytest.mark.parametrize("args", MODULE_FORMS, ids=lambda a: " ".join(a))
async def test_der_startbefehl_bringt_den_server_hoch(args: list[str]) -> None:
    params = StdioServerParameters(command=sys.executable, args=args, env=_env())
    async with Client(params) as client:
        tools = (await client.list_tools()).tools
    assert len(tools) == 10


def test_die_desktop_konfiguration_nennt_eine_gepruefte_form() -> None:
    """Die Beispielkonfiguration darf nicht auf einen ungeprueften Aufruf
    zeigen — sonst waere der Test oben gruen und der Nutzer trotzdem ohne
    Server."""
    config = json.loads((REPO / "claude_desktop_config.json").read_text(encoding="utf-8"))
    for server in config["mcpServers"].values():
        assert server["args"] in MODULE_FORMS, server["args"]
