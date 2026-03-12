# AgroMind AI - Exact Commands to Run

## 🚀 FASTEST WAY (Recommended)

### Double-click this file:
```
C:\My files\AroMindAI\start_all.bat
```

**That's it!** All 6 services will start automatically.

---

## 📋 MANUAL STARTUP (If batch file doesn't work)

Open **6 separate PowerShell windows** and run these commands in order:

### Window 1: MQTT Broker
```powershell
net start mosquitto
```
✅ Should show: "The Mosquitto service is starting..."

---

### Window 2: FastAPI Backend
```powershell
cd "C:\My files\AroMindAI\backend"
C:\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
✅ Should show: "Uvicorn running on http://0.0.0.0:8000"

---

### Window 3: n8n Workflow Engine
```powershell
n8n start
```
✅ Should show: "n8n ready on http://localhost:5678"

---

### Window 4: Build & Serve Dashboard
```powershell
cd "C:\My files\AroMindAI\dashboard"
npm run build
serve -s dist -l 5173
```
✅ Should show: "Accepting connections at http://localhost:5173"

---

### Window 5: ngrok Public Tunnel
```powershell
cd "C:\My files\AroMindAI"
.\ngrok.exe http 5173
```
✅ Should show: "Forwarding https://[random-id].ngrok-free.app -> http://localhost:5173"

---

### Window 6: Monitor (Optional)
```powershell
# Just keep this open to watch for errors
# Or run this to check all ports:
netstat -ano | findstr :8000
netstat -ano | findstr :5173
netstat -ano | findstr :5678
netstat -ano | findstr :1883
```

---

## ✅ VERIFICATION COMMANDS

After all services are running, verify each one:

### Check MQTT Broker
```powershell
netstat -ano | findstr :1883
```
Should show: `LISTENING`

### Check Backend API
```powershell
curl http://localhost:8000/health
```
Should return: `{"status":"ok"}`

### Check Backend Docs
```powershell
start http://localhost:8000/docs
```
Should open Swagger UI in browser

### Check Agent Health
```powershell
curl http://localhost:8000/agents/health
```
Should return: Agent status JSON

### Check n8n
```powershell
start http://localhost:5678
```
Should open n8n login page

### Check Dashboard
```powershell
start http://localhost:5173
```
Should show dashboard with "System Online"

### Check ngrok
Look at the ngrok terminal window for the public URL:
```
https://columbus-unacidulated-alvina.ngrok-free.app
```

---

## 🔧 TROUBLESHOOTING COMMANDS

### Port Already in Use?
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual number)
taskkill /PID 12345 /F

# Then restart the service
```

### Backend Won't Start?
```powershell
# Check Python is installed
C:\Python314\python.exe --version

# Check uvicorn is installed
C:\Python314\python.exe -m pip list | findstr uvicorn

# Check .env file exists
cat "C:\My files\AroMindAI\backend\.env"

# Check GROQ_API_KEY is set
$env:GROQ_API_KEY
```

### Dashboard Won't Build?
```powershell
cd "C:\My files\AroMindAI\dashboard"

# Check npm is installed
npm --version

# Install dependencies
npm install

# Try building again
npm run build

# Check dist folder was created
ls dist
```

### ngrok Not Working?
```powershell
# Check ngrok.exe exists
ls "C:\My files\ngrok.exe"

# Check internet connection
ping google.com

# Try running ngrok manually
cd "C:\My files\AroMindAI"
.\ngrok.exe http 5173

# If it closes, check ngrok is authenticated
.\ngrok.exe config check
```

### MQTT Connection Failed?
```powershell
# Check Mosquitto is running
net start mosquitto

# Check port 1883 is listening
netstat -ano | findstr :1883

# Restart Mosquitto
net stop mosquitto
net start mosquitto
```

---

## 📊 MONITORING COMMANDS

### Watch Backend Logs
```powershell
# If backend is running in a window, you'll see logs there
# Or check the database:
sqlite3 "C:\My files\AroMindAI\backend\agromind.db" "SELECT * FROM sensor_logs ORDER BY timestamp DESC LIMIT 5;"
```

### Watch MQTT Messages
```powershell
# If mosquitto_sub is installed:
mosquitto_sub -h 10.64.168.176 -t "agromind/#"

# Or use Python:
python -m paho-mqtt.client -h 10.64.168.176 -t "agromind/#"
```

### Watch Dashboard Requests
```powershell
# In the backend window, you'll see HTTP requests logged
# Or check with curl:
curl -v http://localhost:8000/sensor/latest
```

---

## 🌐 ACCESS POINTS

### Local Computer
```
Dashboard:     http://localhost:5173
Backend API:   http://localhost:8000
API Docs:      http://localhost:8000/docs
Agent Health:  http://localhost:8000/agents/health
n8n:           http://localhost:5678
```

### Same WiFi Network
```
Dashboard:     http://10.21.34.128:5173
Backend API:   http://10.21.34.128:8000
API Docs:      http://10.21.34.128:8000/docs
n8n:           http://10.21.34.128:5678
```

### Public Internet (via ngrok)
```
Dashboard:     https://columbus-unacidulated-alvina.ngrok-free.app
               (Check ngrok window for actual URL)
```

---

## 🛑 STOPPING SERVICES

### Stop All Services
```powershell
# Close each terminal window (Ctrl+C in each)
# Or kill all processes:
taskkill /F /IM python.exe
taskkill /F /IM node.exe
taskkill /F /IM ngrok.exe
net stop mosquitto
```

### Stop Individual Services
```powershell
# Stop MQTT
net stop mosquitto

# Stop Backend (Ctrl+C in backend window)

# Stop n8n (Ctrl+C in n8n window)

# Stop Dashboard (Ctrl+C in dashboard window)

# Stop ngrok (Ctrl+C in ngrok window)
```

---

## 📝 QUICK REFERENCE

| Service | Port | Command | Status Check |
|---------|------|---------|--------------|
| MQTT | 1883 | `net start mosquitto` | `netstat -ano \| findstr :1883` |
| Backend | 8000 | `uvicorn main:app --host 0.0.0.0 --port 8000` | `curl http://localhost:8000/health` |
| n8n | 5678 | `n8n start` | `curl http://localhost:5678` |
| Dashboard | 5173 | `serve -s dist -l 5173` | `curl http://localhost:5173` |
| ngrok | - | `ngrok http 5173` | Check ngrok window |

---

## 🎯 NEXT STEPS

1. **Run**: `C:\My files\AroMindAI\start_all.bat`
2. **Wait**: ~15 seconds for all services to start
3. **Check**: http://localhost:5173 should show dashboard
4. **Verify**: All 6 terminal windows should be open
5. **Access**: Use ngrok URL from phone/other device

---

## 💡 TIPS

- **Keep all 6 windows open** while system is running
- **Don't close any window** unless you want to stop that service
- **Check ngrok window** for the public URL (changes each time)
- **Use Ctrl+C** to stop a service gracefully
- **Use Ctrl+Shift+Esc** to force-kill a process if needed
- **Run as Administrator** if you get permission errors

---

**Ready to start? Run: `C:\My files\AroMindAI\start_all.bat`**
