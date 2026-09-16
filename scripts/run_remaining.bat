@echo off
cd /d "%~dp0\.."
".venv\Scripts\python.exe" scripts\run_remaining.py %*
if errorlevel 1 pause
