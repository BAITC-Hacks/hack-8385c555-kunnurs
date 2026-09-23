"""Never use a developer's credentials or network during automated tests."""

import pytest

from ai import cache


@pytest.fixture(autouse=True)
def isolated_ai_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "unit-test-model")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("AI_CACHE_ENABLED", "true")
    with cache._lock:
        cache._entries.clear()
    yield
    with cache._lock:
        cache._entries.clear()
