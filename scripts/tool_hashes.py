#!/usr/bin/env python3
"""Tool-definition hash snapshot (SEC-022, rug-pull guard).

Computes a SHA-256 over each MCP tool's *contract* — name, description and
input/output JSON schemas — and compares it against a committed snapshot
(`tool-hashes.json`). A drift means a tool's observable definition changed; in CI
that fails the build so a silent ("rug-pull") change to what a tool claims to do
cannot ship unnoticed. Intentional changes are acknowledged by regenerating the
snapshot (`--write`) in the same PR, which makes the diff reviewable.

Usage:
    python scripts/tool_hashes.py --check    # CI: fail on drift (default)
    python scripts/tool_hashes.py --write    # update the snapshot after an
                                             # intentional tool change
    python scripts/tool_hashes.py --print     # print current hashes
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

# Allow running from the repo root without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

SNAPSHOT = Path(__file__).resolve().parent.parent / "tool-hashes.json"


def _tool_hash(tool) -> str:
    """Stable SHA-256 of a tool's observable contract."""
    payload = {
        "name": tool.name,
        "description": tool.description or "",
        "inputSchema": tool.inputSchema,
        "outputSchema": getattr(tool, "outputSchema", None),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def current_hashes() -> dict[str, str]:
    from bag_health_mcp.server import mcp

    tools = await mcp.list_tools()
    return {t.name: _tool_hash(t) for t in sorted(tools, key=lambda t: t.name)}


def load_snapshot() -> dict[str, str]:
    if not SNAPSHOT.exists():
        return {}
    return json.loads(SNAPSHOT.read_text())["tools"]


def write_snapshot(hashes: dict[str, str]) -> None:
    SNAPSHOT.write_text(
        json.dumps({"algorithm": "sha256", "tools": hashes}, indent=2) + "\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="fail on drift (default)")
    g.add_argument("--write", action="store_true", help="update the snapshot")
    g.add_argument("--print", action="store_true", help="print current hashes")
    args = ap.parse_args()

    hashes = asyncio.run(current_hashes())

    if args.print:
        print(json.dumps(hashes, indent=2))
        return 0
    if args.write:
        write_snapshot(hashes)
        print(f"wrote {SNAPSHOT.name} ({len(hashes)} tools)")
        return 0

    # default: --check
    expected = load_snapshot()
    if not expected:
        print(f"ERROR: no snapshot at {SNAPSHOT}; run --write first", file=sys.stderr)
        return 2
    if hashes != expected:
        print("ERROR: tool-definition hash drift detected (SEC-022).", file=sys.stderr)
        for name in sorted(set(hashes) | set(expected)):
            cur, exp = hashes.get(name), expected.get(name)
            if cur != exp:
                print(f"  {name}: snapshot={exp} current={cur}", file=sys.stderr)
        print(
            "If this change is intentional, run "
            "`python scripts/tool_hashes.py --write` and commit the updated "
            "tool-hashes.json in this PR.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: {len(hashes)} tool hashes match the snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
