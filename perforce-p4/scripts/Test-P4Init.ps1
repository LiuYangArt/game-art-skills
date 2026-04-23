[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ThrowsLike {
    param(
        [scriptblock]$ScriptBlock,
        [string]$Pattern,
        [string]$Message
    )

    try {
        & $ScriptBlock
    }
    catch {
        if ($_.Exception.Message -match $Pattern) {
            return
        }

        throw "Unexpected error. Expected pattern '$Pattern' but got '$($_.Exception.Message)'."
    }

    throw $Message
}

$scriptPath = Join-Path $PSScriptRoot 'p4-init.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("p4-init-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    $statePath = Join-Path $tempRoot 'mock-state.json'
    $mockP4Path = Join-Path $tempRoot 'mock-p4.cmd'
    $mockP4ScriptPath = Join-Path $tempRoot 'mock-p4-inner.ps1'
    $configPath = Join-Path $tempRoot 'p4-connection.json'
    $mockState = [ordered]@{
        trustedServers = @('perforce.example:1666')
        unicodeCounter = 1
        streams = @('//streams/project-main', '//streams/engine-main')
        clients = @{}
        loginCalls = 0
        syncCalls = @()
    } | ConvertTo-Json -Depth 10
    Set-Content -LiteralPath $statePath -Value $mockState -Encoding utf8

    $mockP4 = @'
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Load-State {
    return Get-Content -LiteralPath $env:MOCK_P4_STATE -Raw | ConvertFrom-Json -AsHashtable
}

function Save-State {
    param([hashtable]$State)
    $State | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $env:MOCK_P4_STATE -Encoding utf8
}

$server = ''
$user = ''
$client = ''
$charset = ''
$commandArgs = New-Object System.Collections.Generic.List[string]
$rawArgs = @()
if (-not [string]::IsNullOrWhiteSpace($env:MOCK_P4_RAW_ARGS)) {
    $rawArgs = $env:MOCK_P4_RAW_ARGS.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
}

for ($i = 0; $i -lt $rawArgs.Count; $i++) {
    $token = $rawArgs[$i]
    if ($token -ceq '-p') {
        $i++
        $server = $rawArgs[$i]
        continue
    }

    if ($token -ceq '-u') {
        $i++
        $user = $rawArgs[$i]
        continue
    }

    if ($token -ceq '-C') {
        $i++
        $charset = $rawArgs[$i]
        continue
    }

    if ($token -ceq '-c') {
        $i++
        $client = $rawArgs[$i]
        continue
    }

    $null = $commandArgs.Add($token)
}

$state = Load-State
$command = if ($commandArgs.Count -gt 0) { $commandArgs[0] } else { '' }

if ($command -and $command -ne 'trust') {
    if ([int]$state.unicodeCounter -eq 0 -and $charset -ne 'none') {
        Write-Error 'Unicode clients require a unicode enabled server.'
        exit 1
    }

    if ([int]$state.unicodeCounter -eq 1 -and $charset -eq 'none') {
        Write-Error 'Unicode server permits only unicode enabled clients.'
        exit 1
    }
}

switch ($command) {
    'counter' {
        if ($commandArgs.Count -ge 2 -and $commandArgs[1] -eq 'unicode') {
            Write-Output ([string]$state.unicodeCounter)
            exit 0
        }
    }
    'trust' {
        if ($commandArgs.Count -ge 2 -and $commandArgs[1] -eq '-l') {
            foreach ($entry in $state.trustedServers) {
                Write-Output "$entry FA:KE:FP"
            }
            exit 0
        }
    }
    'stream' {
        $streamName = $commandArgs[2]
        if ($state.streams -contains $streamName) {
            Write-Output "Stream:`t$streamName"
            exit 0
        }

        Write-Error "Stream not found: $streamName"
        exit 1
    }
    'clients' {
        $name = $commandArgs[2]
        if ($state.clients.ContainsKey($name)) {
            $root = $state.clients[$name].root
            Write-Output "Client $name 2026/04/23 root $root '$name'"
        }
        exit 0
    }
    'client' {
        if ($commandArgs.Count -ge 5 -and $commandArgs[1] -eq '-S' -and $commandArgs[3] -eq '-o') {
            $streamName = $commandArgs[2]
            $name = $commandArgs[4]
            if (-not ($state.streams -contains $streamName)) {
                Write-Error "Stream not found: $streamName"
                exit 1
            }

            @(
                "Client:`t$name"
                "Owner:`t$user"
                "Root:`tC:\placeholder"
                "Stream:`t$streamName"
                "View:"
                "`t$streamName/... //$name/..."
            )
            exit 0
        }

        if ($commandArgs.Count -ge 2 -and $commandArgs[1] -eq '-i') {
            $specText = [Console]::In.ReadToEnd()
            $clientName = [regex]::Match($specText, '(?m)^Client:\s*(.+)$').Groups[1].Value.Trim()
            $rootPath = [regex]::Match($specText, '(?m)^Root:\s*(.+)$').Groups[1].Value.Trim()
            $streamName = [regex]::Match($specText, '(?m)^Stream:\s*(.+)$').Groups[1].Value.Trim()
            $state.clients[$clientName] = @{
                root = $rootPath
                stream = $streamName
            }
            Save-State -State $state
            Write-Output "Client $clientName saved."
            exit 0
        }

        if ($commandArgs.Count -ge 2 -and $commandArgs[1] -eq '-o') {
            $name = $commandArgs[2]
            if (-not $state.clients.ContainsKey($name)) {
                Write-Error "Client not found: $name"
                exit 1
            }

            $clientState = $state.clients[$name]
            @(
                "Client:`t$name"
                "Owner:`t$user"
                "Root:`t$($clientState.root)"
                "Stream:`t$($clientState.stream)"
            )
            exit 0
        }
    }
    'login' {
        [void][Console]::In.ReadToEnd()
        $state.loginCalls = [int]$state.loginCalls + 1
        Save-State -State $state
        Write-Output "User $user logged in."
        exit 0
    }
    'sync' {
        $state.syncCalls = @($state.syncCalls) + $client
        Save-State -State $state
        Write-Output "//$client/...#1 - added"
        exit 0
    }
}

Write-Error "Unsupported mock command: $($commandArgs -join ' ')"
exit 1
'@
    Set-Content -LiteralPath $mockP4ScriptPath -Value $mockP4 -Encoding utf8
    $mockP4Cmd = "@echo off`r`nset MOCK_P4_RAW_ARGS=%*`r`npwsh -NoProfile -File `"%~dp0mock-p4-inner.ps1`"`r`nexit /b %ERRORLEVEL%`r`n"
    Set-Content -LiteralPath $mockP4Path -Value $mockP4Cmd -Encoding ascii
    @{
        server = 'ssl:perforce.example:1666'
        user = 'alice'
        password = ''
    } | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
    $env:MOCK_P4_STATE = $statePath

    $workspaceRoot = Join-Path $tempRoot 'workspace-art'
    $result = & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streams/project-main' -ProjectRoot $workspaceRoot -ProjectClient 'alice_TEST_Project' -SkipLogin
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-True -Condition (Test-Path -LiteralPath $workspaceRoot) -Message 'Expected workspace root to be created.'
    Assert-True -Condition ($result.server -eq 'ssl:perforce.example:1666') -Message 'Expected server to fall back from the local connection config.'
    Assert-True -Condition ($result.user -eq 'alice') -Message 'Expected user to fall back from the local connection config.'
    Assert-True -Condition ($result.charsetMode -eq 'current-environment') -Message 'Expected unicode server to keep the current charset mode.'
    Assert-True -Condition $result.serverUnicodeEnabled -Message 'Expected unicode server detection to report true.'
    Assert-True -Condition $result.projectWorkspaceCreated -Message 'Expected project workspace to be reported as created.'
    Assert-True -Condition ($state.clients.ContainsKey('alice_TEST_Project')) -Message 'Expected client spec to be written.'
    Assert-True -Condition (@($state.syncCalls).Count -eq 0) -Message 'Expected no sync call when -Sync is not specified.'
    Assert-True -Condition ($result.recommendedNextStep -match 'P4V') -Message 'Expected next-step guidance to recommend P4V.'

    $nonUnicodeStatePath = Join-Path $tempRoot 'mock-state-nonunicode.json'
    $nonUnicodeState = [ordered]@{
        trustedServers = @('perforce.example:1666')
        unicodeCounter = 0
        streams = @('//streams/project-main')
        clients = @{}
        loginCalls = 0
        syncCalls = @()
    } | ConvertTo-Json -Depth 10
    Set-Content -LiteralPath $nonUnicodeStatePath -Value $nonUnicodeState -Encoding utf8
    $env:MOCK_P4_STATE = $nonUnicodeStatePath
    $nonUnicodeRoot = Join-Path $tempRoot 'workspace-nonunicode'
    $nonUnicodeResult = & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streams/project-main' -ProjectRoot $nonUnicodeRoot -ProjectClient 'alice_TEST_Project_None' -SkipLogin
    $nonUnicodeStateReloaded = Get-Content -LiteralPath $nonUnicodeStatePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-True -Condition ($nonUnicodeResult.charsetMode -eq 'none') -Message 'Expected non-unicode server to switch to -C none.'
    Assert-True -Condition (-not $nonUnicodeResult.serverUnicodeEnabled) -Message 'Expected non-unicode server detection to report false.'
    Assert-True -Condition ($nonUnicodeStateReloaded.clients.ContainsKey('alice_TEST_Project_None')) -Message 'Expected client creation to succeed in verified non-unicode mode.'

    $env:MOCK_P4_STATE = $statePath

    $syncRoot = Join-Path $tempRoot 'workspace-sync'
    $syncResult = & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streams/project-main' -ProjectRoot $syncRoot -ProjectClient 'alice_TEST_Project_Sync' -SkipLogin -Sync
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-True -Condition (@($state.syncCalls).Count -eq 1) -Message 'Expected exactly one sync call when -Sync is specified.'
    Assert-True -Condition ($syncResult.syncRequested) -Message 'Expected syncRequested to be true when -Sync is specified.'

    $state.clients['alice_EXISTS_Art'] = @{
        root = 'F:\Existing'
        stream = '//streams/project-main'
    }
    $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statePath -Encoding utf8
    Assert-ThrowsLike -Pattern 'Workspace already exists' -Message 'Expected existing workspace guard to throw.' -ScriptBlock {
        & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streams/project-main' -ProjectRoot (Join-Path $tempRoot 'workspace-exists') -ProjectClient 'alice_EXISTS_Art' -SkipLogin | Out-Null
    }

    $nonEmptyRoot = Join-Path $tempRoot 'workspace-non-empty'
    New-Item -ItemType Directory -Force -Path $nonEmptyRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $nonEmptyRoot 'keep.txt') -Value 'x' -Encoding utf8
    Assert-ThrowsLike -Pattern 'Workspace root is not empty' -Message 'Expected non-empty root guard to throw.' -ScriptBlock {
        & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streams/project-main' -ProjectRoot $nonEmptyRoot -ProjectClient 'alice_NONEMPTY_Art' -SkipLogin | Out-Null
    }

    $untrustedStatePath = Join-Path $tempRoot 'mock-state-untrusted.json'
    $untrustedState = [ordered]@{
        trustedServers = @()
        unicodeCounter = 1
        streams = @('//streams/project-main')
        clients = @{}
        loginCalls = 0
        syncCalls = @()
    } | ConvertTo-Json -Depth 10
    Set-Content -LiteralPath $untrustedStatePath -Value $untrustedState -Encoding utf8
    $env:MOCK_P4_STATE = $untrustedStatePath
    Assert-ThrowsLike -Pattern 'SSL trust is not configured' -Message 'Expected SSL trust guard to throw.' -ScriptBlock {
        & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streams/project-main' -ProjectRoot (Join-Path $tempRoot 'workspace-untrusted') -ProjectClient 'alice_UNTRUSTED_Art' -SkipLogin | Out-Null
    }

    'All p4-init tests passed.'
}
finally {
    Remove-Item Env:MOCK_P4_STATE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}