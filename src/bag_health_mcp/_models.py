"""Pydantic input and output models for the bag-health-mcp tools.

Split out of server.py (ARCH-011). Input models enforce strict validation
(SEC-018); output models give each tool a precise outputSchema with a shared
Provenance block (SDK-002 / CH-004). Re-exported from
``bag_health_mcp.server`` for backward compatibility.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

Language = Literal["de", "fr", "it", "en"]
CantonCode = Literal[
    "AG","AI","AR","BE","BL","BS","FR","GE","GL","GR",
    "JU","LU","NE","NW","OW","SG","SH","SO","SZ","TG",
    "TI","UR","VD","VS","ZG","ZH","FL","all",
]


class _StrictInput(BaseModel):
    """Base for every tool input (SEC-018).

    ``strict=True`` disables silent type coercion (a string is not accepted where
    an int is declared, etc.) and ``extra='forbid'`` rejects unexpected fields.
    Both propagate into the JSON inputSchema advertised to clients, so invalid
    arguments are refused at the protocol boundary before any tool body runs.
    Free-form string fields that flow into upstream URL paths additionally carry
    length and pattern constraints below.
    """

    model_config = ConfigDict(strict=True, extra="forbid")


# Slugs (topic, export file) and series ids only ever contain these characters in
# the real IDD API; constraining them caps unbounded user input before it reaches
# a URL path (SEC-018). Series ids are 'topic/chapter/aggregation/temporality'.
_SLUG_PATTERN = r"^[A-Za-z0-9_-]+$"
_SERIES_ID_PATTERN = r"^[A-Za-z0-9_/-]+$"
_AGE_GROUP_PATTERN = r"^[0-9 +-]+$"


class ListDiseasesInput(_StrictInput):
    pass


class DataSetsInput(_StrictInput):
    topic: str = Field(
        min_length=1,
        max_length=64,
        pattern=_SLUG_PATTERN,
        description=(
            "Disease topic slug, e.g. 'influenza', 'covid19', 'measles'. "
            "Use bag_health_mcp__list_diseases to get valid values."
        ),
    )


class SeriesDetailsInput(_StrictInput):
    series_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SERIES_ID_PATTERN,
        description=(
            "Full series identifier in format 'topic/chapter/aggregation/temporality', "
            "e.g. 'influenza/cases/incValue/iso_week'. "
            "Use bag_health_mcp__list_series to discover available series for a topic."
        ),
    )


class DiseaseDataInput(_StrictInput):
    series_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SERIES_ID_PATTERN,
        description=(
            "Full series identifier, e.g. 'influenza/cases/incValue/iso_week'. "
            "Use bag_health_mcp__get_series_details to check available filters."
        ),
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
        max_length=32,
        pattern=_AGE_GROUP_PATTERN,
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


class ExportFilesInput(_StrictInput):
    version: Literal["latest", "archived"] = Field(
        default="latest",
        description="'latest' for current data, 'archived' for historical snapshots.",
    )


class ExportDownloadInput(_StrictInput):
    file: str = Field(
        min_length=1,
        max_length=128,
        pattern=_SLUG_PATTERN,
        description=(
            "File name from bag_health_mcp__list_export_files, e.g. 'INFLUENZA_oblig', "
            "'COVID19_wastewater_sequencing'."
        ),
    )
    format: Literal["csv", "json"] = Field(
        default="csv",
        description="Export format.",
    )


class DataVersionInput(_StrictInput):
    pass


# ---------------------------------------------------------------------------
# Health-indicator inputs (multi-source extension)
# ---------------------------------------------------------------------------
#
# Two source-agnostic tools cover three additional Swiss health-data providers
# behind a single input shape (see docs/tool-design-health-indicators.md).
# ``indicator_id`` and ``region`` flow into upstream URL paths, so both carry
# strict length + pattern constraints (SEC-018); ``topic`` is only used for local
# substring filtering of a cached catalogue, so it needs a length cap, not a path
# pattern.

HealthSource = Literal["obsan", "versorgungsatlas", "suchtschweiz"]

# Obsan indicator ids come as either the internal id ("_330") or the navigable
# "<topic>/<slug>" path ("monam/alkoholkonsum-alter-11-15"); Versorgungsatlas as
# "<id>/<aspect>" ("_003/b"). This pattern covers all three.
_INDICATOR_ID_PATTERN = r"^[A-Za-z0-9_/-]+$"
_REGION_PATTERN = r"^[A-Za-z]{2,3}$"


class SearchHealthIndicatorsInput(_StrictInput):
    source: HealthSource = Field(
        description=(
            "Which Swiss health-data source to search: 'obsan' (Swiss Health "
            "Observatory indicators, incl. the HBSC youth-survey series), "
            "'versorgungsatlas' (Swiss health-care supply atlas, ~124 indicators), "
            "or 'suchtschweiz' (addiction/HBSC series — served via Obsan's mirror)."
        ),
    )
    topic: str = Field(
        default="",
        max_length=80,
        description=(
            "Free-text filter matched against indicator titles/topics/slugs "
            "(e.g. 'alkohol', 'impfung', 'kosten'). Empty returns the top of the "
            "catalogue."
        ),
    )
    region: str | None = Field(
        default=None,
        max_length=3,
        pattern=_REGION_PATTERN,
        description=(
            "Optional canton code (e.g. 'ZH') or 'CH'. Note: most indicators here "
            "are national only; a canton hint is recorded but may not narrow "
            "results — see each indicator's regional dimension."
        ),
    )
    year_from: int | None = Field(
        default=None, ge=1900, le=2100,
        description="Optional lower bound (year) — a hint for downstream series retrieval.",
    )
    year_to: int | None = Field(
        default=None, ge=1900, le=2100,
        description="Optional upper bound (year) — a hint for downstream series retrieval.",
    )
    language: Language = Field(default="de", description="Result language for labels.")
    limit: int = Field(
        default=25, ge=1, le=100,
        description="Maximum number of matching indicators to return.",
    )


class GetIndicatorSeriesInput(_StrictInput):
    source: HealthSource = Field(
        description="Source the indicator_id belongs to (as returned by search_health_indicators).",
    )
    indicator_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_INDICATOR_ID_PATTERN,
        description=(
            "Indicator identifier from search_health_indicators. Obsan: internal id "
            "'_330' or path 'monam/alkoholkonsum-alter-11-15'. Versorgungsatlas: "
            "'<id>/<aspect>', e.g. '_003/b'."
        ),
    )
    region: str | None = Field(
        default=None,
        max_length=3,
        pattern=_REGION_PATTERN,
        description=(
            "Optional canton (e.g. 'ZH') or 'CH'. If the indicator has no regional "
            "dimension (most youth-survey/HBSC series), the national series is "
            "returned with a note — a canton-vs-Switzerland comparison is then not "
            "available from this indicator."
        ),
    )
    year_from: int | None = Field(
        default=None, ge=1900, le=2100,
        description="Optional lower year bound; points before it are dropped.",
    )
    year_to: int | None = Field(
        default=None, ge=1900, le=2100,
        description="Optional upper year bound; points after it are dropped.",
    )
    language: Language = Field(default="de", description="Language for labels/units.")


# ---------------------------------------------------------------------------
# Output models (SDK-002)
# ---------------------------------------------------------------------------
#
# Tools return typed Pydantic models rather than bare dict[str, Any], so MCPServer
# advertises a precise outputSchema in tools/list and emits structuredContent.
# Every output carries a shared Provenance block (consistent envelope) naming the
# data source and licence attribution; the loose source/source_date/version
# fields the dicts used are folded into it.

DATA_ATTRIBUTION = (
    "Federal Office of Public Health FOPH — Infectious Disease Dashboard (IDD); "
    "open data via opendata.swiss"
)
# BAG IDD is published on opendata.swiss as federal Open Government Data under
# "free use — source attribution required" terms (the Swiss OGD equivalent of
# CC BY): reuse is permitted provided the source is cited (CH-004).
DATA_LICENSE = (
    "opendata.swiss Open Government Data — free use, source attribution "
    "required (Swiss OGD terms, CC BY-equivalent). Cite: "
    "Federal Office of Public Health FOPH, Infectious Disease Dashboard (IDD)."
)


class Provenance(BaseModel):
    """Where a result came from, attached to every tool output (SDK-002/CH-004).

    Carries the upstream source/date/version plus a controlled licence and
    attribution string so every response states how the data may be reused.
    """

    source: str | None = None
    source_date: str | None = None
    data_version: str | None = None
    attribution: str = DATA_ATTRIBUTION
    license: str = DATA_LICENSE


class ListDiseasesOutput(BaseModel):
    total_topics: int
    categories: dict[str, list[str]]
    usage: str
    provenance: Provenance = Field(default_factory=Provenance)


class ListSeriesOutput(BaseModel):
    topic: str
    total_series: int
    chapters: dict[str, list[str]]
    series_ids: list[str]
    usage: str
    provenance: Provenance = Field(default_factory=Provenance)


class SeriesDetailsOutput(BaseModel):
    series_id: str
    available_filters: dict[str, list[str]]
    cantons: list[str]
    age_groups: list[str]
    sex_options: list[str]
    note: str
    provenance: Provenance = Field(default_factory=Provenance)


class DiseaseDataPoint(BaseModel):
    period: str
    value: float | None = None
    trend: str | None = None
    data_complete: str | None = None


class CantonSeries(BaseModel):
    canton: str
    data_points: int
    series: list[DiseaseDataPoint]


class DiseaseDataSummary(BaseModel):
    canton: str | None = None
    latest_period: str | None = None
    latest_value: float | None = None
    trend: str | None = None
    data_points_returned: int | None = None


class DiseaseDataOutput(BaseModel):
    series_id: str
    topic: str
    aggregation: str
    temporality: str
    filters_applied: dict[str, str]
    summary: DiseaseDataSummary
    # Canton-grouped responses yield CantonSeries; flat responses yield bare
    # DiseaseDataPoints — the union preserves both existing shapes.
    results: list[CantonSeries | DiseaseDataPoint]
    interpretation: str
    provenance: Provenance = Field(default_factory=Provenance)


class ListExportFilesOutput(BaseModel):
    version: str
    total_files: int
    files: list[str]
    usage: str
    provenance: Provenance = Field(default_factory=Provenance)


class DownloadExportOutput(BaseModel):
    file: str
    format: str
    size_bytes: int
    rows: int | None
    preview: str
    note: str
    provenance: Provenance = Field(default_factory=Provenance)


class DataVersionOutput(BaseModel):
    version: str
    date: str
    note: str
    provenance: Provenance = Field(default_factory=Provenance)


class CantonDiseaseStatus(BaseModel):
    """A school-relevant series that could not be resolved for this canton."""

    status: str
    source_date: str | None = None


class CantonDiseaseData(BaseModel):
    """A school-relevant series with current data for this canton."""

    latest_period: str | None = None
    latest_value: float | None = None
    unit: str | None = None
    trend: str | None = None
    change_vs_prev_period_pct: float | None = None
    source_date: str | None = None
    series: list[DiseaseDataPoint] = Field(default_factory=list)


class CantonSituationOutput(BaseModel):
    canton: str
    diseases: dict[str, CantonDiseaseStatus | CantonDiseaseData]
    note: str
    school_relevance: str
    provenance: Provenance = Field(default_factory=Provenance)


# ---------------------------------------------------------------------------
# Health-indicator outputs (multi-source extension)
# ---------------------------------------------------------------------------
#
# Per-source attribution/licence, since the extension reaches beyond the BAG IDD.
# No source below advertises a formal machine-readable licence on its data
# objects; reuse follows Swiss OGD practice (free use with source attribution).
OBSAN_ATTRIBUTION = "Obsan — Swiss Health Observatory, indicator collection (ind.obsan.admin.ch)"
VERSORGUNGSATLAS_ATTRIBUTION = (
    "Versorgungsatlas — Swiss Atlas of Health Care Supply, a BAG/Obsan project "
    "(versorgungsatlas.ch)"
)
SUCHTSCHWEIZ_ATTRIBUTION = (
    "Sucht Schweiz — «Health Behaviour in School-aged Children» (HBSC) survey, "
    "obtained via the Obsan indicator mirror"
)
INDICATOR_LICENSE = (
    "No explicit machine-readable licence published on the data objects. Treat as "
    "Swiss Open Government Data practice: free use with mandatory source "
    "attribution. Always cite the per-indicator 'source' field."
)

# The mandated safeguard label (task requirement): these tools serve AGGREGATED
# population statistics — never individual advice. Surfaced both in the tool
# descriptions and inside every response envelope, in German (school-context
# audience) and English.
AGGREGATE_STATISTICS_NOTICE = (
    "Aggregierte Bevölkerungsstatistik (Prävalenzen/Kennzahlen nach "
    "Alter/Geschlecht/Region) — KEINE individuelle Beratung, Diagnose oder "
    "Fallbeurteilung, kein Personenbezug. Aggregated population statistics, not "
    "individual advice or diagnosis."
)


class IndicatorSummary(BaseModel):
    """One matching indicator from a catalogue search."""

    source: str
    indicator_id: str
    title: str
    topic: str | None = None
    subtitle: str | None = None
    description: str | None = None
    regional_dimension: str | None = None  # e.g. "national" | "canton" | "unknown"


class IndicatorSearchOutput(BaseModel):
    source: str
    query: dict[str, str | int | None]
    total_matches: int
    indicators: list[IndicatorSummary]
    usage: str
    aggregate_statistics_notice: str = AGGREGATE_STATISTICS_NOTICE
    provenance: Provenance = Field(default_factory=Provenance)


class IndicatorSeriesPoint(BaseModel):
    """One observation. Dimension ids (sex/category) are passed through as the
    source encodes them; see the series ``dimensions`` block for their meaning."""

    year: int | None = None
    period: str | None = None
    value: float | None = None
    value_lower_ci: float | None = None
    value_upper_ci: float | None = None
    sample_size: int | None = None
    sex_id: int | None = None
    category_id: int | None = None


class IndicatorSeriesOutput(BaseModel):
    source: str
    indicator_id: str
    title: str
    unit: str | None = None
    region: str | None = None
    region_note: str | None = None
    values_available: bool = True
    dimensions: dict[str, str] = Field(default_factory=dict)
    total_points: int = 0
    points: list[IndicatorSeriesPoint] = Field(default_factory=list)
    interpretation: str = ""
    aggregate_statistics_notice: str = AGGREGATE_STATISTICS_NOTICE
    note: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)

