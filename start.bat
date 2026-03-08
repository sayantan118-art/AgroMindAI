@echo off
echo Starting AgroMind AI...
start "AgroMind Backend" cmd /k "cd C:\MyFiles\AgroMindAI\backend && C:\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000"
start "AgroMind n8n" cmd /k "n8n start"
start "AgroMind Dashboard" cmd /k "cd C:\MyFiles\AgroMindAI\dashboard && npm run dev"
echo All services started.
