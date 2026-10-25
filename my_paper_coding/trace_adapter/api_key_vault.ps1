param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Add", "List", "RunCanary", "RunScenario", "RunDatasetReplay")]
    [string]$Action,

    [string]$Alias,

    [ValidateSet("deepseek")]
    [string]$Provider = "deepseek",

    [string]$Model = "deepseek-flash",

    [string]$RunId,

    [ValidateSet("routing-error-v1", "error-propagation-v1")]
    [string]$Scenario,

    [ValidateSet("AgentTrace", "WhoAndWhen", "TRAIL")]
    [string]$Dataset,

    [string]$SampleId,

    [ValidateSet("agent_a", "agent_b")]
    [string[]]$Agents = @("agent_a"),

    [switch]$BothAgents,

    [ValidateRange(0.001, 0.05)]
    [double]$CliSoftBudgetUsd = 0.04,

    [switch]$IgnoreCumulativeBudget
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
    throw "This vault uses Windows CurrentUser DPAPI; run it with PowerShell 7 (pwsh) on Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$vaultDirectory = Join-Path $repoRoot "my_paper_coding\experiment_control\.secrets"
$vaultPath = Join-Path $vaultDirectory "api_keys.dpapi.json"
$allowedRunRoot = Join-Path $repoRoot "lab\experiment\experiment_20261021_24_agentsight_candidate_mock"

function Protect-VaultDirectory {
    if (-not (Test-Path -LiteralPath $vaultDirectory)) {
        New-Item -ItemType Directory -Path $vaultDirectory -Force | Out-Null
    }

    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner($currentSid)
    foreach ($sid in @($currentSid, $systemSid)) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit,
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $vaultDirectory -AclObject $acl
}

function Read-Vault {
    if (-not (Test-Path -LiteralPath $vaultPath)) {
        return @{ schema_version = 1; entries = @{} }
    }
    $vault = Get-Content -LiteralPath $vaultPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if ($vault.schema_version -ne 1 -or $null -eq $vault.entries) {
        throw "Unsupported or malformed API-key vault."
    }
    return $vault
}

function Write-Vault($vault) {
    Protect-VaultDirectory
    $json = ConvertTo-Json -InputObject $vault -Depth 8
    [System.IO.File]::WriteAllText($vaultPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $fileAcl = [System.Security.AccessControl.FileSecurity]::new()
    $fileAcl.SetAccessRuleProtection($true, $false)
    $fileAcl.SetOwner($currentSid)
    foreach ($sid in @($currentSid, $systemSid)) {
        $fileAcl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        ))
    }
    Set-Acl -LiteralPath $vaultPath -AclObject $fileAcl
}

function Assert-Alias([string]$value) {
    if ($value -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$') {
        throw "Alias must be 1-32 characters: letters, digits, dot, underscore, or hyphen."
    }
}

switch ($Action) {
    "Add" {
        Assert-Alias $Alias
        if ([string]::IsNullOrWhiteSpace($Model) -or $Model.Length -gt 80) {
            throw "Model alias must be between 1 and 80 characters."
        }
        $vault = Read-Vault
        if ($vault.entries.ContainsKey($Alias)) {
            $answer = Read-Host "Alias '$Alias' exists. Replace its key? Type YES to continue"
            if ($answer -cne "YES") { throw "Alias replacement cancelled." }
        }
        $secureKey = Read-Host "Enter the newly rotated $Provider API key (input hidden)" -AsSecureString
        if ($secureKey.Length -lt 8) { throw "Key input is empty or unexpectedly short." }
        $ciphertext = ConvertFrom-SecureString -SecureString $secureKey
        $vault.entries[$Alias] = @{
            provider = $Provider
            model = $Model
            encrypted_key = $ciphertext
            created_utc = [DateTime]::UtcNow.ToString("o")
        }
        Write-Vault $vault
        Write-Output "Saved encrypted key alias '$Alias' ($Provider / $Model). The key itself was not displayed or written in plaintext."
    }
    "List" {
        $vault = Read-Vault
        $rows = foreach ($name in ($vault.entries.Keys | Sort-Object)) {
            $entry = $vault.entries[$name]
            [pscustomobject]@{ Alias = $name; Provider = $entry.provider; Model = $entry.model }
        }
        if ($rows) { $rows | Format-Table -AutoSize } else { Write-Output "No API-key aliases have been stored yet." }
    }
    { $_ -in @("RunCanary", "RunScenario", "RunDatasetReplay") } {
        Assert-Alias $Alias
        if ($Action -eq "RunDatasetReplay") {
            if (-not $RunId -or $RunId -notmatch '^dataset-20261022-(agenttrace|whoandwhen|trail)-01$') {
                throw "Dataset RunId must be a pinned dataset-20261022-<family>-01 identifier."
            }
            if (-not $Dataset -or -not $SampleId) { throw "Dataset and SampleId are required for replay." }
            $outputRelative = "lab/experiment/public_dataset_cross_layer_20261022/$RunId"
        } else {
            if (-not $RunId -or $RunId -notmatch '^real-canary-[0-9]{8}-[0-9]+$') {
                throw "RunId must look like real-canary-YYYYMMDD-N."
            }
            $outputRelative = "lab/experiment/experiment_20261021_24_agentsight_candidate_mock/$RunId"
        }
        $vault = Read-Vault
        if (-not $vault.entries.ContainsKey($Alias)) { throw "Unknown API-key alias '$Alias'. Use List to inspect saved aliases." }
        $entry = $vault.entries[$Alias]
        if ($entry.provider -ne "deepseek") { throw "This canary currently supports only DeepSeek aliases." }

        $outputWindows = Join-Path $repoRoot ($outputRelative -replace '/', '\')
        if (Test-Path -LiteralPath $outputWindows) { throw "Refusing to overwrite existing run: $outputWindows" }

        $repoWsl = (& wsl.exe -d Ubuntu --exec wslpath -a $repoRoot | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $repoWsl.StartsWith("/mnt/")) { throw "Could not resolve the thesis workspace inside Ubuntu WSL." }

        $oldKey = $env:DEEPSEEK_API_KEY
        $oldAuthToken = $env:ANTHROPIC_AUTH_TOKEN
        $oldBaseUrl = $env:ANTHROPIC_BASE_URL
        $oldModel = $env:ANTHROPIC_MODEL
        $oldWslEnv = $env:WSLENV
        $plainKey = $null
        $bstr = [IntPtr]::Zero
        try {
            $secureKey = ConvertTo-SecureString $entry.encrypted_key
            $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
            $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
            $bstr = [IntPtr]::Zero

            $env:DEEPSEEK_API_KEY = $plainKey
            $env:ANTHROPIC_AUTH_TOKEN = $plainKey
            $env:ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
            $env:ANTHROPIC_MODEL = $entry.model
            $forwardNames = @("DEEPSEEK_API_KEY/u", "ANTHROPIC_AUTH_TOKEN/u", "ANTHROPIC_BASE_URL/u", "ANTHROPIC_MODEL/u")
            $existingNames = @($oldWslEnv -split ':' | Where-Object { $_ })
            foreach ($name in $forwardNames) {
                if (($existingNames | ForEach-Object { $_ -replace '/.*$', '' }) -notcontains ($name -replace '/.*$', '')) {
                    $existingNames += $name
                }
            }
            $env:WSLENV = $existingNames -join ':'

            if ($Action -eq "RunDatasetReplay") {
                if ($CliSoftBudgetUsd -gt 0.025) { throw "Dataset replay session soft cap must be no more than $0.025." }
                $replayScript = "$repoWsl/my_paper_coding/trace_adapter/capture_public_dataset_replay.py"
                $agentsightBin = "$repoWsl/lab/agentsight/source/thesis_adapter/collector/target/release/agentsight"
                $bashCommand = "cd '$repoWsl' && python3 '$replayScript' --output '$outputRelative' --dataset '$Dataset' --sample-id '$SampleId' --agentsight-bin '$agentsightBin' --per-session-budget '$([string]$CliSoftBudgetUsd)' --incremental-cap-cny 1.0"
            } elseif ($Action -eq "RunScenario") {
                $scenarioScript = "$repoWsl/my_paper_coding/trace_adapter/capture_real_scenarios.py"
                $agentsightBin = "$repoWsl/lab/agentsight/source/thesis_adapter/collector/target/release/agentsight"
                if ($Scenario -eq "error-propagation-v1") {
                    $cumulativeManifest = "$repoWsl/my_paper_coding/experiment_control/real-api-error-propagation-20261021-run12.json"
                    $cumulativeLedger = "$repoWsl/my_paper_coding/experiment_control/cost-ledger-through-run11-20261021.json"
                    $agentList = if ($BothAgents) { "agent_a agent_b" } else { $Agents -join " " }
                } else {
                    $cumulativeManifest = "$repoWsl/my_paper_coding/experiment_control/real-api-routing-error-single-20261021.json"
                    $cumulativeLedger = "$repoWsl/my_paper_coding/experiment_control/cost-ledger-through-run10-20261021.json"
                    $agentList = if ($BothAgents) { "agent_a agent_b" } else { "agent_a" }
                }
                $manifestPath = Join-Path $repoRoot ($cumulativeManifest.Substring($repoWsl.Length + 1) -replace '/', '\')
                $manifestData = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
                # The cumulative manifest is a historical budget artifact; its
                # collector hash can be stale. Pin against the newest completed
                # run's recorded binary identity without rewriting that history.
                $latestRun = Get-ChildItem -LiteralPath $allowedRunRoot -Directory |
                    Where-Object { $_.Name -match '^real-canary-[0-9]{8}-[0-9]+$' } |
                    Sort-Object { [long]($_.Name -replace '^real-canary-[0-9]{8}-', '') } -Descending |
                    Select-Object -First 1
                if ($null -eq $latestRun) { throw "No completed AgentSight run is available to pin the collector binary." }
                $latestVersionsPath = Join-Path $latestRun.FullName "versions.json"
                if (-not (Test-Path -LiteralPath $latestVersionsPath)) { throw "Latest run lacks versions.json; refusing to infer the collector identity." }
                $latestVersions = Get-Content -LiteralPath $latestVersionsPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $expectedAgentsightSha256 = [string]$latestVersions.agentsight_binary.sha256
                if ($expectedAgentsightSha256 -notmatch '^[A-Fa-f0-9]{64}$') {
                    throw "Latest completed run lacks agentsight_binary.sha256; refusing API launch."
                }
                if ([string]$manifestData.historical_ledger_status -eq "UNVERIFIED_RAW_LOGS") {
                    Write-Warning "Historical cumulative spend remains unverified against raw logs; preserving that uncertainty in the run plan."
                }
                $bashCommand = "cd '$repoWsl' && python3 '$scenarioScript' --output '$outputRelative' --scenario '$Scenario' --agents $agentList --agentsight-bin '$agentsightBin' --expected-agentsight-sha256 '$expectedAgentsightSha256' --per-session-budget '$([string]$CliSoftBudgetUsd)' --experiment-cost-cap-cny 2.0 --planning-usd-cny-rate 10.0 --cumulative-manifest '$cumulativeManifest' --cumulative-ledger '$cumulativeLedger'"
                if ($IgnoreCumulativeBudget) { $bashCommand += " --ignore-cumulative-budget" }
                $bashCommand += " --tool-id-bridge"
            } else {
                $bashScript = "$repoWsl/my_paper_coding/trace_adapter/run_deepseek_real_canary.sh"
                $ignoreBudgetArg = if ($IgnoreCumulativeBudget) { " --ignore-cumulative-budget" } else { "" }
                $bashCommand = "cd '$repoWsl' && bash '$bashScript' '$outputRelative' '$([string]$CliSoftBudgetUsd)'$ignoreBudgetArg"
            }
            & wsl.exe -d Ubuntu -u root --exec /bin/bash -lc $bashCommand
            $runExitCode = $LASTEXITCODE
        }
        finally {
            if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
            Remove-Item Env:\DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
            Remove-Item Env:\ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue
            Remove-Item Env:\ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
            Remove-Item Env:\ANTHROPIC_MODEL -ErrorAction SilentlyContinue
            if ($null -ne $oldKey) { $env:DEEPSEEK_API_KEY = $oldKey }
            if ($null -ne $oldAuthToken) { $env:ANTHROPIC_AUTH_TOKEN = $oldAuthToken }
            if ($null -ne $oldBaseUrl) { $env:ANTHROPIC_BASE_URL = $oldBaseUrl }
            if ($null -ne $oldModel) { $env:ANTHROPIC_MODEL = $oldModel }
            if ($null -ne $oldWslEnv) { $env:WSLENV = $oldWslEnv } else { Remove-Item Env:\WSLENV -ErrorAction SilentlyContinue }
            $plainKey = $null
        }
        exit $runExitCode
    }
}
