import hashlib

from ai import agent, cache
from ai.evidence import build_evidence
from ai.prompts import PROMPT_VERSION
from backend.app.seed import get_catalog
from backend.app.services.simulation import evaluate
from contracts.schemas import AISelection
from scripts.demo_scenarios import DEMO_SCENARIOS


def test_persistent_cache_survives_memory_clear_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_DEMO_CACHE_PATH", str(tmp_path / "demo.json"))
    catalog = get_catalog()
    result = evaluate(DEMO_SCENARIOS["pdf"], catalog)
    evidence = build_evidence(result, catalog)
    payload = agent._payload(result, catalog, evidence)
    key = hashlib.sha256(f"{PROMPT_VERSION}\nunit-test-model\n{payload}".encode()).hexdigest()
    selection = AISelection(strength_ids=list(evidence.strengths)[:2], risk_ids=list(evidence.risks)[:2], recommendation_ids=list(evidence.recommendations)[:1])
    cache.put(key, selection)
    cache.export_demo([key])
    cache._entries.clear()
    monkeypatch.setattr(agent, "AsyncOpenAI", lambda **kw: (_ for _ in ()).throw(AssertionError("No provider call")))
    answer = agent.explain_scenario(result, catalog, mode="live")
    assert (answer.mode, answer.source) == ("live", "cache")
    monkeypatch.setenv("OPENAI_MODEL", "changed-model")
    assert agent.explain_scenario(result, catalog, mode="live").reason == "missing_api_key"


def test_corrupt_cache_is_safe(monkeypatch, tmp_path):
    path = tmp_path / "cache.json"
    monkeypatch.setenv("AI_DEMO_CACHE_PATH", str(path))
    for content in ("broken", "[]", '{"version":1,"entries":{"x":{"strength_ids":[]}}}'):
        path.write_text(content, encoding="utf-8")
        assert cache.get("x") is None


def test_model_is_only_from_environment(monkeypatch):
    from ai.settings import AISettings
    from pydantic import ValidationError
    import pytest
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(ValidationError):
        AISettings.from_env()
