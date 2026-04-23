[CmdletBinding(SupportsShouldProcess = $true, PositionalBinding = $false)]
param(
    [string]$DefaultsPath = (Join-Path $PSScriptRoot '..\config\p4-init.defaults.json'),
    [string]$ConnectionConfigPath = (Join-Path $PSScriptRoot '..\config\p4-connection.json'),
    [string]$P4ExePath,
    [string]$Server,
    [string]$User,
    [string]$Password,
    [string]$ProjectStream,
    [string]$EngineStream,
    [string]$ProjectRoot,
    [string]$EngineRoot,
    [string]$ProjectClient,
    [string]$EngineClient,
    [switch]$InstallIfMissing,
    [switch]$SkipLogin,
    [switch]$Sync,
    [switch]$WriteConnectionConfig,
    [switch]$PersistPassword,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{
            Executable = $python.Source
            PrefixArgs = @()
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return [pscustomobject]@{
            Executable = $py.Source
            PrefixArgs = @('-3')
        }
    }

    throw 'Python is required to run p4-init. Install Python or ensure `python` or `py` is available on PATH.'
}

function Add-StringArgument {
    param(
        [System.Collections.Generic.List[string]]$Arguments,
        [string]$Name,
        [string]$Value
    )

    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        $Arguments.Add($Name)
        $Arguments.Add($Value)
    }
}

function Add-SwitchArgument {
    param(
        [System.Collections.Generic.List[string]]$Arguments,
        [string]$Name,
        [bool]$Enabled
    )

    if ($Enabled) {
        $Arguments.Add($Name)
    }
}

$python = Resolve-PythonCommand
$pythonScriptPath = Join-Path $PSScriptRoot 'p4-init.py'

if (-not (Test-Path -LiteralPath $pythonScriptPath)) {
    throw "Python implementation not found: $pythonScriptPath"
}

$launchArgs = [System.Collections.Generic.List[string]]::new()
foreach ($prefixArg in $python.PrefixArgs) {
    $launchArgs.Add($prefixArg)
}

$launchArgs.Add($pythonScriptPath)
Add-StringArgument -Arguments $launchArgs -Name '--defaults-path' -Value $DefaultsPath
Add-StringArgument -Arguments $launchArgs -Name '--connection-config-path' -Value $ConnectionConfigPath
Add-StringArgument -Arguments $launchArgs -Name '--p4-exe-path' -Value $P4ExePath
Add-StringArgument -Arguments $launchArgs -Name '--server' -Value $Server
Add-StringArgument -Arguments $launchArgs -Name '--user' -Value $User
Add-StringArgument -Arguments $launchArgs -Name '--password' -Value $Password
Add-StringArgument -Arguments $launchArgs -Name '--project-stream' -Value $ProjectStream
Add-StringArgument -Arguments $launchArgs -Name '--engine-stream' -Value $EngineStream
Add-StringArgument -Arguments $launchArgs -Name '--project-root' -Value $ProjectRoot
Add-StringArgument -Arguments $launchArgs -Name '--engine-root' -Value $EngineRoot
Add-StringArgument -Arguments $launchArgs -Name '--project-client' -Value $ProjectClient
Add-StringArgument -Arguments $launchArgs -Name '--engine-client' -Value $EngineClient
Add-SwitchArgument -Arguments $launchArgs -Name '--install-if-missing' -Enabled ([bool]$InstallIfMissing)
Add-SwitchArgument -Arguments $launchArgs -Name '--skip-login' -Enabled ([bool]$SkipLogin)
Add-SwitchArgument -Arguments $launchArgs -Name '--sync' -Enabled ([bool]$Sync)
Add-SwitchArgument -Arguments $launchArgs -Name '--write-connection-config' -Enabled ([bool]$WriteConnectionConfig)
Add-SwitchArgument -Arguments $launchArgs -Name '--persist-password' -Enabled ([bool]$PersistPassword)
Add-SwitchArgument -Arguments $launchArgs -Name '--force' -Enabled ([bool]$Force)
Add-SwitchArgument -Arguments $launchArgs -Name '--what-if' -Enabled ([bool]$WhatIfPreference)

$output = & $python.Executable @launchArgs 2>&1
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    $message = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($message)) {
        $message = "p4-init.py failed with exit code $exitCode."
    }
    throw $message
}

try {
    $json = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $result = $json | ConvertFrom-Json
}
catch {
    throw "Failed to parse JSON output from p4-init.py. Raw output: $json"
}

if ($result.PSObject.Properties.Name -contains 'warnings') {
    foreach ($warning in @($result.warnings)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$warning)) {
            Write-Warning $warning
        }
    }
}

if ($result.PSObject.Properties.Name -contains 'whatIfActions') {
    foreach ($action in @($result.whatIfActions)) {
        if ($null -eq $action) {
            continue
        }

        $description = [string]$action.description
        $target = [string]$action.target
        if (-not [string]::IsNullOrWhiteSpace($description) -and -not [string]::IsNullOrWhiteSpace($target)) {
            Write-Host "What if: Performing the operation `"$description`" on target `"$target`"."
        }
    }
}

$result | Select-Object * -ExcludeProperty warnings, whatIfActions
