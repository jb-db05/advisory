@echo off
cd /d %~dp0
where python >nul 2>nul || (echo Python 3.10 or later is not installed. Install it from the Software Center or python.org, then run this again. & pause & exit /b 1)
echo Creating the environment...
python -m venv .venv || (pause & exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip
echo Installing the Bloomberg Python API (blpapi)...
.venv\Scripts\python -m pip install --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi || (echo Could not install blpapi: ask IT to allow blpapi.bloomberg.com or install it for you. & pause & exit /b 1)
echo Installing Outlook support for e-mail alerts (optional)...
.venv\Scripts\python -m pip install pywin32
echo.
echo Setup done. Start the tool with run_vol_monitor.bat
pause
