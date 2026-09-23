"""The official dataset formula. No network, database or LLM calls."""

from collections import Counter
from math import fsum

from contracts.schemas import (
    AppliedSynergy, Catalog, CriticalIndicator, Decision, DistrictResult,
    MeasureEffect, ScenarioRequest, SimulationResult, ValidationIssue,
)


class InvalidScenario(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("Invalid scenario")


def validate_scenario(request: ScenarioRequest, catalog: Catalog) -> list[ValidationIssue]:
    issues = []

    def reject(code: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, message=message))

    if len(request.decisions) != catalog.rules.decision_count:
        reject("decision_count", "Нужно выбрать ровно 5 мероприятий.")
    measures = {m.id: m for m in catalog.measures}
    districts = {d.id for d in catalog.districts}
    counts = Counter(d.measure_id for d in request.decisions)
    if any(count > 1 for count in counts.values()):
        reject("duplicate_measure", "Каждое мероприятие можно выбрать только один раз.")
    directions: Counter = Counter()
    total_cost = 0
    for decision in request.decisions:
        measure = measures.get(decision.measure_id)
        if measure is None:
            reject("unknown_measure", "Выбрано неизвестное мероприятие.")
            continue
        total_cost += measure.cost
        directions[measure.direction] += 1
        if measure.scope == "city" and decision.district_id is not None:
            reject("city_has_district", f"Для {measure.id} район не указывается.")
        if measure.scope == "district" and decision.district_id not in districts:
            reject("invalid_district", f"Для {measure.id} нужно выбрать существующий район.")
    if total_cost > catalog.rules.budget:
        reject("budget_exceeded", f"Стоимость {total_cost} превышает бюджет {catalog.rules.budget}.")
    if any(count > catalog.rules.max_per_direction for count in directions.values()):
        reject("direction_limit", "Можно выбрать не более 2 мер одного направления.")
    selected = {d.measure_id: d for d in request.decisions}
    for conflict in catalog.conflicts:
        first, second = conflict.measures
        if first in selected and second in selected:
            same_district = selected[first].district_id == selected[second].district_id
            if conflict.scope == "anywhere" or same_district:
                reject("incompatible_measures", conflict.reason)
    return issues


def _calculate(decisions: list[Decision], catalog: Catalog) -> SimulationResult:
    measures = {m.id: m for m in catalog.measures}
    indicators = {d.id: dict(d.indicators) for d in catalog.districts}
    effects = []
    total_cost = 0
    # Canonical order makes the entire response independent of selection order.
    for decision in sorted(decisions, key=lambda d: d.measure_id):
        measure = measures[decision.measure_id]
        total_cost += measure.cost
        fraction = (catalog.rules.horizon_quarters - measure.lag_quarters) / catalog.rules.horizon_quarters
        targets = list(indicators) if measure.scope == "city" else [decision.district_id]
        realized = {key: value * fraction for key, value in measure.effects.items()}
        for district_id in targets:
            for metric, delta in realized.items():
                indicators[district_id][metric] += delta
        effects.append(MeasureEffect(
            measure_id=measure.id, cost=measure.cost, realized_fraction=fraction,
            district_ids=targets, effects=realized,
        ))
    selected = {d.measure_id: d for d in decisions}
    applied_synergies = []
    for synergy in catalog.synergies:
        if all(measure_id in selected for measure_id in synergy.measures):
            district_id = selected[synergy.target_measure].district_id
            for metric, delta in synergy.effects.items():
                indicators[district_id][metric] += delta
            applied_synergies.append(AppliedSynergy(
                measures=synergy.measures, district_id=district_id, effects=synergy.effects,
            ))
    # Clip only after ALL effects and synergies, not after each decision.
    indicators = {
        district_id: {metric: min(100.0, max(0.0, value)) for metric, value in values.items()}
        for district_id, values in indicators.items()
    }
    scores = {
        district_id: fsum(catalog.weights[k] * v for k, v in values.items())
        for district_id, values in indicators.items()
    }
    baseline_scores = {
        d.id: fsum(catalog.weights[k] * v for k, v in d.indicators.items())
        for d in catalog.districts
    }
    critical = [
        CriticalIndicator(district_id=district_id, metric=metric, value=value)
        for district_id, values in indicators.items() for metric, value in values.items()
        if value < catalog.rules.critical_threshold
    ]
    average = fsum(d.population_share * scores[d.id] for d in catalog.districts)
    baseline_average = fsum(d.population_share * baseline_scores[d.id] for d in catalog.districts)
    baseline_critical = sum(
        value < catalog.rules.critical_threshold for d in catalog.districts for value in d.indicators.values()
    )
    score = catalog.rules.average_weight * average + catalog.rules.weakest_weight * min(scores.values()) - catalog.rules.critical_penalty * len(critical)
    baseline = catalog.rules.average_weight * baseline_average + catalog.rules.weakest_weight * min(baseline_scores.values()) - catalog.rules.critical_penalty * baseline_critical
    return SimulationResult(
        dataset_version=catalog.version, budget=catalog.rules.budget, total_cost=total_cost,
        remaining_budget=catalog.rules.budget - total_cost,
        score=round(score, 6), baseline_score=round(baseline, 6), score_delta=round(score - baseline, 6),
        weighted_average=round(average, 6), weakest_district_score=round(min(scores.values()), 6),
        critical_count=len(critical), critical_indicators=critical,
        districts=[DistrictResult(
            district_id=d.id, name=d.name, indicators=indicators[d.id],
            indicator_deltas={k: round(indicators[d.id][k] - v, 6) for k, v in d.indicators.items()},
            score=round(scores[d.id], 6), score_delta=round(scores[d.id] - baseline_scores[d.id], 6),
        ) for d in catalog.districts],
        measure_effects=effects, applied_synergies=applied_synergies,
    )


def baseline(catalog: Catalog) -> SimulationResult:
    """A reference state; empty decisions are not a valid submitted scenario."""
    return _calculate([], catalog)


def evaluate(request: ScenarioRequest, catalog: Catalog) -> SimulationResult:
    issues = validate_scenario(request, catalog)
    if issues:
        raise InvalidScenario(issues)
    return _calculate(request.decisions, catalog)
