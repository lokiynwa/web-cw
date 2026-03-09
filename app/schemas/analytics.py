"""Analytics and affordability response schemas for OpenAPI documentation."""

from __future__ import annotations

from pydantic import Field

from app.schemas.base import SchemaBase


class MetricsSummary(SchemaBase):
    """Numeric summary statistics."""

    average: float | None = Field(None, description="Arithmetic mean of observed values.")
    median: float | None = Field(None, description="Median of observed values.")
    min: float | None = Field(None, description="Minimum observed value.")
    max: float | None = Field(None, description="Maximum observed value.")
    sample_size: int = Field(..., ge=0, description="Number of observations in the sample.")


class RentFilters(SchemaBase):
    """Filter metadata for rental analytics responses."""

    bedrooms: int | None = Field(None, description="Bedroom-count filter applied.")
    property_type: str | None = Field(None, description="Property type filter applied.")
    ensuite_proxy: bool | None = Field(None, description="Ensuite proxy filter applied.")


class CostFilters(SchemaBase):
    """Filter metadata for crowd-cost analytics responses."""

    submission_type: str | None = Field(None, description="Submission type filter applied (for example PINT or TAKEAWAY).")


class CityRentAnalyticsResponse(SchemaBase):
    """City-level rental analytics payload."""

    city: str = Field(..., description="City name from path parameter.")
    filters: RentFilters
    metrics: MetricsSummary


class RentCityItem(SchemaBase):
    """City entry for rental dataset discovery."""

    name: str = Field(..., description="City name in cleaned rental data.")
    sample_size: int = Field(..., ge=0, description="Number of valid rental observations for this city.")


class RentCitiesResponse(SchemaBase):
    """List of available cities with valid rental observations."""

    cities: list[RentCityItem]
    total: int = Field(..., ge=0)


class AreaRentAnalyticsResponse(SchemaBase):
    """Area-level rental analytics payload."""

    city: str = Field(..., description="City name from path parameter.")
    area: str = Field(..., description="Area name from path parameter.")
    filters: RentFilters
    metrics: MetricsSummary


class RentAreaMetricsItem(SchemaBase):
    """Per-area rental metrics row."""

    area: str = Field(..., description="Area name.")
    average: float | None = Field(None)
    median: float | None = Field(None)
    min: float | None = Field(None)
    max: float | None = Field(None)
    sample_size: int = Field(..., ge=0)


class CityAreaRentAnalyticsResponse(SchemaBase):
    """City payload with per-area rental metrics."""

    city: str
    filters: RentFilters
    areas: list[RentAreaMetricsItem]


class CityCostAnalyticsResponse(SchemaBase):
    """City-level active crowd-cost analytics payload."""

    city: str
    filters: CostFilters
    metrics: MetricsSummary


class AreaCostAnalyticsResponse(SchemaBase):
    """Area-level active crowd-cost analytics payload."""

    city: str
    area: str
    filters: CostFilters
    metrics: MetricsSummary


class NormalizationBounds(SchemaBase):
    """Normalization bounds used in affordability scoring."""

    floor: float = Field(..., description="Lower bound for component normalization.")
    ceiling: float = Field(..., description="Upper bound for component normalization.")


class AffordabilityComponent(SchemaBase):
    """Single component contribution to affordability score."""

    submission_type: str | None = Field(None, description="Submission type associated with this component when applicable.")
    metrics: MetricsSummary
    component_score: float | None = Field(None, description="0-100 component score where lower cost yields higher score.")
    normalization_bounds: NormalizationBounds | None = None


class AffordabilityFormula(SchemaBase):
    """Human-readable scoring formula metadata."""

    description: str
    overall: str
    component: str


class AffordabilityWeights(SchemaBase):
    """Requested and effective component weights for score composition."""

    requested: dict[str, float]
    effective: dict[str, float]


class CityAffordabilityScoreResponse(SchemaBase):
    """City-level affordability score response."""

    city: str
    selected_components: list[str]
    score: float = Field(..., ge=0, le=100)
    score_band: str
    components: dict[str, AffordabilityComponent]
    weights: AffordabilityWeights
    formula: AffordabilityFormula


class AffordabilityAreaItem(SchemaBase):
    """Per-area affordability score row."""

    area: str
    score: float = Field(..., ge=0, le=100)
    score_band: str
    components: dict[str, AffordabilityComponent]
    weights: AffordabilityWeights


class CityAreaAffordabilityResponse(SchemaBase):
    """City payload with per-area affordability scores."""

    city: str
    selected_components: list[str]
    formula: AffordabilityFormula
    areas: list[AffordabilityAreaItem]
    total: int = Field(..., ge=0)
