# AgroMind AI — System Architecture

**Project path**: `C:\My files\projectss\AgroMindAI`

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│  PHYSICAL LAYER                                              │
│                                                              │
│  ESP32 + sensors  (or simulator.py for local dev)            │
│  ├─ Capacitive soil moisture sensor  (GPIO 34 — analog)      │
│  ├─ DHT22 temperature/humidity       (GPIO 16 — digital)     │
│  ├─ Rain sensor DO                   (GPIO 18 — digital)     │
│  ├─ LDR light sensor                 (GPIO 35 — analog)      │
│  └─ Relay → water pump               (GPIO 26 — output)      │
│                                                              │
│  Publishes JSON  →  topic: agromind/data                     │
│  Subscribes      →  topic: agromind/data  (pump commands)    │
└───────────────────────────┬──────────────────────────────────┘
                            │ MQTT TLS (port 8883)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  MESSAGING LAYER                                             │
│                                                              │
│  HiveMQ Cloud (free tier)                                    │
│  Topic: agromind/data  — all messages (sensor + pump)        │
│  Message types:                                              │
│    { "type": "sensor", "soil": …, "temp": …, … }            │
│    { "type": "pump",   "action": "ON", "duration_sec": … }   │
└───────────────────────────┬──────────────────────────────────┘
                            │ paho-mqtt v2 (background thread)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  BACKEND LAYER  —  FastAPI (Python)                          │
│  Deployed on Render  (or localhost:8000 in dev)              │
│                                                              │
│  mqtt_worker.py                                              │
│  ├─ Subscribes to agromind/data                              │
│  ├─ Ignores non-sensor messages                              │
│  ├─ Fetches Open-Meteo weather forecast                      │
│  └─ Calls AgentOrchestrator.process_sensor_data()            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  5-AGENT AI PIPELINE (agents/orchestrator.py)        │   │
│  │                                                      │   │
│  │  1. Memory Agent          (no LLM — pure Python)     │   │
│  │  2. Sensor Interpreter    (Groq llama-3.3-70b)        │   │
│  │  3. Crop Doctor           (Groq llama-3.3-70b)        │   │
│  │  4. Weather Intelligence  (Groq llama-3.3-70b)        │   │
│  │  5. Irrigation Planner    (Groq llama-3.3-70b)        │   │
│  │  6. Safety Supervisor     (Groq llama-3.3-70b)        │   │
│  │                                                      │   │
│  │  Fallback: single Groq call → rule-based logic       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  REST endpoints                                              │
│  ├─ GET  /health                  backend health             │
│  ├─ GET  /sensor/latest           most recent reading        │
│  ├─ GET  /sensor/history          historical data            │
│  ├─ GET  /weather/forecast        Open-Meteo proxy           │
│  ├─ POST /pump/log                log pump events            │
│  ├─ GET  /pump/usage/today        today's pump stats         │
│  ├─ POST /agents/decide           run agent pipeline         │
│  ├─ GET  /agents/health           agent system status        │
│  ├─ GET  /agents/memory/context   memory & trends            │
│  ├─ POST /agents/memory/clear     reset memory               │
│  └─ WS   /ws/dashboard            real-time WebSocket        │
│                                                              │
│  Database: SQLite (agromind.db via aiosqlite)                │
│  Tables: sensor_logs, pump_log                               │
└───────────────┬──────────────────────────────────────────────┘
                │ WebSocket  +  MQTT pump publish
       ┌────────┴────────────────┐
       ▼                         ▼
┌──────────────────┐   ┌─────────────────────────────────┐
│  DASHBOARD       │   │  MQTT pump command              │
│  React + Vite    │   │  agromind/data                  │
│  Deployed on     │   │  { "type":"pump","action":"ON", │
│  Vercel          │   │    "duration_sec": 120 }         │
│  (localhost:5173 │   │  → ESP32 relay → water pump      │
│   in dev)        │   └─────────────────────────────────┘
└──────────────────┘
```

---

## File Structure

```
C:\My files\projectss\AgroMindAI\
├── backend\
│   ├── agents\
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── sensor_interpreter.py
│   │   ├── crop_doctor.py
│   │   ├── weather_intelligence.py
│   │   ├── irrigation_planner.py
│   │   ├── safety_supervisor.py
│   │   ├── memory_agent.py
│   │   ├── orchestrator.py
│   │   └── README.md
│   ├── agents_endpoint.py
│   ├── main.py
│   ├── mqtt_worker.py
│   ├── requirements.txt
│   ├── .env
│   └── agromind.db
├── dashboard\
│   ├── src\
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── vercel.json
│   ├── vite.config.js
│   └── package.json
├── firmware\
│   └── agromind_esp32\
│       ├── agromind_esp32.ino
│       ├── secrets.h.example
│       └── secrets.h          (gitignored — WiFi/MQTT creds)
├── docs\
│   ├── MULTI_AGENT_SYSTEM.md
│   ├── SYSTEM_ARCHITECTURE.md  (this file)
│   └── HARDWARE_SHOPPING_LIST.md
├── simulator.py
├── start_all.bat
└── README.md
```

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Backend (FastAPI) | [Render](https://render.com) | Web Service, `backend/` root, Python env |
| Dashboard (React) | [Vercel](https://vercel.com) | `dashboard/` root, `vercel.json` already present |
| MQTT Broker | [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/) | Free tier, TLS port 8883 |

### Render — backend start command

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set all `backend/.env` variables as Render environment variables.

### Vercel — dashboard

```bash
cd dashboard
vercel --prod
```

Set `VITE_API_BASE` and `VITE_WS_BASE` to your Render backend URL in the Vercel project settings.

---

## Local Development

```powershell
# Start all three components with one script
cd "C:\My files\projectss\AgroMindAI"
.\start_all.bat
```

Or manually:

```powershell
# Terminal 1 — Backend
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Dashboard
cd dashboard
npm run dev

# Terminal 3 — Simulator (no ESP32 needed)
cd ..
python simulator.py
```

---

## Environment Variables

All configuration lives in `backend/.env` (see `README.md` for the full table).

Key variables:

| Variable | Purpose |
|---|---|
| `MQTT_BROKER` | HiveMQ Cloud hostname |
| `MQTT_PORT` | `8883` (TLS) |
| `MQTT_USER` / `MQTT_PASS` | HiveMQ credentials |
| `GROQ_API_KEY` | Groq AI — enables the full agent pipeline |
| `LATITUDE` / `LONGITUDE` | Location for Open-Meteo weather |
| `DB_PATH` | SQLite file path |

---

## Key Design Decisions

**Single MQTT topic** (`agromind/data`) — both sensor readings and pump commands share one topic, differentiated by a `type` field. This simplifies HiveMQ ACL rules and ESP32 subscription logic.

**Agents wired into MQTT worker** — the orchestrator runs inline inside `mqtt_worker._process()` on every sensor message. No separate scheduler or HTTP hop is needed.

**Lazy Groq initialisation** — `mqtt_worker.start()` initialises the Groq client *after* `load_dotenv()` has run in `main.py`, so the API key is always available before it is read.

**Graceful degradation** — if `GROQ_API_KEY` is absent, the system falls back automatically: orchestrator → single Groq call → rule-based logic. The server never crashes on a missing key.

**paho-mqtt v2** — callbacks use the v2 five-argument signatures (`flags, reason_code, properties`) required by paho-mqtt ≥ 2.0.
