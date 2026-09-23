import json

import pytest

from ai.agent import explain_scenario
from ai.evidence import build_evidence, composition
from backend.app.seed import ROOT, get_catalog
from backend.app.services.advice import find_alternatives, improving_replacements
from backend.app.services.simulation import InvalidScenario, evaluate, leave_one_out, _calculate
from contracts.schemas import Decision, ScenarioRequest


@pytest.fixture
def source():
    request = ScenarioRequest.model_validate_json((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8"))
    return request, get_catalog()


def test_all_recommendations_are_valid_single_replacements(source):
    request, catalog = source
    before = request.model_dump(), catalog.model_dump()
    current = evaluate(request, catalog)
    alternatives = find_alternatives(request, catalog)
    assert 1 <= len(alternatives) <= 3
    assert len({item.id for item in alternatives}) == len(alternatives)
    assert {objective for item in alternatives for objective in item.objectives} == {"best_score", "lowest_cost", "most_critical"}
    for alternative in alternatives:
        recalculated = evaluate(alternative.scenario, catalog)
        assert alternative.score == recalculated.score
        assert alternative.score_gain == pytest.approx(recalculated.score - current.score)
        assert alternative.score_gain > 0
        assert alternative.total_cost == recalculated.total_cost <= 100
        assert alternative.remaining_budget == recalculated.remaining_budget
        assert alternative.critical_count == recalculated.critical_count
        original = {(d.measure_id, d.district_id) for d in request.decisions}
        changed = {(d.measure_id, d.district_id) for d in alternative.scenario.decisions}
        assert original - changed == {(alternative.removed.measure_id, alternative.removed.district_id)}
        assert changed - original == {(alternative.added.measure_id, alternative.added.district_id)}
    assert (request.model_dump(), catalog.model_dump()) == before


def test_known_alternative_includes_lost_ecology_benefit(source):
    request, catalog = source
    best = find_alternatives(request, catalog)[0]
    assert best.removed.measure_id == "M5"
    assert best.added.measure_id == "M3" and best.added.district_id == "nura"
    assert best.total_cost == 100
    assert best.score == pytest.approx(57.20556)
    assert any("качество воздуха -8.75" in text for text in best.tradeoffs)
    assert any("надёжность ЖКХ -2.50" in text for text in best.tradeoffs)


def test_recommendations_do_not_depend_on_request_order(source):
    request, catalog = source
    reversed_request = ScenarioRequest(decisions=list(reversed(request.decisions)))
    assert find_alternatives(request, catalog) == find_alternatives(reversed_request, catalog)


def test_no_local_improvement_is_not_a_claim_of_global_optimum(source):
    request, catalog = source
    for measure in catalog.measures:
        measure.effects = {}
    catalog.synergies = []
    alternatives = find_alternatives(request, catalog)
    assert alternatives == []
    explanation = explain_scenario(evaluate(request, catalog), catalog, alternatives=alternatives)
    assert "не доказывает глобальный оптимум" in explanation.recommendations[0]


def test_invalid_scenario_is_not_optimized(source):
    _, catalog = source
    with pytest.raises(InvalidScenario):
        find_alternatives(ScenarioRequest(decisions=[]), catalog)


def test_direction_counts_are_separate_from_lag_counts(source):
    request, catalog = source
    result = evaluate(request, catalog)
    assert "соцсфера — 2" in composition(result, catalog)
    assert "экология — 1" in composition(result, catalog)
    evidence = build_evidence(result, catalog)
    lag = evidence.risks["lag_3"]
    assert "у 3 мер" in lag
    assert lag.count("(соцсфера)") == 2
    assert lag.count("(экология)") == 1
    assert "62.5%" in lag


def test_fallback_still_provides_computed_alternatives(source):
    request, catalog = source
    result = evaluate(request, catalog)
    alternatives = find_alternatives(request, catalog)
    analysis = explain_scenario(result, catalog, mode="live", alternatives=alternatives)
    assert analysis.mode == "fallback"
    assert "57.21" in analysis.recommendations[0]
    assert "Сарыарка: качество воздуха -8.75" in analysis.recommendations[0]
    assert "не объединяйте" in analysis.recommendations[0]


def test_analysis_example_includes_replayable_alternatives(source):
    _, catalog = source
    example = json.loads((ROOT / "contracts/examples/analysis.json").read_text(encoding="utf-8"))
    for item in example["alternatives"]:
        result = evaluate(ScenarioRequest.model_validate(item["scenario"]), catalog)
        assert result.score == item["score"]


@pytest.fixture
def user_scenario():
    return ScenarioRequest(decisions=[
        Decision(measure_id="M8", district_id="almaty"),
        Decision(measure_id="M9", district_id="esil"),
        Decision(measure_id="M10", district_id="nura"),
        Decision(measure_id="M12"),
        Decision(measure_id="M5", district_id="saryarka"),
    ])


def test_three_objectives_use_all_improving_replacements(user_scenario):
    catalog = get_catalog()
    all_options = improving_replacements(user_scenario, catalog)
    chosen = find_alternatives(user_scenario, catalog)
    by_objective = {key: item for item in chosen for key in item.objectives}
    assert by_objective["best_score"].score == max(a.score for a in all_options)
    assert by_objective["lowest_cost"].total_cost == min(a.total_cost for a in all_options)
    assert by_objective["most_critical"].critical_count == min(a.critical_count for a in all_options)
    assert len(chosen) == len({a.id for a in chosen})
    assert all(a.score_gain > 0 for a in chosen)
    assert by_objective["lowest_cost"].total_cost < by_objective["best_score"].total_cost
    assert by_objective["best_score"].score == pytest.approx(55.30822)
    assert by_objective["best_score"].added == Decision(measure_id="M7", district_id="nura")
    assert by_objective["lowest_cost"].total_cost == 66
    assert by_objective["lowest_cost"].score == pytest.approx(54.156309)


def test_leave_one_out_recomputes_synergies_and_critical_penalties(source):
    request, catalog = source
    result = evaluate(request, catalog)
    contributions = leave_one_out(result, catalog)
    assert len(contributions) == 5
    for contribution in contributions:
        subset = [d for d in request.decisions if d != contribution.decision]
        expected = _calculate(subset, catalog)
        assert contribution.score_without == expected.score
        assert contribution.score_contribution == pytest.approx(result.score - expected.score, abs=1e-6)
        assert contribution.critical_count_without == expected.critical_count
        with pytest.raises(InvalidScenario):
            evaluate(ScenarioRequest(decisions=subset), catalog)
    without_cameras = _calculate([d for d in request.decisions if d.measure_id != "M10"], catalog)
    assert not without_cameras.applied_synergies
    assert next(c for c in contributions if c.decision.measure_id == "M7").critical_count_without == 1
    # Conditional contributions double-count the shared camera/platform synergy.
    assert sum(c.score_contribution for c in contributions) != pytest.approx(result.score_delta)


@pytest.mark.parametrize("mode", ["mock", "live"])
def test_required_risks_and_all_advice_are_present_in_templates(user_scenario, mode):
    catalog = get_catalog()
    result = evaluate(user_scenario, catalog)
    alternatives = find_alternatives(user_scenario, catalog)
    evidence = build_evidence(result, catalog, alternatives)
    answer = explain_scenario(result, catalog, mode=mode, alternatives=alternatives)
    assert result.total_cost == 81 and result.critical_count == 2
    assert {"critical_nura_S1", "critical_nura_S2", "unused_budget", "allocation_M8", "allocation_M9", "allocation_M5"} <= set(evidence.mandatory_risk_ids)
    assert all(evidence.risks[key] in answer.risks for key in evidence.mandatory_risk_ids)
    assert len(answer.risks) == len(set(answer.risks))
    assert len(answer.recommendations) == len(alternatives)
    assert all("leave-one-out" in text for text in answer.strengths)
    assert all("результат всего набора мер" not in text for text in answer.strengths)
    assert "allocation_M10" not in evidence.risks  # target had initial critical values
    assert "allocation_M12" not in evidence.risks  # citywide measure


@pytest.mark.parametrize("remaining,expected", [(10, False), (11, True), (0, False)])
def test_budget_risk_boundary(source, remaining, expected):
    request, catalog = source
    result = evaluate(request, catalog).model_copy(update={"remaining_budget": remaining})
    assert ("unused_budget" in build_evidence(result, catalog).mandatory_risk_ids) is expected


def test_critical_threshold_and_healthy_target_definition(source, user_scenario):
    _, catalog = source
    # A value exactly 40 is not critical. Other risks must not invent S1.
    next(d for d in catalog.districts if d.id == "nura").indicators["S1"] = 40
    result = evaluate(user_scenario, catalog)
    evidence = build_evidence(result, catalog)
    assert "critical_nura_S1" not in evidence.mandatory_risk_ids
    assert "critical_nura_S2" in evidence.mandatory_risk_ids
    # A district where this scenario resolves a critical value was not healthy initially.
    school = ScenarioRequest(decisions=[Decision(measure_id="M7", district_id="nura"), *user_scenario.decisions[1:]])
    assert "allocation_M7" not in build_evidence(evaluate(school, catalog), catalog).mandatory_risk_ids


def test_negative_marginal_effect_is_not_a_strength(source):
    request, catalog = source
    next(m for m in catalog.measures if m.id == "M7").effects = {"S1": -10}
    result = evaluate(request, catalog)
    evidence = build_evidence(result, catalog)
    assert "contribution_M7" not in evidence.strengths
    assert "negative_M7" in evidence.mandatory_risk_ids


def test_all_critical_risks_are_returned_even_above_model_selection_limit(source):
    request, catalog = source
    for district in catalog.districts:
        district.indicators = {metric: 10 for metric in district.indicators}
    result = evaluate(request, catalog)
    answer = explain_scenario(result, catalog, mode="mock")
    assert result.critical_count == 50
    assert len([text for text in answer.risks if "штраф 1 балл" in text]) == 50
