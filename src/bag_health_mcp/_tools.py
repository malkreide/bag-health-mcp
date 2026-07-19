"""MCP tools, resources and prompts for bag-health-mcp.

Split out of server.py (ARCH-011). Importing this module registers the 8 BAG IDD
tools, 3 resources and 2 prompts on the shared ``mcp`` instance from
``bag_health_mcp.server`` (the 2 multi-source indicator tools live in
``_health_indicators.py``). server.py imports this module at the end of its own
definitions (after ``mcp`` and the helpers exist) to perform that registration;
the tool functions are re-exported from server for backward-compatible imports.
"""
from __future__ import annotations

import asyncio
import json

import httpx
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from bag_health_mcp._models import (
    CantonDiseaseData,
    CantonDiseaseStatus,
    CantonSeries,
    CantonSituationOutput,
    DataSetsInput,
    DataVersionInput,
    DataVersionOutput,
    DiseaseDataInput,
    DiseaseDataOutput,
    DiseaseDataPoint,
    DiseaseDataSummary,
    DownloadExportOutput,
    ExportDownloadInput,
    ExportFilesInput,
    ListDiseasesInput,
    ListDiseasesOutput,
    ListExportFilesOutput,
    ListSeriesOutput,
    Provenance,
    SeriesDetailsInput,
    SeriesDetailsOutput,
)
from bag_health_mcp.server import (
    CANTONS,
    DATA_ATTRIBUTION,
    DATA_CLASSIFICATION,
    DATA_LICENSE,
    DISEASE_CATEGORIES,
    IDD_BASE,
    MIN_AGGREGATION_LEVEL,
    EgressNotAllowed,
    _client,
    _fail,
    _fail_not_found,
    _fmt_isoweek,
    _fmt_year,
    _get,
    _post,
    _traced,
    logger,
    mcp,
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

# Every tool only reads from the public BAG IDD API: no mutations (read-only),
# safe to repeat (idempotent), and reaches an external system (open world).
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


@mcp.tool(name="bag_health_mcp__list_diseases", annotations=READ_ONLY, description=(
    "List all 51 disease topics available in the BAG Infectious Disease Dashboard (IDD). "
    "Returns the topic slug needed for other tools, grouped by category "
    "(respiratory, enteric, STI, vector-borne, wastewater). "
    "<use_case>Discover what diseases are available before querying data.</use_case>"
    "<important_notes>Start here; the topic slugs returned are required inputs "
    "for the other tools.</important_notes>"
    "<example>bag_health_mcp__list_diseases() -> categories incl. 'influenza', 'measles', "
    "'covid19'.</example>"
))
@_traced
async def bag_list_diseases(params: ListDiseasesInput) -> ListDiseasesOutput:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/sets", context="listing disease topics")
        all_sets: list[str] = r.json()

    topics: set[str] = {s.split("/")[0] for s in all_sets}

    # Categorise for readability against the shared taxonomy. Wastewater is
    # matched by substring; whatever is left over lands in 'other'.
    categories: dict[str, list[str]] = {}
    classified: set[str] = set()
    for name, members in DISEASE_CATEGORIES.items():
        present = {t for t in topics if t in members}
        categories[name] = sorted(present)
        classified |= present
    wastewater = {t for t in topics if "wastewater" in t}
    categories["wastewater_surveillance"] = sorted(wastewater)
    classified |= wastewater
    categories["other"] = sorted(topics - classified)

    return ListDiseasesOutput(
        total_topics=len(topics),
        categories=categories,
        usage=(
            "Use a topic slug with bag_health_mcp__list_series(topic=...) "
            "to see available data series."
        ),
    )


@mcp.tool(name="bag_health_mcp__list_series", annotations=READ_ONLY, description=(
    "List all available data series for a specific disease topic. "
    "Each series is identified by 'topic/chapter/aggregation/temporality'. "
    "Returns series IDs to use with bag_health_mcp__get_series_details and bag_health_mcp__get_disease_data."
    "<use_case>Find which exact series exist for a disease (e.g. weekly cases vs "
    "yearly incidence) before fetching data.</use_case>"
    "<important_notes>Needs a valid topic slug from bag_health_mcp__list_diseases.</important_notes>"
    "<example>bag_health_mcp__list_series(topic='influenza') -> "
    "'influenza/cases/incValue/iso_week', ...</example>"
))
@_traced
async def bag_list_series(params: DataSetsInput) -> ListSeriesOutput:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/sets", context="listing data series")
        all_sets: list[str] = r.json()

    topic_sets = [s for s in all_sets if s.startswith(f"{params.topic}/")]
    if not topic_sets:
        all_topics = sorted({s.split("/")[0] for s in all_sets})
        _fail_not_found(
            "Topic", params.topic, all_topics,
            "Use bag_health_mcp__list_diseases to see valid topic slugs.",
        )

    # Parse structure
    chapters: dict[str, list[str]] = {}
    for s in topic_sets:
        parts = s.split("/")
        if len(parts) == 4:
            chapter = parts[1]
            agg_temp = f"{parts[2]}/{parts[3]}"
            chapters.setdefault(chapter, []).append(agg_temp)

    return ListSeriesOutput(
        topic=params.topic,
        total_series=len(topic_sets),
        chapters={ch: sorted(series) for ch, series in sorted(chapters.items())},
        series_ids=sorted(topic_sets),
        usage=(
            "Use a series_id with bag_health_mcp__get_series_details to see available "
            "filter values (canton, age_group, sex, type), then "
            "bag_health_mcp__get_disease_data to fetch the time series."
        ),
    )


@mcp.tool(name="bag_health_mcp__get_series_details", annotations=READ_ONLY, description=(
    "Get metadata and available filter values for a specific data series. "
    "Shows which canton, age group, sex, and other dimensions are available. "
    "Always call this before bag_health_mcp__get_disease_data to know valid filter options."
    "<use_case>Learn the valid filter values (cantons, age groups, sex) for a "
    "series so a subsequent data query uses accepted parameters.</use_case>"
    "<important_notes>Available dimensions vary by series — always check here "
    "rather than assuming.</important_notes>"
    "<example>bag_health_mcp__get_series_details(series_id='influenza/cases/incValue/iso_week') "
    "-> cantons=['ZH','BE',...], age_groups=[...].</example>"
))
@_traced
async def bag_get_series_details(params: SeriesDetailsInput) -> SeriesDetailsOutput:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        _fail(
            "series_id must be in format 'topic/chapter/aggregation/temporality', "
            "e.g. 'influenza/cases/incValue/iso_week'."
        )
    topic, chapter, aggregation, temporality = parts

    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details",
            context=f"fetching details for '{params.series_id}'",
            allow_404=True,
        )
        if r.status_code == 404:
            # Suggest real series for this topic instead of a dead end (ARCH-003).
            sets_r = await _get(c, "/api/v1/data/sets", context="listing series for suggestions")
            topic_series = [s for s in sets_r.json() if s.startswith(f"{topic}/")]
            _fail_not_found(
                "Series", params.series_id, topic_series,
                "Use bag_health_mcp__list_series(topic=...) to discover valid series.",
            )
        data = r.json()

    props = data.get("properties", {})
    # Summarise
    filters: dict[str, list[str]] = {}
    for key, val in props.items():
        if isinstance(val, dict):
            filters[key] = val.get("possibleValues", [])

    return SeriesDetailsOutput(
        series_id=params.series_id,
        available_filters=filters,
        cantons=filters.get("canton", []),
        age_groups=(
            filters.get("agegroup_ili_ari")
            or filters.get("agegroup_oblig")
            or filters.get("agegroup")
            or []
        ),
        sex_options=filters.get("sex", []),
        note=(
            "Use these filter values in bag_health_mcp__get_disease_data. "
            "Use 'all' for any aggregated dimension."
        ),
        provenance=Provenance(
            source=data.get("source"),
            source_date=data.get("sourceDate"),
            data_version=data.get("version"),
        ),
    )


@mcp.tool(name="bag_health_mcp__get_disease_data", annotations=READ_ONLY, description=(
    "Fetch time-series surveillance data for a disease from the BAG IDD. "
    "Returns weekly or yearly case counts, incidence rates, or other metrics. "
    "Data updated every Wednesday. "
    "<use_case>Get the actual numbers/trend for a disease in a canton over "
    "time — the core data-retrieval tool.</use_case>"
    "<important_notes>Call bag_health_mcp__get_series_details first for valid filters. "
    "'incValue' = incidence per 100'000; 'value' = absolute count.</important_notes>"
    "<example>bag_health_mcp__get_disease_data(series_id='influenza/cases/incValue/iso_week', "
    "canton='ZH') -> weekly influenza incidence for Zurich.</example>"
))
@_traced
async def bag_get_disease_data(
    params: DiseaseDataInput, ctx: Context | None = None
) -> DiseaseDataOutput:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        _fail("series_id must be 'topic/chapter/aggregation/temporality'.")
    topic, chapter, aggregation, temporality = parts

    # This tool makes two round-trips (details, then data); surface progress and
    # structured logging to the client when a Context is injected (SDK-003).
    if ctx:
        await ctx.info(f"Resolving filters for '{params.series_id}'")
        await ctx.report_progress(progress=0, total=2)

    # Build filter body based on series details
    async with _client() as c:
        # Fetch details to build correct filter
        dr = await _get(
            c,
            f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details",
            context=f"fetching details for '{params.series_id}'",
            allow_404=True,
        )
        if dr.status_code == 404:
            sets_r = await _get(c, "/api/v1/data/sets", context="listing series for suggestions")
            topic_series = [s for s in sets_r.json() if s.startswith(f"{topic}/")]
            _fail_not_found(
                "Series", params.series_id, topic_series,
                "Use bag_health_mcp__list_series to find valid series_ids.",
            )
        details = dr.json()

    props = details.get("properties", {})
    georegion_options = props.get("georegion", {}).get("possibleValues", [])

    # Determine georegion
    if params.canton == "all":
        if "CHFL" in georegion_options:
            georegion = "CHFL"
        elif "country" in georegion_options:
            georegion = "country"
        else:
            georegion = georegion_options[0] if georegion_options else "canton"
    else:
        georegion = "canton"

    # Build filter body
    body: dict[str, str] = {}
    if "georegion" in props:
        body["georegion"] = georegion
    if "canton" in props:
        body["canton"] = params.canton
    if "CHFL" in props and params.canton == "all":
        body["CHFL"] = "all"
        body.pop("canton", None)
    if "sex" in props:
        body["sex"] = params.sex
    if "country" in props and params.canton == "all":
        body["country"] = "CH"

    # Age group handling
    agegroup_key = None
    for key in ["agegroup_ili_ari", "agegroup_oblig", "agegroup"]:
        if key in props:
            agegroup_key = key
            break

    if agegroup_key:
        ag_options = props[agegroup_key].get("possibleValues", ["all"])
        if params.age_group and params.age_group in ag_options:
            body[agegroup_key] = params.age_group
            if "agegroup" in props and agegroup_key != "agegroup":
                body["agegroup"] = agegroup_key
        else:
            all_val = props[agegroup_key].get("allValue", "all")
            body[agegroup_key] = all_val if all_val else (ag_options[0] if ag_options else "all")
            if "agegroup" in props and agegroup_key != "agegroup":
                body["agegroup"] = agegroup_key

    # Determine groupBy param
    group_by = "canton" if params.canton == "all" else None

    # Fetch data
    if ctx:
        await ctx.info(f"Fetching time series for '{params.series_id}'")
        await ctx.report_progress(progress=1, total=2)
    async with _client() as c:
        url = f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}"
        if group_by:
            url += f"?groupBy={group_by}"
        r = await _post(c, url, json=body, context=f"fetching data for '{params.series_id}'")
        if r.status_code != 200:
            # Surface the status only — never the raw upstream response body,
            # which can leak internal details into the model context (OBS-002).
            _fail(
                f"BAG IDD API error {r.status_code} while fetching "
                f"'{params.series_id}'. Use bag_health_mcp__get_series_details to verify "
                "valid filter values, then retry with adjusted parameters.",
                detail=r.text[:500],
            )
        data = r.json()

    values = data.get("values", {})

    # Normalise to list of {period, value, canton?, ...}
    is_weekly = "week" in temporality or "iso_week" in temporality or "date" in temporality

    def fmt_period(x: int | str) -> str:
        if isinstance(x, int):
            return _fmt_isoweek(x) if is_weekly else _fmt_year(x)
        return str(x)

    result_series: list[CantonSeries | DiseaseDataPoint] = []

    if isinstance(values, dict):
        # grouped by canton
        for canton_key, points in values.items():
            if not isinstance(points, list):
                continue
            # Take last N points
            recent = points[-params.limit_weeks:]
            series_points = [
                DiseaseDataPoint(
                    period=fmt_period(p["x"]),
                    value=p.get("y"),
                    trend=p.get("properties", {}).get("trend"),
                    data_complete=p.get("properties", {}).get("dataComplete"),
                )
                for p in recent
                if p.get("y") is not None
            ]
            if series_points:
                result_series.append(CantonSeries(
                    canton=canton_key,
                    data_points=len(series_points),
                    series=series_points,
                ))
    elif isinstance(values, list):
        recent = values[-params.limit_weeks:]
        result_series = [
            DiseaseDataPoint(
                period=fmt_period(p["x"]),
                value=p.get("y"),
                trend=p.get("properties", {}).get("trend"),
            )
            for p in recent
            if p.get("y") is not None
        ]

    # Summary stats for canton=all case
    summary = DiseaseDataSummary()
    if params.canton == "ZH" or params.canton != "all":
        matching = next(
            (s for s in result_series
             if isinstance(s, CantonSeries) and s.canton == params.canton),
            None,
        )
        if matching and matching.series:
            last = matching.series[-1]
            summary = DiseaseDataSummary(
                canton=params.canton,
                latest_period=last.period,
                latest_value=last.value,
                trend=last.trend,
                data_points_returned=len(matching.series),
            )

    if ctx:
        await ctx.report_progress(progress=2, total=2)

    return DiseaseDataOutput(
        series_id=params.series_id,
        topic=topic,
        aggregation=aggregation,
        temporality=temporality,
        filters_applied=body,
        summary=summary,
        results=result_series,
        interpretation=(
            f"Values represent '{aggregation}' ({chapter}) for '{topic}'. "
            "Period format: YYYY-Www for weekly, YYYY for yearly. "
            "'incValue' = incidence per 100'000 population. "
            "'value' = absolute case count."
        ),
        provenance=Provenance(
            source=data.get("source"),
            source_date=data.get("sourceDate"),
            data_version=data.get("version"),
        ),
    )


@mcp.tool(name="bag_health_mcp__list_export_files", annotations=READ_ONLY, description=(
    "List all available export file names from the BAG IDD. "
    "These are complete datasets (CSV/JSON) per disease, "
    "e.g. INFLUENZA_oblig, COVID19_wastewater_sequencing, MEASLES_oblig. "
    "Use with bag_health_mcp__download_export to get raw data files."
    "<use_case>Discover which complete bulk datasets can be downloaded for "
    "offline/bulk analysis.</use_case>"
    "<important_notes>Returns file names, not the data — pass one to "
    "bag_health_mcp__download_export.</important_notes>"
    "<example>bag_health_mcp__list_export_files() -> ['INFLUENZA_oblig', "
    "'COVID19_wastewater_sequencing', ...].</example>"
))
@_traced
async def bag_list_export_files(params: ExportFilesInput) -> ListExportFilesOutput:
    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/export/{params.version}/files",
            context="listing export files",
        )
        files: list[str] = r.json()

    return ListExportFilesOutput(
        version=params.version,
        total_files=len(files),
        files=sorted(files),
        usage=(
            "Use bag_health_mcp__download_export(file='INFLUENZA_oblig', format='csv') "
            "to download the raw dataset."
        ),
    )


@mcp.tool(name="bag_health_mcp__download_export", annotations=READ_ONLY, description=(
    "Download a complete export dataset from the BAG IDD as CSV or JSON. "
    "Returns the raw data content for a specific disease file. "
    "Useful for bulk analysis. Files are updated weekly."
    "<use_case>Retrieve a full raw dataset (all rows) for one disease for "
    "downstream/offline analysis.</use_case>"
    "<important_notes>The preview is truncated at 3000 chars; for very large "
    "datasets use the IDD web interface. Get file names from "
    "bag_health_mcp__list_export_files.</important_notes>"
    "<example>bag_health_mcp__download_export(file='INFLUENZA_oblig', format='csv') -> raw "
    "CSV content.</example>"
))
@_traced
async def bag_download_export(params: ExportDownloadInput) -> DownloadExportOutput:
    async with _client() as c:
        r = await _get(
            c,
            f"/api/v1/export/latest/{params.file}/{params.format}",
            context=f"downloading export '{params.file}'",
            allow_404=True,
        )
        if r.status_code == 404:
            _fail(
                f"File '{params.file}' not found. "
                "Use bag_health_mcp__list_export_files to see available files."
            )

    content = r.text
    lines = content.split("\n") if params.format == "csv" else []

    return DownloadExportOutput(
        file=params.file,
        format=params.format,
        size_bytes=len(content),
        rows=len(lines) - 1 if lines else None,
        preview=content[:3000],
        note=(
            "Full data returned in 'preview' (truncated at 3000 chars). "
            "For large datasets, use the IDD web interface at idd.bag.admin.ch."
        ),
    )


@mcp.tool(name="bag_health_mcp__get_data_version", annotations=READ_ONLY, description=(
    "Get the current data version of the BAG IDD. "
    "Returns the date of the last data update (format YYYYMMDD). "
    "IDD is updated every Wednesday."
    "<use_case>Check how fresh the data is / which weekly snapshot you are "
    "looking at.</use_case>"
    "<important_notes>Data is updated only weekly (Wednesdays); not "
    "real-time.</important_notes>"
    "<example>bag_health_mcp__get_data_version() -> version='20260325', "
    "date='2026-03-25'.</example>"
))
@_traced
async def bag_get_data_version(params: DataVersionInput) -> DataVersionOutput:
    async with _client() as c:
        r = await _get(c, "/api/v1/data/version", context="fetching data version")
        data = r.json()

    version_str = data.get("name", "")
    # Parse YYYYMMDD
    if len(version_str) == 8:
        formatted = f"{version_str[:4]}-{version_str[4:6]}-{version_str[6:]}"
    else:
        formatted = version_str

    return DataVersionOutput(
        version=version_str,
        date=formatted,
        note="IDD is updated every Wednesday. Data reflects the state as of this date.",
        provenance=Provenance(source_date=formatted, data_version=version_str),
    )


@mcp.tool(name="bag_health_mcp__get_canton_situation", annotations=READ_ONLY, description=(
    "Get a public health situation overview for a specific canton or Switzerland. "
    "Combines current incidence data for key school-relevant diseases "
    "(influenza, measles, norovirus proxy via acute_respiratory_infection) "
    "with trend information. Designed for school authorities and "
    "city administration Public Health Reporting. "
    "<use_case>One-call situational overview for a canton (Schulamt / city "
    "administration) without orchestrating multiple series queries.</use_case>"
    "<important_notes>Aggregates several series; a single unavailable series is "
    "reported as a per-disease status, not a failure of the whole call.</important_notes>"
    "<example>bag_health_mcp__get_canton_situation(canton='ZH') -> per-disease latest value, "
    "trend and change for Zurich. Anchor query: 'Wie ist die aktuelle "
    "Grippesituation im Kanton Zürich?'</example>"
))
@_traced
async def bag_get_canton_situation(
    canton: str = "ZH",
    include_wastewater: bool = False,
    ctx: Context | None = None,
) -> CantonSituationOutput:
    """
    High-level situational awareness tool combining multiple series.
    Optimised for Schulamt / Kreisschulbehörde use cases.
    """
    if canton.upper() not in [c for c in CANTONS if c != "all"]:
        _fail(
            f"Unknown canton '{canton}'. Valid cantons: "
            + ", ".join(c for c in CANTONS if c != "all")
        )

    canton_up = canton.upper()

    # Key disease series for schools
    school_relevant = {
        "influenza": "influenza/cases/incValue/iso_week",
        "influenza_like_illness": "acute_respiratory_infection/consultations/incValue/iso_week",
        "measles": "measles/cases/incValue/year",
        "pertussis": "pertussis/cases/incValue/iso_week",
        "covid19": "covid19/cases/incValue/iso_week",
    }
    if include_wastewater:
        school_relevant["wastewater_covid19"] = "wastewater_viral_load/NA/value/date"

    async def _fetch_series(
        name: str, series_id: str
    ) -> tuple[str, CantonDiseaseStatus | CantonDiseaseData]:
        # This aggregates several independent series into one overview. A failure
        # of a single series is reported inline as that series' status and never
        # fails the whole overview (which would be the wrong granularity); the
        # tool call itself still succeeds. Raw causes are logged server-side.
        parts = series_id.split("/")
        if len(parts) != 4:
            return name, CantonDiseaseStatus(status="unavailable")
        topic, chapter, aggregation, temporality = parts

        is_yearly = "year" in temporality

        try:
            async with _client() as c:
                dr = await c.get(
                    f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details"
                )
                if dr.status_code != 200:
                    return name, CantonDiseaseStatus(status="series_not_found")
                details = dr.json()

            props = details.get("properties", {})
            body: dict[str, str] = {}
            georegion_options = props.get("georegion", {}).get("possibleValues", [])

            if "georegion" in props:
                body["georegion"] = "canton" if "canton" in georegion_options else georegion_options[0]
            if "canton" in props:
                body["canton"] = canton_up
            if "sex" in props:
                body["sex"] = "all"
            if "country" in props:
                body["country"] = "CH"
            for key in ["agegroup_ili_ari", "agegroup_oblig"]:
                if key in props:
                    all_val = props[key].get("allValue", "all")
                    body[key] = all_val or "all"
                    if "agegroup" in props:
                        body["agegroup"] = key
                    break

            async with _client() as c:
                r = await c.post(
                    f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}",
                    json=body,
                )
                if r.status_code != 200:
                    return name, CantonDiseaseStatus(status="data_unavailable")
                data = r.json()

            values = data.get("values", {})
            canton_data: list[dict] = []

            if isinstance(values, dict):
                canton_data = values.get(canton_up, [])
            elif isinstance(values, list):
                canton_data = values

            if not canton_data:
                return name, CantonDiseaseStatus(
                    status="no_data", source_date=data.get("sourceDate")
                )

            recent = canton_data[-8:]  # last 8 periods
            latest = recent[-1]
            prev = recent[-2] if len(recent) >= 2 else None

            trend = latest.get("properties", {}).get("trend")
            period_fmt = (
                _fmt_isoweek(latest["x"]) if not is_yearly else _fmt_year(latest["x"])
            )

            change_pct: float | None = None
            if prev and prev.get("y") and latest.get("y") is not None:
                if prev["y"] != 0:
                    change_pct = round(((latest["y"] - prev["y"]) / prev["y"]) * 100, 1)

            return name, CantonDiseaseData(
                latest_period=period_fmt,
                latest_value=latest.get("y"),
                unit="incidence per 100'000" if "incValue" in aggregation else "absolute count",
                trend=trend,
                change_vs_prev_period_pct=change_pct,
                source_date=data.get("sourceDate"),
                series=[
                    DiseaseDataPoint(
                        period=_fmt_isoweek(p["x"]) if not is_yearly else _fmt_year(p["x"]),
                        value=p.get("y"),
                    )
                    for p in recent if p.get("y") is not None
                ],
            )
        except (EgressNotAllowed, httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            # Don't surface the raw exception to the model — log it server-side
            # and report a stable, generic per-series status (OBS-002). An egress
            # block fails this series closed; the guard already logged the target.
            logger.warning("canton_situation series '%s' failed: %r", name, exc)
            if ctx:
                # Tell the client this series degraded (no raw cause — OBS-002).
                await ctx.warning(f"Series '{name}' unavailable; continuing.")
            return name, CantonDiseaseStatus(status="unavailable")

    # Fan out over the series, reporting progress as each completes. The overview
    # makes 5+ (2 round-trips each) calls and can take a few seconds, so a
    # long-running client gets incremental progress (SDK-003).
    total = len(school_relevant)
    if ctx:
        await ctx.info(f"Building situation overview for canton {canton_up} "
                       f"({total} series)")
    tasks = [
        asyncio.ensure_future(_fetch_series(name, sid))
        for name, sid in school_relevant.items()
    ]
    diseases: dict[str, CantonDiseaseStatus | CantonDiseaseData] = {}
    done = 0
    for coro in asyncio.as_completed(tasks):
        name, value = await coro
        diseases[name] = value
        done += 1
        if ctx:
            await ctx.report_progress(progress=done, total=total)

    return CantonSituationOutput(
        canton=canton_up,
        diseases=diseases,
        note=(
            f"Situation overview for canton {canton_up}. "
            "incValue = incidence per 100'000 population. "
            "Data from BAG Infectious Disease Dashboard, updated weekly. "
            "For outbreak assessment, compare to 5-year mean using series "
            "ending in 'valueMean5y'. "
            f"Classification: {DATA_CLASSIFICATION}; data is aggregated at "
            f"'{MIN_AGGREGATION_LEVEL}' level (public OGD, small cells suppressed "
            "at source by the BAG) — no finer-grained or personal data is exposed."
        ),
        school_relevance=(
            "Influenza and ARI spikes correlate with school outbreak risk. "
            "Measles: single case = potential outbreak in low-vaccination schools. "
            "Pertussis: high risk for unvaccinated infants (siblings of school children)."
        ),
    )


# ---------------------------------------------------------------------------
# Resources (ARCH-008)
# ---------------------------------------------------------------------------
#
# Static reference data is exposed as MCP Resources, not tools: it is fixed,
# read-only and needs no arguments or upstream call, so a Resource (which a host
# can fetch and cache) is the right primitive. Live, parameterised surveillance
# data stays behind Tools.

@mcp.resource(
    "bag://reference/cantons",
    name="swiss_cantons",
    description="The Swiss canton codes accepted by the tools (incl. FL and 'all').",
    mime_type="application/json",
)
def cantons_resource() -> str:
    """The canton allow-list as JSON — reference data for building tool calls."""
    return json.dumps({"cantons": CANTONS})


@mcp.resource(
    "bag://reference/disease-categories",
    name="disease_categories",
    description=(
        "The disease-topic taxonomy: known IDD topic slugs grouped by category. "
        "Static reference; use bag_health_mcp__list_diseases for what the live API currently "
        "serves."
    ),
    mime_type="application/json",
)
def disease_categories_resource() -> str:
    return json.dumps(
        {name: sorted(members) for name, members in DISEASE_CATEGORIES.items()}
    )


@mcp.resource(
    "bag://reference/data-licence",
    name="data_licence",
    description="Data source, attribution and licence terms for the BAG IDD data.",
    mime_type="application/json",
)
def data_licence_resource() -> str:
    return json.dumps(
        {"attribution": DATA_ATTRIBUTION, "license": DATA_LICENSE, "source_api": IDD_BASE}
    )


# ---------------------------------------------------------------------------
# Prompts (ARCH-008)
# ---------------------------------------------------------------------------
#
# Prompts package the recommended multi-tool workflows as reusable, parameterised
# templates a host can surface to the user (e.g. as slash-commands).

@mcp.prompt(
    name="canton_situation_brief",
    title="Canton public-health situation brief",
    description=(
        "Draft a structured public-health situation brief for a Swiss canton "
        "(Schulamt / city-administration use case)."
    ),
)
def canton_situation_brief(canton: str = "ZH") -> str:
    return (
        f"Erstelle einen kurzen Public-Health-Lagebericht für den Kanton {canton}.\n\n"
        "Vorgehen:\n"
        f"1. Rufe bag_health_mcp__get_canton_situation(canton=\"{canton}\") auf.\n"
        "2. Fasse je Krankheit den aktuellen Stand, den Trend und die "
        "Veränderung zur Vorperiode zusammen.\n"
        "3. Hebe schulrelevante Risiken hervor (Influenza/ARI-Spitzen, "
        "Masern-Einzelfälle, Pertussis).\n"
        "4. Nenne Datenstand und Quelle (provenance) am Ende.\n"
        "Antworte auf Deutsch, prägnant, für eine Schulbehörde."
    )


@mcp.prompt(
    name="outbreak_check",
    title="Disease outbreak check",
    description="Check whether a given disease is currently elevated in Switzerland.",
)
def outbreak_check(disease: str = "measles", canton: str = "all") -> str:
    return (
        f"Prüfe, ob bei '{disease}' aktuell ein Ausbruch bzw. eine erhöhte "
        f"Aktivität im Gebiet '{canton}' vorliegt.\n\n"
        "Vorgehen:\n"
        f"1. bag_health_mcp__list_series(topic=\"{disease}\") um eine geeignete Serie zu finden.\n"
        "2. bag_health_mcp__get_series_details(series_id=...) für gültige Filter.\n"
        f"3. bag_health_mcp__get_disease_data(series_id=..., canton=\"{canton}\") für die "
        "Zeitreihe.\n"
        "4. Bewerte den Trend; vergleiche – wenn verfügbar – mit dem 5-Jahres-"
        "Mittel (Serien mit 'valueMean5y').\n"
        "Gib eine klare Einschätzung (erhöht / normal / unklar) mit Datenstand "
        "und Quelle."
    )


