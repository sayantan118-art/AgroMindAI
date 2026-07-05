# AgroMind AI

**Agentic Cyber-Physical Farming Intelligence System**

AgroMind AI autonomously monitors crop conditions and controls irrigation using multi-agent AI reasoning, IoT sensors, and cloud infrastructure.

---

## Architecture (v3.0 — Cloud-Native)

```text
ESP32 Sensors
  → MQTT (Mosquitto local / HiveMQ Cloud)
  → FastAPI backend with built-in MQTT worker
  → Groq-powered multi-agent decision engine
  → Validated irrigation decision
  → MQTT pump command
  → ESP32 relay → water pump
  → React dashboard
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Firmware | Arduino C++ (ESP32) |
| Communication | MQTT (Mosquitto / HiveMQ Cloud) |
| Backend | FastAPI (Python) with Uvicorn |
| AI | Groq API — llama-3.3-70b-versatile (6 specialized agents) |
| Database | SQLite |
| Dashboard | React + Vite + Recharts |
| Weather | Open-Meteo API |

## Project Structure

```text
AgroMindAI/
├── backend/                  # FastAPI backend + multi-agent system
│   ├── agents/               # AI agents and orchestrator
│   ├── agents_endpoint.py    # Agent API endpoints
│   ├── main.py               # API server entry point
│   ├── mqtt_worker.py        # Background MQTT subscriber
│   └── requirements.txt
├── dashboard/                # React dashboard (Vite)
├── docs/                     # Project documentation
├── firmware/                 # ESP32 Arduino sketch and MQTT notes
├── simulator.py              # Local simulation helper
├── start_all.bat             # Local development startup script
└── README.md
```

## Quick Start (Local Dev)

```powershell
# 1. Install backend dependencies
cd backend
pip install -r requirements.txt

# 2. Install dashboard dependencies
cd ../dashboard
npm install

# 3. Start local services
cd ..
start_all.bat

# 4. Open the dashboard and backend docs
#    Backend: http://localhost:8000/docs
#    Dashboard: http://localhost:5173
```

> The current implementation uses the built-in MQTT worker in the backend rather than a separate n8n workflow engine.

## AI Agents

The system uses 6 specialized agents powered by Groq (llama-3.3-70b-versatile):

1. **Sensor Interpreter** — Classifies environmental state from raw readings
2. **Crop Doctor** — Assesses crop health (0–100 score) and stress type
3. **Weather Intelligence** — Analyzes Open-Meteo forecast for irrigation impact
4. **Irrigation Planner** — Creates an irrigation strategy with safety rules
5. **Safety Supervisor** — Validates commands and enforces the pump runtime limit
6. **Memory Agent** — Tracks recent trends in sensor history

## Safety

- Pump runtime is hard-capped at 180 seconds in the control flow and safety validation
- Each LLM-based agent has a rule-based fallback path
- Invalid AI responses trigger fallback irrigation logic automatically

## Environment Variables

Create a backend/.env file and provide values such as:

```env
GROQ_API_KEY=your_groq_api_key
ALLOWED_ORIGINS=http://localhost:5173,https://your-dashboard.pages.dev
DB_PATH=agromind.db
LATITUDE=22.5726
LONGITUDE=88.3639
MQTT_BROKER=your_broker_host
MQTT_PORT=8883
MQTT_USER=your_username
MQTT_PASS=your_password
```

## Deployment

- **Backend**: Render Web Service or another Python host; deploy from the backend folder
- **Dashboard**: Vite static build deployed to Render, Cloudflare Pages, or similar
- **MQTT**: Configure a broker such as Mosquitto or HiveMQ Cloud and set the MQTT environment variables
