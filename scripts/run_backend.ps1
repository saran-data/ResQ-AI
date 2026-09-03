# =============================================================
# ResQAI - Run Backend (WITHOUT Docker)
# Uses SQLite in-memory fallback when PostgreSQL is unavailable
# =============================================================

$root = Split-Path -Parent $PSScriptRoot
$backendDir = "$root\backend"

Write-Host "`n=== Starting ResQAI Backend ===" -ForegroundColor Cyan
Set-Location $backendDir

# Activate virtual environment
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "ERROR: Virtual environment not found." -ForegroundColor Red
    Write-Host "Run .\scripts\install_backend.ps1 first." -ForegroundColor Yellow
    exit 1
}

# Load .env
if (Test-Path "$root\.env") {
    Write-Host "Loading .env..." -ForegroundColor Gray
    Get-Content "$root\.env" | Where-Object { $_ -match "^\w" -and $_ -notmatch "^#" } | ForEach-Object {
        $parts = $_ -split "=", 2
        if ($parts.Length -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
    }
}

Write-Host "`nBackend starting at: http://localhost:8000" -ForegroundColor Green
Write-Host "API Docs:            http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray

# Run with --reload for hot-reloading during development
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
