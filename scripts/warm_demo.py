"""One command: python -m scripts.warm_demo. Up to three paid AI calls."""

import hashlib
import json
from time import perf_counter

from backend.app.main import AI_MODE  # Loads the local .env without exposing it.
from backend.app.seed import get_catalog
from backend.app.services.advice import find_alternatives
from backend.app.services.simulation import evaluate, leave_one_out
from ai import agent, cache
from ai.evidence import build_evidence
from ai.prompts import PROMPT_VERSION
from ai.settings import AISettings
from scripts.demo_scenarios import DEMO_SCENARIOS


def main() -> int:
    try:
        settings = AISettings.from_env()
    except ValueError:
        print("Invalid AI settings: configure OPENAI_MODEL and timeouts in .env.")
        return 1
    if not settings.cache_enabled:
        print("Enable AI_CACHE_ENABLED before warming the cache.")
        return 1
    catalog = get_catalog()
    keys = []
    failed = False
    for name, request in DEMO_SCENARIOS.items():
        started = perf_counter()
        result = evaluate(request, catalog)
        alternatives = find_alternatives(request, catalog)
        contributions = leave_one_out(result, catalog)
        evidence = build_evidence(result, catalog, alternatives, contributions)
        payload = agent._payload(result, catalog, evidence)
        answer = agent.explain_scenario(result, catalog, mode="live", alternatives=alternatives, contributions=contributions)
        print(json.dumps({"scenario": name, "model": settings.model, "seconds": round(perf_counter()-started, 3), "payload_bytes": len(payload.encode()), "score": result.score, "critical_count": result.critical_count, "mode": answer.mode, "source": answer.source, "reason": answer.reason}), flush=True)
        if answer.mode != "live":
            failed = True
            continue
        keys.append(hashlib.sha256(f"{PROMPT_VERSION}\n{settings.model}\n{payload}".encode()).hexdigest())
    if keys:
        cache.export_demo(keys)
        print(f"Persisted {len(keys)} verified selections (no TTL, no secrets).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
