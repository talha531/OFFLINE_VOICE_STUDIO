@echo off
REM Double-click: installs offline voice cloning (needs internet once, about 2.5 GB).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_cloning.ps1"
pause
