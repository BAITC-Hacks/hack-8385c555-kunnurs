"""One-shot quality gate, usable on Windows and Linux. Does not start servers."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> None:
    run([sys.executable, "-m", "pytest", "contracts/tests", "backend/tests", "-q", "-p", "no:cacheprovider"])
    run([sys.executable, "-c", "from backend.app.main import app; assert app.openapi()['paths']"])
    # OPS checks predate the live provider. Never inherit a personal API key
    # into offline tests; an existing empty variable also blocks dotenv loading.
    offline_env = {**os.environ, "OPENAI_API_KEY": "", "AI_MODE": "mock"}
    run([
        sys.executable, "-m", "pytest", "tests/e2e", "--in-process",
        "--expected-ai-mode", "mock", "-q", "-p", "no:cacheprovider",
    ], env=offline_env)
    run([
        sys.executable, "-m", "pytest", "tests/e2e/test_api.py", "--in-process",
        "--expected-ai-mode", "fallback", "-q", "-p", "no:cacheprovider",
    ], env=offline_env)
    if (ROOT / "frontend/node_modules").is_dir():
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise SystemExit("npm is required for the frontend build")
        run([npm, "run", "build"], cwd=ROOT / "frontend")
    elif "--require-frontend" in sys.argv:
        raise SystemExit("Install frontend dependencies with npm ci first")
    else:
        print("SKIP frontend build: run npm ci in frontend to enable it")
    print("OK: checks passed")


if __name__ == "__main__":
    main()
