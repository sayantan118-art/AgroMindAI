# AgroMind AI — Service Port Checker
# Run this script in PowerShell to verify all services are running

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host " AgroMind AI - Service Status Check" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

function Check-Port {
    param([string]$Name, [int]$Port)
    $result = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($result) {
        Write-Host "  PASS  $Name (port $Port)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  $Name (port $Port)" -ForegroundColor Red
    }
}

Check-Port "Mosquitto MQTT"      1883
Check-Port "FastAPI Backend"     8000
Check-Port "n8n Workflow Engine" 5678
Check-Port "AnythingLLM"         3001
Check-Port "Ollama"              11434
Check-Port "React Dashboard"     5173

Write-Host "`n======================================`n" -ForegroundColor Cyan
