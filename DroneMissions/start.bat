@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo      DRONE MISSIONS - GROUND STATION
echo ========================================
where python >nul 2>nul
if errorlevel 1 (echo Python 3.10+ is required. Install from https://python.org and enable PATH.& pause& exit /b 1)
python -c "import urllib.request; s=urllib.request.urlopen('http://127.0.0.1:8000/',timeout=1).read(8192).decode('utf-8','ignore'); raise SystemExit(0 if 'Drone Missions | Ground Control Station' in s else 1)" >nul 2>nul
if not errorlevel 1 (
  echo Drone Missions is already running on port 8000. Opening the existing application.
  start "" http://127.0.0.1:8000
  exit /b 0
)
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',8000); exit 0 } catch { exit 1 } finally { if ($c) { $c.Dispose() } }" >nul 2>nul
if not errorlevel 1 (
  echo ERROR: Port 8000 is already used by another application.
  echo Close that application or change the Drone Missions port in start.bat.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (echo Creating virtual environment...& python -m venv .venv || (echo Could not create virtual environment.& pause& exit /b 1))
echo Installing backend requirements...
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 (echo Dependency installation failed. Check internet connection.& pause& exit /b 1)
start "Drone Missions" http://127.0.0.1:8000
echo Server starting at http://127.0.0.1:8000 (API docs /docs)
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
