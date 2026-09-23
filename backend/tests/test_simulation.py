import itertools

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.seed import ROOT, get_catalog, load_catalog
from backend.app.services.simulation import InvalidScenario, baseline, evaluate
from contracts.schemas import Decision, ScenarioRequest


@pytest.fixture
def catalog():
    return get_catalog()


@pytest.fixture
def scenario():
    return ScenarioRequest.model_validate_json((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8"))


def make_request(*pairs):
    return ScenarioRequest(decisions=[Decision(measure_id=measure, district_id=district) for measure, district in pairs])


def test_official_baseline(catalog):
    result = baseline(catalog)
    assert [d.score for d in result.districts] == pytest.approx([62.99, 57.06, 54.65, 56.63, 49.18])
    assert result.weighted_average == pytest.approx(56.8624)
    assert result.critical_count == 2
    assert result.score == pytest.approx(52.55768)


def test_official_example(catalog, scenario):
    result = evaluate(scenario, catalog)
    assert (result.total_cost, result.remaining_budget) == (95, 5)
    assert result.score == pytest.approx(56.54307)
    assert result.score_delta == pytest.approx(3.98539)
    assert result.critical_count == 0
    nura = next(d for d in result.districts if d.district_id == "nura")
    assert nura.indicators["S1"] == 48
    assert nura.indicators["S2"] == 43.75
    assert nura.indicators["B1"] == 67.5  # 55 + 12 * 7/8 + 2 (unscaled synergy)
    assert nura.indicators["C2"] == 54.375
    assert len(result.applied_synergies) == 1


@pytest.mark.parametrize("pairs,code", [
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
])
def test_invalid_scenarios_have_no_score(catalog, pairs, code):
    with pytest.raises(InvalidScenario) as caught:
        evaluate(make_request(*pairs), catalog)
    assert code in {issue.code for issue in caught.value.issues}


def test_exact_budget_is_valid(catalog):
    result = evaluate(make_request(("M3", "nura"), ("M7", "nura"), ("M8", "nura"), ("M10", "nura"), ("M12", None)), catalog)
    assert result.total_cost == 100
    assert result.remaining_budget == 0


def test_district_conflicts_do_not_cross_districts(catalog):
    result = evaluate(make_request(("M4", "esil"), ("M7", "nura"), ("M8", "nura"), ("M10", "nura"), ("M12", None)), catalog)
    assert result.total_cost == 85


def test_cheapest_example_and_negative_effect(catalog):
    result = evaluate(make_request(("M9", "nura"), ("M11", "almaty"), ("M10", "nura"), ("M12", None), ("M4", "saryarka")), catalog)
    assert result.total_cost == 61
    almaty = next(d for d in result.districts if d.district_id == "almaty")
    assert almaty.indicators["T1"] == 38.25
    assert almaty.indicator_deltas["T1"] == -1.75
    assert any(item.district_id == "almaty" and item.metric == "T1" for item in result.critical_indicators)


def test_order_independence_and_no_state_leaks(catalog, scenario):
    snapshot = catalog.model_dump()
    expected = evaluate(scenario, catalog)
    for permutation in itertools.permutations(scenario.decisions):
        assert evaluate(ScenarioRequest(decisions=list(permutation)), catalog) == expected
    assert catalog.model_dump() == snapshot
    alternate = scenario.model_copy(deep=True)
    alternate.decisions[0].district_id = "esil"
    assert evaluate(alternate, catalog).score != expected.score
    assert evaluate(scenario, catalog) == expected


def test_threshold_is_strictly_below_40(catalog):
    catalog.districts[-1].indicators["S2"] = 40
    assert baseline(catalog).critical_count == 1


def test_clamp_after_all_effects_and_synergy(catalog):
    catalog.districts[-1].indicators["T1"] = 99
    result = evaluate(make_request(("M1", "nura"), ("M2", None), ("M11", "nura"), ("M9", "nura"), ("M12", None)), catalog)
    nura = next(d for d in result.districts if d.district_id == "nura")
    assert nura.indicators["T1"] == 100
    catalog.districts[-1].indicators["T1"] = 0
    negative = evaluate(make_request(("M4", "saryarka"), ("M11", "nura"), ("M10", "nura"), ("M9", "nura"), ("M12", None)), catalog)
    assert negative.districts[-1].indicators["T1"] == 0


def test_ecology_synergy_and_city_scope(catalog):
    result = evaluate(make_request(("M5", "saryarka"), ("M6", None), ("M9", "nura"), ("M10", "nura"), ("M12", None)), catalog)
    saryarka = next(d for d in result.districts if d.district_id == "saryarka")
    assert saryarka.indicators["E2"] == 40 + 14 * 5 / 8 + 3 * 4 / 8 + 2
    assert all(d.indicator_deltas["E1"] == 2.5 for d in result.districts)


def test_seed_fallback(catalog):
    missing = ROOT / "data" / "missing-test-catalog.json"
    assert not missing.exists()
    assert load_catalog(missing) == catalog


client = TestClient(app)


@pytest.mark.parametrize("path", ["/api/health", "/api/catalog", "/api/baseline"])
def test_read_endpoints(path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/api/simulations/evaluate", "/api/simulations/analyze"])
def test_scenario_endpoints(path, scenario):
    response = client.post(path, json=scenario.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert (data.get("result") or data)["score"] == pytest.approx(56.54307)
    invalid = client.post(path, json={"decisions": []})
    assert invalid.status_code == 422
    assert "score" not in invalid.json()
    assert invalid.json()["error"]["issues"][0]["code"] == "decision_count"


def test_client_cannot_override_cost_or_score(scenario):
    payload = scenario.model_dump()
    payload["score"] = 100
    response = client.post("/api/simulations/evaluate", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_invalid_json_and_private_input_not_echoed():
    response = client.post("/api/simulations/analyze", content='{"private": "person@example.com",', headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "person@example.com" not in response.text


def test_mock_and_live_fallback_are_explicit(catalog, scenario):
    from ai.agent import explain_scenario

    result = evaluate(scenario, catalog)
    assert explain_scenario(result, catalog).mode == "mock"
    assert explain_scenario(result, catalog, mode="live").mode == "fallback"


def test_cors_only_allows_configured_origins():
    allowed = client.options("/api/simulations/evaluate", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    forbidden = client.options("/api/simulations/evaluate", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in forbidden.headers
