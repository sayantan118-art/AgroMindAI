# AgroMind AI

**Agentic Smart Farming System — ESP32 + Cloud Python Backend + React Dashboard**

AgroMind AI autonomously monitors crop conditions and controls irrigation using AI reasoning, IoT sensors, and a fully cloud-native Python backend — no n8n or local automation tools required.

---

## Architecture (v3.0 — Cloud-Native, n8n-Free)

```
ESP32 Sensors
  → HiveMQ Cloud (MQTT broker)
  → Render Python Backend (mqtt_worker.py)
      ├─ Open-Meteo API (weather forecast)
      ├─ Groq API — Llama 3.3 70B (AI irrigation decision)
      ├─ SQLite (sensor log, pump log, reports)
      └─ WebSocket broadcast → React Dashboard
  → MQTT pump command → ESP32 Relay → Water Pump
```

**Key change from v2:** n8n workflows are completely removed. All automation (MQTT subscription, AI decision, DB logging, WebSocket broadcast, pump control) runs inside `backend/mqtt_worker.py` on Render.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Firmware | Arduino C++ (ESP32) |
| MQTT Broker | HiveMQ Cloud (TLS 8883) |
| Backend | FastAPI + Python on Render |
| AI Pipeline | Groq API — llama-3.3-70b-versatile |
| Analytics | Pure Python (ET₀, Stress Index, Pest Risk, Irrigation ETA) |
| Database | SQLite (Render persistent disk) |
| Dashboard | React + Vite + Recharts |
| Weather | Open-Meteo API (free, no key needed) |

---

## Project Structure

```
AgroMindAI/
├── backend/
│   ├── main.py              # FastAPI server + all API endpoints
│   ├── mqtt_worker.py       # MQTT subscriber + Groq AI + WebSocket broadcaster
│   ├── analytics.py         # ET₀, Crop Stress, Pest Risk, Irrigation ETA, Water Usage
│   ├── crop_config.py       # Crop stage profiles (7 crops × 4 stages)
│   ├── agents_endpoint.py   # Multi-agent REST API (optional)
│   ├── agents/              # Specialized AI agents
│   ├── requirements.txt
│   └── .env                 # Local secrets (not committed)
├── dashboard/               # React + Vite dashboard
│   └── src/App.jsx          # Main dashboard with 7 analytics panels
├── firmware/
│   └── agromind_esp32/      # ESP32 Arduino sketch
├── docs/                    # Documentation
├── simulator.py             # Sensor data simulator for testing
└── start_all.bat            # Local dev startup script
```

---

## Quick Start (Local Dev)

```powershell
# Start backend + dashboard + ngrok in one click:
start_all.bat

# Or individually:
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

cd dashboard
npm run dev
```

The React dashboard connects to the **Render cloud backend** by default.
To use your local backend, change `API_BASE` in `dashboard/src/App.jsx`.

---

## Analytics Features

The dashboard displays 7 computed analytics panels from live sensor data:

1. **ET₀ Drying Rate** — How fast soil is losing moisture (mm/day)
2. **Crop Stress Index** — 0–100 plant health score from all 5 sensors
3. **Pest & Disease Risk** — Fungal risk level from temp + humidity
4. **Irrigation ETA** — Predicted hours until next irrigation needed
5. **Water Usage** — Litres used today and this week
6. **Historical Charts** — 24h and 7-day soil/temp/humidity trends
7. **Crop Stage Selector** — Set crop type + growth stage; AI adjusts thresholds

---

## AI Decision Pipeline

Each sensor reading triggers:
1. **Open-Meteo** weather lookup (rain probability)
2. **Groq Llama 3.3** decision: `IRRIGATE / DELAY / SKIP`
3. If IRRIGATE → MQTT pump command sent to ESP32
4. All data logged to SQLite + broadcast to dashboard WebSocket

Rule-based fallback activates if Groq is unavailable.

---

## Environment Variables (Render)

Set these in your Render dashboard under **Environment**:

```
GROQ_API_KEY=gsk_...
MQTT_BROKER=***REMOVED***
MQTT_PORT=8883
MQTT_USER=***REMOVED***
MQTT_PASS=your_mqtt_password
DB_PATH=agromind.db
LATITUDE=22.5726
LONGITUDE=88.3639
```

---

## Deployment

- **Backend**: Render Web Service — `backend/` directory, start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Dashboard**: Any static host (Netlify, Vercel, Cloudflare Pages) — build `dashboard/` with `npm run build`
- **MQTT**: HiveMQ Cloud free tier — credentials stored in Render env vars only