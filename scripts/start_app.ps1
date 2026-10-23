$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run: python -m venv .venv"
}

Write-Host "ShopLite: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Demo account: demo / Demo123!" -ForegroundColor Cyan
& $python -m uvicorn app.main:app --reload --port 8000
