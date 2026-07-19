"""Multi-source health-indicator tools for bag-health-mcp.

Adds two source-agnostic tools on top of the BAG IDD tools (see
``docs/tool-design-health-indicators.md``):

* ``bag_health_mcp__search_health_indicators`` — discover indicators across
  Obsan, the Versorgungsatlas and Sucht Schweiz (HBSC).
* ``bag_health_mcp__get_indicator_series`` — fetch one indicator's time series.

Access model (verified live, see ``docs/probe-*.md``):

* **Obsan** (`ind.obsan.admin.ch`) — clean JSON API ``/api/<id>/g/json`` (fallback
  ``/gum/json``). Indicator ids resolved from the SSR page's ``__NEXT_DATA__``.
  Catalogue via ``sitemap.xml``. This is ARCH A (live API) and the workhorse.
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

from mcp.server.fastmcp import Context
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
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
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
_OBSAN_IND_RE = re.compile(
    r"/(?:(de|fr|it|en)/)?indicator/([a-z0-9_]+)/([a-z0-9-]+)$", re.I
)


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
                out.append({"lang": (m.group(1) or "").lower(), "topic": m.group(2),
                            "slug": m.group(3)})
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
                regional_dimension="mostly national (see series)",
            )
        )
        if len(matches) >= params.limit:
            break

    return IndicatorSearchOutput(
        source=params.source,
        query={"topic": params.topic, "region": params.region,
               "year_from": params.year_from, "year_to": params.year_to},
        total_matches=len(matches),
        indicators=matches,
        usage=(
            "Pass an indicator_id to bag_health_mcp__get_indicator_series("
            f"source='{params.source}', indicator_id=...) for the time series. "
            "Titles here are derived from the slug; the series call returns the "
            "authoritative title, unit and source."
        ),
        provenance=Provenance(
            source=attribution, attribution=attribution, license=INDICATOR_LICENSE
        ),
    )


async def _obsan_resolve_id(indicator_id: str, lang: Language) -> str:
    """Map an Obsan '<topic>/<slug>' path to its internal id ('_330').

    An already-internal id ('_123') is returned unchanged.
    """
    if _INTERNAL_ID_RE.match(indicator_id):
        return indicator_id
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
                "Obsan indicator", indicator_id, ids,
                "Use bag_health_mcp__search_health_indicators(source='obsan', ...).",
            )
    data = _extract_next_data(r.text)
    internal = (data.get("props", {}).get("pageProps", {}) or {}).get("id")
    if not internal:
        _fail(
            f"Could not resolve Obsan indicator '{indicator_id}' to a data id "
            "(page structure may have changed)."
        )
    return internal


async def _obsan_series(
    params: GetIndicatorSeriesInput, *, attribution: str
) -> IndicatorSeriesOutput:
    lang = params.language
    internal = await _obsan_resolve_id(params.indicator_id, lang)

    async with _client() as c:
        r = await _get_with_retry(
            c, f"{OBSAN_BASE}/api/{internal}/g/json",
            context=f"fetching Obsan series '{internal}'", allow_404=True,
        )
        if r.status_code == 404:
            # Not every indicator exposes the '/g' variant; fall back to '/gum'.
            r = await _get_with_retry(
                c, f"{OBSAN_BASE}/api/{internal}/gum/json",
                context=f"fetching Obsan series '{internal}' (gum variant)",
            )
    payload = r.json()

    def _lang(field: Any) -> str | None:
        return field.get(lang) or field.get("de") if isinstance(field, dict) else None

    title = _lang(payload.get("title", {})) or params.indicator_id
    unit = _lang(payload.get("value", {}))
    source_label = _lang(payload.get("source", {})) or attribution

    raw = payload.get("data", [])
    points = [
        IndicatorSeriesPoint(
            year=p.get("year"),
            value=p.get("value"),
            value_lower_ci=p.get("value_lci"),
            value_upper_ci=p.get("value_uci"),
            sample_size=p.get("n"),
            sex_id=p.get("sex_id"),
            category_id=p.get("category_id"),
        )
        for p in raw
        if isinstance(p, dict)
    ]
    points = _apply_year_filter(points, params.year_from, params.year_to)

    # Dimension legend so the model can read sex_id/category_id and CI fields.
    dims: dict[str, str] = {}
    if any(p.sex_id is not None for p in points):
        dims["sex_id"] = "0 = total; other codes = sex breakdown (see source remarks)"
    if any(p.category_id is not None for p in points):
        dims["category_id"] = "category breakdown (see source remarks)"
    if any(p.value_lower_ci is not None for p in points):
        dims["value_lower_ci/value_upper_ci"] = "95% confidence interval bounds"

    # Regional dimension: Obsan consumption/HBSC indicators are national only.
    region_note = None
    if params.region and params.region.upper() not in ("CH",):
        region_note = (
            f"This indicator is published at national (Switzerland) level; no "
            f"'{params.region.upper()}' breakdown is available. HBSC youth surveys "
            "are not cantonally representative, so a canton-vs-Switzerland "
            "comparison is not possible from this series."
        )

    return IndicatorSeriesOutput(
        source=params.source,
        indicator_id=params.indicator_id,
        title=title,
        unit=unit,
        region="CH",
        region_note=region_note,
        values_available=bool(points),
        dimensions=dims,
        total_points=len(points),
        points=points,
        interpretation=(
            f"'{title}'. Values in unit '{unit}'. National Swiss time series; "
            "confidence intervals given where the source provides them. Source: "
            f"{source_label}."
        ),
        note=None,
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
                c, f"{VERSORGUNGSATLAS_BASE}/search/search_{lang}.json",
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
            for k in ("title", "aspect_title", "topic", "description",
                      "search_terms", "group_terms")
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
                regional_dimension="canton / MedStat region",
            )
        )
        if len(matches) >= params.limit:
            break

    return IndicatorSearchOutput(
        source=params.source,
        query={"topic": params.topic, "region": params.region,
               "year_from": params.year_from, "year_to": params.year_to},
        total_matches=len(matches),
        indicators=matches,
        usage=(
            "Pass an indicator_id (e.g. '_003/b') to bag_health_mcp__get_indicator_series"
            "(source='versorgungsatlas', indicator_id=...) for indicator metadata "
            "and dimensions."
        ),
        provenance=Provenance(
            source=VERSORGUNGSATLAS_ATTRIBUTION,
            attribution=VERSORGUNGSATLAS_ATTRIBUTION, license=INDICATOR_LICENSE,
        ),
    )


async def _va_series(params: GetIndicatorSeriesInput) -> IndicatorSeriesOutput:
    lang = params.language
    parts = params.indicator_id.split("/")
    ind_id = parts[0]
    aspect = parts[1] if len(parts) > 1 else ""

    page_path = f"/indicator/{ind_id}/{aspect}" if aspect else f"/indicator/{ind_id}"
    async with _client() as c:
        r = await _get_with_retry(
            c, f"{VERSORGUNGSATLAS_BASE}{page_path}",
            context=f"fetching Versorgungsatlas indicator '{params.indicator_id}'",
            allow_404=True,
        )
        if r.status_code == 404:
            _fail_not_found(
                "Versorgungsatlas indicator", params.indicator_id, [],
                "Use bag_health_mcp__search_health_indicators(source='versorgungsatlas', ...).",
            )
    data = _extract_next_data(r.text)
    indicator = (data.get("props", {}).get("pageProps", {}) or {}).get("indicator", {})
    labels = indicator.get("labels", {}) if isinstance(indicator, dict) else {}
    title = labels.get(lang) or labels.get("de") or params.indicator_id

    dims: dict[str, str] = {}
    for asp in indicator.get("aspects", []) or []:
        if not aspect or asp.get("aspect_id") == aspect:
            geos = ", ".join(asp.get("geos", []) or [])
            if geos:
                dims["geos"] = geos  # e.g. "kt" = canton
            if asp.get("hasAG"):
                dims["age_groups"] = "available"
            sub = asp.get("subtitle", {})
            if isinstance(sub, dict) and sub.get(lang):
                dims["subtitle"] = sub[lang]
            break

    return IndicatorSeriesOutput(
        source=params.source,
        indicator_id=params.indicator_id,
        title=title,
        unit=None,
        region=params.region.upper() if params.region else None,
        region_note=None,
        values_available=False,
        dimensions=dims,
        total_points=0,
        points=[],
        interpretation=(
            "Versorgungsatlas indicator metadata. This source serves numeric values "
            "only inside its interactive atlas (the per-aspect value files sit behind "
            "the web runtime and are not retrievable as a stable machine endpoint), so "
            "no time series is returned here — see the atlas view for the figures."
        ),
        note=(
            f"Open the interactive chart at {VERSORGUNGSATLAS_BASE}{page_path}. "
            "Dimensions (canton/MedStat region, age groups) are listed above; the "
            "atlas is updated roughly annually from the Tarifpool (SASIS AG)."
        ),
        provenance=Provenance(
            source=VERSORGUNGSATLAS_ATTRIBUTION,
            attribution=VERSORGUNGSATLAS_ATTRIBUTION, license=INDICATOR_LICENSE,
        ),
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(name="bag_health_mcp__search_health_indicators", annotations=READ_ONLY_INDICATORS, description=(
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
    "<important_notes>Most indicators are national; cantonal breakdowns are rare "
    "(HBSC youth surveys are not cantonally representative).</important_notes>"
    "<example>bag_health_mcp__search_health_indicators(source='suchtschweiz', "
    "topic='alkohol') -> Obsan HBSC alcohol-prevalence indicators.</example>"
))
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


@mcp.tool(name="bag_health_mcp__get_indicator_series", annotations=READ_ONLY_INDICATORS, description=(
    "Fetch one health indicator's time series from Obsan, the Versorgungsatlas or "
    "Sucht Schweiz (HBSC). Use an indicator_id from bag_health_mcp__search_health_indicators. "
    "Obsan/suchtschweiz return year/value points (with 95% confidence intervals and "
    "sex/category dimensions where available); versorgungsatlas returns indicator "
    "metadata + dimensions (its numeric values live only in the interactive atlas). "
    "IMPORTANT: AGGREGATED population statistics only — NOT individual advice, "
    "diagnosis or case assessment, no personal data. For 'suchtschweiz' (school-context "
    "prevention topics) the values are national HBSC survey aggregates by age/sex. "
    "<use_case>Get a national trend, e.g. youth alcohol prevalence since 2010.</use_case>"
    "<important_notes>If you pass a canton for a national-only indicator, the national "
    "series is returned with a note — a canton-vs-Switzerland comparison is then not "
    "available from that indicator.</important_notes>"
    "<example>bag_health_mcp__get_indicator_series(source='suchtschweiz', "
    "indicator_id='monam/alkoholkonsum-alter-11-15', year_from=2010) -> Swiss HBSC "
    "alcohol-prevalence series (11-15y), by sex, with CIs.</example>"
))
@_traced
async def bag_get_indicator_series(
    params: GetIndicatorSeriesInput, ctx: Context | None = None
) -> IndicatorSeriesOutput:
    if ctx:
        await ctx.info(
            f"Fetching {params.source} indicator '{params.indicator_id}'"
        )
    if params.source == "obsan":
        return await _obsan_series(params, attribution=OBSAN_ATTRIBUTION)
    if params.source == "suchtschweiz":
        return await _obsan_series(params, attribution=SUCHTSCHWEIZ_ATTRIBUTION)
    return await _va_series(params)
