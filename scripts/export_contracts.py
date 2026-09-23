"""Regenerate deterministic contract examples after an intentional API change."""

import json
from pathlib import Path

from ai.agent import explain_scenario
from backend.app.seed import get_catalog
from backend.app.services.simulation import InvalidScenario, baseline, evaluate, leave_one_out
from backend.app.services.advice import find_alternatives
from contracts.schemas import AnalysisResponse, ErrorBody, ErrorResponse, HealthResponse, ScenarioRequest

ROOT = Path(__file__).resolve().parents[1]


def example_models() -> dict:
    catalog = get_catalog()
    request = ScenarioRequest.model_validate_json((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8"))
    result = evaluate(request, catalog)
    alternatives = find_alternatives(request, catalog)
    try:
        evaluate(ScenarioRequest(decisions=[]), catalog)
    except InvalidScenario as exc:
        error = ErrorResponse(error=ErrorBody(code="invalid_scenario", message="Набор решений не прошёл проверку.", issues=exc.issues))
    return {
        "health.json": HealthResponse(dataset_version=catalog.version, ai_mode="mock"),
        "catalog.json": catalog,
        "baseline.json": baseline(catalog),
        "evaluation.json": result,
        "analysis.json": AnalysisResponse(result=result, alternatives=alternatives, contributions=leave_one_out(result, catalog), analysis=explain_scenario(result, catalog, alternatives=alternatives)),
        "error.json": error,
    }


if __name__ == "__main__":
    for filename, model in example_models().items():
        (ROOT / "contracts/examples" / filename).write_text(
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print("Contract examples exported")
