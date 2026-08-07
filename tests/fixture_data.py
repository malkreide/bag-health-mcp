"""Access to the recorded fixtures under ``tests/fixtures/``.

Those files are **recorded, not invented**: source, retrieval date, selection
rule and SHA-256 are listed in ``tests/fixtures/PROVENANCE.md``, written by
``scripts/record_fixtures.py``.

Before this, every payload in the suite was a literal in the test module, and
the repository's only ``@pytest.mark.live`` test is skipped -- ``pytest -m live``
collects zero tests here. Nothing had ever compared these assumptions against
the real hosts. When they finally were compared, the sitemap fixture turned out
to describe a shape the source does not produce (see PROVENANCE.md).

A missing name is an error, never an empty string: the fallback value of a
lookup would otherwise be the whole cause -- a test against an empty fixture
checks nothing and reports success.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(name: str) -> str:
    """The recorded payload for ``name``, verbatim."""
    path = FIXTURES / name
    if not path.is_file():
        available = sorted(p.name for p in FIXTURES.iterdir() if p.is_file())
        raise FileNotFoundError(
            f"No fixture {name!r} under {FIXTURES}. Available: {available}. "
            "Re-record with `python scripts/record_fixtures.py`."
        )
    return path.read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def internal_id(page_fixture: str) -> str:
    """The Obsan internal id carried by a recorded indicator page.

    Read out of the fixture instead of written down next to it: the id is the
    one thing the server extracts from that page, and a copy in the test file
    would be a second place for it to be wrong.
    """
    match = re.search(r'"id"\s*:\s*"([^"]+)"', fixture_text(page_fixture))
    if not match:
        raise AssertionError(
            f"{page_fixture}: no 'id' in the __NEXT_DATA__ block -- page shape "
            "changed, re-record and check the server's extractor"
        )
    return match.group(1)


def catalogue_ids(sitemap_fixture: str = "obsan_sitemap.xml") -> list[str]:
    """``topic/slug`` for every indicator URL in the recorded sitemap."""
    locs = re.findall(r"<loc>(.*?)</loc>", fixture_text(sitemap_fixture))
    out = []
    for loc in locs:
        m = re.search(r"/indicator/([a-z0-9_-]+)/([a-z0-9_-]+)$", loc)
        if m:
            ident = f"{m.group(1)}/{m.group(2)}"
            if ident not in out:
                out.append(ident)
    return out
