# Reproducible local build of the Windows desktop package.
# Requires the project virtualenv with requirements.txt + requirements-dev.txt.
#
# Usage (from the repository root, in the activated .venv):
#   .\build.ps1
#
# Produces dist\KindergartenHealth\KindergartenHealth.exe (one-dir, windowed).
# build\ and dist\ are git-ignored. No publishing is performed.

param(
    [string]$SpecFile = "KindergartenHealth.spec"
)

$ErrorActionPreference = "Stop"

Write-Host "== KindergartenHealth local build =="
Write-Host "Python: $(python --version)"

if (-not (Test-Path $SpecFile)) {
    throw "Spec file not found: $SpecFile"
}

# Build with the spec (deterministic configuration, no ad-hoc CLI flags).
python -m PyInstaller $SpecFile --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed (exit $LASTEXITCODE)."
}

$exe = Join-Path "dist" "KindergartenHealth\KindergartenHealth.exe"
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "Build OK -> $exe ($size MB)"
} else {
    throw "Expected output not found: $exe"
}

Write-Host "NOTE: a successful build does NOT verify GUI behaviour."
Write-Host "Manual GUI verification remains the next stage: python main.py"
