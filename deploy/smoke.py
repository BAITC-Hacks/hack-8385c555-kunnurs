"""Finite release probe. A missing service is a failure, never a successful skip."""

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        path = values.get("src") if tag == "script" else values.get("href") if tag == "link" and values.get("rel") == "stylesheet" else None
        if path:
            self.paths.append(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Service origin, e.g. https://your-service.onrender.com")
    parser.add_argument("--require-https", action="store_true")
    parser.add_argument("--expected-ai-mode", choices=("mock", "live", "fallback"), default="mock")
    parser.add_argument("--require-provider", action="store_true", help="Require a fresh live provider response, not cache")
    args = parser.parse_args()
    origin = args.url.rstrip("/")
    parts = urlsplit(origin)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path or parts.query or parts.fragment or parts.username or parts.password:
        parser.error("URL must be an HTTP(S) origin without credentials, path, query or fragment")
    if args.require_https and parts.scheme != "https":
        parser.error("Public release requires HTTPS")

    def fetch(path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(origin + path, data=body, headers={} if body is None else {"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError("Unexpected HTTP status")
            final = urlsplit(response.url)
            if (final.scheme, final.netloc) != (parts.scheme, parts.netloc):
                raise ValueError("Unexpected redirect to another origin")
            return response.read(), response.headers.get_content_type()

    def get_json(path, payload=None):
        body, content_type = fetch(path, payload)
        if content_type != "application/json":
            raise ValueError("Expected JSON response")
        return json.loads(body)

    try:
        page, content_type = fetch("/")
        if content_type != "text/html":
            raise ValueError("Frontend is not HTML")
        assets = Assets()
        assets.feed(page.decode("utf-8"))
        if not assets.paths:
            raise ValueError("Frontend has no script or stylesheet assets")
        for path in assets.paths:
            if not path.startswith("/assets/") or ".." in path:
                raise ValueError("Frontend asset must use the same origin")
            body, asset_type = fetch(path)
            if not body or asset_type == "text/html":
                raise ValueError("Missing frontend asset")
        health = get_json("/api/health")
        catalog = get_json("/api/catalog")
        baseline = get_json("/api/baseline")
        scenario = json.loads((ROOT / "data/scenarios/pdf-example.json").read_text(encoding="utf-8"))
        result = get_json("/api/simulations/evaluate", scenario)
        analysis = get_json("/api/simulations/analyze", scenario)
        if health["status"] != "ok" or health["api_version"] != "1":
            raise ValueError("Invalid health response")
        if not (health["dataset_version"] == catalog["version"] == baseline["dataset_version"] == result["dataset_version"]):
            raise ValueError("Dataset versions disagree")
        if abs(baseline["score"] - 52.55768) > 1e-6 or abs(result["score"] - 56.54307) > 1e-6:
            raise ValueError("Score does not match SPEC")
        if (result["total_cost"], result["remaining_budget"], result["critical_count"]) != (95, 5, 0):
            raise ValueError("Demo result does not match SPEC")
        if analysis["result"] != result or not analysis["analysis"]["notice"].strip():
            raise ValueError("AI response changed the calculation or omitted its notice")
        if analysis["analysis"]["mode"] != args.expected_ai_mode:
            raise ValueError("AI mode differs from the expected release mode")
        if health["ai_mode"] != args.expected_ai_mode and not (health["ai_mode"] == "live" and args.expected_ai_mode == "fallback"):
            raise ValueError("AI configuration differs from the expected release mode")
        if args.require_provider and (analysis["analysis"]["mode"] != "live" or analysis["analysis"].get("source") != "provider" or analysis["analysis"].get("reason") is not None):
            raise ValueError("Fresh live provider response required")
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError):
        print("FAIL: release probe failed; check platform health, assets, SPEC values and AI mode.", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "checked_at": datetime.now(timezone.utc).isoformat(), "url": origin,
                      "dataset_version": result["dataset_version"], "score": result["score"],
                      "ai_mode": analysis["analysis"]["mode"], "ai_source": analysis["analysis"].get("source"),
                      "ai_reason": analysis["analysis"].get("reason"), "assets": len(assets.paths)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
