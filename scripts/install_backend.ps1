# =============================================================
# ResQAI - Backend Install Script (Windows PowerShell)
# Run this ONCE to set up the Python virtual environment
# =============================================================

$root = Split-Path -Parent $PSScriptRoot
$backendDir = "$root\backend"

Write-Host "`n=== ResQAI Backend Setup ===" -ForegroundColor Cyan
Set-Location $backendDir

# Create virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "  Virtual environment created at backend\.venv" -ForegroundColor Green
} else {
    Write-Host "[1/4] Virtual environment already exists, skipping..." -ForegroundColor Gray
}

# Activate venv
Write-Host "[2/4] Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "[3/4] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host "[4/4] Installing Python dependencies (this takes ~2-3 minutes)..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

Write-Host "`n Backend setup complete!" -ForegroundColor Green
Write-Host "Next: Run .\scripts\run_backend.ps1" -ForegroundColor Cyan
