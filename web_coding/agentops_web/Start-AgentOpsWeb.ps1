param([ValidateRange(1024,65535)][int]$Port = 3017)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    if ($health.platform -eq 'agentops-web') {
        Write-Host "AgentOps Web is already running: http://127.0.0.1:$Port/overview"
        exit 0
    }
} catch { }
$runtime = Get-Command node -ErrorAction SilentlyContinue
if (-not $runtime) { throw 'Node.js is required. Install Node.js and reopen PowerShell.' }
$nodeMajor = [int]((& $runtime.Source --version).TrimStart('v').Split('.')[0])
if ($nodeMajor -lt 24) { throw 'Node.js 24 or later is required for the local SQLite store.' }
if (-not (Test-Path -LiteralPath 'node_modules/next/dist/bin/next')) { throw 'Dependencies are missing. Run pnpm install in this directory first.' }
Write-Host "AgentOps Web: http://127.0.0.1:$Port/overview"
Write-Host 'Keep this terminal open. Press Ctrl+C to stop the preview.'
& $runtime.Source 'node_modules/next/dist/bin/next' dev --hostname 127.0.0.1 --port $Port
exit $LASTEXITCODE
