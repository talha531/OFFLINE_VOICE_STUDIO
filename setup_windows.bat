@echo off
REM Double-click for first-time setup (needs uv and internet once).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1"
pause
