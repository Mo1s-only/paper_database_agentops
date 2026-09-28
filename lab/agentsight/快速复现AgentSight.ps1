[CmdletBinding()]
param(
    [string]$Distro = "Ubuntu",
    [string]$AgentSightRoot = "C:\Users\mobao\Desktop\agentsight",
    [string]$ArchiveRoot = "$PSScriptRoot\results\runs",
    [string]$SummaryRoot = "$PSScriptRoot\results\experiments",
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function ConvertTo-BashSingleQuoted {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value.Contains("'")) {
        throw "路径不能包含单引号：$Value"
    }
    return "'" + $Value + "'"
}

function Copy-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function Test-RunAlreadyArchived {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$RawRoot
    )

    $sourceDb = Join-Path $Source "session.db"
    if (-not (Test-Path -LiteralPath $sourceDb)) {
        return $false
    }
    $sourceHash = (Get-FileHash -LiteralPath $sourceDb -Algorithm SHA256).Hash
    foreach ($directory in Get-ChildItem -LiteralPath $RawRoot -Directory -ErrorAction SilentlyContinue) {
        $candidateDb = Join-Path $directory.FullName "session.db"
        if ((Test-Path -LiteralPath $candidateDb) -and
            (Get-FileHash -LiteralPath $candidateDb -Algorithm SHA256).Hash -eq $sourceHash) {
            return $true
        }
    }
    return $false
}

function Write-ExperimentDocument {
    param(
        [Parameter(Mandatory = $true)][string]$ExperimentId,
        [Parameter(Mandatory = $true)][string]$RawPath,
        [Parameter(Mandatory = $true)][string]$DocumentRoot,
        [Parameter(Mandatory = $true)][string]$Purpose,
        [Parameter(Mandatory = $true)][string]$Status
    )

    $rowCounts = @{}
    $rowFile = Join-Path $RawPath "db-rows.txt"
    if (Test-Path -LiteralPath $rowFile) {
        foreach ($line in Get-Content -LiteralPath $rowFile) {
            if ($line -match '^\s*([a-z_]+)\s+(\d+)') {
                $rowCounts[$matches[1]] = [int]$matches[2]
            }
        }
    }
    $auditFile = Join-Path $RawPath "report-audit.txt"
    $orphanCount = if (Test-Path -LiteralPath $auditFile) {
        @(Select-String -LiteralPath $auditFile -Pattern 'orphan_response').Count
    } else { 0 }
    $verificationFile = Join-Path $RawPath "verification.txt"
    $verification = if (Test-Path -LiteralPath $verificationFile) {
        $match = Select-String -LiteralPath $verificationFile -Pattern 'passed \d+, failed \d+' |
            Select-Object -Last 1
        if ($match) { $match.Matches.Value } else { "未记录" }
    } else { "未单独保存；请查运行终端" }

    $documentDirectory = Join-Path $DocumentRoot $ExperimentId
    New-Item -ItemType Directory -Path $documentDirectory -Force | Out-Null
    $document = @"
# AgentSight 实验结果｜$ExperimentId

| 字段 | 值 |
|---|---|
| 实验 ID | ``$ExperimentId`` |
| 目的 | $Purpose |
| 状态 | ``$Status`` |
| 验证 | $verification |
| ``process_nodes`` | $($rowCounts['process_nodes']) |
| ``audit_events`` | $($rowCounts['audit_events']) |
| ``llm_calls`` | $($rowCounts['llm_calls']) |
| ``token_usage`` | $($rowCounts['token_usage']) |
| ``tool_calls`` | $($rowCounts['tool_calls']) |
| ``network_targets`` | $($rowCounts['network_targets']) |
| ``orphan_response`` | $orphanCount |

## 证据边界

- ``VERIFIED``：本文档中的数量来自该实验独立目录中的 ``db-rows.txt`` 和 ``report-audit.txt``。
- ``UNVERIFIED``：观测链路通过不等于 request—response 已完整配对，也不等于故障归因已达标。

## 原始证据

```text
lab/agentsight/results/runs/$ExperimentId/
```

本文档只对应这一次运行，后续实验必须创建新的实验 ID 和新文档。
"@
    Set-Content -LiteralPath (Join-Path $documentDirectory "实验结果.md") -Value $document -Encoding utf8
}

$resolvedAgentSightRoot = (Resolve-Path -LiteralPath $AgentSightRoot).Path
$testRoot = Join-Path $resolvedAgentSightRoot "test"
$runScript = Join-Path $testRoot "run-test.sh"
$verifyScript = Join-Path $testRoot "verify.sh"
$envFile = Join-Path $testRoot ".env"
$outRoot = Join-Path $testRoot "out"

foreach ($requiredPath in @($testRoot, $runScript, $verifyScript, $envFile)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "缺少必需文件：$requiredPath"
    }
}

$distroNames = @(& wsl.exe --list --quiet 2>$null) |
    ForEach-Object { ($_ -replace "`0", "").Trim() } |
    Where-Object { $_ }
if ($Distro -notin $distroNames) {
    throw "找不到 WSL 发行版 '$Distro'。当前可用：$($distroNames -join ', ')"
}

$portableTestRoot = $testRoot.Replace("\", "/")
$wslTestRoot = (& wsl.exe -d $Distro -u root -- wslpath -a $portableTestRoot 2>$null |
    ForEach-Object { ($_ -replace "`0", "").Trim() } |
    Select-Object -Last 1)
if (-not $wslTestRoot) {
    throw "无法把测试目录转换为 WSL 路径：$testRoot"
}
$quotedTestRoot = ConvertTo-BashSingleQuoted $wslTestRoot

$preflight = @"
set -euo pipefail
cd $quotedTestRoot
test "`$(uname -s)" = Linux
test "`$(id -u)" = 0
test -f .env
command -v agentsight >/dev/null
command -v claude >/dev/null
test -d /sys/kernel/tracing/events/sched/sched_process_exec || mount -t tracefs tracefs /sys/kernel/tracing
test -d /sys/kernel/tracing/events/sched/sched_process_exec
printf 'kernel=%s\n' "`$(uname -r)"
printf 'agentsight=%s\n' "`$(agentsight --version)"
printf 'claude=%s\n' "`$(claude --version 2>&1 | head -1)"
printf 'credential_file=present\n'
"@

Write-Host "[1/4] 检查 WSL、eBPF、AgentSight、Claude 和凭据文件..."
& wsl.exe -d $Distro -u root -- bash -lc $preflight
if ($LASTEXITCODE -ne 0) {
    throw "预检失败，请根据上方输出修复环境。"
}

if ($PreflightOnly) {
    Write-Host "预检通过；未调用模型，也未改动实验输出。"
    exit 0
}

$timestamp = Get-Date -Format "yyyyMMddTHHmmss"
$resolvedArchiveRoot = [System.IO.Path]::GetFullPath($ArchiveRoot)
$archiveBase = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "results\runs"))
if (-not $resolvedArchiveRoot.StartsWith($archiveBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "归档目录必须位于 $archiveBase 内，当前为 $resolvedArchiveRoot"
}
New-Item -ItemType Directory -Path $resolvedArchiveRoot -Force | Out-Null
$resolvedSummaryRoot = [System.IO.Path]::GetFullPath($SummaryRoot)
$summaryBase = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "results\experiments"))
if (-not $resolvedSummaryRoot.StartsWith($summaryBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "结果文档目录必须位于 $summaryBase 内，当前为 $resolvedSummaryRoot"
}
New-Item -ItemType Directory -Path $resolvedSummaryRoot -Force | Out-Null

if (Test-Path -LiteralPath $outRoot) {
    if (Test-RunAlreadyArchived -Source $outRoot -RawRoot $resolvedArchiveRoot) {
        Write-Host "[2/4] 旧 out 已有相同 session.db 归档，跳过重复复制。"
    } else {
        $existingTime = (Get-Item -LiteralPath $outRoot).LastWriteTime.ToString("yyyyMMddTHHmmss")
        $existingId = "${existingTime}_agentsight_e2e_imported"
        $existingArchive = Join-Path $resolvedArchiveRoot $existingId
        Write-Host "[2/4] 把未归档的旧 out 作为独立实验保存到 $existingArchive"
        Copy-DirectoryContents -Source $outRoot -Destination $existingArchive
        Write-ExperimentDocument -ExperimentId $existingId -RawPath $existingArchive `
            -DocumentRoot $resolvedSummaryRoot -Purpose "运行前发现的未归档历史结果" -Status "IMPORTED"
    }
} else {
    Write-Host "[2/4] 当前没有旧 out，跳过运行前归档。"
}

$runCommand = @"
set -euo pipefail
cd $quotedTestRoot
chmod +x ./run-test.sh ./verify.sh
./run-test.sh
./verify.sh | tee ./out/verification.txt
"@

Write-Host "[3/4] 在 WSL '$Distro' 中运行 AgentSight 端到端实验..."
& wsl.exe -d $Distro -u root -- bash -lc $runCommand
if ($LASTEXITCODE -ne 0) {
    throw "实验或验证失败。原始输出仍保留在 $outRoot"
}

$experimentId = "${timestamp}_agentsight_e2e"
$runArchive = Join-Path $resolvedArchiveRoot $experimentId
Write-Host "[4/4] 归档本次结果到 $runArchive"
Copy-DirectoryContents -Source $outRoot -Destination $runArchive

$runInfo = @(
    "timestamp_local=$timestamp"
    "wsl_distro=$Distro"
    "source_test_root=$testRoot"
    "result=passed"
) -join [Environment]::NewLine
Set-Content -LiteralPath (Join-Path $runArchive "run-info.txt") -Value $runInfo -Encoding utf8
Write-ExperimentDocument -ExperimentId $experimentId -RawPath $runArchive `
    -DocumentRoot $resolvedSummaryRoot -Purpose "AgentSight 端到端快速复现" -Status "VERIFIED"

Write-Host ""
Write-Host "复现完成：run-test.sh 与 verify.sh 均通过。"
Write-Host "结果目录：$runArchive"
Write-Host "结果文档：$(Join-Path $resolvedSummaryRoot "$experimentId\实验结果.md")"
Write-Host "重点查看：record.log、db-rows.txt、report-audit.txt、report-token.txt、session.db"
