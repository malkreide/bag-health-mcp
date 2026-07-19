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
                regional_dimension="canton (kt): 26 cantons + CH national",
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
            "(source='versorgungsatlas', indicator_id=..., region='ZH') for a cantonal "
            "time series with 95% CIs and a canton-vs-Switzerland comparison."
        ),
        provenance=Provenance(
            source=VERSORGUNGSATLAS_ATTRIBUTION,
            attribution=VERSORGUNGSATLAS_ATTRIBUTION, license=INDICATOR_LICENSE,
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
            c, f"{VERSORGUNGSATLAS_BASE}/data/{base}_{suffix}.json",
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
            "Versorgungsatlas indicator", params.indicator_id, [],
            "Use bag_health_mcp__search_health_indicators(source='versorgungsatlas', ...).",
        )

    var_label = meta.get("var1_label", "")
    unit = _VA_VAR_LABELS.get(var_label, var_label or None)
    population = (meta.get("population") or {}).get(lang) or (meta.get("population") or {}).get("de")
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
            params.year_from, params.year_to,
        )
        dims["regions_available"] = ", ".join(available)

        # Canton-vs-Switzerland comparison from the latest shared year (rr = ratio
        # to the national value, provided by the source).
        region_note = None
        if region != "CH":
            ch_by_year = {r["year"]: r.get("var1") for r in regional
                          if r.get("region_name") == "CH"}
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
            params.year_from, params.year_to,
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
                if params.region and params.region.upper() != "CH" else None
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
    "Obsan/suchtschweiz return national year/value points (with 95% confidence "
    "intervals and sex/category dimensions where available); versorgungsatlas returns "
    "a cantonal year/value series (26 cantons + a 'CH' national total, with 95% CIs "
    "and a canton-vs-Switzerland ratio) — pass region='ZH' for a canton. "
    "IMPORTANT: AGGREGATED population statistics only — NOT individual advice, "
    "diagnosis or case assessment, no personal data. For 'suchtschweiz' (school-context "
    "prevention topics) the values are national HBSC survey aggregates by age/sex. "
    "<use_case>Get a national trend (obsan/suchtschweiz) or a cantonal series with a "
    "Switzerland comparison (versorgungsatlas).</use_case>"
    "<important_notes>obsan/suchtschweiz indicators are national — passing a canton "
    "returns the national series with an explanatory note (HBSC is not cantonally "
    "representative). versorgungsatlas supports cantons: region='ZH' returns ZH plus a "
    "canton-vs-CH comparison.</important_notes>"
    "<example>bag_health_mcp__get_indicator_series(source='versorgungsatlas', "
    "indicator_id='_003/b', region='ZH') -> ZH cantonal series with 95% CIs and its "
    "ratio to the Swiss average.</example>"
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
