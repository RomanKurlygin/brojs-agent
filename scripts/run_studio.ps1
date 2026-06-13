# LangGraph dev (Studio / API) — без Deep Agents UI
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"

Write-Host "LangGraph API: http://127.0.0.1:2024"
Write-Host "Deep Agents UI: powershell scripts\run_ui.ps1 -> http://localhost:3000"
Write-Host "Studio (tunnel): см. URL в выводе ниже"
Write-Host ""

& "$Root\.venv\Scripts\langgraph.exe" dev --allow-blocking --port 2024 --tunnel
