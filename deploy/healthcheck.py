"""Finite container health probe using only the Python standard library."""

import json
import os
import sys
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    try:
        port = int(os.getenv("PORT", "8000"))
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
            payload = json.load(response)
            return 0 if response.status == 200 and payload.get("status") == "ok" else 1
    except (URLError, OSError, ValueError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
