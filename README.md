# AgroMind AI

AgroMind AI is an intelligent irrigation platform that combines IoT sensor data, weather forecasting, and AI decisions to automate farm watering in real time.

## Tech Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | React 19, Vite, Recharts, Lucide React | Live monitoring dashboard and controls |
| Backend API | FastAPI, Uvicorn | Sensor ingestion, decision logs, pump logs, WebSocket streaming |
| Database | SQLite (`agromind.db`), `aiosqlite` | Persistent storage for sensor and pump activity |
| Automation | n8n, MQTT (Mosquitto) | Sensor event workflows and pump command orchestration |
| AI Decisioning | Ollama (`qwen2.5:14b`) | Irrigation decision and crop-health inference |
| External Data | Open-Meteo API | Short-range rainfall probability for irrigation context |

## How To Run

### Prerequisites
- Python 3.14+
- Node.js + npm
- n8n installed and available in PATH
- Ollama running locally (default: `http://localhost:11434`)

### Start Everything
```bat
start.bat
```

This starts:
- FastAPI backend on `http://localhost:8000`
- n8n service
- React dashboard dev server (Vite)

## Architecture Overview

1. Field sensors publish readings to MQTT topics.
2. n8n workflow (`workflow-main.json`) triggers on sensor messages.
3. n8n fetches weather forecast from backend `/weather/forecast`.
4. n8n calls Ollama to generate irrigation decision JSON.
5. Decision + sensor snapshot are stored via backend `/sensor/log`.
6. If irrigation is needed, n8n publishes pump `ON/OFF` commands over MQTT.
7. Dashboard reads latest/history via REST and receives live updates from backend WebSocket.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Service health and current backend timestamp |
| `POST` | `/sensor/log` | Store sensor snapshot plus AI decision metadata |
| `GET` | `/sensor/latest` | Return latest sensor/decision record |
| `GET` | `/sensor/history?limit=100` | Return recent sensor history records |
| `GET` | `/weather/forecast` | Return next-hour rain probability and rain flag |
| `POST` | `/pump/log` | Store pump action events (`ON`/`OFF`) |
| `GET` | `/pump/usage/today` | Daily pump usage totals and event log |
| `WS` | `/ws/dashboard` | Push live sensor/decision updates to dashboard clients |

## Folder Structure

```text
AgroMindAI/
|-- backend/
|   |-- main.py
|   |-- requirements.txt
|   |-- .env
|   `-- agromind.db
|-- dashboard/
|   |-- src/
|   |-- public/
|   |-- package.json
|   `-- vite.config.js
|-- reports/
|-- workflow-main.json
|-- workflow-health.json
|-- workflow-sync.json
|-- workflow-report.json
|-- start.bat
|-- mosquitto.conf
`-- README.md
```