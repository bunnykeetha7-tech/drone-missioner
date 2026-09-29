@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo      DRONE MISSIONS - GROUND STATION
echo ========================================
where python >nul 2>nul
if errorlevel 1 (echo Python 3.10+ is required. Install from https://python.org and enable PATH.& pause& exit /b 1)
if not exist ".venv\Scripts\python.exe" (echo Creating virtual environment...& python -m venv .venv || (echo Could not create virtual environment.& pause& exit /b 1))
echo Installing backend requirements...
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 (echo Dependency installation failed. Check internet connection.& pause& exit /b 1)
start "Drone Missions" http://127.0.0.1:8000
echo Server starting at http://127.0.0.1:8000 (API docs /docs)
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
