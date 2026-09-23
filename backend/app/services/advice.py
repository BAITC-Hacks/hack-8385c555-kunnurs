"""Evaluate every one-slot replacement, then offer a few verified improvements."""

from contracts.schemas import Catalog, Decision, ScenarioAlternative, ScenarioRequest
from backend.app.services.simulation import InvalidScenario, evaluate

METRIC_NAMES = {
    "T1": "разгрузка дорог", "T2": "доступность транспорта", "E1": "озеленение", "E2": "качество воздуха",
    "S1": "школы и детсады", "S2": "поликлиники", "B1": "безопасность улиц", "B2": "дорожная безопасность",
    "C1": "надёжность ЖКХ", "C2": "обращения жителей",
}


def improving_replacements(request: ScenarioRequest, catalog: Catalog) -> list[ScenarioAlternative]:
    """All valid Score-improving replacements, with deterministic tie breaking."""
    current = evaluate(request, catalog)
    before = {d.district_id: d for d in current.districts}
    choices = [
        Decision(measure_id=measure.id, district_id=district_id)
        for measure in sorted(catalog.measures, key=lambda m: m.id)
        for district_id in ([None] if measure.scope == "city" else sorted(d.id for d in catalog.districts))
    ]
    improvements = []
    canonical = sorted(request.decisions, key=lambda d: d.measure_id)
    for index, removed in enumerate(canonical):
        for added in choices:
            if added == removed:
                continue
            candidate = ScenarioRequest(decisions=[added if i == index else d for i, d in enumerate(canonical)])
            try:
                result = evaluate(candidate, catalog)
            except InvalidScenario:
                continue
            gain = round(result.score - current.score, 6)
            if gain <= 0:
                continue
            losses = [
                (round(value - before[d.district_id].indicators[metric], 6), f"{d.name}: {METRIC_NAMES[metric]}")
                for d in result.districts for metric, value in d.indicators.items()
                if value < before[d.district_id].indicators[metric]
            ]
            losses.sort(key=lambda item: (item[0], item[1]))
            tradeoffs = [f"{label} {delta:+.2f}" for delta, label in losses]
            improvements.append(ScenarioAlternative(
                id=f"replace_{removed.measure_id}_{removed.district_id or 'city'}_with_{added.measure_id}_{added.district_id or 'city'}",
                removed=removed.model_copy(), added=added.model_copy(), scenario=candidate,
                score=result.score, score_gain=gain, total_cost=result.total_cost,
                remaining_budget=result.remaining_budget, critical_count=result.critical_count, tradeoffs=tradeoffs,
            ))
    improvements.sort(key=lambda item: (-item.score_gain, item.total_cost, item.id))
    return improvements


def find_alternatives(request: ScenarioRequest, catalog: Catalog) -> list[ScenarioAlternative]:
    improvements = improving_replacements(request, catalog)
    if not improvements:
        return []
    winners = [
        ("best_score", improvements[0]),
        ("lowest_cost", min(improvements, key=lambda a: (a.total_cost, -a.score_gain, a.id))),
        ("most_critical", min(improvements, key=lambda a: (a.critical_count, -a.score_gain, a.total_cost, a.id))),
    ]
    selected = {}
    for objective, winner in winners:
        if winner.id not in selected:
            selected[winner.id] = winner.model_copy(deep=True)
        selected[winner.id].objectives.append(objective)
    return list(selected.values())
