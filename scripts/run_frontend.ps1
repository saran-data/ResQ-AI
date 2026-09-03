# =============================================================
# ResQAI - Run Frontend (Next.js Dev Server)
# Requires Node.js 20+ installed
# =============================================================

$root = Split-Path -Parent $PSScriptRoot
$frontendDir = "$root\frontend"

Write-Host "`n=== Starting ResQAI Frontend ===" -ForegroundColor Cyan
Set-Location $frontendDir

# Check Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Node.js not found." -ForegroundColor Red
    Write-Host "Download from: https://nodejs.org (LTS version)" -ForegroundColor Yellow
    exit 1
}

$nodeVersion = node --version
Write-Host "Node.js: $nodeVersion" -ForegroundColor Green

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm packages (first run ~2 minutes)..." -ForegroundColor Yellow
    npm install
}

Write-Host "`nFrontend starting at: http://localhost:3000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray

# Create local env file for Next.js
$envLocal = "$frontendDir\.env.local"
if (-not (Test-Path $envLocal)) {
    @"
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
"@ | Set-Content $envLocal
    Write-Host "Created frontend\.env.local" -ForegroundColor Green
}

npm run dev
