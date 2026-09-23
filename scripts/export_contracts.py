"""Regenerate deterministic contract examples after an intentional API change."""

import json
from pathlib import Path

from ai.agent import explain_scenario
from backend.app.seed import get_catalog
from backend.app.services.simulation import InvalidScenario, baseline, evaluate
from contracts.schemas import AnalysisResponse, ErrorBody, ErrorResponse, HealthResponse, ScenarioRequest

ROOT = Path(__file__).resolve().parents[1]


def example_models() -> dict:
    catalog = get_catalog()
    request = ScenarioRequest.model_validate_json((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8"))
    result = evaluate(request, catalog)
    try:
        evaluate(ScenarioRequest(decisions=[]), catalog)
    except InvalidScenario as exc:
        error = ErrorResponse(error=ErrorBody(code="invalid_scenario", message="Набор решений не прошёл проверку.", issues=exc.issues))
    return {
        "health.json": HealthResponse(dataset_version=catalog.version, ai_mode="mock"),
        "catalog.json": catalog,
        "baseline.json": baseline(catalog),
        "evaluation.json": result,
        "analysis.json": AnalysisResponse(result=result, analysis=explain_scenario(result, catalog)),
        "error.json": error,
    }


if __name__ == "__main__":
    for filename, model in example_models().items():
        (ROOT / "contracts/examples" / filename).write_text(
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print("Contract examples exported")
