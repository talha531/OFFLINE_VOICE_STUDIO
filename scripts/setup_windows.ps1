<#
  Offline Voice Studio - one-time setup for Windows (PowerShell, uv).
  Run from the project folder:   .\scripts\setup_windows.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv was not found. Install it once with:" -ForegroundColor Yellow
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host "Then open a NEW PowerShell window and run this script again."
    exit 1
}

Write-Host "1/3  Creating virtual environment (.venv, Python 3.12)..." -ForegroundColor Cyan
uv venv --python 3.12 .venv

Write-Host "2/3  Installing packages..." -ForegroundColor Cyan
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Package installation failed. See the message above." -ForegroundColor Red; exit 1 }

Write-Host "3/3  Voice models" -ForegroundColor Cyan
$existing = @(Get-ChildItem models\piper -Filter *.onnx -ErrorAction SilentlyContinue).Count
if ($existing -gt 0) {
    Write-Host "     $existing voice model(s) already in models\piper - skipping download."
} else {
    $answer = Read-Host "     Download the 4 starter voices now (about 240 MB, internet needed once)? [Y/n]"
    if ($answer -eq "" -or $answer -match "^[Yy]") {
        .venv\Scripts\python.exe scripts\download_voices.py
    } else {
        Write-Host "     Skipped. Later run:  .venv\Scripts\python.exe scripts\download_voices.py"
    }
}

Write-Host "Optional: Urdu / Hindi / Arabic and 1,000+ more languages (Meta MMS; PyTorch, non-commercial licence)" -ForegroundColor Cyan
$mms = Read-Host "     Install and download Urdu, Hindi and Arabic now (about 2 GB)? [y/N]"
if ($mms -match "^[Yy]") {
    uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cpu
    uv pip install --python .venv\Scripts\python.exe -r requirements-mms.txt
    .venv\Scripts\python.exe scripts\download_mms.py urd-script_arabic hin ara
}

Write-Host ""
Write-Host "Setup complete. Start the app with:  .\scripts\run_studio.ps1   (or double-click run_studio.bat)" -ForegroundColor Green
