"""The five acceptance criteria from the task PDF, plus exact release numbers."""
import pytest
from fastapi.testclient import TestClient
from backend.app import main
from backend.app.seed import get_catalog
from backend.app.services.simulation import baseline, evaluate
from scripts.demo_scenarios import DEMO_SCENARIOS, scenario


def test_criterion_1():
    c = get_catalog()
    before = c.model_dump()
    first = baseline(c)
    evaluate(DEMO_SCENARIOS["pdf"], c)
    assert baseline(c) == first
    assert c.model_dump() == before
    assert first.budget == 100 and first.score == pytest.approx(52.55768, abs=0.000001)


def test_criterion_2():
    q = scenario(("M1", "nura"), ("M5", "saryarka"), ("M7", "nura"), ("M8", "nura"), ("M12", None))
    with TestClient(main.app) as client:
        response = client.post("/api/simulations/evaluate", json=q.model_dump())
    assert response.status_code == 422
    assert "budget_exceeded" in response.text and '"score"' not in response.text


def test_criterion_3():
    r = evaluate(DEMO_SCENARIOS["pdf"], get_catalog())
    nura = next(d for d in r.districts if d.district_id == "nura")
    assert nura.indicators["S1"] == 48
    assert nura.indicators["S2"] == 43.75
    assert nura.indicators["B1"] == 67.5


def test_criterion_4(monkeypatch):
    monkeypatch.setattr(main, "AI_MODE", "live")
    with TestClient(main.app) as client:
        data = client.post("/api/simulations/analyze", json=DEMO_SCENARIOS["all_esil"].model_dump()).json()
    analysis = data["analysis"]
    assert all(analysis[key] for key in ["strengths", "risks", "recommendations", "notice"])
    for critical in data["result"]["critical_indicators"]:
        assert any(critical["metric"] in text for text in analysis["risks"])
    assert analysis["source"] == "template" and analysis["reason"] == "missing_api_key"
    assert "contributions" in data and data["alternatives"]


def test_criterion_5():
    q = DEMO_SCENARIOS["pdf"].model_copy(deep=True)
    q.decisions[0].district_id = "esil"
    r = evaluate(q, get_catalog())
    assert r.score == pytest.approx(55.29777, abs=0.000001)
    assert r.critical_count == 1
    assert r.score != evaluate(DEMO_SCENARIOS["pdf"], get_catalog()).score


@pytest.mark.parametrize("name,score,critical", [("pdf", 56.54307, 0), ("all_esil", 53.856547, 2), ("best_known", 57.236735, 0)])
def test_release_reference_numbers(name, score, critical):
    result = evaluate(DEMO_SCENARIOS[name], get_catalog())
    assert result.score == pytest.approx(score, abs=0.000001)
    assert result.critical_count == critical
