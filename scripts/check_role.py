"""Check staged paths only. Never stage, reset or otherwise change user work."""

import subprocess

ALLOWED = {
    "frontend": ("frontend/",),
    "ops": ("data/", "tests/e2e/", "deploy/", "docs/", "README.md"),
}


def main() -> int:
    role = subprocess.run(["git", "config", "--get", "team.role"], capture_output=True, text=True).stdout.strip()
    if role == "lead":
        return 0
    if role not in ALLOWED:
        print("Set your role: git config team.role lead|frontend|ops")
        return 1
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "--no-renames", "-z"]).decode("utf-8").split("\0")
    forbidden = [path for path in staged if path and not any(path.startswith(prefix) if prefix.endswith("/") else path == prefix for prefix in ALLOWED[role])]
    if forbidden:
        print("Files outside your role:\n" + "\n".join(forbidden))
        print("Unstage the listed files (keep local edits): git restore --staged -- <path>")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
