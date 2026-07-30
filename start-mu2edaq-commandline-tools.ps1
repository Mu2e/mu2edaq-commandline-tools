<#
.SYNOPSIS
    Bring the venv up to date (creating it on first run) and hand off to the
    mu2edaq-tools dispatcher. PowerShell port of start-mu2edaq-commandline-tools.sh.

.DESCRIPTION
    Any remaining arguments are passed straight through to mu2edaq-tools, e.g.:
        .\start-mu2edaq-commandline-tools.ps1 config --json

.PARAMETER NoUpdate
    Skip the dependency refresh and start immediately.
#>
[CmdletBinding()]
param(
    [switch]$NoUpdate,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ToolArgs
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
$Venv = Join-Path $Here 'venv'
$PidFile = if ($env:MU2EDAQ_TOOLS_PIDFILE) { $env:MU2EDAQ_TOOLS_PIDFILE } else { Join-Path $Here '.mu2edaq-tools.pid' }

if (-not (Test-Path $Venv)) {
    Write-Host '==> No venv yet, bootstrapping'
    & (Join-Path $Here 'bootstrap.ps1')
} elseif (-not $NoUpdate) {
    Write-Host '==> Refreshing dependencies'
    & (Join-Path $Here 'bootstrap.ps1') | Out-Null
}

$VenvPy = Join-Path $Venv 'Scripts\python.exe'
Set-Content -Path $PidFile -Value $PID -Encoding ascii
try {
    & $VenvPy -m mu2edaq_commandline_tools.cli @ToolArgs
    $rc = $LASTEXITCODE
} finally {
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}
exit $rc
