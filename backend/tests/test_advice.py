import json

import pytest

from ai.agent import explain_scenario
from ai.evidence import build_evidence, composition
from backend.app.seed import ROOT, get_catalog
from backend.app.services.advice import find_alternatives
from backend.app.services.simulation import InvalidScenario, evaluate
from contracts.schemas import ScenarioRequest


@pytest.fixture
def source():
    request = ScenarioRequest.model_validate_json((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8"))
    return request, get_catalog()


def test_all_recommendations_are_valid_single_replacements(source):
    request, catalog = source
    before = request.model_dump(), catalog.model_dump()
    current = evaluate(request, catalog)
    alternatives = find_alternatives(request, catalog)
    assert len(alternatives) == 3
    assert len({item.id for item in alternatives}) == 3
    assert [item.score for item in alternatives] == sorted([item.score for item in alternatives], reverse=True)
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
