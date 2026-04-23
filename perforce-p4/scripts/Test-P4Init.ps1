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
    $mockState = [ordered]@{
        trustedServers = @('perforce.example:1666')
        streams = @('//streammain/Art', '//streammain/Engine')
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
$commandArgs = New-Object System.Collections.Generic.List[string]
$rawArgs = @()
if (-not [string]::IsNullOrWhiteSpace($env:MOCK_P4_RAW_ARGS)) {
    $rawArgs = $env:MOCK_P4_RAW_ARGS.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)
}

for ($i = 0; $i -lt $rawArgs.Count; $i++) {
    switch ($rawArgs[$i]) {
        '-p' {
            $i++
            $server = $rawArgs[$i]
        }
        '-u' {
            $i++
            $user = $rawArgs[$i]
        }
        '-c' {
            $i++
            $client = $rawArgs[$i]
        }
        default {
            $null = $commandArgs.Add($rawArgs[$i])
        }
    }
}

$state = Load-State
$command = if ($commandArgs.Count -gt 0) { $commandArgs[0] } else { '' }

switch ($command) {
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
    $env:MOCK_P4_STATE = $statePath

    $workspaceRoot = Join-Path $tempRoot 'workspace-art'
    $result = & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streammain/Art' -ProjectRoot $workspaceRoot -ProjectClient 'alice_TEST_Art' -SkipLogin
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-True -Condition (Test-Path -LiteralPath $workspaceRoot) -Message 'Expected workspace root to be created.'
    Assert-True -Condition $result.projectWorkspaceCreated -Message 'Expected project workspace to be reported as created.'
    Assert-True -Condition ($state.clients.ContainsKey('alice_TEST_Art')) -Message 'Expected client spec to be written.'
    Assert-True -Condition (@($state.syncCalls).Count -eq 0) -Message 'Expected no sync call when -Sync is not specified.'
    Assert-True -Condition ($result.recommendedNextStep -match 'P4V') -Message 'Expected next-step guidance to recommend P4V.'

    $syncRoot = Join-Path $tempRoot 'workspace-sync'
    $syncResult = & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streammain/Art' -ProjectRoot $syncRoot -ProjectClient 'alice_TEST_Art_Sync' -SkipLogin -Sync
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -AsHashtable
    Assert-True -Condition (@($state.syncCalls).Count -eq 1) -Message 'Expected exactly one sync call when -Sync is specified.'
    Assert-True -Condition ($syncResult.syncRequested) -Message 'Expected syncRequested to be true when -Sync is specified.'

    $state.clients['alice_EXISTS_Art'] = @{
        root = 'F:\Existing'
        stream = '//streammain/Art'
    }
    $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statePath -Encoding utf8
    Assert-ThrowsLike -Pattern 'Workspace already exists' -Message 'Expected existing workspace guard to throw.' -ScriptBlock {
        & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streammain/Art' -ProjectRoot (Join-Path $tempRoot 'workspace-exists') -ProjectClient 'alice_EXISTS_Art' -SkipLogin | Out-Null
    }

    $nonEmptyRoot = Join-Path $tempRoot 'workspace-non-empty'
    New-Item -ItemType Directory -Force -Path $nonEmptyRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $nonEmptyRoot 'keep.txt') -Value 'x' -Encoding utf8
    Assert-ThrowsLike -Pattern 'Workspace root is not empty' -Message 'Expected non-empty root guard to throw.' -ScriptBlock {
        & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streammain/Art' -ProjectRoot $nonEmptyRoot -ProjectClient 'alice_NONEMPTY_Art' -SkipLogin | Out-Null
    }

    $untrustedStatePath = Join-Path $tempRoot 'mock-state-untrusted.json'
    $untrustedState = [ordered]@{
        trustedServers = @()
        streams = @('//streammain/Art')
        clients = @{}
        loginCalls = 0
        syncCalls = @()
    } | ConvertTo-Json -Depth 10
    Set-Content -LiteralPath $untrustedStatePath -Value $untrustedState -Encoding utf8
    $env:MOCK_P4_STATE = $untrustedStatePath
    Assert-ThrowsLike -Pattern 'SSL trust is not configured' -Message 'Expected SSL trust guard to throw.' -ScriptBlock {
        & $scriptPath -P4ExePath $mockP4Path -Server 'ssl:perforce.example:1666' -User 'alice' -ProjectStream '//streammain/Art' -ProjectRoot (Join-Path $tempRoot 'workspace-untrusted') -ProjectClient 'alice_UNTRUSTED_Art' -SkipLogin | Out-Null
    }

    'All p4-init tests passed.'
}
finally {
    Remove-Item Env:MOCK_P4_STATE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
