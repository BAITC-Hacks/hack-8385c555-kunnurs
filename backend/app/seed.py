"""Load the versioned synthetic dataset; never accept data overrides from clients."""

from functools import lru_cache
from pathlib import Path

from contracts.schemas import Catalog

ROOT = Path(__file__).resolve().parents[2]


def load_catalog(data_path: Path | None = None) -> Catalog:
    path = data_path if data_path is not None else ROOT / "data" / "city.json"
    if not path.is_file():
        path = ROOT / "contracts" / "examples" / "catalog.json"
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _cached_catalog() -> Catalog:
    return load_catalog()


def get_catalog() -> Catalog:
    # Each request receives its own copy; one simulation cannot change another.
    return _cached_catalog().model_copy(deep=True)
