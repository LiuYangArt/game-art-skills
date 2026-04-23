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

function Invoke-ExternalPwsh {
    param(
        [string[]]$Arguments,
        [hashtable]$Environment
    )

    $command = @'
import json
import os
import subprocess
import sys

args = json.loads(os.environ["CODER_ARGS"])
env = os.environ.copy()
for key, value in json.loads(os.environ["CODER_ENV"]).items():
    env[key] = value

completed = subprocess.run(
    args,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
    env=env,
)
payload = {
    "exitCode": completed.returncode,
    "stdout": completed.stdout,
    "stderr": completed.stderr,
}
print(json.dumps(payload, ensure_ascii=True))
'@

    $previousArgs = $env:CODER_ARGS
    $previousEnv = $env:CODER_ENV
    try {
        $env:CODER_ARGS = ($Arguments | ConvertTo-Json -Compress)
        $env:CODER_ENV = (($Environment ?? @{}) | ConvertTo-Json -Compress)
        $json = python -c $command
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to run external pwsh harness."
        }
        return $json | ConvertFrom-Json
    }
    finally {
        if ($null -eq $previousArgs) {
            Remove-Item Env:CODER_ARGS -ErrorAction SilentlyContinue
        }
        else {
            $env:CODER_ARGS = $previousArgs
        }

        if ($null -eq $previousEnv) {
            Remove-Item Env:CODER_ENV -ErrorAction SilentlyContinue
        }
        else {
            $env:CODER_ENV = $previousEnv
        }
    }
}

$scriptPath = Join-Path $PSScriptRoot 'Invoke-P4.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("invoke-p4-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    $mockPythonPath = Join-Path $tempRoot 'mock_p4.py'
    $mockP4Path = Join-Path $tempRoot 'p4.cmd'
    $configPath = Join-Path $tempRoot 'p4-connection.json'

    $mockPython = @'
import os
import sys

args = sys.argv[1:]
server = ""
user = ""
command_args = []
i = 0
while i < len(args):
    if args[i] == "-p":
        i += 1
        server = args[i]
    elif args[i] == "-u":
        i += 1
        user = args[i]
    else:
        command_args.append(args[i])
    i += 1

print(f"SERVER={server}")
print(f"USER={user}")
print(f"ARGS={' '.join(command_args)}")
print(f"PASSWD={os.environ.get('P4PASSWD', '')}")
sys.exit(0)
'@
    Set-Content -LiteralPath $mockPythonPath -Value $mockPython -Encoding utf8
    $mockP4Cmd = "@echo off`r`npython `"%~dp0mock_p4.py`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    Set-Content -LiteralPath $mockP4Path -Value $mockP4Cmd -Encoding ascii

    $profile = @{
        server = 'ssl:perforce.example:1666'
        user = 'alice'
        password = ''
    } | ConvertTo-Json
    Set-Content -LiteralPath $configPath -Value $profile -Encoding utf8

    $pathEnv = "$tempRoot;$env:PATH"
    $commonEnv = @{
        PATH = $pathEnv
    }

    $resultDefault = Invoke-ExternalPwsh -Arguments @(
        'pwsh', '-NoProfile', '-File', $scriptPath, '-ConfigPath', $configPath
    ) -Environment $commonEnv
    Assert-True -Condition ($resultDefault.exitCode -eq 0) -Message 'Expected default Invoke-P4 call to succeed.'
    Assert-True -Condition ($resultDefault.stdout -match 'ARGS=info') -Message 'Expected default command to be info.'
    Assert-True -Condition ($resultDefault.stdout -match 'SERVER=ssl:perforce\.example:1666') -Message 'Expected server to be passed through.'
    Assert-True -Condition ($resultDefault.stdout -match 'USER=alice') -Message 'Expected user to be passed through.'
    Assert-True -Condition ($resultDefault.stdout -match 'PASSWD=$') -Message 'Expected empty password to stay empty.'

    $profileWithPassword = @{
        server = 'ssl:perforce.example:1666'
        user = 'alice'
        password = 'secret-pass'
    } | ConvertTo-Json
    Set-Content -LiteralPath $configPath -Value $profileWithPassword -Encoding utf8

    $resultPassword = Invoke-ExternalPwsh -Arguments @(
        'pwsh', '-NoProfile', '-File', $scriptPath, '-ConfigPath', $configPath, 'files', '//depot/...'
    ) -Environment $commonEnv
    Assert-True -Condition ($resultPassword.exitCode -eq 0) -Message 'Expected password-backed Invoke-P4 call to succeed.'
    Assert-True -Condition ($resultPassword.stdout -match 'ARGS=files //depot/\.\.\.') -Message 'Expected custom p4 args to pass through.'
    Assert-True -Condition ($resultPassword.stdout -match 'PASSWD=secret-pass') -Message 'Expected P4PASSWD to be injected.'

    $missingConfig = Join-Path $tempRoot 'missing.json'
    $resultMissing = Invoke-ExternalPwsh -Arguments @(
        'pwsh', '-NoProfile', '-File', $scriptPath, '-ConfigPath', $missingConfig
    ) -Environment $commonEnv
    Assert-True -Condition ($resultMissing.exitCode -ne 0) -Message 'Expected missing config to fail.'
    Assert-True -Condition ($resultMissing.stderr -match 'Connection profile not found') -Message 'Expected missing config error message.'

    $profileMissingUser = @{
        server = 'ssl:perforce.example:1666'
        user = ''
        password = ''
    } | ConvertTo-Json
    Set-Content -LiteralPath $configPath -Value $profileMissingUser -Encoding utf8
    $resultMissingUser = Invoke-ExternalPwsh -Arguments @(
        'pwsh', '-NoProfile', '-File', $scriptPath, '-ConfigPath', $configPath
    ) -Environment $commonEnv
    Assert-True -Condition ($resultMissingUser.exitCode -ne 0) -Message 'Expected missing required user to fail.'
    Assert-True -Condition ($resultMissingUser.stderr -match "Missing required field 'user'") -Message 'Expected missing user error message.'

    'All Invoke-P4 tests passed.'
}
finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
