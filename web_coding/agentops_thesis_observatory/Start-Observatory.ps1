param(
    [ValidateRange(1024,65525)][int]$Port = 8780,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$SiteRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $SiteRoot 'runtime'
New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
$Python = (Get-Command python -ErrorAction Stop).Source
$ServerScript = Join-Path $SiteRoot 'server.py'
function Get-PlatformHealth([int]$Candidate) {
    try { return Invoke-RestMethod -Uri "http://127.0.0.1:$Candidate/api/health" -TimeoutSec 1 } catch { return $null }
}
function Test-Port([int]$Candidate) {
    $Client = New-Object System.Net.Sockets.TcpClient
    try { $Pending = $Client.BeginConnect('127.0.0.1',$Candidate,$null,$null); if (-not $Pending.AsyncWaitHandle.WaitOne(200)) { return $false }; $Client.EndConnect($Pending); return $true } catch { return $false } finally { $Client.Dispose() }
}
$SelectedPort = $null
# Reuse our own version before selecting another free port.
foreach ($Candidate in $Port..($Port+10)) {
    $Health = Get-PlatformHealth $Candidate
    if ($Health -and $Health.platform -eq 'agentops-observatory' -and $Health.version -eq '2.0' -and $Health.workspace -eq $SiteRoot) { $SelectedPort=$Candidate; break }
}
if ($null -eq $SelectedPort) {
    foreach ($Candidate in $Port..($Port+10)) { if (-not (Test-Port $Candidate)) { $SelectedPort=$Candidate; break } }
    if ($null -eq $SelectedPort) { throw 'No available local port.' }
    $Arguments = '-u "{0}" --port {1}' -f $ServerScript,$SelectedPort
    Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $SiteRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RuntimeRoot 'server.log') -RedirectStandardError (Join-Path $RuntimeRoot 'server-error.log') | Out-Null
    $Ready=$false
    foreach ($Attempt in 1..45) {
        Start-Sleep -Milliseconds 500
        $Health=Get-PlatformHealth $SelectedPort
        if($Health -and $Health.platform -eq 'agentops-observatory' -and $Health.version -eq '2.0') { $Ready=$true; break }
    }
    if(-not $Ready) { throw 'Startup failed. See runtime/server-error.log.' }
}
$Address="http://127.0.0.1:$SelectedPort/"
if(-not $NoBrowser) { Start-Process $Address }
Write-Output "Observatory 2 ready: $Address"
