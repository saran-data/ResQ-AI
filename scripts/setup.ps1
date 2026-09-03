# =============================================================
# ResQAI - Setup Script (PowerShell)
# Automated development environment bootstrap
# =============================================================

param(
    [switch]$SkipDocker,
    [switch]$DevMode,
    [switch]$SeedData
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "`n=== ResQAI Setup Script ===" -ForegroundColor Cyan
Write-Host "AI Powered Intelligent Food Rescue Ecosystem`n" -ForegroundColor Green

# ---- Step 1: Check Prerequisites ----
Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow

function Check-Command {
    param([string]$cmd, [string]$installHint)
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "  MISSING: $cmd — $installHint" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "  OK: $cmd" -ForegroundColor Green
    }
}

Check-Command "docker" "Install Docker Desktop from https://docker.com"
Check-Command "node" "Install Node.js 20+ from https://nodejs.org"
Check-Command "python" "Install Python 3.11+ from https://python.org"
Check-Command "git" "Install Git from https://git-scm.com"

# ---- Step 2: Copy .env ----
Write-Host "[2/7] Setting up environment..." -ForegroundColor Yellow
if (-not (Test-Path "$ROOT\.env")) {
    Copy-Item "$ROOT\.env.example" "$ROOT\.env"
    Write-Host "  Created .env from .env.example" -ForegroundColor Green
    Write-Host "  IMPORTANT: Edit .env and add your API keys before continuing!" -ForegroundColor Red
} else {
    Write-Host "  .env already exists" -ForegroundColor Green
}

# ---- Step 3: Frontend deps ----
Write-Host "[3/7] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location "$ROOT\frontend"
npm ci --frozen-lockfile
Write-Host "  Frontend dependencies installed" -ForegroundColor Green

# ---- Step 4: Backend Python venv ----
Write-Host "[4/7] Setting up Python virtual environment..." -ForegroundColor Yellow
Set-Location "$ROOT\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Write-Host "  Backend dependencies installed" -ForegroundColor Green

# ---- Step 5: Docker ----
if (-not $SkipDocker) {
    Write-Host "[5/7] Starting Docker services..." -ForegroundColor Yellow
    Set-Location $ROOT
    docker-compose up -d postgres redis qdrant kafka zookeeper
    Write-Host "  Waiting for services to be ready..." -ForegroundColor Cyan
    Start-Sleep -Seconds 15

    # Run migrations
    Write-Host "  Running database migrations..." -ForegroundColor Cyan
    docker-compose run --rm backend alembic upgrade head
    Write-Host "  Migrations complete" -ForegroundColor Green
} else {
    Write-Host "[5/7] Skipping Docker (--SkipDocker flag set)" -ForegroundColor Gray
}

# ---- Step 6: Seed data ----
if ($SeedData) {
    Write-Host "[6/7] Seeding database with sample data..." -ForegroundColor Yellow
    Set-Location $ROOT
    docker-compose run --rm backend python scripts/seed.py
    Write-Host "  Database seeded" -ForegroundColor Green
} else {
    Write-Host "[6/7] Skipping data seed (pass -SeedData to seed)" -ForegroundColor Gray
}

# ---- Step 7: Summary ----
Write-Host "`n[7/7] Setup complete!" -ForegroundColor Green
Write-Host "`n=== ResQAI is ready ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Start all services:     docker-compose up -d" -ForegroundColor White
Write-Host "Frontend dev server:    cd frontend && npm run dev" -ForegroundColor White
Write-Host "Backend dev server:     cd backend && uvicorn app.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "Frontend:  http://localhost:3000" -ForegroundColor Cyan
Write-Host "API Docs:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Grafana:   http://localhost:3001" -ForegroundColor Cyan
Write-Host "Kafka UI:  http://localhost:8080" -ForegroundColor Cyan
Write-Host "Qdrant:    http://localhost:6333/dashboard`n" -ForegroundColor Cyan
