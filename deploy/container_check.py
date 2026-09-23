"""Build and check an isolated container, then remove it even on failure."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy.smoke import probe


def run(args, *, timeout=60, env=None):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="akim-city:ops-check")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--mode", choices=("mock", "fallback"), default="mock")
    parser.add_argument("--browser", action="store_true", help="Also run the finite Chromium smoke test; needs Node and Chromium")
    args = parser.parse_args()
    name = "akim-ops-check-" + uuid.uuid4().hex[:12]
    stage = "build" if args.build else "start"
    started = False
    report = {"status": "fail", "image": args.image}
    exit_code = 1
    try:
        if args.build:
            run(["docker", "build", "-f", "deploy/Dockerfile", "-t", args.image, "."], timeout=600)
        stage = "start"
        run(["docker", "run", "-d", "--name", name, "--read-only", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:size=32m,mode=1777",
             "-p", "127.0.0.1::8000", "-e", "PORT=8000", "-e", "OPENAI_API_KEY=",
             "-e", "AI_MODE=" + ("live" if args.mode == "fallback" else "mock"), args.image])
        started = True
        mapping = run(["docker", "port", name, "8000/tcp"])
        if not re.fullmatch(r"127\.0\.0\.1:\d+", mapping):
            raise ValueError("Unexpected port mapping")
        stage = "smoke"
        report = probe("http://" + mapping, args.mode, wait_seconds=30)
        if report["status"] != "ok":
            return 1
        stage = "runtime"
        runtime = json.loads(run(["docker", "exec", name, "python", "-c",
            "import os,json,pathlib; print(json.dumps({'uid':os.getuid(),"
            "'has_env':pathlib.Path('/app/.env').exists(),"
            "'has_git':pathlib.Path('/app/.git').exists(),"
            "'has_ai_cache_module':pathlib.Path('/app/ai/cache/__init__.py').is_file()}))"]))
        if runtime != {"uid": 10001, "has_env": False, "has_git": False, "has_ai_cache_module": True}:
            raise ValueError("Runtime packaging mismatch")
        report["runtime"] = runtime
        report["image_id"] = run(["docker", "inspect", "--format", "{{.Image}}", name])
        stage = "pytest"
        environment = {**os.environ, "API_URL": "http://" + mapping, "OPENAI_API_KEY": ""}
        output = run([sys.executable, "-m", "pytest", "tests/e2e", "--require-api", "--expected-ai-mode", args.mode,
                      "-q", "-p", "no:cacheprovider"], timeout=120, env=environment)
        counts = re.findall(r"\b(\d+) passed\b", output)
        if not counts or re.search(r"\b\d+ skipped\b", output):
            raise ValueError("Missing passing tests or skipped tests")
        report["pytest_passed"] = int(counts[-1])
        if args.browser:
            stage = "browser"
            node = shutil.which("node")
            if not node:
                raise ValueError("Node is required")
            environment["EXPECTED_AI_MODE"] = args.mode
            output = run([node, "tests/e2e/browser_smoke.mjs", "http://" + mapping], timeout=90, env=environment)
            report["browser"] = json.loads(output)
        exit_code = 0
    except (subprocess.SubprocessError, OSError, ValueError):
        report.update(status="fail", stage=stage, code="container_check_failed")
    finally:
        # Only remove the unique container created by this invocation; no images or volumes.
        if started:
            try:
                run(["docker", "stop", "--time", "10", name], timeout=25)
                run(["docker", "rm", name], timeout=20)
            except (subprocess.SubprocessError, OSError):
                report.update(status="fail", stage="cleanup", code="cleanup_failed", container=name)
                exit_code = 1
        print(json.dumps(report, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
