param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & $Python scripts/check.py --require-frontend
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
