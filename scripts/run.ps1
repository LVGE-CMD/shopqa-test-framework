param(
    [ValidateSet("all", "api", "ui", "smoke", "regression")]
    [string]$Suite = "all",
    [switch]$Report
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found: $python. Run: python -m venv .venv"
}

$target = switch ($Suite) {
    "all"        { @("tests") }
    "api"        { @("tests/api") }
    "ui"         { @("tests/ui") }
    "smoke"      { @("tests", "-m", "smoke") }
    "regression" { @("tests", "-m", "regression") }
}

Write-Host ("Running: pytest " + ($target -join " ")) -ForegroundColor Cyan
& $python -m pytest $target

if ($Report) {
    & "$PSScriptRoot\report.ps1"
}
