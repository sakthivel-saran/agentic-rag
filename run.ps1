$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

# Prefer the project's named Conda environment when available. This avoids
# resolving the broken Windows Store Python alias on PATH.
$condaPython = if ($env:CONDA_PREFIX) {
    Join-Path $env:CONDA_PREFIX "python.exe"
} else {
    ""
}
if ($env:CONDA_DEFAULT_ENV -eq "agentic-rag1" -and (Test-Path -LiteralPath $condaPython)) {
    $python = $condaPython
}
elseif (Test-Path -LiteralPath "C:\Users\sakth\miniconda3\envs\agentic-rag1\python.exe") {
    $python = "C:\Users\sakth\miniconda3\envs\agentic-rag1\python.exe"
}

if (-not (Test-Path -LiteralPath $python)) {
    $basePython = Get-Command python -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike "*\\Microsoft\\WindowsApps\\python.exe" } |
        Select-Object -First 1
    if (-not $basePython) {
        throw "Python was not found. Install Python 3 and make sure python.exe is on PATH."
    }

    & $basePython.Source -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python)) {
        throw "Could not create the project virtual environment with '$($basePython.Source)'. Check that this Python installation includes venv and pip support."
    }
}

& $python -c "import pydantic_settings" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install -r (Join-Path $projectRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. Repair or reinstall Python with pip support, then run .\run.ps1 again."
    }
}

& $python -m uvicorn app.main:app --reload --port 8080
