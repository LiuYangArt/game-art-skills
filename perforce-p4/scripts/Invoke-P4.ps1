[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\config\p4-connection.json'),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$P4Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ProfileValue {
    param(
        [pscustomobject]$Profile,
        [string]$Name,
        [switch]$Required
    )

    $property = $Profile.PSObject.Properties[$Name]
    if ($null -eq $property) {
        if ($Required) {
            throw "Missing required field '$Name' in $resolvedConfigPath"
        }

        return ''
    }

    $value = $property.Value
    if ($Required -and [string]::IsNullOrWhiteSpace([string]$value)) {
        throw "Missing required field '$Name' in $resolvedConfigPath"
    }

    return [string]$value
}

$resolvedConfig = Resolve-Path -LiteralPath $ConfigPath -ErrorAction SilentlyContinue
if (-not $resolvedConfig) {
    throw "Connection profile not found: $ConfigPath. Run scripts\\p4-init.ps1 or copy config\\p4-connection.template.json to config\\p4-connection.json first."
}

$resolvedConfigPath = $resolvedConfig.Path
$profile = Get-Content -LiteralPath $resolvedConfigPath -Raw | ConvertFrom-Json

$server = Get-ProfileValue -Profile $profile -Name 'server' -Required
$user = Get-ProfileValue -Profile $profile -Name 'user' -Required
$password = Get-ProfileValue -Profile $profile -Name 'password'
$client = Get-ProfileValue -Profile $profile -Name 'client'
$charset = Get-ProfileValue -Profile $profile -Name 'charset'

$p4 = Get-Command p4 -ErrorAction Stop
$argumentList = @('-p', $server, '-u', $user)

if (-not [string]::IsNullOrWhiteSpace($client)) {
    $argumentList += @('-c', $client)
}

if (-not $P4Args -or $P4Args.Count -eq 0) {
    $P4Args = @('info')
}

$previousPassword = $env:P4PASSWD
$previousCharset = $env:P4CHARSET
$setPassword = -not [string]::IsNullOrWhiteSpace($password)
$setCharset = -not [string]::IsNullOrWhiteSpace($charset) -and $charset -ne 'none'

try {
    if ($setPassword) {
        $env:P4PASSWD = $password
    }

    if ($setCharset) {
        $env:P4CHARSET = $charset
    }
    else {
        Remove-Item Env:P4CHARSET -ErrorAction SilentlyContinue
    }

    & $p4.Source @argumentList @P4Args
    exit $LASTEXITCODE
}
finally {
    if ($setPassword) {
        if ($null -eq $previousPassword) {
            Remove-Item Env:P4PASSWD -ErrorAction SilentlyContinue
        }
        else {
            $env:P4PASSWD = $previousPassword
        }
    }

    if ($null -eq $previousCharset) {
        Remove-Item Env:P4CHARSET -ErrorAction SilentlyContinue
    }
    else {
        $env:P4CHARSET = $previousCharset
    }
}