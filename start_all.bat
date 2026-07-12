@echo off
setlocal enabledelayedexpansion
echo =========================================
echo    AgroMind AI - Local Dev Startup
echo =========================================
echo.

REM Set project root (update this if you move the folder)
set PROJECT_ROOT=C:\My files\projectss\AgroMindAI

echo [1] Starting FastAPI Backend (port 8000)...
start "AgroMind Backend" cmd /k "cd /d "%PROJECT_ROOT%\backend" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 >nul

echo [2] Starting React Dashboard (port 5173)...
start "AgroMind Dashboard" cmd /k "cd /d "%PROJECT_ROOT%\dashboard" && npm run dev"
timeout /t 2 >nul

echo [3] Starting Sensor Simulator...
start "AgroMind Simulator" cmd /k "cd /d "%PROJECT_ROOT%" && python simulator.py"

echo.
echo =========================================
echo  All services started!
echo =========================================
echo.
echo  LOCAL ACCESS:
echo  - Backend API:    http://localhost:8000
echo  - API Docs:       http://localhost:8000/docs
echo  - Agent Health:   http://localhost:8000/agents/health
echo  - Dashboard:      http://localhost:5173
echo.
echo  MQTT Broker (HiveMQ Cloud):
echo  - Host in backend/.env  (MQTT_BROKER)
echo  - Topic: agromind/data
echo.
echo  Press Ctrl+C in any window to stop that service.
echo =========================================
pause
