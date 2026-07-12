@echo off
setlocal enabledelayedexpansion
echo =========================================
echo    AgroMind AI v3.0 - Full Stack Startup
echo =========================================
echo.

REM Set project root
set PROJECT_ROOT=C:\My files\AgroMindAI

echo [1] Starting Mosquitto MQTT Broker...
start "Mosquitto" cmd /k "net start mosquitto"
timeout /t 2 >nul

echo [2] Starting FastAPI Backend (port 8000)...
start "Backend" cmd /k "cd /d "%PROJECT_ROOT%\backend" && C:\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 >nul

echo [3] Starting n8n Workflow Engine (port 5678)...
start "n8n" cmd /k "n8n start"
timeout /t 5 >nul

echo [4] Building React Dashboard...
cd /d "%PROJECT_ROOT%\dashboard"
call npm run build
timeout /t 3 >nul

echo [5] Starting React Dashboard (port 5173)...
start "Dashboard" cmd /k "serve -s "%PROJECT_ROOT%\dashboard\dist" -l 5173"
timeout /t 2 >nul

echo [6] Starting ngrok tunnel for public access...
start "ngrok" cmd /k "cd /d "%PROJECT_ROOT%" && "C:\My files\ngrok.exe" http 5173"
timeout /t 3 >nul

echo.
echo =========================================
echo  All services started!
echo =========================================
echo.
echo  LOCAL ACCESS:
echo  - Backend API:    http://localhost:8000
echo  - Backend Docs:   http://localhost:8000/docs
echo  - Agent Health:   http://localhost:8000/agents/health
echo  - Dashboard:      http://localhost:5173
echo  - n8n Workflows:  http://localhost:5678
echo.
echo  PUBLIC ACCESS (via ngrok):
echo  - Check ngrok terminal window for public URL
echo  - Format: https://[random-id].ngrok-free.app
echo.
echo  MQTT Broker:      10.64.168.176:1883
echo.
echo  Workflows:        %PROJECT_ROOT%\workflows\
echo  (use workflow-main.json, workflow-health.json, workflow-report.json)
echo.
echo =========================================
echo  Press Ctrl+C in any window to stop that service
echo =========================================
pause
