"""Generate repeatable ScenarioRequest examples without changing the city dataset.

Only the standard library is used. Score is always obtained from the backend.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
SEED = 8385


def generate(count: int = 5, seed: int = SEED) -> list[dict]:
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError("count must be an integer from 1 to 100")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    catalog = json.loads((ROOT / "data/city.json").read_text(encoding="utf-8"))
    rng = random.Random(seed)
    measures = sorted(catalog["measures"], key=lambda measure: measure["id"])
    districts = sorted(district["id"] for district in catalog["districts"])
    rules = catalog["rules"]
    output = []
    seen = set()
    for _ in range(10000):
        chosen = rng.sample(measures, rules["decision_count"])
        if sum(measure["cost"] for measure in chosen) > rules["budget"]:
            continue
        if max(Counter(measure["direction"] for measure in chosen).values()) > rules["max_per_direction"]:
            continue
        decisions = [
            {"measure_id": measure["id"], **({"district_id": rng.choice(districts)} if measure["scope"] == "district" else {})}
            for measure in sorted(chosen, key=lambda measure: measure["id"])
        ]
        targets = {decision["measure_id"]: decision.get("district_id") for decision in decisions}
        conflict = False
        for rule in catalog["conflicts"]:
            first, second = rule["measures"]
            if first in targets and second in targets:
                if rule["scope"] == "anywhere" or targets[first] == targets[second]:
                    conflict = True
        signature = tuple((decision["measure_id"], decision.get("district_id")) for decision in decisions)
        if not conflict and signature not in seen:
            seen.add(signature)
            output.append({"decisions": decisions})
            if len(output) == count:
                return output
    raise RuntimeError("Could not generate the requested number of valid scenarios")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--count", type=int, choices=range(1, 101), default=5, metavar="1..100")
    parser.add_argument("--output", type=Path, default=ROOT / "data/generated")
    args = parser.parse_args()
    scenarios = generate(args.count, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    for index, scenario in enumerate(scenarios, start=1):
        path = args.output / f"seed-{args.seed}-{index:03d}.json"
        path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(scenarios)} scenarios, seed={args.seed}. Evaluate via the API.")


if __name__ == "__main__":
    main()
