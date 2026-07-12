# AgroMind AI — Multi-Agent System

The multi-agent pipeline is the decision brain of AgroMind AI. It runs automatically inside `mqtt_worker.py` every time a sensor message arrives over MQTT, and is also exposed as a REST endpoint at `POST /agents/decide`.

---

## Agent Pipeline

```
MQTT sensor message (agromind/data)
        │
        ▼
  mqtt_worker._process()
        │
        ▼
  AgentOrchestrator.process_sensor_data()
        │
   ┌────┴────────────────────────────────────────────────────┐
   │  1. Memory Agent          – update history, get trends  │
   │  2. Sensor Interpreter    – classify environment         │
   │  3. Crop Doctor           – assess crop health           │
   │  4. Weather Intelligence  – analyse forecast             │
   │  5. Irrigation Planner    – create strategy              │
   │  6. Safety Supervisor     – validate & cap command       │
   └────────────────────────────────────────────────────────┘
        │
        ▼
  Final command → MQTT pump message + WebSocket broadcast + SQLite log
```

---

## Agents

### 1. Sensor Interpreter Agent
- **Input**: `soil_moisture`, `temperature`, `humidity`, `light`, `rain_detected`
- **Output**: `soil_status` (dry/optimal/wet), `heat_stress` (bool), `evaporation_risk` (low/medium/high)
- **Fallback**: Rule-based thresholds (e.g. soil < 30% → dry)

### 2. Crop Doctor Agent
- **Input**: Environmental state, raw sensor data, memory context
- **Output**: `health_score` (0–100), `diagnosis`, `stress_type`, `urgency`
- **Fallback**: Score based on soil moisture and temperature ranges

### 3. Weather Intelligence Agent
- **Input**: Open-Meteo forecast, current sensor readings
- **Output**: `rain_probability`, `rain_expected`, `irrigation_impact`, `wait_recommendation`
- **Fallback**: Use `rain_probability` threshold directly (> 60% → skip irrigation)

### 4. Irrigation Planner Agent
- **Input**: All previous agent outputs, memory context
- **Output**: `decision` (IRRIGATE/DELAY/SKIP), `irrigation_duration_sec`, `next_check_minutes`, `reasoning`, `confidence`
- **Rules enforced**:
  1. Skip if rain probability > 60 %
  2. Irrigate if soil moisture < 30 % and no rain expected
  3. Increase urgency if temp > 34 °C and humidity < 40 %
  4. Never exceed 180 seconds duration
  5. Factor in crop health score and stress type
  6. Consider evaporation risk

### 5. Safety Supervisor Agent
- **Input**: Irrigation plan, raw sensor data, memory context
- **Output**: `approved` (bool), `validated_command` (`pump`, `duration_sec`, `explanation`), `risk_level`, `safety_notes`
- **Checks**: Duration cap (180 s), daily limit (10 irrigations), sensor validity, repeated-loop detection

### 6. Memory Agent *(pure Python — no LLM)*
- **Storage**: `deque` capped at 5 sensor records
- **Functions**: Trend detection (increasing/decreasing/stable), irrigation history, daily counter

---

## Wiring into the MQTT Pipeline

`mqtt_worker._process()` calls the orchestrator after fetching weather:

```python
# Short → long name mapping (MQTT payload uses short names)
sensor_long = {
    "soil_moisture": sensor.get("soil"),
    "temperature":   sensor.get("temp"),
    "humidity":      sensor.get("hum"),
    "light":         sensor.get("light"),
    "rain_detected": sensor.get("rain", False),
}
result = await orch.process_sensor_data(sensor_long, weather)
```

If `GROQ_API_KEY` is missing or the orchestrator raises, the worker falls back to a single direct Groq call (`_ask_groq()`). If Groq is also unavailable, a rule-based fallback runs.

---

## REST API

### `POST /agents/decide`

Run the full pipeline manually (useful for testing without MQTT).

**Request**
```json
{
  "sensor_data": {
    "soil_moisture": 25.0,
    "temperature": 35.0,
    "humidity": 38.0,
    "light": 3000,
    "rain_detected": false
  },
  "weather_data": {
    "rain_probability_next_hour": 10,
    "temperature_2m_max": 36.0,
    "precipitation_probability_max": 15
  }
}
```

**Response**
```json
{
  "status": "success",
  "decision": {
    "environmental_state": { "soil_status": "dry", "heat_stress": true, "evaporation_risk": "high" },
    "crop_health":         { "health_score": 45, "stress_type": "dehydration", "urgency": "high" },
    "weather_intelligence":{ "rain_probability": 10, "rain_expected": false },
    "irrigation_plan":     { "decision": "IRRIGATE", "irrigation_duration_sec": 150, "next_check_minutes": 5 },
    "safety_validation":   { "approved": true, "risk_level": "safe" },
    "final_command":       { "pump": "ON", "duration_sec": 150, "explanation": "..." },
    "memory_context":      { "trend_summary": "...", "recent_irrigation_count": 0 }
  }
}
```

Returns **503** if `GROQ_API_KEY` is not configured.

### `GET /agents/health`

Returns the status of each agent and current memory statistics.

### `GET /agents/memory/context`

Returns the current memory context (last 5 sensor readings, trend summary, recent irrigation count).

### `POST /agents/memory/clear`

Clears agent memory — useful during testing.

---

## Usage Examples

### Quick curl test

```bash
curl -X POST http://localhost:8000/agents/decide \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_data": {"soil_moisture": 25, "temperature": 35, "humidity": 38, "light": 3000, "rain_detected": false},
    "weather_data": {"rain_probability_next_hour": 10}
  }'
```

### Python — test the orchestrator directly

```python
import asyncio
from agents.orchestrator import AgentOrchestrator

orch = AgentOrchestrator(groq_api_key="gsk_...")
result = asyncio.run(orch.process_sensor_data(
    sensor_data={"soil_moisture": 25, "temperature": 35, "humidity": 38, "light": 3000, "rain_detected": False},
    weather_data={"rain_probability_next_hour": 10}
))
print(result["final_command"])
```

### Python — test a single agent

```python
import asyncio
from agents.sensor_interpreter import SensorInterpreterAgent

agent = SensorInterpreterAgent(groq_api_key="gsk_...")
result = asyncio.run(agent.execute({
    "soil_moisture": 45, "temperature": 28,
    "humidity": 65, "light": 2000, "rain_detected": False
}))
print(result)
```

---

## File Locations

```
C:\My files\projectss\AgroMindAI\
└── backend\
    ├── agents\
    │   ├── __init__.py
    │   ├── base_agent.py
    │   ├── sensor_interpreter.py
    │   ├── crop_doctor.py
    │   ├── weather_intelligence.py
    │   ├── irrigation_planner.py
    │   ├── safety_supervisor.py
    │   ├── memory_agent.py
    │   ├── orchestrator.py
    │   └── README.md
    └── agents_endpoint.py
```

---

## Performance Notes

| Metric | Value |
|---|---|
| Decision time (with Groq) | 2–4 seconds |
| Decision time (fallback) | < 100 ms |
| API calls per decision | 5 (one per LLM-backed agent) |
| Memory footprint | ~5 MB (5 sensor records) |
| Groq model | llama-3.3-70b-versatile |
| LLM temperature | 0.1–0.3 (deterministic) |
