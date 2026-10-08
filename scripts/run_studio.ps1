
<#
Offline Voice Studio
Windows launcher with FFmpeg Shared DLL support for TorchCodec.

Everything runs locally on this computer.
#>

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# 1. Go to project root
# ------------------------------------------------------------

Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "       OFFLINE VOICE STUDIO" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 2. Python virtual environment
# ------------------------------------------------------------

$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "ERROR: Python virtual environment was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Expected:"
    Write-Host $python
    Write-Host ""
    Write-Host "Run the project setup first:" -ForegroundColor Yellow
    Write-Host ".\scripts\setup_windows.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "Python:" -ForegroundColor Green
Write-Host $python
Write-Host ""

# ------------------------------------------------------------
# 3. Find FFmpeg Shared installation
# ------------------------------------------------------------

$wingetPackages = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"

$ffmpegSharedRoot = Join-Path `
    $wingetPackages `
    "Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe"

$ffmpegSharedBin = $null

if (Test-Path $ffmpegSharedRoot) {

    $ffmpegBinCandidate = Get-ChildItem `
        -Path $ffmpegSharedRoot `
        -Directory `
        -ErrorAction SilentlyContinue |
        Where-Object {
            Test-Path (Join-Path $_.FullName "bin\avcodec-*.dll")
        } |
        Select-Object -First 1

    if ($ffmpegBinCandidate) {
        $ffmpegSharedBin = Join-Path $ffmpegBinCandidate.FullName "bin"
    }
}

# ------------------------------------------------------------
# 4. Verify FFmpeg Shared installation
# ------------------------------------------------------------

if (-not $ffmpegSharedBin) {

    Write-Host "ERROR: FFmpeg Shared installation was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "winget install --id Gyan.FFmpeg.Shared -e" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "FFmpeg Shared:" -ForegroundColor Green
Write-Host $ffmpegSharedBin
Write-Host ""

# ------------------------------------------------------------
# 5. Verify required FFmpeg DLLs
# ------------------------------------------------------------

$requiredDlls = @(
    "avcodec-63.dll",
    "avdevice-63.dll",
    "avfilter-12.dll",
    "avformat-63.dll",
    "avutil-61.dll",
    "swresample-7.dll",
    "swscale-10.dll"
)

foreach ($dll in $requiredDlls) {

    $dllPath = Join-Path $ffmpegSharedBin $dll

    if (-not (Test-Path $dllPath)) {

        Write-Host "ERROR: Missing FFmpeg DLL:" -ForegroundColor Red
        Write-Host $dll -ForegroundColor Red
        Write-Host ""

        exit 1
    }
}

Write-Host "FFmpeg Shared DLLs: OK" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# 6. Put FFmpeg Shared first in PATH
# ------------------------------------------------------------

$env:Path = "$ffmpegSharedBin;$env:Path"

Write-Host "FFmpeg Shared added to PATH." -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# 7. Verify FFmpeg executable
# ------------------------------------------------------------

$ffmpegExe = Join-Path $ffmpegSharedBin "ffmpeg.exe"

if (Test-Path $ffmpegExe) {

    Write-Host "FFmpeg executable:" -ForegroundColor Green
    Write-Host $ffmpegExe
    Write-Host ""

    & $ffmpegExe -version | Select-Object -First 1

}
else {

    Write-Host "WARNING: ffmpeg.exe was not found." -ForegroundColor Yellow
}

Write-Host ""

# ------------------------------------------------------------
# 8. Start Streamlit
# ------------------------------------------------------------

Write-Host "Starting Offline Voice Studio..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Local URL: http://127.0.0.1:8501" -ForegroundColor Green
Write-Host ""

& $python -m streamlit run app.py --server.address 127.0.0.1