"""Canonical request/response models shared by the backend and AI adapter."""

from math import isclose
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Metric = Literal["T1", "T2", "E1", "E2", "S1", "S2", "B1", "B2", "C1", "C2"]
Direction = Literal["transport", "ecology", "social", "safety", "services"]
METRICS = ("T1", "T2", "E1", "E2", "S1", "S2", "B1", "B2", "C1", "C2")
Indicator = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class District(Contract):
    id: str
    name: str
    population_share: Annotated[float, Field(gt=0, le=1)]
    profile: str
    indicators: dict[Metric, Indicator]

    @model_validator(mode="after")
    def complete_indicators(self) -> Self:
        if set(self.indicators) != set(METRICS):
            raise ValueError("All ten indicators are required")
        return self


class Measure(Contract):
    id: str
    name: str
    direction: Direction
    scope: Literal["district", "city"]
    cost: Annotated[int, Field(gt=0)]
    lag_quarters: Annotated[int, Field(ge=0, le=8)]
    effects: dict[Metric, float]


class Synergy(Contract):
    measures: tuple[str, str]
    target_measure: str
    effects: dict[Metric, float]


class Conflict(Contract):
    measures: tuple[str, str]
    scope: Literal["anywhere", "same_district"]
    reason: str


class Rules(Contract):
    budget: Literal[100] = 100
    decision_count: Literal[5] = 5
    max_per_direction: Literal[2] = 2
    horizon_quarters: Literal[8] = 8
    critical_threshold: Literal[40] = 40
    average_weight: Literal[0.7] = 0.7
    weakest_weight: Literal[0.3] = 0.3
    critical_penalty: Literal[1.0] = 1.0


class Catalog(Contract):
    version: str
    rules: Rules
    weights: dict[Metric, Annotated[float, Field(ge=0, le=1)]]
    districts: list[District] = Field(min_length=5, max_length=5)
    measures: list[Measure] = Field(min_length=14, max_length=14)
    synergies: list[Synergy]
    conflicts: list[Conflict]

    @model_validator(mode="after")
    def consistent_dataset(self) -> Self:
        if set(self.weights) != set(METRICS) or not isclose(sum(self.weights.values()), 1):
            raise ValueError("All ten weights must sum to one")
        if not isclose(sum(d.population_share for d in self.districts), 1):
            raise ValueError("Population shares must sum to one")
        if len({d.id for d in self.districts}) != len(self.districts):
            raise ValueError("Duplicate district IDs")
        ids = {m.id for m in self.measures}
        if len(ids) != len(self.measures):
            raise ValueError("Duplicate measure IDs")
        for rule in [*self.synergies, *self.conflicts]:
            if not set(rule.measures) <= ids or len(set(rule.measures)) != 2:
                raise ValueError("Invalid measure pair")
        for synergy in self.synergies:
            if synergy.target_measure not in synergy.measures:
                raise ValueError("Synergy target must be a member of its pair")
        return self


class Decision(Contract):
    measure_id: str = Field(min_length=1, max_length=16)
    district_id: str | None = Field(default=None, min_length=1, max_length=32)


class ScenarioRequest(Contract):
    # Domain validation returns a readable decision_count error for incomplete sets.
    decisions: list[Decision] = Field(max_length=14)


class ValidationIssue(Contract):
    code: str
    message: str


class ErrorBody(Contract):
    code: str
    message: str
    issues: list[ValidationIssue]


class ErrorResponse(Contract):
    error: ErrorBody


class DistrictResult(Contract):
    district_id: str
    name: str
    indicators: dict[Metric, Indicator]
    indicator_deltas: dict[Metric, float]
    score: float
    score_delta: float


class CriticalIndicator(Contract):
    district_id: str
    metric: Metric
    value: Indicator


class MeasureEffect(Contract):
    measure_id: str
    cost: int
    realized_fraction: float
    district_ids: list[str]
    effects: dict[Metric, float]


class AppliedSynergy(Contract):
    measures: tuple[str, str]
    district_id: str
    effects: dict[Metric, float]


class SimulationResult(Contract):
    dataset_version: str
    budget: int
    total_cost: int
    remaining_budget: int
    score: float
    baseline_score: float
    score_delta: float
    weighted_average: float
    weakest_district_score: float
    critical_count: int
    critical_indicators: list[CriticalIndicator]
    districts: list[DistrictResult]
    measure_effects: list[MeasureEffect]
    applied_synergies: list[AppliedSynergy]


class Analysis(Contract):
    mode: Literal["mock", "live", "fallback"]
    summary: str
    strengths: list[str]
    risks: list[str]
    recommendations: list[str]
    notice: str
    source: Literal["provider", "cache", "template"] = "template"
    reason: str | None = None


class AINarrative(Contract):
    """Provider-only schema: numeric summary and score never come from the LLM."""

    strengths: list[Annotated[str, Field(min_length=1, max_length=450)]] = Field(min_length=1, max_length=4)
    risks: list[Annotated[str, Field(min_length=1, max_length=450)]] = Field(min_length=1, max_length=4)
    recommendations: list[Annotated[str, Field(min_length=1, max_length=450)]] = Field(min_length=1, max_length=4)


class AnalysisResponse(Contract):
    result: SimulationResult
    analysis: Analysis


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    api_version: Literal["1"] = "1"
    dataset_version: str
    ai_mode: Literal["mock", "live", "fallback"]
