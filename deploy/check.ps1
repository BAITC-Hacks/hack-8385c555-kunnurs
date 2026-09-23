param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & $Python scripts/check.py --require-frontend
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pytest tests/e2e --in-process --expected-ai-mode mock -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pytest tests/e2e/test_api.py --in-process --expected-ai-mode fallback -q -p no:cacheprovider
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
