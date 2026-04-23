[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\config\p4-connection.json'),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$P4Args
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

    throw 'Python is required to run Invoke-P4. Install Python or ensure `python` or `py` is available on PATH.'
}

$python = Resolve-PythonCommand
$pythonScriptPath = Join-Path $PSScriptRoot 'Invoke-P4.py'

if (-not (Test-Path -LiteralPath $pythonScriptPath)) {
    throw "Python implementation not found: $pythonScriptPath"
}

$launchArgs = [System.Collections.Generic.List[string]]::new()
foreach ($prefixArg in $python.PrefixArgs) {
    $launchArgs.Add($prefixArg)
}

$launchArgs.Add($pythonScriptPath)
$launchArgs.Add('--config-path')
$launchArgs.Add($ConfigPath)
if ($P4Args -and $P4Args.Count -gt 0) {
    $launchArgs.Add('--')
    foreach ($arg in $P4Args) {
        $launchArgs.Add($arg)
    }
}

$json = & $python.Executable @launchArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

try {
    $result = $json | ConvertFrom-Json
}
catch {
    throw "Failed to parse JSON output from Invoke-P4.py. Raw output: $json"
}

if ([string]$result.status -eq 'error') {
    throw [string]$result.message
}

if (-not [string]::IsNullOrEmpty([string]$result.stdout)) {
    [Console]::Out.Write([string]$result.stdout)
}

if (-not [string]::IsNullOrEmpty([string]$result.stderr)) {
    [Console]::Error.Write([string]$result.stderr)
}

exit ([int]$result.exitCode)
