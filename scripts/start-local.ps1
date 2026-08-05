[CmdletBinding()]
param(
    [switch]$Reindex,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $Root "docker-compose.local.yml"
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$Python = Join-Path $Root ".venv\Scripts\python.exe"

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Get-DotEnvValue([string]$Name, [string]$Default = "") {
    if (-not (Test-Path $EnvFile)) { return $Default }
    $prefix = "$Name="
    $line = Get-Content -LiteralPath $EnvFile | Where-Object { $_.StartsWith($prefix) } | Select-Object -Last 1
    if (-not $line) { return $Default }
    return $line.Substring($prefix.Length).Trim().Trim('"').Trim("'")
}

function Add-DotEnvDefault([string]$Name, [string]$Value) {
    if (-not (Get-Content -LiteralPath $EnvFile | Where-Object { $_.StartsWith("$Name=") })) {
        Add-Content -LiteralPath $EnvFile -Value "$Name=$Value" -Encoding utf8
    }
}

function Wait-ForContainerHealth([string]$Name, [int]$TimeoutSeconds = 240) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $Name 2>$null
        if ($LASTEXITCODE -eq 0 -and ($status -eq "healthy" -or $status -eq "running")) {
            Write-Host "$Name is $status." -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "$Name did not become healthy within $TimeoutSeconds seconds. Run: docker logs $Name"
}

function Pull-DockerImage([string]$Image, [int]$Attempts = 3) {
    docker image inspect $Image *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Using local image $Image." -ForegroundColor Green
        return
    }
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        docker pull $Image
        if ($LASTEXITCODE -eq 0) { return }
        if ($attempt -eq $Attempts) { break }
        Write-Host "Image download failed for $Image (attempt $attempt/$Attempts). Retrying in 8 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 8
    }
    throw "Could not download $Image after $Attempts attempts. Check Docker Desktop network/proxy settings and retry."
}

Set-Location $Root

Write-Step "Checking local prerequisites"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and open Docker Desktop first."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop Engine is not running. Open Docker Desktop and wait for 'Engine running'."
}
if (-not (Test-Path $Python)) {
    throw "Python environment is missing at .venv. Create it with 'uv sync' before starting the app."
}

$Listener = Get-NetTCPConnection -LocalPort 8505 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($Listener) {
    $ListenerProcess = Get-Process -Id $Listener.OwningProcess -ErrorAction SilentlyContinue
    $ProcessName = if ($ListenerProcess) { $ListenerProcess.ProcessName } else { "unknown" }
    $Hint = if ($ProcessName -match "python|streamlit") {
        "This is likely an older Streamlit process. Stop its terminal with Ctrl+C, then run this script again."
    } else {
        "The script will not stop an unknown process automatically. Close it or configure another port."
    }
    throw "Port 8505 is already used by PID $($Listener.OwningProcess) ($ProcessName). $Hint"
}

$Branch = git branch --show-current 2>$null
$Commit = git rev-parse --short HEAD 2>$null
if ($LASTEXITCODE -eq 0 -and $Commit) {
    Write-Host "Source version: $Branch@$Commit" -ForegroundColor Green
} else {
    Write-Host "Source version: Git metadata unavailable; continuing with the current files." -ForegroundColor Yellow
}

Write-Step "Checking Streamlit page imports"
& $Python scripts\check_streamlit_pages.py
if ($LASTEXITCODE -ne 0) {
    throw "Streamlit UI preflight failed. Fix the reported import or render error before starting local services."
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
}
Add-DotEnvDefault "LOCAL_MONGODB_URI" "mongodb://localhost:62262/?directConnection=true"
Add-DotEnvDefault "LOCAL_COLLECTION_NAME" "portfolio_knowledge_local"
Add-DotEnvDefault "OLLAMA_BASE_URL" "http://localhost:11434"
Add-DotEnvDefault "OLLAMA_MODEL" "qwen2.5:3b"
$Model = Get-DotEnvValue "OLLAMA_MODEL" "qwen2.5:3b"

Write-Step "Starting MongoDB Atlas Local and Ollama"
Pull-DockerImage "mongodb/mongodb-atlas-local:latest"
Pull-DockerImage "ollama/ollama:latest"
docker compose -f $ComposeFile up -d --pull never
if ($LASTEXITCODE -ne 0) { throw "Docker Compose could not start the downloaded local services." }
Wait-ForContainerHealth "portfolio-rag-mongodb"
Wait-ForContainerHealth "portfolio-rag-ollama"

Write-Step "Ensuring Ollama model $Model"
$InstalledModels = docker exec portfolio-rag-ollama ollama list
if ($LASTEXITCODE -ne 0) { throw "Could not read the Ollama model list." }
if (-not ($InstalledModels | Select-String -SimpleMatch $Model -Quiet)) {
    Write-Host "First run: downloading $Model. This can take several minutes." -ForegroundColor Yellow
    docker exec portfolio-rag-ollama ollama pull $Model
    if ($LASTEXITCODE -ne 0) { throw "Ollama could not download $Model." }
}

Write-Step "Checking the local vector and text indexes"
$IndexState = & $Python scripts\local_status.py
if ($LASTEXITCODE -ne 0) { throw "Could not inspect the local MongoDB collection." }
$VectorReady = $IndexState | Select-String -Pattern "^vector=[1-9][0-9]*\|READY$" -Quiet
$TextReady = $IndexState | Select-String -Pattern "^text=[1-9][0-9]*\|READY$" -Quiet
$NeedsIndex = $Reindex -or -not ($VectorReady -and $TextReady)
if ($NeedsIndex) {
    Write-Host "Building embeddings plus Vector Search and BM25 text indexes." -ForegroundColor Yellow
    & $Python scripts\ingest.py
    if ($LASTEXITCODE -ne 0) { throw "Local ingestion failed." }
} else {
    Write-Host "Existing local retrieval indexes are ready ($($IndexState -join ', '))." -ForegroundColor Green
}

if (-not $SkipSmokeTest) {
    Write-Step "Running the end-to-end smoke test"
    & $Python scripts\smoke_test.py
    if ($LASTEXITCODE -ne 0) { throw "The local smoke test failed." }
}

Write-Step "Starting Streamlit"
Write-Host "Open http://localhost:8505" -ForegroundColor Green
Write-Host "Keep this terminal open. Press Ctrl+C to stop Streamlit." -ForegroundColor DarkGray
& $Python -m streamlit run app.py --server.port 8505
