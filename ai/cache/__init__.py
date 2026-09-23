"""Bounded process-local cache for validated AI narratives."""

from collections import OrderedDict
from threading import Lock
from time import monotonic

from contracts.schemas import AINarrative

MAX_ENTRIES = 128
TTL_SECONDS = 3600
_entries: OrderedDict[str, tuple[float, AINarrative]] = OrderedDict()
_lock = Lock()


def get(key: str) -> AINarrative | None:
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


def put(key: str, narrative: AINarrative) -> None:
    with _lock:
        _entries[key] = (monotonic(), narrative.model_copy(deep=True))
        _entries.move_to_end(key)
        while len(_entries) > MAX_ENTRIES:
            _entries.popitem(last=False)
