"""Multi-source health-indicator tools for bag-health-mcp.

Adds two source-agnostic tools on top of the BAG IDD tools (see
``docs/tool-design-health-indicators.md``):

* ``bag_health_mcp__search_health_indicators`` — discover indicators across
  Obsan, the Versorgungsatlas and Sucht Schweiz (HBSC).
* ``bag_health_mcp__get_indicator_series`` — fetch one indicator's time series.

Access model (verified live, see ``docs/probe-*.md``):

* **Obsan** (`ind.obsan.admin.ch`) — clean JSON API ``/api/<id>/<cut>/json``.
  Which cuts exist differs per indicator and is declared on the SSR page, next to
  the internal id, in ``__NEXT_DATA__``; both are read from there rather than
  guessed (see ``_OBSAN_VARIANT_ORDER``). Catalogue via ``sitemap.xml``. This is
  ARCH A (live API) and the workhorse.
* **Versorgungsatlas** — static catalogue ``/search/search_<lang>.json`` (search)
  plus SSR indicator pages for metadata. The numeric value files sit behind the
  SPA runtime and are not reliably retrievable over plain HTTP, so series calls
  degrade gracefully to metadata + a pointer to the atlas (documented limitation).
* **Sucht Schweiz** — the HBSC youth-survey series are re-published by Obsan with
  provenance intact, so they are served through the Obsan path (the public
  ``zahlen-fakten`` host was unreachable at probe time and only offers Tableau/PDF).

Every response carries the mandated aggregate-statistics safeguard label: these
tools serve aggregated population statistics, never individual advice.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from html import unescape
from typing import Any

from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from bag_health_mcp._models import (
    INDICATOR_LICENSE,
    OBSAN_ATTRIBUTION,
    SUCHTSCHWEIZ_ATTRIBUTION,
    VERSORGUNGSATLAS_ATTRIBUTION,
    GetIndicatorSeriesInput,
    IndicatorSearchOutput,
    IndicatorSeriesOutput,
    IndicatorSeriesPoint,
    IndicatorSummary,
    Provenance,
    SearchHealthIndicatorsInput,
)
from bag_health_mcp.server import (
    OBSAN_BASE,
    VERSORGUNGSATLAS_BASE,
    Language,
    _client,
    _fail,
    _fail_not_found,
    _get_with_retry,
    _traced,
    mcp,
)

# Read-only, idempotent, open-world — same posture as the IDD tools (ARCH-009).
READ_ONLY_INDICATORS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)


# ---------------------------------------------------------------------------
# Tiny TTL cache (catalogues change slowly; one fetch serves many searches)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 6 * 3600
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()


async def _cached(key: str, factory: Any) -> Any:
    """Return a cached value for ``key`` or compute+store it via ``factory``.

    ``factory`` is an async callable. TTL is :data:`_CACHE_TTL_SECONDS`. The lock
    keeps two concurrent misses from both hitting the upstream for the same key.
    """
    now = time.monotonic()
    async with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
        value = await factory()
        _cache[key] = (now + _CACHE_TTL_SECONDS, value)
        return value


def _clear_cache() -> None:
    """Drop all cached catalogues (used by tests)."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
_INTERNAL_ID_RE = re.compile(r"^_\d+$")


def _extract_next_data(html: str) -> dict[str, Any]:
    """Parse the Next.js ``__NEXT_DATA__`` blob out of an SSR page."""
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return {}
    try:
        return json.loads(unescape(m.group(1)))
    except (json.JSONDecodeError, ValueError):
        return {}


def _apply_year_filter(
    points: list[IndicatorSeriesPoint], year_from: int | None, year_to: int | None
) -> list[IndicatorSeriesPoint]:
    def keep(p: IndicatorSeriesPoint) -> bool:
        if p.year is None:
            return True
        if year_from is not None and p.year < year_from:
            return False
        if year_to is not None and p.year > year_to:
            return False
        return True

    return [p for p in points if keep(p)]


# ---------------------------------------------------------------------------
# Obsan adapter (also backs the 'suchtschweiz' source via the HBSC mirror)
# ---------------------------------------------------------------------------

_SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>")
# Indicator locations look like ".../<lang>/indicator/<topic>/<slug>" or, for the
# canonical entry, ".../indicator/<topic>/<slug>" with no language segment.
_OBSAN_IND_RE = re.compile(r"/(?:(de|fr|it|en)/)?indicator/([a-z0-9_]+)/([a-z0-9-]+)$", re.I)


async def _obsan_catalogue() -> list[dict[str, str]]:
    """Return the Obsan indicator catalogue parsed from sitemap.xml (cached).

    Each entry: ``{"topic": ..., "slug": ..., "lang": ...}``. Language-neutral
    (canonical) locations are tagged ``lang=""`` and matched for any language.
    """

    async def factory() -> list[dict[str, str]]:
        async with _client() as c:
            r = await _get_with_retry(
                c, f"{OBSAN_BASE}/sitemap.xml", context="loading the Obsan catalogue"
            )
        out: list[dict[str, str]] = []
        for loc in _SITEMAP_LOC_RE.findall(r.text):
            m = _OBSAN_IND_RE.search(loc)
            if m:
                out.append(
                    {"lang": (m.group(1) or "").lower(), "topic": m.group(2), "slug": m.group(3)}
                )
        return out

    return await _cached("obsan:sitemap", factory)


def _humanize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().capitalize()


async def _obsan_search(
    params: SearchHealthIndicatorsInput, *, topic_scope: str | None, attribution: str
) -> IndicatorSearchOutput:
    catalogue = await _obsan_catalogue()
    lang = params.language
    term = params.topic.lower().strip()

    seen: set[str] = set()
    matches: list[IndicatorSummary] = []
    for entry in catalogue:
        if topic_scope and entry["topic"] != topic_scope:
            continue
        # Prefer the requested language; keep language-neutral entries too.
        if entry["lang"] and entry["lang"] != lang:
            continue
        slug = entry["slug"]
        if term and term not in slug.replace("-", " ") and term not in slug:
            continue
        indicator_id = f"{entry['topic']}/{slug}"
        if indicator_id in seen:
            continue
        seen.add(indicator_id)
        matches.append(
            IndicatorSummary(
                source=params.source,
                indicator_id=indicator_id,
                title=_humanize_slug(slug),
                topic=entry["topic"],
                # The sitemap carries URLs, nothing else — it does not say which
                # cuts an indicator publishes, and finding out costs one page
                # fetch per hit. So this says so, instead of the "mostly
                # national" that used to stand here: measured 2026-08-08, 50 of
                # 60 sampled indicators do have a cantonal cut.
                regional_dimension=(
                    "not stated in the catalogue — the series call reports which "
                    "cuts exist (national / by canton / by age / by social position)"
                ),
            )
        )
        if len(matches) >= params.limit:
            break

    return IndicatorSearchOutput(
        source=params.source,
        query={
            "topic": params.topic,
            "region": params.region,
            "year_from": params.year_from,
            "year_to": params.year_to,
        },
        total_matches=len(matches),
        indicators=matches,
        usage=(
            "Pass an indicator_id to bag_health_mcp__get_indicator_series("
            f"source='{params.source}', indicator_id=...) for the time series. "
            "Titles here are derived from the slug; the series call returns the "
            "authoritative title, unit and source, names which cut of the "
            "indicator it returned ('variant') and which other cuts exist. Pass "
            "region='ZH' there for a cantonal series where the indicator has one. "
            "Not every catalogue entry has data behind it — measured 2026-08-08, "
            "8 of 60 sampled indicators publish no series at all, and the series "
            "call says so plainly rather than returning an empty result."
        ),
        provenance=Provenance(
            source=attribution, attribution=attribution, license=INDICATOR_LICENSE
        ),
    )


# --- Which cuts an Obsan indicator actually publishes -----------------------
#
# The indicator page lists them: ``props.pageProps.jsonLDs.links.od3.<id>`` maps
# each available API variant to its full ``apiUrl``. This client used to ignore
# that list and guess two fixed suffixes instead — ``/g/json``, falling back to
# ``/gum/json``.
#
# Measured over 60 language-neutral indicators on 2026-08-08:
#
#     kg  (nach Kantonen)      50     gum (Verteilung)      9
#     ag  (nach Altersklasse)  49     agum                  5
#     sd  (nach sozialer Lage) 24     g   (national)        3
#                                     bg                    1
#
#     weder g noch gum: 49 von 60   ·   gar keine Variante: 8 von 60
#
# So the two suffixes the client asked for were the two rarest; 49 of 60
# indicators answered 404 on both, and 41 of those 49 do have data — under a
# suffix nobody asked for. The catalogue was never offering more than the source
# has. The question was wrong, not the answer.
#
# The order below is the preference when several exist. It is a preference, not
# a fallback chain: whichever cut is returned is named in the response, because
# they are different measurements with different units, not degraded copies of
# one another.
_OBSAN_VARIANT_ORDER = ("g", "kg", "ag", "sd", "gum", "agum", "bg")

# What each suffix is, for the response text. Read off the payloads' own
# ``title``/``value`` labels on 2026-08-08; anything not listed here is still
# fetched and still labelled — from the payload, not from this table.
_OBSAN_VARIANT_MEANING = {
    "g": "national time series",
    "kg": "by canton (kanton_nr, BFS numbering; 0 = Switzerland)",
    "ag": "national, by age class",
    "sd": "national, by social position (group_id / characteristic_id)",
    "gum": "distribution across segments (segment_id) — a share, not the headline rate",
    "agum": "distribution across segments, by age class",
    "bg": "additional breakdown published for this indicator",
}


def _obsan_variants(page_data: dict[str, Any], internal: str) -> dict[str, str]:
    """The API variants the indicator page declares, ``{suffix: apiUrl}``."""
    links = ((page_data.get("props", {}).get("pageProps", {}) or {}).get("jsonLDs", {}) or {}).get(
        "links", {}
    ) or {}
    od3 = (links.get("od3") or {}).get(internal) or {}
    out: dict[str, str] = {}
    for suffix, entry in od3.items():
        url = (entry or {}).get("apiUrl") if isinstance(entry, dict) else None
        if isinstance(url, str) and url.startswith(OBSAN_BASE):
            out[suffix] = url
    return out


async def _obsan_resolve(indicator_id: str, lang: Language) -> tuple[str, dict[str, str] | None]:
    """Resolve an Obsan indicator to ``(internal_id, declared_variants)``.

    ``declared_variants`` is ``None`` — meaning *unknown*, not *none* — when the
    caller passed a bare internal id like ``_330``. There is no page to read in
    that case, so the series call has to probe instead of choose. The two states
    are kept apart on purpose: an empty dict is a measured "this indicator
    publishes nothing", and answering that from a guess would be the same
    mistake in the other direction.
    """
    if _INTERNAL_ID_RE.match(indicator_id):
        return indicator_id, None
    if "/" not in indicator_id:
        _fail(
            "Obsan indicator_id must be an internal id like '_330' or a "
            "'<topic>/<slug>' path like 'monam/alkoholkonsum-alter-11-15'."
        )
    async with _client() as c:
        r = await _get_with_retry(
            c,
            f"{OBSAN_BASE}/{lang}/indicator/{indicator_id}",
            context=f"resolving Obsan indicator '{indicator_id}'",
            allow_404=True,
        )
        if r.status_code == 404:
            catalogue = await _obsan_catalogue()
            ids = [f"{e['topic']}/{e['slug']}" for e in catalogue]
            _fail_not_found(
                "Obsan indicator",
                indicator_id,
                ids,
                "Use bag_health_mcp__search_health_indicators(source='obsan', ...).",
            )
    data = _extract_next_data(r.text)
    internal = (data.get("props", {}).get("pageProps", {}) or {}).get("id")
    if not internal:
        _fail(
            f"Could not resolve Obsan indicator '{indicator_id}' to a data id "
            "(page structure may have changed)."
        )
    return internal, _obsan_variants(data, internal)


# Official BFS canton numbers, plus 0 for the national total, as the ``kg`` cut
# uses them. The German names are carried along on purpose rather than dropped:
# every ``kg`` payload ships its own ``kanton_nr.codes`` table, so this mapping
# is checked against the source on each call instead of trusted. A wrong canton
# number is the worst shape a wrong answer can take — it is complete, plausible,
# correctly formatted, and about somewhere else.
_BFS_CANTONS: dict[str, tuple[int, str]] = {
    "ZH": (1, "Zürich"),
    "BE": (2, "Bern"),
    "LU": (3, "Luzern"),
    "UR": (4, "Uri"),
    "SZ": (5, "Schwyz"),
    "OW": (6, "Obwalden"),
    "NW": (7, "Nidwalden"),
    "GL": (8, "Glarus"),
    "ZG": (9, "Zug"),
    "FR": (10, "Freiburg"),
    "SO": (11, "Solothurn"),
    "BS": (12, "Basel-Stadt"),
    "BL": (13, "Basel-Landschaft"),
    "SH": (14, "Schaffhausen"),
    "AR": (15, "Appenzell Ausserrhoden"),
    "AI": (16, "Appenzell Innerrhoden"),
    "SG": (17, "St. Gallen"),
    "GR": (18, "Graubünden"),
    "AG": (19, "Aargau"),
    "TG": (20, "Thurgau"),
    "TI": (21, "Tessin"),
    "VD": (22, "Waadt"),
    "VS": (23, "Wallis"),
    "NE": (24, "Neuenburg"),
    "GE": (25, "Genf"),
    "JU": (26, "Jura"),
}
_BFS_BY_NUMBER = {nr: code for code, (nr, _name) in _BFS_CANTONS.items()}


def _canton_number(code: str, payload: dict[str, Any]) -> int:
    """The BFS number for a canton code, verified against the payload's own table.

    ``code`` is 'CH' (→ 0) or a two-letter canton code. Raises rather than guess
    when the source's German name for that number is not the expected one: at
    that point one of the two tables has moved, and picking either would answer
    confidently about the wrong canton.
    """
    if code == "CH":
        return 0
    entry = _BFS_CANTONS.get(code)
    if entry is None:
        _fail(
            f"'{code}' is not a Swiss canton code. Use one of: "
            f"{', '.join(sorted(_BFS_CANTONS))}, or 'CH' for the national total."
        )
    number, expected_name = entry
    codes = (payload.get("kanton_nr") or {}).get("codes") or {}
    got = (codes.get(str(number)) or {}).get("de")
    if got is not None and got.strip().casefold() != expected_name.casefold():
        _fail(
            f"Canton mapping disagrees with the source: BFS number {number} is "
            f"'{expected_name}' here but '{got}' upstream. Refusing to guess — "
            "the canton numbering in this client needs re-checking."
        )
    return number


def _split_period(raw: Any) -> tuple[int | None, str | None]:
    """Split an Obsan ``year`` value into ``(year, period)``.

    Obsan writes a single year as an int and a pooled band as a string —
    ``"1998-02"`` is the five-year window 1998–2002, not February 1998 (the
    ``kg`` cut of indicator _010 is titled "5-Jahresmittelwert"). Both forms
    reach the same field, so both are read here: the band keeps its full label
    in ``period`` and contributes its first year to ``year``, which is what the
    year filter compares against. Feeding ``"1998-02"`` straight into an ``int``
    field, as before, raises a validation error the caller never sees coming.
    """
    if isinstance(raw, bool):
        return None, None
    if isinstance(raw, int):
        return raw, None
    if isinstance(raw, str):
        head = raw.strip()[:4]
        return (int(head) if head.isdigit() else None), raw.strip()
    return None, None


def _dimension_legend(payload: dict[str, Any], lang: Language, keys: set[str]) -> dict[str, str]:
    """Build the dimension legend from the payload's own code tables.

    Obsan ships a labelled ``codes`` block for every dimension it uses —
    ``sex_id``, ``category_id``, ``age_class``, ``kanton_nr`` and so on, each
    translated. Reading them beats the fixed strings that used to stand here
    ("category breakdown (see source remarks)"), which said the same thing for
    an indicator split by suicide-vs-assisted-suicide and one split by life
    expectancy at birth vs at 65.
    """

    def label(field: Any) -> str | None:
        if isinstance(field, dict):
            v = field.get(lang) or field.get("de")
            return v if isinstance(v, str) else None
        return field if isinstance(field, str) else None

    dims: dict[str, str] = {}
    for key in sorted(keys):
        block = payload.get(key)
        if not isinstance(block, dict) or "codes" not in block:
            continue
        codes = block.get("codes") or {}
        rendered = ", ".join(
            f"{code} = {label(name)}"
            for code, name in sorted(codes.items(), key=lambda kv: str(kv[0]))
            if label(name)
        )
        heading = label(block) or key
        dims[key] = f"{heading}: {rendered}" if rendered else heading
    return dims


async def _obsan_fetch_variant(
    internal: str, declared: dict[str, str] | None, want: list[str]
) -> tuple[str, dict[str, Any]]:
    """Fetch the first cut in ``want`` that exists, returning ``(suffix, payload)``.

    With ``declared`` known the choice needs no probing — the page already said
    which cuts exist. With ``declared`` None (a bare internal id, no page) the
    candidates are probed in order, which is the old behaviour narrowed to the
    one case where there is genuinely nothing to read.
    """
    if declared is not None:
        available = [s for s in want if s in declared]
        if not available:
            offered = sorted(declared)
            _fail(
                f"Obsan indicator '{internal}' publishes no time series"
                + (f" — the source offers only: {', '.join(offered)}." if offered else ".")
                + " Not every catalogue entry has one; try a neighbouring "
                "indicator from bag_health_mcp__search_health_indicators."
            )
        suffix = available[0]
        async with _client() as c:
            r = await _get_with_retry(
                c,
                declared[suffix],
                context=f"fetching Obsan series '{internal}' ({suffix} variant)",
            )
        return suffix, r.json()

    async with _client() as c:
        for suffix in want:
            r = await _get_with_retry(
                c,
                f"{OBSAN_BASE}/api/{internal}/{suffix}/json",
                context=f"fetching Obsan series '{internal}' ({suffix} variant)",
                allow_404=True,
            )
            if r.status_code != 404:
                return suffix, r.json()
    _fail(
        f"Obsan indicator '{internal}' publishes none of the known cuts "
        f"({', '.join(want)}). Pass the '<topic>/<slug>' form instead of the "
        "internal id — then the indicator page states which cuts exist."
    )


async def _obsan_series(
    params: GetIndicatorSeriesInput, *, attribution: str
) -> IndicatorSeriesOutput:
    lang = params.language
    internal, declared = await _obsan_resolve(params.indicator_id, lang)

    requested_region = (params.region or "CH").upper()
    # A canton was asked for: the cantonal cut goes first, otherwise the order
    # stands as published. 'kg' also carries the national total (kanton_nr 0),
    # so it serves a plain 'CH' request too when no 'g' cut exists.
    want = list(_OBSAN_VARIANT_ORDER)
    if requested_region != "CH":
        want = ["kg"] + [s for s in want if s != "kg"]

    suffix, payload = await _obsan_fetch_variant(internal, declared, want)

    def _lang(field: Any) -> str | None:
        return field.get(lang) or field.get("de") if isinstance(field, dict) else None

    title = _lang(payload.get("title", {})) or params.indicator_id
    unit = _lang(payload.get("value", {}))
    source_label = _lang(payload.get("source", {})) or attribution

    raw = [p for p in payload.get("data", []) if isinstance(p, dict)]
    region = "CH"
    region_note: str | None = None

    if suffix == "kg":
        wanted_nr = _canton_number(requested_region, payload)
        present = sorted({p.get("kanton_nr") for p in raw if p.get("kanton_nr") is not None})
        if wanted_nr not in present:
            names = ", ".join(_BFS_BY_NUMBER.get(nr, str(nr)) for nr in present if nr != 0)
            _fail(
                f"'{requested_region}' is not published for this indicator. "
                f"Available: CH{', ' + names if names else ''}."
            )
        raw = [p for p in raw if p.get("kanton_nr") == wanted_nr]
        region = requested_region
    elif requested_region != "CH":
        # 'kg' leads the preference order whenever a canton is asked for, so
        # reaching here means the indicator has no cantonal cut at all.
        offered = sorted(declared) if declared is not None else [suffix]
        region_note = (
            f"This indicator has no cantonal cut, so no '{requested_region}' "
            f"breakdown is available; the national '{suffix}' cut is returned "
            f"instead. Cuts the source publishes for it: {', '.join(offered)}."
        )

    points: list[IndicatorSeriesPoint] = []
    for p in raw:
        year, period = _split_period(p.get("year"))
        points.append(
            IndicatorSeriesPoint(
                year=year,
                period=period,
                value=p.get("value"),
                value_lower_ci=p.get("value_lci"),
                value_upper_ci=p.get("value_uci"),
                sample_size=p.get("n"),
                sex_id=p.get("sex_id"),
                category_id=p.get("category_id"),
                canton_nr=p.get("kanton_nr"),
                canton=_BFS_BY_NUMBER.get(p["kanton_nr"], "CH")
                if p.get("kanton_nr") is not None
                else None,
                age_class=p.get("age_class"),
                group_id=p.get("group_id"),
                characteristic_id=p.get("characteristic_id"),
                segment_id=p.get("segment_id"),
            )
        )
    points = _apply_year_filter(points, params.year_from, params.year_to)

    dims = _dimension_legend(
        payload,
        lang,
        {k for p in raw for k in p} | {"kanton_nr"},
    )
    if any(p.value_lower_ci is not None for p in points):
        dims["value_lower_ci/value_upper_ci"] = "95% confidence interval bounds"
    if any(p.period for p in points):
        dims["period"] = (
            "The source labels these observations with a pooled span rather than "
            "a single year (see the title and note); 'year' holds its first year."
        )

    variant_meaning = _OBSAN_VARIANT_MEANING.get(suffix, "cut published by the source")
    remarks = _lang(payload.get("remarks", {}))

    return IndicatorSeriesOutput(
        source=params.source,
        indicator_id=params.indicator_id,
        title=title,
        unit=unit,
        region=region,
        region_note=region_note,
        values_available=bool(points),
        dimensions=dims,
        total_points=len(points),
        points=points,
        variant=suffix,
        variants_available=sorted(declared) if declared is not None else [suffix],
        interpretation=(
            f"'{title}'. Values in unit '{unit}'. Cut '{suffix}' — {variant_meaning}"
            + (f", filtered to {region}" if suffix == "kg" else "")
            + ". Confidence intervals given where the source provides them. "
            f"Source: {source_label}."
        ),
        note=remarks,
        provenance=Provenance(
            source=source_label,
            data_version=str(payload.get("version") or "") or None,
            source_date=payload.get("last_updated_at"),
            attribution=attribution,
            license=INDICATOR_LICENSE,
        ),
    )


# ---------------------------------------------------------------------------
# Versorgungsatlas adapter
# ---------------------------------------------------------------------------


async def _va_catalogue(lang: Language) -> list[dict[str, Any]]:
    """The Versorgungsatlas catalogue (~285 aspects / 124 indicators), cached."""

    async def factory() -> list[dict[str, Any]]:
        async with _client() as c:
            r = await _get_with_retry(
                c,
                f"{VERSORGUNGSATLAS_BASE}/search/search_{lang}.json",
                context="loading the Versorgungsatlas catalogue",
            )
        data = r.json()
        return data if isinstance(data, list) else []

    return await _cached(f"va:search:{lang}", factory)


async def _va_search(params: SearchHealthIndicatorsInput) -> IndicatorSearchOutput:
    catalogue = await _va_catalogue(params.language)
    term = params.topic.lower().strip()

    matches: list[IndicatorSummary] = []
    for entry in catalogue:
        hay = " ".join(
            str(entry.get(k, ""))
            for k in (
                "title",
                "aspect_title",
                "topic",
                "description",
                "search_terms",
                "group_terms",
            )
        ).lower()
        if term and term not in hay:
            continue
        ind_id = entry.get("id", "")
        aspect = entry.get("aspect", "")
        matches.append(
            IndicatorSummary(
                source=params.source,
                indicator_id=f"{ind_id}/{aspect}" if aspect else ind_id,
                title=entry.get("title", ind_id),
                subtitle=entry.get("aspect_title"),
                topic=entry.get("topic"),
                description=(entry.get("description") or "")[:280] or None,
                regional_dimension="canton (kt): 26 cantons + CH national",
            )
        )
        if len(matches) >= params.limit:
            break

    return IndicatorSearchOutput(
        source=params.source,
        query={
            "topic": params.topic,
            "region": params.region,
            "year_from": params.year_from,
            "year_to": params.year_to,
        },
        total_matches=len(matches),
        indicators=matches,
        usage=(
            "Pass an indicator_id (e.g. '_003/b') to bag_health_mcp__get_indicator_series"
            "(source='versorgungsatlas', indicator_id=..., region='ZH') for a cantonal "
            "time series with 95% CIs and a canton-vs-Switzerland comparison."
        ),
        provenance=Provenance(
            source=VERSORGUNGSATLAS_ATTRIBUTION,
            attribution=VERSORGUNGSATLAS_ATTRIBUTION,
            license=INDICATOR_LICENSE,
        ),
    )


# Versorgungsatlas serves three JSON files per indicator-aspect, keyed
# "/data/<id><aspect>_<suffix>.json" (URL scheme confirmed by a network trace):
#   _ad = aspect definition/metadata (var1_label, datasource, population, remark)
#   _rz = by region — one row per (year, region); region_name is a canton code
#         (geo="kt") plus a "CH" national total, with 95% CI and a rate ratio (rr)
#   _ag = by age group — national, one row per (year, ageclass, sex)
# The regional file makes a real canton-vs-Switzerland comparison possible.
_VA_VAR_LABELS = {
    "std_costs": "age/sex-standardised costs (CHF per capita)",
    "costs": "costs (CHF per capita)",
    "rate": "rate",
    "share": "share (%)",
    "prev": "prevalence (%)",
}


async def _va_fetch_data(base: str, suffix: str) -> Any | None:
    """Fetch one Versorgungsatlas data file, or ``None`` if it does not exist."""
    async with _client() as c:
        r = await _get_with_retry(
            c,
            f"{VERSORGUNGSATLAS_BASE}/data/{base}_{suffix}.json",
            context=f"fetching Versorgungsatlas data '{base}_{suffix}'",
            allow_404=True,
        )
    if r.status_code == 404:
        return None
    return r.json()


async def _va_lookup_title(ind_id: str, aspect: str, lang: Language) -> tuple[str, str | None]:
    """Title + subtitle for an indicator/aspect from the cached catalogue."""
    for e in await _va_catalogue(lang):
        if e.get("id") == ind_id and (not aspect or e.get("aspect") == aspect):
            return e.get("title", ind_id), e.get("aspect_title")
    return f"{ind_id}/{aspect}" if aspect else ind_id, None


async def _va_series(params: GetIndicatorSeriesInput) -> IndicatorSeriesOutput:
    lang = params.language
    parts = params.indicator_id.split("/")
    ind_id = parts[0]
    aspect = parts[1] if len(parts) > 1 else ""
    base = f"{ind_id}{aspect}"

    title, subtitle = await _va_lookup_title(ind_id, aspect, lang)
    meta = await _va_fetch_data(base, "ad")
    if meta is None:
        _fail_not_found(
            "Versorgungsatlas indicator",
            params.indicator_id,
            [],
            "Use bag_health_mcp__search_health_indicators(source='versorgungsatlas', ...).",
        )

    var_label = meta.get("var1_label", "")
    unit = _VA_VAR_LABELS.get(var_label, var_label or None)
    population = (meta.get("population") or {}).get(lang) or (meta.get("population") or {}).get(
        "de"
    )
    dims: dict[str, str] = {}
    if subtitle:
        dims["subtitle"] = subtitle
    if population:
        dims["population"] = population
    dims["value_lower_ci/value_upper_ci"] = "95% confidence interval bounds"

    prov = Provenance(
        source=f"{VERSORGUNGSATLAS_ATTRIBUTION}; data source: {meta.get('datasource', 'Tarifpool')}",
        data_version=str(meta.get("version") or "") or None,
        source_date=meta.get("date_export"),
        attribution=VERSORGUNGSATLAS_ATTRIBUTION,
        license=INDICATOR_LICENSE,
    )

    region = (params.region or "CH").upper()
    regional = await _va_fetch_data(base, "rz")

    if regional:
        available = sorted({r.get("region_name") for r in regional if r.get("region_name")})
        rows = [r for r in regional if r.get("region_name") == region]
        if not rows:
            _fail(
                f"Region '{region}' is not available for this indicator. "
                f"Available: {', '.join(available)}."
            )
        points = _apply_year_filter(
            [
                IndicatorSeriesPoint(
                    year=r.get("year"),
                    value=r.get("var1"),
                    value_lower_ci=r.get("lci1"),
                    value_upper_ci=r.get("uci1"),
                    sex_id=r.get("sex"),
                )
                for r in rows
                if r.get("var1") is not None
            ],
            params.year_from,
            params.year_to,
        )
        dims["regions_available"] = ", ".join(available)

        # Canton-vs-Switzerland comparison from the latest shared year (rr = ratio
        # to the national value, provided by the source).
        region_note = None
        if region != "CH":
            ch_by_year = {
                r["year"]: r.get("var1") for r in regional if r.get("region_name") == "CH"
            }
            latest = max((r["year"] for r in rows), default=None)
            rr = next((r.get("rr") for r in rows if r.get("year") == latest), None)
            ch_val = ch_by_year.get(latest)
            can_val = next((r.get("var1") for r in rows if r.get("year") == latest), None)
            if latest is not None and ch_val is not None and can_val is not None:
                direction = "above" if can_val > ch_val else "below" if can_val < ch_val else "at"
                region_note = (
                    f"Canton-vs-Switzerland ({latest}): {region}={can_val}, CH={ch_val}"
                    + (f", ratio rr={rr}" if rr is not None else "")
                    + f" — {region} is {direction} the national value. Call again with "
                    "region='CH' for the full national series."
                )

        return IndicatorSeriesOutput(
            source=params.source,
            indicator_id=params.indicator_id,
            title=title,
            unit=unit,
            region=region,
            region_note=region_note,
            values_available=bool(points),
            dimensions=dims,
            total_points=len(points),
            points=points,
            interpretation=(
                f"'{title}'. Values are '{var_label}' ({unit}); denominator: "
                f"{meta.get('denominator', 'n/a')}. Regional series (geo='kt') for "
                f"'{region}', with 95% CIs. Source: {meta.get('datasource', 'Tarifpool')} "
                "via Versorgungsatlas (BAG/Obsan)."
            ),
            provenance=prov,
        )

    # No regional file: fall back to the national age-group series (_ag).
    age = await _va_fetch_data(base, "ag")
    if age:
        points = _apply_year_filter(
            [
                IndicatorSeriesPoint(
                    year=r.get("year"),
                    value=r.get("var1"),
                    value_lower_ci=r.get("lci1"),
                    value_upper_ci=r.get("uci1"),
                    sex_id=r.get("sex"),
                    category_id=r.get("ageclass"),
                )
                for r in age
                if r.get("var1") is not None
            ],
            params.year_from,
            params.year_to,
        )
        dims["category_id"] = "age class (see 'age' labels in the atlas)"
        return IndicatorSeriesOutput(
            source=params.source,
            indicator_id=params.indicator_id,
            title=title,
            unit=unit,
            region="CH",
            region_note=(
                "This indicator has no regional file; the national age-group series "
                "is returned (category_id = age class)."
                if params.region and params.region.upper() != "CH"
                else None
            ),
            values_available=bool(points),
            dimensions=dims,
            total_points=len(points),
            points=points,
            interpretation=(
                f"'{title}'. Values are '{var_label}' ({unit}), national by age class. "
                f"Source: {meta.get('datasource', 'Tarifpool')} via Versorgungsatlas."
            ),
            provenance=prov,
        )

    # Metadata only (no data files) — graceful degradation.
    return IndicatorSeriesOutput(
        source=params.source,
        indicator_id=params.indicator_id,
        title=title,
        unit=unit,
        region=region,
        region_note=None,
        values_available=False,
        dimensions=dims,
        total_points=0,
        points=[],
        interpretation=(
            f"'{title}'. Definition available, but this indicator exposes no regional "
            "or age-group data file — see the interactive atlas for the figures."
        ),
        note=f"Open the interactive chart at {VERSORGUNGSATLAS_BASE}/indicator/{ind_id}/{aspect}.",
        provenance=prov,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bag_health_mcp__search_health_indicators",
    annotations=READ_ONLY_INDICATORS,
    description=(
        "Search health indicators across three Swiss sources: 'obsan' (Swiss Health "
        "Observatory — hundreds of indicators incl. the HBSC youth-survey series), "
        "'versorgungsatlas' (Swiss health-care supply atlas, ~124 indicators), and "
        "'suchtschweiz' (addiction / HBSC series, served via Obsan's official mirror). "
        "Returns matching indicator_ids to pass to bag_health_mcp__get_indicator_series. "
        "IMPORTANT: this serves AGGREGATED population statistics (prevalences/metrics by "
        "age/sex/region) — NOT individual advice, diagnosis or case assessment, and no "
        "personal data. Especially for 'suchtschweiz' (prevention topics in a school "
        "context): the figures are population-level survey aggregates only. "
        "<use_case>Find which indicators exist for a topic (e.g. youth alcohol) before "
        "fetching a series.</use_case>"
        "<important_notes>The catalogue does not state which cuts an indicator "
        "publishes — get_indicator_series reports that per indicator ('variant', "
        "'variants_available'). Most Obsan indicators DO have a cantonal cut (50 of 60 "
        "sampled); the HBSC youth series (source='suchtschweiz', ages 11-15) is the "
        "exception and is national only, as HBSC is not cantonally representative. Other "
        "'monam' indicators come from the Swiss Health Survey and are cantonal. A few "
        "catalogue entries have no series at all; the series call names that case rather "
        "than returning nothing.</important_notes>"
        "<example>bag_health_mcp__search_health_indicators(source='suchtschweiz', "
        "topic='alkohol') -> Obsan HBSC alcohol-prevalence indicators.</example>"
    ),
)
@_traced
async def bag_search_health_indicators(
    params: SearchHealthIndicatorsInput,
) -> IndicatorSearchOutput:
    if params.source == "obsan":
        return await _obsan_search(params, topic_scope=None, attribution=OBSAN_ATTRIBUTION)
    if params.source == "suchtschweiz":
        # HBSC/addiction indicators live in Obsan's 'monam' monitoring topic.
        return await _obsan_search(
            params, topic_scope="monam", attribution=SUCHTSCHWEIZ_ATTRIBUTION
        )
    return await _va_search(params)


@mcp.tool(
    name="bag_health_mcp__get_indicator_series",
    annotations=READ_ONLY_INDICATORS,
    description=(
        "Fetch one health indicator's time series from Obsan, the Versorgungsatlas or "
        "Sucht Schweiz (HBSC). Use an indicator_id from bag_health_mcp__search_health_indicators. "
        "Obsan publishes an indicator in several CUTS (national, by canton, by age class, "
        "by social position, as a distribution); this tool picks one, names it in "
        "'variant' and lists the others in 'variants_available'. They are different "
        "measurements with different units, not interchangeable. Pass region='ZH' for the "
        "cantonal cut where the indicator has one. Versorgungsatlas returns a cantonal "
        "year/value series (26 cantons + a 'CH' total, 95% CIs, canton-vs-Switzerland ratio). "
        "IMPORTANT: AGGREGATED population statistics only — NOT individual advice, "
        "diagnosis or case assessment, no personal data. For 'suchtschweiz' (school-context "
        "prevention topics) the values are national HBSC survey aggregates by age/sex. "
        "<use_case>Get a national trend, or a cantonal series with a Switzerland "
        "comparison.</use_case>"
        "<important_notes>Read 'variant' before reading the numbers: 'g'/'kg' are rates, "
        "'gum' is a distribution in %. The HBSC youth series (source='suchtschweiz', ages "
        "11-15) is national only — a canton request returns the national cut with a note, "
        "because HBSC is not cantonally representative. Some Obsan observations are pooled "
        "spans ('1998-02' = 1998–2002); those carry the full label in 'period' and its "
        "first year in 'year'. Where an indicator publishes no series, the call fails with "
        "that reason instead of returning an empty series.</important_notes>"
        "<example>bag_health_mcp__get_indicator_series(source='obsan', "
        "indicator_id='obsan/lebenserwartung', region='ZH') -> ZH life expectancy from the "
        "'kg' cut, with the source's own canton and category legends.</example>"
    ),
)
@_traced
async def bag_get_indicator_series(
    params: GetIndicatorSeriesInput, ctx: Context | None = None
) -> IndicatorSeriesOutput:
    if ctx:
        await ctx.info(f"Fetching {params.source} indicator '{params.indicator_id}'")
    if params.source == "obsan":
        return await _obsan_series(params, attribution=OBSAN_ATTRIBUTION)
    if params.source == "suchtschweiz":
        return await _obsan_series(params, attribution=SUCHTSCHWEIZ_ATTRIBUTION)
    return await _va_series(params)
