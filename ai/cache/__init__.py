"""Bounded process-local cache for validated AI narratives."""

from collections import OrderedDict
import json
import os
from pathlib import Path
from threading import Lock
from time import monotonic

from contracts.schemas import AISelection

MAX_ENTRIES = 128
TTL_SECONDS = 3600
_entries: OrderedDict[str, tuple[float, AISelection]] = OrderedDict()
_lock = Lock()


def get(key: str) -> AISelection | None:
    # Only the explicit warm-up command writes this portable demo cache. No TTL:
    # the key includes model, prompt version, dataset and all calculated evidence.
    try:
        path = demo_path()
        if path.stat().st_size <= 131072:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") == 1 and key in data.get("entries", {}):
                return AISelection.model_validate(data["entries"][key])
    except (OSError, ValueError, TypeError, AttributeError):
        pass  # Missing/corrupt demo files never break the calculation.
    with _lock:
        item = _entries.get(key)
        if item is None:
            return None
        created, narrative = item
        if monotonic() - created >= TTL_SECONDS:
            del _entries[key]
            return None
        _entries.move_to_end(key)
        return narrative.model_copy(deep=True)


def put(key: str, narrative: AISelection) -> None:
    with _lock:
        _entries[key] = (monotonic(), narrative.model_copy(deep=True))
        _entries.move_to_end(key)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)


def demo_path() -> Path:
    return Path(os.getenv("AI_DEMO_CACHE_PATH") or Path(__file__).resolve().parents[1] / "demo_cache.json")


def export_demo(keys: list[str]) -> None:
    """Atomically persist only validated provider selections, never credentials."""
    entries = {}
    for key in keys:
        selection = get(key)
        if selection is None:
            raise ValueError("Cannot persist a missing AI selection")
        entries[key] = selection.model_dump()
    path = demo_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "entries": entries}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
