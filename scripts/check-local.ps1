[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $Root "docker-compose.local.yml"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Failures = 0

function Report([string]$Name, [bool]$Healthy, [string]$Detail) {
    $color = if ($Healthy) { "Green" } else { "Red" }
    $mark = if ($Healthy) { "OK" } else { "FAIL" }
    Write-Host "[$mark] $Name - $Detail" -ForegroundColor $color
    if (-not $Healthy) { $script:Failures++ }
}

Set-Location $Root
docker info *> $null
$DockerCliHealthy = $LASTEXITCODE -eq 0
if ($DockerCliHealthy) {
    Report "Docker Engine" $true "Docker Desktop engine and CLI are available"
} else {
    Write-Host "[WARN] Docker CLI is unavailable in this terminal; probing local services directly" -ForegroundColor Yellow
}

if ($DockerCliHealthy) {
    docker compose -f $ComposeFile ps
    $MongoHealth = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" portfolio-rag-mongodb 2>$null
    if (-not $MongoHealth) { $MongoHealth = "container missing or stopped" }
    Report "MongoDB Atlas Local" ($LASTEXITCODE -eq 0 -and ($MongoHealth -eq "healthy" -or $MongoHealth -eq "running")) $MongoHealth
}

try {
    $Tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    $Names = @($Tags.models | ForEach-Object { $_.name })
    Report "Ollama" $true ("models: " + ($Names -join ", "))
} catch {
    Report "Ollama" $false $_.Exception.Message
}

if (Test-Path $Python) {
    $IndexState = & $Python scripts\local_status.py
    Report "Knowledge index" ($LASTEXITCODE -eq 0) "MongoDB collection and index inspection"
    if ($LASTEXITCODE -eq 0) { Write-Host "       $($IndexState | Select-Object -Last 1) (documents|index)" -ForegroundColor DarkGray }
} else {
    Report "Python environment" $false ".venv\\Scripts\\python.exe is missing"
}

$Streamlit = netstat -ano | Select-String -Pattern ":8505\s+.*LISTENING"
if ($Streamlit) {
    Write-Host "[OK] Streamlit - http://localhost:8505" -ForegroundColor Green
} else {
    Write-Host "[INFO] Streamlit - not running; start-local.ps1 launches it after checks" -ForegroundColor Yellow
}

if ($Failures -gt 0) { exit 1 }
