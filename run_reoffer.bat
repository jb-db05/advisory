@echo off
REM Double-click: imports everything in workspace\inbox and rebuilds the reports.
cd /d "%~dp0"
python -m reoffer run
echo.
if errorlevel 1 (echo Some rows were refused - open the exceptions file in workspace\output.) else (echo All rows imported.)
start "" "workspace\output"
pause
