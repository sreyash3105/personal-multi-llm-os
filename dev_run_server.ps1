param(
    [int]$Port = 6969
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Project root: $root"

# --- SMART ENVIRONMENT DETECTION ---
$TargetEnv = "ai-gpu"

if (Get-Command "conda" -ErrorAction SilentlyContinue) {
    $CurrentEnv = $env:CONDA_DEFAULT_ENV
    
    if ($CurrentEnv -eq $TargetEnv) {
        Write-Host "Active Conda environment: $TargetEnv" -ForegroundColor Green
    } else {
        Write-Host "---------------------------------------------------" -ForegroundColor Yellow
        Write-Host "WARNING: Wrong Environment Detected" -ForegroundColor Yellow
        Write-Host "Current: $CurrentEnv" -ForegroundColor Yellow
        Write-Host "Target:  $TargetEnv" -ForegroundColor Yellow
        Write-Host "Please run: conda activate $TargetEnv" -ForegroundColor Yellow
        Write-Host "---------------------------------------------------" -ForegroundColor Yellow
    }
}

# --- LAUNCH ---
$env:PYTHONPATH = $root
Write-Host "Starting Local AI OS on port $Port..." -ForegroundColor Cyan

python -m uvicorn backend.code_server:app `
    --host 0.0.0.0 `
    --port $Port `
    --reload `
    --reload-dir "$root\backend" `
    --reload-dir "$root\static"