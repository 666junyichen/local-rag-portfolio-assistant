[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $Root "docker-compose.local.yml"

Set-Location $Root
docker compose -f $ComposeFile stop
if ($LASTEXITCODE -ne 0) { throw "Could not stop the local RAG containers." }
Write-Host "Local RAG containers stopped. MongoDB data and Ollama models were preserved." -ForegroundColor Green
Write-Host "Press Ctrl+C in the Streamlit terminal if it is still running." -ForegroundColor DarkGray
