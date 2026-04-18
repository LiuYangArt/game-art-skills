[CmdletBinding(SupportsShouldProcess = $true, PositionalBinding = $false)]
param(
    [string]$DefaultsPath = (Join-Path $PSScriptRoot '..\config\p4-init.defaults.json'),
    [string]$ConnectionConfigPath = (Join-Path $PSScriptRoot '..\config\p4-connection.json'),
    [string]$Server,
    [string]$User,
    [string]$Password,
    [string]$ProjectStream,
    [string]$EngineStream,
    [string]$ProjectRoot,
    [string]$EngineRoot,
    [string]$ProjectClient,
    [string]$EngineClient,
    [string]$Charset,
    [switch]$InstallIfMissing,
    [switch]$SkipLogin,
    [switch]$Sync,
    [switch]$WriteConnectionConfig,
    [switch]$PersistPassword,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ConfigValue {
    param(
        [pscustomobject]$Object,
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-StreamLeaf {
    param([string]$Stream)

    if ([string]::IsNullOrWhiteSpace($Stream)) {
        return ''
    }

    return ($Stream.TrimEnd('/') -split '/')[-1]
}

function Expand-WorkspacePattern {
    param(
        [string]$Pattern,
        [string]$ResolvedUser,
        [string]$Leaf
    )

    if ([string]::IsNullOrWhiteSpace($Pattern)) {
        return ''
    }

    return $Pattern.Replace('{user}', $ResolvedUser).Replace('{computer}', $env:COMPUTERNAME).Replace('{leaf}', $Leaf)
}

function Ensure-P4Installed {
    param([string]$WingetId)

    $command = Get-Command p4 -ErrorAction SilentlyContinue
    if ($command) {
        return $command
    }

    if (-not $InstallIfMissing) {
        throw 'p4 was not found on PATH. Re-run with -InstallIfMissing or install Perforce.P4V first.'
    }

    if ([string]::IsNullOrWhiteSpace($WingetId)) {
        $WingetId = 'Perforce.P4V'
    }

    if ($PSCmdlet.ShouldProcess($WingetId, 'Install P4V with winget')) {
        & winget install -e --id $WingetId
        if ($LASTEXITCODE -ne 0) {
            throw 'winget install failed.'
        }
    }

    $command = Get-Command p4 -ErrorAction SilentlyContinue
    if (-not $command) {
        throw 'p4 is still unavailable after install attempt.'
    }

    return $command
}

function Test-ClientExists {
    param(
        [string]$P4Exe,
        [string]$ResolvedServer,
        [string]$ResolvedUser,
        [string]$ClientName
    )

    $output = & $P4Exe -p $ResolvedServer -u $ResolvedUser clients -e $ClientName 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }

    return ($output | Where-Object { $_ -match ('^Client\s+' + [regex]::Escape($ClientName) + '\b') }).Count -gt 0
}

function Assert-RootReady {
    param([string]$RootPath)

    if ([string]::IsNullOrWhiteSpace($RootPath)) {
        throw 'Workspace root is required.'
    }

    if (-not (Test-Path -LiteralPath $RootPath)) {
        return
    }

    $items = Get-ChildItem -LiteralPath $RootPath -Force
    if ($items.Count -gt 0 -and -not $Force) {
        throw "Workspace root is not empty: $RootPath. Re-run with -Force only after confirming it is safe."
    }
}

function New-StreamWorkspace {
    param(
        [string]$P4Exe,
        [string]$ResolvedServer,
        [string]$ResolvedUser,
        [string]$Stream,
        [string]$ClientName,
        [string]$RootPath,
        [string]$Label,
        [switch]$DoSync
    )

    if ([string]::IsNullOrWhiteSpace($Stream)) {
        return
    }

    Assert-RootReady -RootPath $RootPath

    if ($PSCmdlet.ShouldProcess($ClientName, "Create $Label workspace for $Stream at $RootPath")) {
        if ((Test-ClientExists -P4Exe $P4Exe -ResolvedServer $ResolvedServer -ResolvedUser $ResolvedUser -ClientName $ClientName) -and -not $Force) {
            throw "Workspace already exists: $ClientName. Re-run with -Force only after confirming overwrite is intended."
        }

        New-Item -ItemType Directory -Force -Path $RootPath | Out-Null

        $specLines = & $P4Exe -p $ResolvedServer -u $ResolvedUser client -S $Stream -o $ClientName
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to generate client spec for $ClientName"
        }

        $specText = [string]::Join("`n", $specLines)
        if ($specText -notmatch '(?m)^Root:\s+') {
            throw "Generated client spec for $ClientName does not contain a Root field."
        }

        $specText = [regex]::Replace($specText, '(?m)^Root:\s+.*$', "Root: $RootPath")
        $specText | & $P4Exe -p $ResolvedServer -u $ResolvedUser client -i
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create workspace $ClientName"
        }

        if ($DoSync) {
            & $P4Exe -p $ResolvedServer -u $ResolvedUser -c $ClientName sync
            if ($LASTEXITCODE -ne 0) {
                throw "Initial sync failed for workspace $ClientName"
            }
        }
    }
}

$defaults = $null
$resolvedDefaults = Resolve-Path -LiteralPath $DefaultsPath -ErrorAction SilentlyContinue
if ($resolvedDefaults) {
    $defaults = Get-Content -LiteralPath $resolvedDefaults.Path -Raw | ConvertFrom-Json
}

$recommendedRoots = Get-ConfigValue -Object $defaults -Name 'recommendedRoots'
$workspacePattern = Get-ConfigValue -Object $defaults -Name 'workspacePattern'
$install = Get-ConfigValue -Object $defaults -Name 'install'

if ([string]::IsNullOrWhiteSpace($Server)) {
    $Server = [string](Get-ConfigValue -Object $defaults -Name 'server')
}
if ([string]::IsNullOrWhiteSpace($Server)) {
    $Server = '47.116.182.134:1666'
}

if ([string]::IsNullOrWhiteSpace($Charset)) {
    $Charset = [string](Get-ConfigValue -Object $defaults -Name 'charset')
}
if ([string]::IsNullOrWhiteSpace($Charset)) {
    $Charset = 'none'
}

if ([string]::IsNullOrWhiteSpace($User)) {
    throw 'User is required.'
}
if ([string]::IsNullOrWhiteSpace($ProjectStream)) {
    throw 'ProjectStream is required.'
}

$projectLeaf = Get-StreamLeaf -Stream $ProjectStream
$engineLeaf = Get-StreamLeaf -Stream $EngineStream

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $projectBase = [string](Get-ConfigValue -Object $recommendedRoots -Name 'project')
    if ([string]::IsNullOrWhiteSpace($projectBase)) {
        $projectBase = 'D:\Perforce\Project'
    }
    $ProjectRoot = Join-Path $projectBase $projectLeaf
}

if (-not [string]::IsNullOrWhiteSpace($EngineStream) -and [string]::IsNullOrWhiteSpace($EngineRoot)) {
    $engineBase = [string](Get-ConfigValue -Object $recommendedRoots -Name 'engine')
    if ([string]::IsNullOrWhiteSpace($engineBase)) {
        $engineBase = 'D:\Perforce\Engine'
    }
    $EngineRoot = Join-Path $engineBase $engineLeaf
}

if ([string]::IsNullOrWhiteSpace($ProjectClient)) {
    $pattern = [string](Get-ConfigValue -Object $workspacePattern -Name 'project')
    if ([string]::IsNullOrWhiteSpace($pattern)) {
        $pattern = '{user}_{computer}_{leaf}'
    }
    $ProjectClient = Expand-WorkspacePattern -Pattern $pattern -ResolvedUser $User -Leaf $projectLeaf
}

if (-not [string]::IsNullOrWhiteSpace($EngineStream) -and [string]::IsNullOrWhiteSpace($EngineClient)) {
    $pattern = [string](Get-ConfigValue -Object $workspacePattern -Name 'engine')
    if ([string]::IsNullOrWhiteSpace($pattern)) {
        $pattern = '{user}_{computer}_Engine_{leaf}'
    }
    $EngineClient = Expand-WorkspacePattern -Pattern $pattern -ResolvedUser $User -Leaf $engineLeaf
}

$wingetId = [string](Get-ConfigValue -Object $install -Name 'wingetId')
$p4 = Ensure-P4Installed -WingetId $wingetId

if (-not $SkipLogin) {
    if ([string]::IsNullOrWhiteSpace($Password)) {
        Write-Warning 'No password provided. The script will rely on an existing p4 login ticket.'
    }
    elseif ($PSCmdlet.ShouldProcess("$User@$Server", 'Run p4 login')) {
        $Password | & $p4.Source -p $Server -u $User login
        if ($LASTEXITCODE -ne 0) {
            throw 'p4 login failed.'
        }
    }
}

New-StreamWorkspace -P4Exe $p4.Source -ResolvedServer $Server -ResolvedUser $User -Stream $ProjectStream -ClientName $ProjectClient -RootPath $ProjectRoot -Label 'project' -DoSync:$Sync

if (-not [string]::IsNullOrWhiteSpace($EngineStream)) {
    New-StreamWorkspace -P4Exe $p4.Source -ResolvedServer $Server -ResolvedUser $User -Stream $EngineStream -ClientName $EngineClient -RootPath $EngineRoot -Label 'engine' -DoSync:$Sync
}

if ($WriteConnectionConfig -and $PSCmdlet.ShouldProcess($ConnectionConfigPath, 'Write local p4 connection config')) {
    $profile = [ordered]@{
        server = $Server
        user = $User
        password = if ($PersistPassword) { $Password } else { '' }
        client = $ProjectClient
        charset = $Charset
    } | ConvertTo-Json

    $configDir = Split-Path -Parent $ConnectionConfigPath
    if (-not (Test-Path -LiteralPath $configDir)) {
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    }

    Set-Content -LiteralPath $ConnectionConfigPath -Value $profile -Encoding utf8
}

[pscustomobject]@{
    server = $Server
    user = $User
    projectStream = $ProjectStream
    projectRoot = $ProjectRoot
    projectClient = $ProjectClient
    engineStream = $EngineStream
    engineRoot = $EngineRoot
    engineClient = $EngineClient
    wroteConnectionConfig = [bool]$WriteConnectionConfig
    persistedPassword = [bool]$PersistPassword
    syncRequested = [bool]$Sync
}