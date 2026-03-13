@echo off
setlocal enabledelayedexpansion
echo =============================================
echo   AgroMind AI v3.0 - Local Dev Startup
echo =============================================
echo.
echo   Architecture: ESP32 -> HiveMQ Cloud -> Render Backend -> Dashboard
echo   n8n is NOT used. All automation runs in the Python backend on Render.
echo.

REM Set project root
set PROJECT_ROOT=C:\My files\AroMindAI

echo [1] Starting FastAPI Backend (port 8000)...
echo     NOTE: On Render this starts automatically. Run locally only for testing.
start "AgroMind Backend" cmd /k "cd /d "%PROJECT_ROOT%\backend" && C:\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 >nul

echo [2] Starting React Dashboard Dev Server (port 5173)...
start "AgroMind Dashboard" cmd /k "cd /d "%PROJECT_ROOT%\dashboard" && npm run dev"
timeout /t 3 >nul

echo [3] Starting ngrok tunnel (exposes port 5173 publicly)...
start "ngrok" cmd /k "cd /d "%PROJECT_ROOT%" && "C:\My files\ngrok.exe" http 5173"
timeout /t 3 >nul

echo.
echo =============================================
echo  Services Started!
echo =============================================
echo.
echo  LOCAL ACCESS:
echo  - Backend API:     http://localhost:8000
echo  - Backend Docs:    http://localhost:8000/docs
echo  - Dashboard:       http://localhost:5173
echo.
echo  CLOUD (always running on Render):
echo  - Backend:         https://agromindai-q5m4.onrender.com
echo  - Health check:    https://agromindai-q5m4.onrender.com/health
echo  - Analytics:       https://agromindai-q5m4.onrender.com/analytics/all
echo.
echo  MQTT (HiveMQ Cloud - managed by Render backend):
echo  - Broker:          ***REMOVED***:8883
echo  - Topics:          agromind/sensors  (ESP32 -> Cloud)
echo  -                  agromind/pump     (Cloud -> ESP32)
echo.
echo  PUBLIC ACCESS (via ngrok):
echo  - Check ngrok terminal for the https://xxxx.ngrok-free.app URL
echo.
echo =============================================
echo  Press Ctrl+C in any window to stop that service
echo =============================================
pause
