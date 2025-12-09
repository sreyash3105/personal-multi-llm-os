param(
    [int]$Port = 6969   # ⬅ change default port here
)

$ErrorActionPreference = "Stop"

# Move to project root
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Project root: $root"

# ------------------------------
#  Activate virtual environment
# ------------------------------
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating .venv ..."
    . ".venv\Scripts\Activate.ps1"
}
elseif (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating venv ..."
    . "venv\Scripts\Activate.ps1"
}
else {
    Write-Host "⚠ No virtual environment found → using global python" -ForegroundColor Yellow
}

# ------------------------------
#  Ensure backend is importable
# ------------------------------
$env:PYTHONPATH = $root
Write-Host "PYTHONPATH = $env:PYTHONPATH"

# ------------------------------
#  Start server with auto-reload
# ------------------------------
Write-Host "🚀 Starting Uvicorn on port $Port (reload enabled)" -ForegroundColor Green

python -m uvicorn backend.code_server:app `
    --host 0.0.0.0 `
    --port $Port `
    --reload `
    --reload-dir "$root\backend" `
    --reload-dir "$root\static"
