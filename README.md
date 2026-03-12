# AgroMind AI

**Agentic Cyber-Physical Farming Intelligence System**

AgroMind AI autonomously monitors crop conditions and controls irrigation using multi-agent AI reasoning, IoT sensors, and cloud infrastructure.

---

## Architecture (v3.0 — Cloud-Native)

```
ESP32 Sensors
  → MQTT (Mosquitto local / HiveMQ Cloud)
  → n8n Workflows
  → FastAPI Backend (Render)
  → Groq API Multi-Agent System (llama-3.3-70b-versatile)
  → Validated Irrigation Decision
  → MQTT Pump Command
  → ESP32 Relay → Water Pump
  → Dashboard (React)
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Firmware | Arduino C++ (ESP32) |
| Communication | MQTT (Mosquitto / HiveMQ Cloud) |
| Automation | n8n Workflows |
| Backend | FastAPI (Python) on Render |
| AI | Groq API — llama-3.3-70b-versatile (6 specialized agents) |
| Database | SQLite (Render persistent disk) |
| Dashboard | React + Vite + Recharts |
| Weather | Open-Meteo API |

## Project Structure

```
AgroMindAI/
├── backend/            # FastAPI backend + multi-agent system
│   ├── agents/         # 6 AI agents (Groq-powered)
│   ├── main.py         # API server
│   ├── agents_endpoint.py
│   └── requirements.txt
├── dashboard/          # React dashboard (Vite)
├── firmware/
│   ├── agromind_esp32/ # ESP32 Arduino sketch
│   └── MQTT_CONFIG.md  # MQTT broker migration guide
├── workflows/          # n8n workflow JSON files
│   ├── workflow-main.json    # Main CPS loop
│   ├── workflow-health.json  # Health monitor (every 30 min)
│   └── workflow-report.json  # Daily report (8 AM)
├── docs/               # Extended documentation
├── reports/            # Generated farm reports (legacy local)
├── start_all.bat       # Local dev startup script
└── mosquitto.conf      # Local MQTT broker config
```

## Quick Start (Local Dev)

```powershell
# 1. Start all local services
start_all.bat

# 2. Backend available at:
#    http://localhost:8000/docs

# 3. Import workflows in n8n (http://localhost:5678)
#    from: workflows/workflow-main.json etc.
```

## AI Agents

The system uses 6 specialized agents powered by Groq (llama-3.3-70b-versatile):

1. **Sensor Interpreter** — Classifies environmental state from raw readings
2. **Crop Doctor** — Assesses crop health (0–100 score) and stress type
3. **Weather Intelligence** — Analyzes Open-Meteo forecast for irrigation impact
4. **Irrigation Planner** — Creates optimal irrigation strategy (6 safety rules)
5. **Safety Supervisor** — Validates all commands; max 180s pump runtime enforced
6. **Memory Agent** — Tracks trends in last 5 readings (pure Python, no LLM)

## Safety

- Pump runtime is **hard-capped at 180 seconds** in firmware AND by the Safety Supervisor agent
- Every LLM agent has a **rule-based fallback** — the system never relies solely on AI output
- Invalid AI responses trigger fallback irrigation logic automatically

## Environment Variables

Copy `backend/.env` and fill in:

```
GROQ_API_KEY=your_groq_api_key
ALLOWED_ORIGINS=http://localhost:5173,https://your-dashboard.pages.dev
DB_PATH=agromind.db
LATITUDE=22.5726
LONGITUDE=88.3639
```

## Deployment

- **Backend**: Render Web Service — deploy from `backend/` with persistent disk at `/data`
- **Dashboard**: Render Static Site or Cloudflare Pages — set `VITE_API_BASE` env var
- **MQTT**: See `firmware/MQTT_CONFIG.md` for HiveMQ Cloud setup