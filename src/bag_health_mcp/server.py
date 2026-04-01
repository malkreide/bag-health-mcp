"""
bag-health-mcp — Swiss Federal Office of Public Health (BAG)
Infectious Disease Surveillance MCP Server

Data source: IDD API (api.idd.bag.admin.ch)
No authentication required. All data is public.
"""

from __future__ import annotations

import sys
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDD_BASE = "https://api.idd.bag.admin.ch"
TIMEOUT = 30.0
USER_AGENT = "bag-health-mcp/0.1.0 (https://github.com/malkreide/bag-health-mcp)"

# Swiss cantons (incl. FL = Liechtenstein as BAG tracks it)
CANTONS = [
    "AG","AI","AR","BE","BL","BS","FR","GE","GL","GR",
    "JU","LU","NE","NW","OW","SG","SH","SO","SZ","TG",
    "TI","UR","VD","VS","ZG","ZH","FL","all",
]

# ---------------------------------------------------------------------------
# FastMCP setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="bag-health-mcp",
    instructions=(
        "Access Swiss Federal Office of Public Health (BAG) infectious disease "
        "surveillance data via the IDD API. Covers 51 pathogens including "
        "influenza, COVID-19, measles, tuberculosis, wastewater surveillance, "
        "and more. Data is updated weekly every Wednesday. "
        "Use bag_list_diseases first to discover available topics, then "
        "bag_get_series_details to understand available filters, then "
        "bag_get_disease_data to retrieve time-series values."
    ),
)


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=IDD_BASE,
        timeout=TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        follow_redirects=True,
    )


def _fmt_isoweek(x: int) -> str:
    """Convert IDD isoweek int (e.g. 202413) → '2024-W13'."""
    s = str(x)
    if len(s) == 6:
        return f"{s[:4]}-W{s[4:]}"
    return str(x)


def _fmt_year(x: int) -> str:
    return str(x)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

Language = Literal["de", "fr", "it", "en"]
CantonCode = Literal[
    "AG","AI","AR","BE","BL","BS","FR","GE","GL","GR",
    "JU","LU","NE","NW","OW","SG","SH","SO","SZ","TG",
    "TI","UR","VD","VS","ZG","ZH","FL","all",
]


class ListDiseasesInput(BaseModel):
    pass


class DataSetsInput(BaseModel):
    topic: str = Field(
        description=(
            "Disease topic slug, e.g. 'influenza', 'covid19', 'measles'. "
            "Use bag_list_diseases to get valid values."
        )
    )


class SeriesDetailsInput(BaseModel):
    series_id: str = Field(
        description=(
            "Full series identifier in format 'topic/chapter/aggregation/temporality', "
            "e.g. 'influenza/cases/incValue/iso_week'. "
            "Use bag_list_series to discover available series for a topic."
        )
    )


class DiseaseDataInput(BaseModel):
    series_id: str = Field(
        description=(
            "Full series identifier, e.g. 'influenza/cases/incValue/iso_week'. "
            "Use bag_get_series_details to check available filters."
        )
    )
    canton: CantonCode = Field(
        default="all",
        description="Canton abbreviation or 'all' for Switzerland-wide data.",
    )
    sex: Literal["male", "female", "all"] = Field(
        default="all",
        description="Sex filter. Use 'all' for aggregated data.",
    )
    age_group: str | None = Field(
        default=None,
        description=(
            "Age group filter if the series supports it, "
            "e.g. '0 - 4', '5 - 14', '15 - 29', '30 - 64', '65+'. "
            "Leave None for aggregated data."
        ),
    )
    limit_weeks: int = Field(
        default=104,
        ge=1,
        le=600,
        description="Maximum number of data points to return (default 104 = ~2 years).",
    )


class ExportFilesInput(BaseModel):
    version: Literal["latest", "archived"] = Field(
        default="latest",
        description="'latest' for current data, 'archived' for historical snapshots.",
    )


class ExportDownloadInput(BaseModel):
    file: str = Field(
        description=(
            "File name from bag_list_export_files, e.g. 'INFLUENZA_oblig', "
            "'COVID19_wastewater_sequencing'."
        )
    )
    format: Literal["csv", "json"] = Field(
        default="csv",
        description="Export format.",
    )


class DataVersionInput(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(description=(
    "List all 51 disease topics available in the BAG Infectious Disease Dashboard (IDD). "
    "Returns the topic slug needed for other tools, grouped by category "
    "(respiratory, enteric, STI, vector-borne, wastewater). "
    "Start here to discover what data is available."
))
async def bag_list_diseases(params: ListDiseasesInput) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get("/api/v1/data/sets")
        r.raise_for_status()
        all_sets: list[str] = r.json()

    topics: set[str] = {s.split("/")[0] for s in all_sets}

    # Categorise for readability
    respiratory = {t for t in topics if t in {
        "acute_respiratory_infection", "influenza", "influenza-like_illness",
        "respiratory_pathogens", "covid19",
    }}
    enteric = {t for t in topics if t in {
        "campylobacteriosis", "salmonellosis", "ehec", "listeriosis",
        "hepatitis_a", "hepatitis_e", "shigellosis", "cholera",
        "typhoidParatyphoidFever", "trichinellosis", "botulism", "qFever",
    }}
    sti_blood = {t for t in topics if t in {
        "hiv", "aids", "syphilis", "gonorrhea", "chlamydiosis",
        "hepatitis_b", "hepatitis_c",
    }}
    vaccine_prev = {t for t in topics if t in {
        "measles", "rubella", "pertussis", "diphtheria", "tetanus",
        "haemophilusInfluenzae", "ipd", "meningo", "herpesZoster",
        "postZosterNeuralgia",
    }}
    vector_borne = {t for t in topics if t in {
        "lyme_borreliosis", "tick-borne_encephalitis", "dengueFever",
        "malaria", "westnileFever", "chikungunya", "zika", "yellowFever",
        "hanta", "tularemia",
    }}
    wastewater = {t for t in topics if "wastewater" in t}
    other = topics - respiratory - enteric - sti_blood - vaccine_prev - vector_borne - wastewater

    return {
        "total_topics": len(topics),
        "data_version": "see bag_get_data_version",
        "categories": {
            "respiratory": sorted(respiratory),
            "enteric": sorted(enteric),
            "sti_and_bloodborne": sorted(sti_blood),
            "vaccine_preventable": sorted(vaccine_prev),
            "vector_borne": sorted(vector_borne),
            "wastewater_surveillance": sorted(wastewater),
            "other": sorted(other),
        },
        "usage": (
            "Use a topic slug with bag_list_series(topic=...) "
            "to see available data series."
        ),
    }


@mcp.tool(description=(
    "List all available data series for a specific disease topic. "
    "Each series is identified by 'topic/chapter/aggregation/temporality'. "
    "Returns series IDs to use with bag_get_series_details and bag_get_disease_data."
))
async def bag_list_series(params: DataSetsInput) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get("/api/v1/data/sets")
        r.raise_for_status()
        all_sets: list[str] = r.json()

    topic_sets = [s for s in all_sets if s.startswith(f"{params.topic}/")]
    if not topic_sets:
        return {
            "error": f"Topic '{params.topic}' not found.",
            "hint": "Use bag_list_diseases to see valid topic slugs.",
        }

    # Parse structure
    chapters: dict[str, list[str]] = {}
    for s in topic_sets:
        parts = s.split("/")
        if len(parts) == 4:
            chapter = parts[1]
            agg_temp = f"{parts[2]}/{parts[3]}"
            chapters.setdefault(chapter, []).append(agg_temp)

    return {
        "topic": params.topic,
        "total_series": len(topic_sets),
        "chapters": {ch: sorted(series) for ch, series in sorted(chapters.items())},
        "series_ids": sorted(topic_sets),
        "usage": (
            "Use a series_id with bag_get_series_details to see available "
            "filter values (canton, age_group, sex, type), then "
            "bag_get_disease_data to fetch the time series."
        ),
    }


@mcp.tool(description=(
    "Get metadata and available filter values for a specific data series. "
    "Shows which canton, age group, sex, and other dimensions are available. "
    "Always call this before bag_get_disease_data to know valid filter options."
))
async def bag_get_series_details(params: SeriesDetailsInput) -> dict[str, Any]:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        return {
            "error": "series_id must be in format 'topic/chapter/aggregation/temporality'",
            "example": "influenza/cases/incValue/iso_week",
        }
    topic, chapter, aggregation, temporality = parts

    async with _client() as c:
        r = await c.get(
            f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details"
        )
        if r.status_code == 404:
            return {
                "error": f"Series '{params.series_id}' not found.",
                "hint": "Use bag_list_series(topic=...) to discover valid series.",
            }
        r.raise_for_status()
        data = r.json()

    props = data.get("properties", {})
    # Summarise
    filters: dict[str, list[str]] = {}
    for key, val in props.items():
        if isinstance(val, dict):
            filters[key] = val.get("possibleValues", [])

    return {
        "series_id": params.series_id,
        "source": data.get("source"),
        "source_date": data.get("sourceDate"),
        "version": data.get("version"),
        "available_filters": filters,
        "cantons": filters.get("canton", []),
        "age_groups": (
            filters.get("agegroup_ili_ari")
            or filters.get("agegroup_oblig")
            or filters.get("agegroup")
            or []
        ),
        "sex_options": filters.get("sex", []),
        "note": (
            "Use these filter values in bag_get_disease_data. "
            "Use 'all' for any aggregated dimension."
        ),
    }


@mcp.tool(description=(
    "Fetch time-series surveillance data for a disease from the BAG IDD. "
    "Returns weekly or yearly case counts, incidence rates, or other metrics. "
    "Data updated every Wednesday. "
    "Example: Influenza incidence per 100k population in Zurich by week."
))
async def bag_get_disease_data(params: DiseaseDataInput) -> dict[str, Any]:
    parts = params.series_id.split("/")
    if len(parts) != 4:
        return {"error": "series_id must be 'topic/chapter/aggregation/temporality'"}
    topic, chapter, aggregation, temporality = parts

    # Build filter body based on series details
    async with _client() as c:
        # Fetch details to build correct filter
        dr = await c.get(
            f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details"
        )
        if dr.status_code == 404:
            return {
                "error": f"Series not found: {params.series_id}",
                "hint": "Use bag_list_series to find valid series_ids.",
            }
        dr.raise_for_status()
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
    async with _client() as c:
        url = f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}"
        if group_by:
            url += f"?groupBy={group_by}"
        r = await c.post(url, json=body)
        if r.status_code != 200:
            return {
                "error": f"API error {r.status_code}",
                "detail": r.text[:500],
                "hint": (
                    "Use bag_get_series_details to verify valid filter values, "
                    "then retry with adjusted parameters."
                ),
            }
        data = r.json()

    values = data.get("values", {})

    # Normalise to list of {period, value, canton?, ...}
    is_weekly = "week" in temporality or "iso_week" in temporality or "date" in temporality

    def fmt_period(x: int | str) -> str:
        if isinstance(x, int):
            return _fmt_isoweek(x) if is_weekly else _fmt_year(x)
        return str(x)

    result_series: list[dict[str, Any]] = []

    if isinstance(values, dict):
        # grouped by canton
        for canton_key, points in values.items():
            if not isinstance(points, list):
                continue
            # Take last N points
            recent = points[-params.limit_weeks:]
            series_points = [
                {
                    "period": fmt_period(p["x"]),
                    "value": p.get("y"),
                    "trend": p.get("properties", {}).get("trend"),
                    "data_complete": p.get("properties", {}).get("dataComplete"),
                }
                for p in recent
                if p.get("y") is not None
            ]
            if series_points:
                result_series.append({
                    "canton": canton_key,
                    "data_points": len(series_points),
                    "series": series_points,
                })
    elif isinstance(values, list):
        recent = values[-params.limit_weeks:]
        result_series = [
            {
                "period": fmt_period(p["x"]),
                "value": p.get("y"),
                "trend": p.get("properties", {}).get("trend"),
            }
            for p in recent
            if p.get("y") is not None
        ]

    # Summary stats for canton=all case
    summary: dict[str, Any] = {}
    if params.canton == "ZH" or params.canton != "all":
        matching = next(
            (s for s in result_series if isinstance(s, dict) and s.get("canton") == params.canton),
            None,
        )
        if matching:
            pts = matching["series"]
            if pts:
                last = pts[-1]
                summary = {
                    "canton": params.canton,
                    "latest_period": last["period"],
                    "latest_value": last["value"],
                    "trend": last.get("trend"),
                    "data_points_returned": len(pts),
                }

    return {
        "series_id": params.series_id,
        "topic": topic,
        "aggregation": aggregation,
        "temporality": temporality,
        "source": data.get("source"),
        "source_date": data.get("sourceDate"),
        "data_version": data.get("version"),
        "filters_applied": body,
        "summary": summary,
        "results": result_series,
        "interpretation": (
            f"Values represent '{aggregation}' ({chapter}) for '{topic}'. "
            "Period format: YYYY-Www for weekly, YYYY for yearly. "
            "'incValue' = incidence per 100'000 population. "
            "'value' = absolute case count."
        ),
    }


@mcp.tool(description=(
    "List all available export file names from the BAG IDD. "
    "These are complete datasets (CSV/JSON) per disease, "
    "e.g. INFLUENZA_oblig, COVID19_wastewater_sequencing, MEASLES_oblig. "
    "Use with bag_download_export to get raw data files."
))
async def bag_list_export_files(params: ExportFilesInput) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get(f"/api/v1/export/{params.version}/files")
        r.raise_for_status()
        files: list[str] = r.json()

    return {
        "version": params.version,
        "total_files": len(files),
        "files": sorted(files),
        "usage": (
            "Use bag_download_export(file='INFLUENZA_oblig', format='csv') "
            "to download the raw dataset."
        ),
    }


@mcp.tool(description=(
    "Download a complete export dataset from the BAG IDD as CSV or JSON. "
    "Returns the raw data content for a specific disease file. "
    "Useful for bulk analysis. Files are updated weekly."
))
async def bag_download_export(params: ExportDownloadInput) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get(f"/api/v1/export/latest/{params.file}/{params.format}")
        if r.status_code == 404:
            return {
                "error": f"File '{params.file}' not found.",
                "hint": "Use bag_list_export_files to see available files.",
            }
        r.raise_for_status()

    content = r.text
    lines = content.split("\n") if params.format == "csv" else []

    return {
        "file": params.file,
        "format": params.format,
        "size_bytes": len(content),
        "rows": len(lines) - 1 if lines else None,
        "preview": content[:3000],
        "note": (
            "Full data returned in 'preview' (truncated at 3000 chars). "
            "For large datasets, use the IDD web interface at idd.bag.admin.ch."
        ),
    }


@mcp.tool(description=(
    "Get the current data version of the BAG IDD. "
    "Returns the date of the last data update (format YYYYMMDD). "
    "IDD is updated every Wednesday."
))
async def bag_get_data_version(params: DataVersionInput) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get("/api/v1/data/version")
        r.raise_for_status()
        data = r.json()

    version_str = data.get("name", "")
    # Parse YYYYMMDD
    if len(version_str) == 8:
        formatted = f"{version_str[:4]}-{version_str[4:6]}-{version_str[6:]}"
    else:
        formatted = version_str

    return {
        "version": version_str,
        "date": formatted,
        "note": "IDD is updated every Wednesday. Data reflects the state as of this date.",
    }


@mcp.tool(description=(
    "Get a public health situation overview for a specific canton or Switzerland. "
    "Combines current incidence data for key school-relevant diseases "
    "(influenza, measles, norovirus proxy via acute_respiratory_infection) "
    "with trend information. Designed for school authorities and "
    "city administration Public Health Reporting. "
    "Anchor query: 'Was ist die aktuelle Grippesituation im Kanton Zürich?'"
))
async def bag_get_canton_situation(
    canton: str = "ZH",
    include_wastewater: bool = False,
) -> dict[str, Any]:
    """
    High-level situational awareness tool combining multiple series.
    Optimised for Schulamt / Kreisschulbehörde use cases.
    """
    if canton.upper() not in [c for c in CANTONS if c != "all"]:
        return {
            "error": f"Unknown canton '{canton}'.",
            "valid_cantons": [c for c in CANTONS if c != "all"],
        }

    canton_up = canton.upper()
    results: dict[str, Any] = {"canton": canton_up, "diseases": {}}

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

    async def _fetch_series(name: str, series_id: str) -> tuple[str, Any]:
        parts = series_id.split("/")
        if len(parts) != 4:
            return name, {"error": "Invalid series_id"}
        topic, chapter, aggregation, temporality = parts

        is_yearly = "year" in temporality

        try:
            async with _client() as c:
                dr = await c.get(
                    f"/api/v1/data/{topic}/{chapter}/{aggregation}/{temporality}/details"
                )
                if dr.status_code != 200:
                    return name, {"error": f"Series not found: {series_id}"}
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
                    return name, {"error": f"Data fetch failed: {r.status_code}"}
                data = r.json()

            values = data.get("values", {})
            canton_data: list[dict] = []

            if isinstance(values, dict):
                canton_data = values.get(canton_up, [])
            elif isinstance(values, list):
                canton_data = values

            if not canton_data:
                return name, {"status": "no_data", "source_date": data.get("sourceDate")}

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

            return name, {
                "latest_period": period_fmt,
                "latest_value": latest.get("y"),
                "unit": "incidence per 100'000" if "incValue" in aggregation else "absolute count",
                "trend": trend,
                "change_vs_prev_period_pct": change_pct,
                "source_date": data.get("sourceDate"),
                "series": [
                    {
                        "period": _fmt_isoweek(p["x"]) if not is_yearly else _fmt_year(p["x"]),
                        "value": p.get("y"),
                    }
                    for p in recent if p.get("y") is not None
                ],
            }
        except Exception as e:
            return name, {"error": str(e)}

    import asyncio
    tasks = [_fetch_series(name, sid) for name, sid in school_relevant.items()]
    fetched = await asyncio.gather(*tasks)

    for name, data in fetched:
        results["diseases"][name] = data

    results["note"] = (
        f"Situation overview for canton {canton_up}. "
        "incValue = incidence per 100'000 population. "
        "Data from BAG Infectious Disease Dashboard, updated weekly. "
        "For outbreak assessment, compare to 5-year mean using series "
        "ending in 'valueMean5y'."
    )
    results["school_relevance"] = (
        "Influenza and ARI spikes correlate with school outbreak risk. "
        "Measles: single case = potential outbreak in low-vaccination schools. "
        "Pertussis: high risk for unvaccinated infants (siblings of school children)."
    )

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--http" in sys.argv:
        port_idx = sys.argv.index("--port") + 1 if "--port" in sys.argv else None
        port     = int(sys.argv[port_idx]) if port_idx else 8000
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run()
