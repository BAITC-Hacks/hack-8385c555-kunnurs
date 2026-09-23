"""Regression checks for OPS tooling. No real provider, listener or Docker needed."""

import json
from urllib.error import URLError

from fastapi.testclient import TestClient
import pytest

from data.generate import generate
from deploy import healthcheck, smoke
from deploy.app import create_app


@pytest.fixture
def fetch(tmp_path, monkeypatch):
    import backend.app.main as main

    monkeypatch.setattr(main, "AI_MODE", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("// fixture", encoding="utf-8")
    (tmp_path / "index.html").write_text('<script src="/assets/app.js"></script>', encoding="utf-8")
    with TestClient(create_app(tmp_path)) as client:
        def call(path, payload=None, expected=200):
            response = client.get(path) if payload is None else client.post(path, json=payload)
            smoke.require(response.status_code == expected, "unexpected_http_status")
            return response.content, response.headers["content-type"].split(";")[0]
        yield call


def altered(fetch, target, mutate):
    def call(path, payload=None, expected=200):
        body, mime = fetch(path, payload, expected)
        if path == target:
            value = json.loads(body)
            mutate(value)
            body = json.dumps(value).encode()
        return body, mime
    return call


def test_full_release_probe_offline(fetch):
    report = smoke.probe("http://localhost:8000", fetch=fetch)
    assert report["status"] == "ok"
    assert report["score"] == 56.54307
    assert report["school_in_esil_score"] == 55.29777
    # The best Score and fewest critical values select the same replacement.
    assert report["alternatives"] == 2
    assert report["ai_source"] == "template"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "56.54307", None])
def test_probe_rejects_invalid_scores(fetch, value):
    modified = altered(fetch, "/api/baseline", lambda obj: obj.update(score=value))
    report = smoke.probe("http://localhost:8000", fetch=modified)
    assert (report["status"], report["stage"], report["code"]) == ("fail", "calculation", "score_mismatch")


@pytest.mark.parametrize("mode,source,reason,expected,require_provider,code", [
    ("live", "provider", None, "live", True, None),
    ("live", "cache", None, "live", False, None),
    ("live", "cache", None, "live", True, "fresh_provider_required"),
    ("live", "template", None, "live", False, "invalid_live_source"),
    ("fallback", "template", "timeout", "fallback", False, None),
    ("fallback", "template", "missing_api_key", "live", True, "ai_mode_mismatch"),
    ("mock", "provider", None, "mock", False, "invalid_template_source"),
    ("fallback", "template", "SECRET-DO-NOT-LOG", "fallback", False, "invalid_template_source"),
])
def test_probe_reports_actual_ai_mode(fetch, mode, source, reason, expected, require_provider, code):
    modified = altered(fetch, "/api/health", lambda obj: obj.update(ai_mode="live" if mode != "mock" else "mock"))
    modified = altered(modified, "/api/simulations/analyze", lambda obj: obj["analysis"].update(mode=mode, source=source, reason=reason))
    report = smoke.probe("http://localhost:8000", expected, require_provider, fetch=modified)
    assert report.get("code") == code
    assert report["status"] == ("fail" if code else "ok")
    assert "SECRET-DO-NOT-LOG" not in json.dumps(report)


def test_probe_never_retries_analysis(fetch):
    calls = []

    def failed(path, payload=None, expected=200):
        if path.endswith("analyze"):
            calls.append(path)
            raise smoke.ProbeFailure("service_unreachable")
        return fetch(path, payload, expected)

    assert smoke.probe("http://localhost:8000", fetch=failed, wait_seconds=1)["status"] == "fail"
    assert len(calls) == 1


def test_unavailable_probe_fails_without_echoing_error():
    def failed(*args):
        raise smoke.ProbeFailure("service_unreachable")
    assert smoke.probe("http://localhost:8000", fetch=failed)["code"] == "service_unreachable"


@pytest.mark.parametrize("origin", ["ftp://localhost", "http://a/b", "http://a?token=secret", "http://a/#x",
                                   "http://user:secret@localhost", "http://localhost:0", "http://localhost:bad",
                                   "http://localhost:65536", "http://a\\b", "http://a\n", "http://", "//localhost"])
def test_origin_validation(origin):
    with pytest.raises(ValueError):
        smoke.valid_origin(origin)


def test_http_probe_disallows_redirects_and_hides_network_errors(monkeypatch):
    assert smoke.NoRedirect().redirect_request(None, None, 302, "", {}, "http://elsewhere") is None
    client = smoke.HTTPClient("http://localhost:8000")

    def failed(*args, **kwargs):
        raise URLError("SECRET-DO-NOT-LOG")
    monkeypatch.setattr(client.opener, "open", failed)
    with pytest.raises(smoke.ProbeFailure) as error:
        client.fetch("/api/health")
    assert error.value.code == "service_unreachable"
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize("count", [0, -1, 101, True, 1.5])
def test_generator_rejects_bad_count(count):
    with pytest.raises(ValueError):
        generate(count=count)


def test_generator_maximum_is_unique_and_deterministic():
    scenarios = generate(count=100, seed=-1)
    assert len({json.dumps(value, sort_keys=True) for value in scenarios}) == 100
    assert scenarios == generate(count=100, seed=-1)


@pytest.mark.parametrize("payload,status,expected", [
    ({"status": "ok", "api_version": "1"}, 200, 0),
    ({"status": "ok", "api_version": "2"}, 200, 1),
    ({"status": "ok", "api_version": "1"}, 500, 1),
    ([], 200, 1), (None, 200, 1),
])
def test_healthcheck_handles_invalid_responses(monkeypatch, payload, status, expected):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps(payload).encode()
    response = Response()
    response.status = status
    class Opener:
        def open(self, *args, **kwargs):
            return response
    monkeypatch.setattr(healthcheck, "build_opener", lambda *args: Opener())
    assert healthcheck.main() == expected


@pytest.mark.parametrize("port", ["0", "-1", "65536", "invalid"])
def test_healthcheck_rejects_invalid_ports(monkeypatch, port):
    monkeypatch.setenv("PORT", port)
    assert healthcheck.main() == 1
