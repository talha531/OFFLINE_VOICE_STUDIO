<#
  One-click install of offline voice cloning (Coqui XTTS-v2) for Offline Voice Studio.
  Needs internet once (~2.5 GB). Run from the project folder:  .\scripts\install_cloning.ps1
#>
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = ".venv\Scripts\python.exe"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is not installed. Run this once, open a NEW PowerShell, then retry:" -ForegroundColor Yellow
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    exit 1
}

# XTTS needs Python 3.10-3.12. Recreate the environment if it is missing or uses another version.
$needNew = $true
if (Test-Path $py) {
    $ver = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($ver -in @("3.10", "3.11", "3.12")) { $needNew = $false } else { Write-Host "Python $ver is not supported by the cloning engine; recreating .venv with 3.11." -ForegroundColor Yellow }
}
if ($needNew) {
    if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
    uv venv --python 3.11 .venv
    Write-Host "Installing the app's base packages..." -ForegroundColor Cyan
    uv pip install --python $py -r requirements.txt
}

Write-Host "1/3  Installing PyTorch (CPU)..." -ForegroundColor Cyan
uv pip install --python $py torch torchaudio --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { Write-Host "PyTorch install failed (see above)." -ForegroundColor Red; exit 1 }

Write-Host "2/3  Installing the cloning engine..." -ForegroundColor Cyan
uv pip install --python $py -r requirements-cloning.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Cloning package install failed (see above). Send me that error text." -ForegroundColor Red; exit 1 }

Write-Host "3/3  Downloading the XTTS-v2 model (~2 GB)..." -ForegroundColor Cyan
& $py scripts\download_xtts.py
if ($LASTEXITCODE -ne 0) { Write-Host "Model download failed. Check your internet and run this script again (it resumes)." -ForegroundColor Red; exit 1 }

Write-Host "`nVerifying..." -ForegroundColor Cyan
& $py scripts\check_setup.py
Write-Host "`nRestart the app (Ctrl+C, then .\scripts\run_studio.ps1). In Custom Voice open My voices and click 'Build speaker model'." -ForegroundColor Green
