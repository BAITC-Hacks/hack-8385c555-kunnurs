"""Valid, deterministic demo inputs; no client-provided scores."""

from contracts.schemas import ScenarioRequest


def scenario(*pairs: tuple[str, str | None]) -> ScenarioRequest:
    return ScenarioRequest(decisions=[{"measure_id": m, "district_id": d} for m, d in pairs])


DEMO_SCENARIOS = {
    "pdf": scenario(("M7", "nura"), ("M8", "nura"), ("M10", "nura"), ("M12", None), ("M5", "saryarka")),
    # M4+M7 in the same district is forbidden. Keep the PDF's M5 instead.
    "all_esil": scenario(("M7", "esil"), ("M8", "esil"), ("M10", "esil"), ("M12", None), ("M5", "esil")),
    # Best supplied candidate; do not claim a proven global optimum.
    "best_known": scenario(("M2", None), ("M3", "nura"), ("M8", "nura"), ("M9", "nura"), ("M14", None)),
}
