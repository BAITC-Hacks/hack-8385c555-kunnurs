from copy import deepcopy

import pytest

from contracts.schemas import AnalysisResponse, Catalog, ErrorResponse, HealthResponse, SimulationResult

POST_PATHS = ("/api/simulations/evaluate", "/api/simulations/analyze")


def checked(response, schema):
    assert response.status_code == 200
    return schema.model_validate(response.json())


@pytest.mark.parametrize("path,schema", [
    ("/api/health", HealthResponse),
    ("/api/catalog", Catalog),
    ("/api/baseline", SimulationResult),
])
def test_get_contracts(api, path, schema):
    checked(api.get(path), schema)


def test_baseline(api):
    result = checked(api.get("/api/baseline"), SimulationResult)
    assert result.score == pytest.approx(52.55768, abs=1e-6)
    assert (result.total_cost, result.budget, result.remaining_budget) == (0, 100, 100)
    assert result.critical_count == 2
    assert {(value.district_id, value.metric, value.value) for value in result.critical_indicators} == {("nura", "S1", 38), ("nura", "S2", 35)}


@pytest.mark.parametrize("path", POST_PATHS)
def test_pdf_example(api, scenario, path):
    schema = AnalysisResponse if path.endswith("analyze") else SimulationResult
    response = checked(api.post(path, json=scenario), schema)
    result = response.result if isinstance(response, AnalysisResponse) else response
    assert result.score == pytest.approx(56.54307, abs=1e-6)
    assert result.score_delta == pytest.approx(3.98539, abs=1e-6)
    assert (result.total_cost, result.remaining_budget, result.critical_count) == (95, 5, 0)
    nura = next(d for d in result.districts if d.district_id == "nura")
    assert (nura.indicators["S1"], nura.indicators["S2"], nura.indicators["B1"]) == (48, 43.75, 67.5)
    assert len(result.applied_synergies) == 1


INVALID_CASES = [
    ([], "decision_count"),
    ([("M7", "nura")] * 5, "duplicate_measure"),
    ([("M3", "nura"), ("M5", "saryarka"), ("M7", "nura"), ("M10", "nura"), ("M12", None)], "budget_exceeded"),
    ([("M7", "nura"), ("M8", "nura"), ("M9", "nura"), ("M10", "nura"), ("M12", None)], "direction_limit"),
    ([("M1", "nura"), ("M3", "esil"), ("M9", "nura"), ("M10", "nura"), ("M12", None)], "incompatible_measures"),
    ([("M4", "nura"), ("M7", "nura"), ("M8", "nura"), ("M10", "nura"), ("M12", None)], "incompatible_measures"),
    ([("M5", "nura"), ("M13", "nura"), ("M9", "nura"), ("M10", "nura"), ("M12", None)], "incompatible_measures"),
    ([("M99", None)], "unknown_measure"),
    ([("M10", None)], "invalid_district"),
    ([("M10", "unknown")], "invalid_district"),
    ([("M12", "nura")], "city_has_district"),
]


@pytest.mark.parametrize("path", POST_PATHS)
@pytest.mark.parametrize("pairs,code", INVALID_CASES)
def test_invalid_scenarios(api, path, pairs, code):
    payload = {"decisions": [{"measure_id": measure, "district_id": district} for measure, district in pairs]}
    response = api.post(path, json=payload)
    assert response.status_code == 422
    error = ErrorResponse.model_validate(response.json())
    assert error.error.code == "invalid_scenario"
    assert code in {issue.code for issue in error.error.issues}
    assert "score" not in response.json()


def test_exact_budget_and_cross_district_conflict(api, scenario):
    exact = deepcopy(scenario)
    exact["decisions"][-1] = {"measure_id": "M3", "district_id": "nura"}
    result = checked(api.post(POST_PATHS[0], json=exact), SimulationResult)
    assert (result.total_cost, result.remaining_budget) == (100, 0)
    separate = deepcopy(scenario)
    separate["decisions"][-1] = {"measure_id": "M4", "district_id": "esil"}
    checked(api.post(POST_PATHS[0], json=separate), SimulationResult)


def test_repeated_ordered_and_alternate_scenarios(api, scenario):
    baseline = checked(api.get("/api/baseline"), SimulationResult)
    catalog = checked(api.get("/api/catalog"), Catalog)
    first = checked(api.post(POST_PATHS[0], json=scenario), SimulationResult)
    reverse = {"decisions": list(reversed(scenario["decisions"]))}
    assert checked(api.post(POST_PATHS[0], json=reverse), SimulationResult) == first
    alternate = deepcopy(scenario)
    alternate["decisions"][0]["district_id"] = "esil"
    assert checked(api.post(POST_PATHS[0], json=alternate), SimulationResult).score != first.score
    assert checked(api.post(POST_PATHS[0], json=scenario), SimulationResult) == first
    assert checked(api.get("/api/baseline"), SimulationResult) == baseline
    assert checked(api.get("/api/catalog"), Catalog) == catalog


def test_ai_mode_is_explicit_and_does_not_change_score(api, scenario, request):
    health = checked(api.get("/api/health"), HealthResponse)
    evaluation = checked(api.post(POST_PATHS[0], json=scenario), SimulationResult)
    analysis = checked(api.post(POST_PATHS[1], json=scenario), AnalysisResponse)
    assert analysis.result == evaluation
    assert analysis.analysis.mode == health.ai_mode
    assert analysis.analysis.notice.strip()
    expected = request.config.getoption("--expected-ai-mode")
    if expected:
        assert analysis.analysis.mode == expected
