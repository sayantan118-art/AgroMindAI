# AgroMind AI

**Agentic Cyber-Physical Farming Intelligence System**

AgroMind AI autonomously monitors crop conditions and controls irrigation using a 5-agent AI pipeline, IoT sensors, and cloud infrastructure — no n8n, no Mosquitto, no ngrok required.

---

## Architecture

```
ESP32 / Simulator
  → HiveMQ Cloud MQTT (agromind/data, TLS port 8883)
  → FastAPI backend  (mqtt_worker.py subscribes in background)
  → 5-Agent AI pipeline  (AgentOrchestrator)
       ├─ Sensor Interpreter   – classifies environmental state
       ├─ Crop Doctor          – scores crop health (0-100)
       ├─ Weather Intelligence – reads Open-Meteo forecast
       ├─ Irrigation Planner   – decides IRRIGATE / DELAY / SKIP
       └─ Safety Supervisor    – validates & caps pump runtime
  → MQTT pump command  (agromind/data, type=pump)
  → WebSocket broadcast
  → React dashboard    (real-time sensor + AI data)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Firmware | Arduino C++ (ESP32) |
| Communication | MQTT over TLS — HiveMQ Cloud (port 8883) |
| Backend | FastAPI + Uvicorn (Python) |
| AI | Groq API — llama-3.3-70b-versatile |
| Database | SQLite via aiosqlite |
| Dashboard | React 18 + Vite + Recharts + Tailwind CSS |
| Weather | Open-Meteo API (free, no key needed) |
| Deployment | Render (backend) + Vercel (dashboard) |

---

## Project Structure

```
AgroMindAI/
├── backend/
│   ├── agents/                  # 5-agent AI pipeline
│   │   ├── base_agent.py        # Shared base class (Groq HTTP calls)
│   │   ├── sensor_interpreter.py
│   │   ├── crop_doctor.py
│   │   ├── weather_intelligence.py
│   │   ├── irrigation_planner.py
│   │   ├── safety_supervisor.py
│   │   ├── memory_agent.py      # In-process short-term memory
│   │   ├── orchestrator.py      # Coordinates the full pipeline
│   │   └── README.md
│   ├── agents_endpoint.py       # /agents/* REST API
│   ├── main.py                  # FastAPI app entry point
│   ├── mqtt_worker.py           # Background MQTT subscriber + AI dispatch
│   ├── requirements.txt
│   ├── .env                     # Local env vars (not committed)
│   └── agromind.db              # SQLite database
├── dashboard/
│   ├── src/
│   │   ├── App.jsx              # Main React component
│   │   └── main.jsx
│   ├── vercel.json              # Vercel SPA rewrite rule
│   ├── vite.config.js
│   └── package.json
├── firmware/
│   └── agromind_esp32/
│       ├── agromind_esp32.ino   # ESP32 Arduino sketch
│       └── secrets.h.example   # WiFi + MQTT credentials template
├── docs/
│   ├── MULTI_AGENT_SYSTEM.md   # Agent pipeline details
│   ├── SYSTEM_ARCHITECTURE.md  # Full architecture reference
│   └── HARDWARE_SHOPPING_LIST.md
├── simulator.py                 # Sends mock sensor data via MQTT
├── start_all.bat                # Windows one-click dev startup
└── README.md
```

---

## Quick Start (Local Dev — no ESP32 needed)

**Prerequisites:** Python 3.10+, Node.js 18+

```powershell
# 1. Clone and enter the project
cd "C:\My files\projectss\AgroMindAI"

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt

# 3. Configure environment variables
#    Copy the example and fill in your values (see section below)
copy .env .env.local   # already present; just add GROQ_API_KEY

# 4. Install dashboard dependencies
cd ..\dashboard
npm install

# 5. Start everything
cd ..
start_all.bat
```

`start_all.bat` opens three terminal windows:
- Window 1 — FastAPI backend on `http://localhost:8000`
- Window 2 — React dashboard on `http://localhost:5173`
- Window 3 — Sensor simulator (publishes fake readings to HiveMQ)

---

## Environment Variables

Create (or edit) `backend/.env`:

```dotenv
# ── MQTT (HiveMQ Cloud) ──────────────────────────────────────
MQTT_BROKER=<your-hivemq-host>.hivemq.cloud
MQTT_PORT=8883
MQTT_USER=<hivemq-username>
MQTT_PASS=<hivemq-password>

# ── Groq AI ──────────────────────────────────────────────────
# Get a free key at https://console.groq.com/keys
# Without this, the system uses rule-based fallback logic.
GROQ_API_KEY=

# ── Location for weather forecast (Open-Meteo) ───────────────
LATITUDE=22.5726
LONGITUDE=88.3639

# ── Database ─────────────────────────────────────────────────
DB_PATH=agromind.db
```

| Variable | Description |
|---|---|
| `MQTT_BROKER` | HiveMQ Cloud hostname |
| `MQTT_PORT` | TLS port — usually `8883` |
| `MQTT_USER` | HiveMQ username |
| `MQTT_PASS` | HiveMQ password |
| `GROQ_API_KEY` | Groq API key for the AI pipeline |
| `LATITUDE` | Decimal latitude for weather queries |
| `LONGITUDE` | Decimal longitude for weather queries |
| `DB_PATH` | SQLite database filename (relative to `backend/`) |

---

## AI Agents

The full pipeline runs automatically for every incoming sensor message.

| # | Agent | Role |
|---|---|---|
| 1 | Sensor Interpreter | Classifies soil status, heat stress, evaporation risk |
| 2 | Crop Doctor | Scores crop health 0–100, diagnoses stress type |
| 3 | Weather Intelligence | Reads Open-Meteo forecast, determines irrigation impact |
| 4 | Irrigation Planner | Decides IRRIGATE / DELAY / SKIP, calculates pump duration |
| 5 | Safety Supervisor | Validates command, enforces pump runtime cap (180 s max) |
| 6 | Memory Agent | Tracks last 5 readings, detects soil/temp trends |

Each agent has a rule-based fallback — if Groq is unavailable the system keeps working.

---

## Safety Features

- Pump runtime hard-capped at 180 seconds in Safety Supervisor
- Maximum 10 irrigation events per day enforced by Safety Supervisor
- Sensor validity range checks before any irrigation decision
- Every agent has a deterministic fallback path — no single point of failure
- If `GROQ_API_KEY` is missing, the system falls back to rule-based logic automatically

---

## Deployment

### Backend → Render

1. Create a new **Web Service** pointing to the `backend/` folder.
2. Set **Start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Add all environment variables from the table above in the Render dashboard.

### Dashboard → Vercel

`dashboard/vercel.json` already contains the SPA rewrite rule.

```bash
cd dashboard
vercel --prod
```

Set `VITE_API_BASE` and `VITE_WS_BASE` in the Vercel project settings to point at your Render backend URL.

### MQTT Broker

Use [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/) free tier.  
Topic: `agromind/data` (both sensor publishes and pump commands use this single topic).

---

## API Reference (quick)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend health check |
| `GET` | `/sensor/latest` | Most recent sensor reading |
| `GET` | `/sensor/history` | Historical readings |
| `GET` | `/weather/forecast` | Current Open-Meteo forecast |
| `POST` | `/agents/decide` | Run the full agent pipeline manually |
| `GET` | `/agents/health` | Agent system status |
| `WS` | `/ws/dashboard` | Real-time WebSocket stream |

Full interactive docs available at `http://localhost:8000/docs`.
