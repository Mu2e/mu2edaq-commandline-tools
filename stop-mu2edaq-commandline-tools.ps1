<#
.SYNOPSIS
    Stop anything left running by start-mu2edaq-commandline-tools.ps1 and clean
    up its temporary files. PowerShell port of stop-mu2edaq-commandline-tools.sh.

.PARAMETER Timeout
    Seconds to wait for a clean exit before forcing (default 10).

.PARAMETER KeepLogs
    Do not remove the log directory.
#>
[CmdletBinding()]
param(
    [int]$Timeout = 10,
    [switch]$KeepLogs
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = if ($env:MU2EDAQ_TOOLS_PIDFILE) { $env:MU2EDAQ_TOOLS_PIDFILE } else { Join-Path $Here '.mu2edaq-tools.pid' }
$LogDir  = if ($env:MU2EDAQ_TOOLS_LOG_DIR) { $env:MU2EDAQ_TOOLS_LOG_DIR } else { Join-Path $Here 'logs' }

function Test-ProcessAlive([int]$ProcId) {
    return [bool](Get-Process -Id $ProcId -ErrorAction SilentlyContinue)
}

if (Test-Path $PidFile) {
    $ProcId = [int]((Get-Content $PidFile -Raw).Trim())
    if ($ProcId -and (Test-ProcessAlive $ProcId)) {
        Write-Host "==> Stopping mu2edaq-tools (pid $ProcId)"
        $proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
        if ($proc) { $proc.CloseMainWindow() | Out-Null }
        $waited = 0
        while ((Test-ProcessAlive $ProcId) -and $waited -lt $Timeout) {
            Start-Sleep -Seconds 1; $waited++
        }
        if (Test-ProcessAlive $ProcId) {
            Write-Host "    still alive after ${Timeout}s, forcing"
            Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "==> Stale pidfile (pid $ProcId not running)"
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "==> Nothing to stop (no $PidFile)"
}

Get-ChildItem -Path $Here -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
if (-not $KeepLogs -and (Test-Path $LogDir)) {
    Write-Host "==> Removing $LogDir"
    Remove-Item -Recurse -Force $LogDir -ErrorAction SilentlyContinue
}

Write-Host 'Done.'
