# LangGraph dev + tunnel for LangSmith Studio (Chrome PNA / mixed content fix)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"

Write-Host ""
Write-Host "brojs-agent Studio"
Write-Host "  1) Server: http://127.0.0.1:2024"
Write-Host "  2) After start, copy the https://....trycloudflare.com URL from this terminal"
Write-Host "  3) Open https://smith.langchain.com/studio/"
Write-Host "     -> Connect to a local server -> paste tunnel URL"
Write-Host ""
Write-Host "Chrome only (localhost): lock icon on smith.langchain.com -> Local network access -> Allow"
Write-Host ""

& "$Root\.venv\Scripts\langgraph.exe" dev --allow-blocking --port 2024 --tunnel
