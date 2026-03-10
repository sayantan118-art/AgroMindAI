@echo off
echo Starting AgroMind AI Full Stack...

echo Starting Mosquitto MQTT...
start "Mosquitto" cmd /k "net start mosquitto"

timeout /t 2

echo Starting FastAPI Backend...
start "Backend" cmd /k "cd C:\My files\AroMindAI\backend && C:\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 3

echo Starting n8n...
start "n8n" cmd /k "n8n start"

timeout /t 5

echo Starting Dashboard...
start "Dashboard" cmd /k "serve -s C:\My files\AroMindAI\dashboard\dist -l 5173"

timeout /t 2

echo Starting ngrok tunnel for dashboard...
start "ngrok" cmd /k "C:\My files\AroMindAI\ngrok.exe http 5173"

timeout /t 2

echo.
echo All services started!
echo Dashboard: https://columbus-unacidulated-alvina.ngrok-free.dev
echo Backend: Check ngrok terminal for backend tunnel URL
pause
