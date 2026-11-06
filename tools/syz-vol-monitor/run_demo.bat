@echo off
cd /d %~dp0
where python >nul 2>nul || (echo Python is not installed. & pause & exit /b 1)
if exist .venv\Scripts\python.exe (.venv\Scripts\python -m vol_monitor.app --demo) else (python -m vol_monitor.app --demo)
pause
