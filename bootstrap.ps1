<#
.SYNOPSIS
    Create/refresh the venv for mu2edaq-commandline-tools and install the
    package. PowerShell port of bootstrap.sh.

.PARAMETER Dev
    Also install the dev extras (pytest).

.PARAMETER Cpp
    Configure and build the CMake targets under build\ (needs a compiler + CMake).

.PARAMETER Clean
    Remove venv\ and build\ before doing anything.

.PARAMETER PythonPath
    Interpreter to build the venv with (default: $env:PYTHON or python).

.PARAMETER Version
    Print the package version and exit.
#>
[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Cpp,
    [switch]$Clean,
    [string]$PythonPath,
    [switch]$Version
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
$Venv = Join-Path $Here 'venv'
$Build = Join-Path $Here 'build'

function Get-PkgVersion {
    $init = Join-Path $Here 'src\mu2edaq_commandline_tools\__init__.py'
    foreach ($line in Get-Content $init) {
        if ($line -match '__version__\s*=\s*"(.*)"') { return $Matches[1] }
    }
}
if ($Version) { Write-Host "mu2edaq-commandline-tools $(Get-PkgVersion)"; exit 0 }

if ($Clean) {
    if (Test-Path $Venv)  { Remove-Item -Recurse -Force $Venv }
    if (Test-Path $Build) { Remove-Item -Recurse -Force $Build }
}

# Prefer 'python'; fall back to the py launcher ('python3' on Windows is the
# Microsoft Store alias stub, so it is not used here).
$Python = $PythonPath
if (-not $Python) { $Python = $env:PYTHON }
if (-not $Python) {
    if (Get-Command python -ErrorAction SilentlyContinue) { $Python = 'python' }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = 'py' }
    else { Write-Error 'Python 3.9+ not found on PATH. Install it first.'; exit 1 }
}

if (-not (Test-Path $Venv)) { & $Python -m venv $Venv }
$VenvPy = Join-Path $Venv 'Scripts\python.exe'
& $VenvPy -m pip install --upgrade pip | Out-Null
if ($Dev) { & $VenvPy -m pip install -e '.[dev]' } else { & $VenvPy -m pip install -e '.' }

if ($Cpp) {
    if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
        Write-Warning 'cmake not found on PATH; skipping the C++ build.'
    } else {
        & cmake -S $Here -B $Build
        & cmake --build $Build
    }
}

Write-Host 'Done. Start with:  .\start-mu2edaq-commandline-tools.ps1'
