"""Finite container health probe using only the Python standard library."""

import json
import os
import sys
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def main() -> int:
    try:
        port = int(os.getenv("PORT", "8000"))
        if not 1 <= port <= 65535:
            return 1
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
            payload = json.load(response)
            return 0 if response.status == 200 and isinstance(payload, dict) and payload.get("status") == "ok" and payload.get("api_version") == "1" else 1
    except (URLError, OSError, ValueError, TypeError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
