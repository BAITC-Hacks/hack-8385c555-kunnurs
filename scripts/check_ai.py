"""One-shot live smoke test using the PDF example. Never prints credentials."""

import json
import sys

from ai.agent import explain_scenario
from backend.app.main import AI_MODE
from backend.app.seed import ROOT, get_catalog
from backend.app.services.simulation import evaluate
from backend.app.services.advice import find_alternatives
from contracts.schemas import ScenarioRequest


def main() -> int:
    catalog = get_catalog()
    scenario = ScenarioRequest.model_validate_json((ROOT / "contracts/examples/scenario.json").read_text(encoding="utf-8"))
    result = evaluate(scenario, catalog)
    analysis = explain_scenario(result, catalog, mode=AI_MODE, alternatives=find_alternatives(scenario, catalog))
    print(json.dumps({"mode": analysis.mode, "source": analysis.source, "reason": analysis.reason, "score": result.score}, ensure_ascii=True))
    if "--show-analysis" in sys.argv:
        print(analysis.model_dump_json(indent=2))
    return 0 if analysis.mode == "live" else 1


if __name__ == "__main__":
    raise SystemExit(main())
