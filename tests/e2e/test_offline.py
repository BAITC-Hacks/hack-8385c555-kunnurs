"""Finite local checks for OPS artifacts; no network listeners."""

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from contracts.schemas import Catalog, ScenarioRequest

ROOT = Path(__file__).resolve().parents[2]


def test_dataset_matches_contract_fixture():
    source = Catalog.model_validate_json((ROOT / "data/city.json").read_text(encoding="utf-8"))
    fixture = Catalog.model_validate_json((ROOT / "contracts/examples/catalog.json").read_text(encoding="utf-8"))
    assert source == fixture


def test_generated_scenarios_are_repeatable_and_accepted():
    from backend.app.main import app

    spec = importlib.util.spec_from_file_location("ops_generator", ROOT / "data/generate.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generated = generator.generate()
    assert generated == generator.generate()
    assert generated != generator.generate(seed=8386)
    assert len(generated) == 5
    committed = sorted((ROOT / "data/generated").glob("seed-8385-*.json"))
    assert [json.loads(path.read_text(encoding="utf-8")) for path in committed] == generated
    with TestClient(app) as client:
        for scenario in generated:
            ScenarioRequest.model_validate(scenario)
            assert client.post("/api/simulations/evaluate", json=scenario).status_code == 200


def test_committed_demo_scenarios():
    from backend.app.main import app

    scores = []
    with TestClient(app) as client:
        for name in ("pdf-example", "school-in-esil"):
            payload = json.loads((ROOT / f"data/scenarios/{name}.json").read_text(encoding="utf-8"))
            ScenarioRequest.model_validate(payload)
            response = client.post("/api/simulations/evaluate", json=payload)
            assert response.status_code == 200
            scores.append(response.json()["score"])
    assert scores[0] == pytest.approx(56.54307, abs=1e-6)
    assert scores[1] == pytest.approx(55.29777, abs=1e-6)


def test_deployment_serves_assets_api_and_no_private_files(tmp_path):
    from deploy.app import create_app

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text('<html><div id="root"></div></html>', encoding="utf-8")
    (tmp_path / "assets/app.js").write_text("console.log('fixture');", encoding="utf-8")
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "immutable" in asset.headers["cache-control"]
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["cache-control"] == "no-store"
        assert "/api/simulations/evaluate" in client.get("/openapi.json").json()["paths"]
        assert client.get("/docs").status_code == 200
        for path in ("/.env", "/.git/config", "/requirements.txt", "/assets/%2e%2e/requirements.txt", "/api/missing", "/assets/missing.js"):
            assert client.get(path).status_code == 404


def test_deployment_requires_built_frontend(tmp_path):
    from deploy.app import create_app

    with pytest.raises(RuntimeError, match="Build the frontend"):
        create_app(tmp_path)
