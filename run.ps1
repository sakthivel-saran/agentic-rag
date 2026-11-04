$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    py -3 -m venv (Join-Path $projectRoot ".venv")
}

& $python -c "import pydantic_settings" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r (Join-Path $projectRoot "requirements.txt")
}

& $python -m uvicorn app.main:app --reload --port 8080
