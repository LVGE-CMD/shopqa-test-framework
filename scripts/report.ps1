param(
    [switch]$Serve
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$allure = ".\tools\allure-2.29.0\bin\allure.bat"
if (-not (Test-Path $allure)) {
    throw "Allure CLI not found. Extract allure-2.29.0 to tools\allure-2.29.0, or install allure globally."
}

if (-not (Test-Path "reports\allure-results")) {
    throw "No test results found. Run .\scripts\run.ps1 first."
}

& $allure generate "reports\allure-results" -o "reports\allure-report" --clean
Write-Host ""
Write-Host "Report generated: $((Resolve-Path 'reports\allure-report\index.html').Path)" -ForegroundColor Green

if ($Serve) {
    & $allure open "reports\allure-report"
}
