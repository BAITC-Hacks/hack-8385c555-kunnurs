import json

from pydantic import TypeAdapter

from backend.app.main import app
from backend.app.seed import ROOT
from scripts.export_contracts import example_models


def test_examples_are_current_and_validate():
    for filename, model in example_models().items():
        content = json.loads((ROOT / "contracts/examples" / filename).read_text(encoding="utf-8"))
        parsed = TypeAdapter(type(model)).validate_python(content)
        assert parsed == model, f"Stale contract example: {filename}"


def test_openapi_publishes_all_endpoints_and_errors():
    schema = app.openapi()
    assert set(schema["paths"]) == {"/api/health", "/api/catalog", "/api/baseline", "/api/simulations/evaluate", "/api/simulations/analyze"}
    for path in ("/api/simulations/evaluate", "/api/simulations/analyze"):
        ref = schema["paths"][path]["post"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse")
