# brojs-agent: LangGraph API + Deep Agents UI
# https://github.com/langchain-ai/deep-agents-ui
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"

$UiDir = Join-Path $Root "deep-agents-ui"
$EnvLocal = Join-Path $UiDir ".env.local"
$EnvExample = Join-Path $UiDir ".env.local.example"

if (-not (Test-Path (Join-Path $UiDir "package.json"))) {
    Write-Error "deep-agents-ui not found. Run git pull."
}

if (-not (Test-Path $EnvLocal) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvLocal
    Write-Host "Created deep-agents-ui/.env.local"
}

function Invoke-UiInstall {
    param([string]$Dir)
    Push-Location $Dir
    if (Get-Command yarn -ErrorAction SilentlyContinue) {
        yarn install
    } else {
        Write-Host "Using npm install --legacy-peer-deps"
        npm install --legacy-peer-deps
    }
    Pop-Location
}

function Invoke-UiDev {
    param([string]$Dir)
    Push-Location $Dir
    if (Get-Command yarn -ErrorAction SilentlyContinue) {
        yarn dev
    } else {
        npm run dev
    }
    Pop-Location
}

if (-not (Test-Path (Join-Path $UiDir "node_modules"))) {
    Write-Host "Installing deep-agents-ui dependencies..."
    Invoke-UiInstall $UiDir
}

Write-Host ""
Write-Host "LangGraph API:  http://127.0.0.1:2024"
Write-Host "Deep Agents UI: http://localhost:3000"
Write-Host "Assistant ID:   agent"
Write-Host "Pipeline CLI:   .venv\Scripts\python scripts\run_pipeline.py"
Write-Host ""

$lg = Start-Process -FilePath "$Root\.venv\Scripts\langgraph.exe" `
    -ArgumentList "dev", "--allow-blocking", "--port", "2024" `
    -WorkingDirectory $Root -PassThru -NoNewWindow

Write-Host "Waiting for LangGraph API..."
Start-Sleep -Seconds 8

$apiOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:2024/docs" -UseBasicParsing -TimeoutSec 3
    $apiOk = $r.StatusCode -eq 200
} catch {
    $apiOk = $false
}

if (-not $apiOk) {
    Write-Host "WARNING: API on port 2024 is not responding. UI will show Failed to fetch."
}

try {
    Invoke-UiDev $UiDir
} finally {
    if ($lg -and -not $lg.HasExited) {
        Stop-Process -Id $lg.Id -Force -ErrorAction SilentlyContinue
    }
}
