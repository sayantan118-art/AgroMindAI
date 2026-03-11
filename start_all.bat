@echo off
echo =========================================
echo    AgroMind AI v3.0 - Local Dev Startup
echo =========================================
echo.

echo [1] Starting Mosquitto MQTT Broker...
start "Mosquitto" /min cmd /c "net start mosquitto"
timeout /t 2 >nul

echo [2] Starting FastAPI Backend (port 8000)...
start "Backend" /min cmd /c "cd /d "C:\My files\AroMindAI\backend" && C:\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 >nul

echo [3] Starting n8n Workflow Engine (port 5678)...
start "n8n" /min cmd /c "n8n start"
timeout /t 5 >nul

echo [4] Starting React Dashboard (port 5173)...
start "Dashboard" /min cmd /c "serve -s "C:\My files\AroMindAI\dashboard\dist" -l 5173"
timeout /t 2 >nul

echo.
echo =========================================
echo  All services started in background!
echo =========================================
echo.
echo  Backend API:    http://localhost:8000
echo  Backend Docs:   http://localhost:8000/docs
echo  Agent Health:   http://localhost:8000/agents/health
echo  Dashboard:      http://localhost:5173
echo  n8n Workflows:  http://localhost:5678
echo.
echo  NOTE: Backend is ALSO deployed on Render:
echo        https://agromind-ai.onrender.com
echo.
echo  Import workflows from: C:\My files\AroMindAI\workflows\
echo  (use workflow-main.json, workflow-health.json, workflow-report.json)
echo.
echo =========================================
pause
