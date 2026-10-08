@echo off
REM Double-click: shows which voices and cloning engines are ready.
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\check_setup.py"
pause
