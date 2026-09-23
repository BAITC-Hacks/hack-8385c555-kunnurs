"""Finite release probe using the standard library; reports only safe diagnostics."""

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
REASONS = {"missing_api_key", "invalid_configuration", "timeout", "connection_error",
           "authentication_error", "permission_error", "rate_limit", "provider_error", "invalid_output"}


class ProbeFailure(Exception):
    def __init__(self, code):
        self.code = code


def require(condition, code):
    if not condition:
        raise ProbeFailure(code)


def valid_origin(value):
    try:
        parts = urlsplit(value)
        valid = (parts.scheme in {"http", "https"} and parts.hostname and parts.port != 0
                 and parts.path in {"", "/"} and not (parts.query or parts.fragment or parts.username or parts.password)
                 and not any(char.isspace() or ord(char) < 32 for char in value) and "\\" not in value)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Use an HTTP(S) origin without credentials, path, query or fragment")
    return value.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class HTTPClient:
    def __init__(self, origin, timeout=20):
        self.origin = valid_origin(origin)
        self.timeout = timeout
        self.deadline = time.monotonic() + 120
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def fetch(self, path, payload=None, expected=200):
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "deadline_exceeded")
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode("utf-8")
        request = Request(self.origin + path, data=body, headers={} if body is None else {"Content-Type": "application/json"})
        try:
            try:
                response = self.opener.open(request, timeout=min(self.timeout, remaining))
            except HTTPError as error:
                response = error
            with response:
                require(response.status == expected, "unexpected_http_status")
                content = response.read(4 * 1024 * 1024 + 1)
                require(len(content) <= 4 * 1024 * 1024, "response_too_large")
                return content, response.headers.get_content_type()
        except (URLError, OSError, TimeoutError):
            raise ProbeFailure("service_unreachable") from None


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        path = values.get("src") if tag == "script" else values.get("href") if tag == "link" and values.get("rel") == "stylesheet" else None
        if path:
            self.paths.append(path)


def probe(origin, expected_mode="mock", require_provider=False, *, fetch=None, wait_seconds=0):
    """fetch is injectable for offline regression tests; HTTP is used by the CLI."""
    origin = valid_origin(origin)
    require(expected_mode in {"mock", "live", "fallback"}, "invalid_mode")
    require(not require_provider or expected_mode == "live", "provider_requires_live")
    require(0 <= wait_seconds <= 60, "invalid_wait")
    fetch = fetch or HTTPClient(origin).fetch
    report = {"status": "fail", "checked_at": datetime.now(timezone.utc).isoformat(), "url": origin}
    stage = "health"

    def get_json(path, payload=None, expected=200):
        body, content_type = fetch(path, payload, expected)
        require(content_type == "application/json", "expected_json")
        value = json.loads(body)
        require(isinstance(value, dict), "invalid_response_shape")
        return value

    def score_equals(value, expected):
        return type(value) in {int, float} and math.isfinite(value) and abs(value - expected) <= 1e-6

    try:
        ready_deadline = time.monotonic() + wait_seconds
        while True:
            try:
                health = get_json("/api/health")
                break
            except ProbeFailure as error:
                if error.code not in {"service_unreachable", "unexpected_http_status"} or time.monotonic() >= ready_deadline:
                    raise
                time.sleep(min(1, max(0, ready_deadline - time.monotonic())))
        require(health["status"] == "ok" and health["api_version"] == "1", "invalid_health")
        stage = "frontend"
        page, content_type = fetch("/")
        require(content_type == "text/html", "expected_html")
        assets = Assets()
        assets.feed(page.decode("utf-8"))
        require(bool(assets.paths), "missing_assets")
        stage = "assets"
        for path in assets.paths:
            parts = urlsplit(path)
            require(path.startswith("/assets/") and not (parts.scheme or parts.netloc or parts.query or parts.fragment)
                    and ".." not in unquote(path) and "\\" not in unquote(path), "invalid_asset_path")
            body, asset_type = fetch(path)
            require(bool(body) and asset_type in {"text/css", "text/javascript", "application/javascript"}, "invalid_asset")
        stage = "calculation"
        catalog = get_json("/api/catalog")
        baseline = get_json("/api/baseline")
        scenario = json.loads((ROOT / "data/scenarios/pdf-example.json").read_text(encoding="utf-8"))
        result = get_json("/api/simulations/evaluate", scenario)
        require(health["dataset_version"] == catalog["version"] == baseline["dataset_version"] == result["dataset_version"], "dataset_mismatch")
        require(score_equals(baseline["score"], 52.55768) and score_equals(result["score"], 56.54307), "score_mismatch")
        require((result["total_cost"], result["remaining_budget"], result["critical_count"]) == (95, 5, 0), "demo_mismatch")
        alternate = json.loads((ROOT / "data/scenarios/school-in-esil.json").read_text(encoding="utf-8"))
        school = get_json("/api/simulations/evaluate", alternate)
        require(score_equals(school["score"], 55.29777), "alternate_score_mismatch")
        stage = "analysis"
        analysis = get_json("/api/simulations/analyze", scenario)
        ai = analysis["analysis"]
        mode, source, reason = ai["mode"], ai.get("source"), ai.get("reason")
        # Never copy arbitrary provider/server text into release logs.
        report.update(ai_mode=mode if mode in {"mock", "live", "fallback"} else "unknown",
                      ai_source=source if source in {"template", "provider", "cache"} else "unknown",
                      ai_reason=reason if reason is None or reason in REASONS else "unknown")
        require(analysis["result"] == result and bool(ai["notice"].strip()), "analysis_mismatch")
        require(mode == expected_mode, "ai_mode_mismatch")
        require(health["ai_mode"] == mode or (health["ai_mode"] == "live" and mode == "fallback"), "health_mode_mismatch")
        if mode == "live":
            require(source in {"provider", "cache"} and reason is None, "invalid_live_source")
        else:
            require(source == "template" and (reason in REASONS if mode == "fallback" else reason is None), "invalid_template_source")
        require(not require_provider or source == "provider", "fresh_provider_required")
        stage = "recommendations"
        alternatives = analysis.get("alternatives", [])
        require(isinstance(alternatives, list) and len(alternatives) <= 3, "invalid_alternatives")
        for alternative in alternatives:
            calculated = get_json("/api/simulations/evaluate", alternative["scenario"])
            require(score_equals(calculated["score"], alternative["score"]) and calculated["score"] > result["score"]
                    and calculated["total_cost"] == alternative["total_cost"] <= 100, "alternative_mismatch")
        stage = "invalid_request"
        rejected = get_json("/api/simulations/evaluate", {"decisions": []}, expected=422)
        require(rejected["error"]["code"] == "invalid_scenario" and "score" not in rejected, "invalid_error_contract")
        stage = "private_files"
        for path in ("/.env", "/.git/config"):
            fetch(path, expected=404)
        report.update(status="ok", dataset_version=result["dataset_version"], score=result["score"],
                      school_in_esil_score=school["score"], assets=len(assets.paths), alternatives=len(alternatives))
    except ProbeFailure as error:
        report.update(stage=stage, code=error.code)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        report.update(stage=stage, code="invalid_response")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Service origin")
    parser.add_argument("--require-https", action="store_true")
    parser.add_argument("--expected-ai-mode", choices=("mock", "live", "fallback"), default="mock")
    parser.add_argument("--require-provider", action="store_true", help="Require a fresh live response, not cache")
    parser.add_argument("--wait-seconds", type=int, choices=range(61), default=0, metavar="0..60", help="Retry health while the service starts; never retry paid analysis")
    parser.add_argument("--output", type=Path, help="Also save the safe JSON report")
    args = parser.parse_args(argv)
    try:
        origin = valid_origin(args.url)
    except ValueError as error:
        parser.error(str(error))
    if args.require_https and urlsplit(origin).scheme != "https":
        parser.error("Public release requires HTTPS")
    if args.require_provider and args.expected_ai_mode != "live":
        parser.error("--require-provider needs --expected-ai-mode live")
    report = probe(origin, args.expected_ai_mode, args.require_provider, wait_seconds=args.wait_seconds)
    rendered = json.dumps(report, ensure_ascii=False)
    if args.output:
        try:
            args.output.write_text(rendered + "\n", encoding="utf-8")
        except OSError:
            print("FAIL: could not write report", file=sys.stderr)
            return 1
    print(rendered, file=sys.stdout if report["status"] == "ok" else sys.stderr)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
