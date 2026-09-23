"""HTTP contract checks; remote by default, explicit in-process mode for CI."""

from copy import deepcopy
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


def pytest_addoption(parser):
    parser.addoption("--in-process", action="store_true", help="Use FastAPI TestClient; no listening server")
    parser.addoption("--expected-ai-mode", choices=("mock", "live", "fallback"))
    parser.addoption("--require-api", action="store_true", help="Fail instead of skip if the remote API is unavailable")


@pytest.fixture(scope="session")
def api(request):
    if request.config.getoption("--in-process"):
        from fastapi.testclient import TestClient
        import backend.app.main as main

        expected = request.config.getoption("--expected-ai-mode") or "mock"
        if expected == "live":
            pytest.fail("Use remote API_URL for live checks; in-process checks never use credentials")
        mode = "mock" if expected == "mock" else "live"
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("OPENAI_API_KEY", "")
            patch.setenv("OPENAI_MODEL", "unit-test-model")
            patch.setenv("AI_TIMEOUT_SECONDS", "12")
            patch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "12")
            patch.setenv("AI_CACHE_ENABLED", "false")
            patch.setattr(main, "AI_MODE", mode)
            with TestClient(main.app, raise_server_exceptions=False) as client:
                yield client
        return
    url = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path or parts.query or parts.fragment or parts.username or parts.password:
        pytest.fail("API_URL must be an HTTP(S) origin without credentials, path, query or fragment")
    with httpx.Client(base_url=url, timeout=20, follow_redirects=False, trust_env=False) as client:
        try:
            response = client.get("/api/health")
        except (httpx.ConnectError, httpx.TimeoutException):
            if request.config.getoption("--require-api"):
                pytest.fail("API unavailable; release checks require a reachable API")
            pytest.skip("API unavailable: start the server separately and set API_URL")
        assert response.status_code == 200, "API is reachable but health check failed"
        yield client


@pytest.fixture
def scenario():
    return deepcopy(json.loads((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8")))
