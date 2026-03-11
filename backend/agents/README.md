# AgroMind AI - Multi-Agent System

## Overview

This is an **Agentic Cyber-Physical Farming Intelligence System** that uses multiple specialized AI agents to autonomously monitor crop conditions, plan irrigation, and control physical hardware through IoT infrastructure.

## Architecture

### Agent Roles

1. **Sensor Interpreter Agent**
   - Translates raw sensor data into environmental insights
   - Output: soil_status, heat_stress, evaporation_risk, interpretation

2. **Crop Doctor Agent**
   - Assesses crop health based on environmental conditions
   - Output: health_score (0-100), diagnosis, stress_type, urgency

3. **Weather Intelligence Agent**
   - Analyzes weather forecasts for irrigation planning
   - Output: rain_probability, rain_expected, forecast_summary

4. **Irrigation Planner Agent**
   - Creates optimal irrigation strategy
   - Output: decision (IRRIGATE/DELAY/SKIP), duration, reasoning

5. **Safety Supervisor Agent**
   - Validates decisions before hardware execution
   - Output: approved, validated_command, safety_notes

6. **Memory Agent**
   - Maintains short-term memory of readings and events
   - Provides trend analysis and context

### Autonomous Control Loop

```
1. Receive sensor data from ESP32 via MQTT
2. Update memory with new reading
3. Interpret environment (Sensor Interpreter)
4. Evaluate crop health (Crop Doctor)
5. Analyze weather forecast (Weather Intelligence)
6. Generate irrigation plan (Irrigation Planner)
7. Validate safety (Safety Supervisor)
8. Execute command via MQTT
9. Log results to database
```

## API Endpoints

### POST /agents/decide
Main endpoint for autonomous irrigation decisions.

**Request:**
```json
{
  "sensor_data": {
    "soil_moisture": 45.0,
    "temperature": 28.5,
    "humidity": 65.0,
    "light": 2048,
    "rain_detected": false
  },
  "weather_data": {
    "rain_probability_next_hour": 20,
    "temperature_2m_max": 32.0,
    "precipitation_probability_max": 25
  }
}
```

**Response:**
```json
{
  "status": "success",
  "decision": {
    "environmental_state": {
      "soil_status": "optimal",
      "heat_stress": false,
      "evaporation_risk": "medium"
    },
    "crop_health": {
      "health_score": 75,
      "stress_type": "healthy",
      "urgency": "low"
    },
    "irrigation_plan": {
      "decision": "SKIP",
      "irrigation_duration_sec": 0,
      "next_check_minutes": 15
    },
    "final_command": {
      "pump": "OFF",
      "duration_sec": 0,
      "explanation": "Soil moisture adequate"
    }
  }
}
```

### GET /agents/health
Health check for agent system.

### GET /agents/memory/context
Get current memory context and trends.

### POST /agents/memory/clear
Clear agent memory (for testing).

## Irrigation Rules

1. **Avoid irrigation if rain probability > 60%**
2. **Irrigate if soil moisture < 30% and no rain expected**
3. **Increase urgency if temperature > 34°C and humidity < 40%**
4. **Never exceed irrigation_duration_sec = 180**
5. **Consider crop health score and stress type**
6. **Factor in evaporation risk**

## Safety Features

- Duration limits (0-180 seconds)
- Sensor validity checks
- Irrigation frequency limits (max 10/day)
- Abnormal reading detection
- Repeated irrigation loop prevention

## Fallback Logic

If LLM fails or returns invalid JSON, each agent has rule-based fallback logic:

**Example Fallback:**
```python
if soil_moisture < 30 and not rain_expected:
    decision = "IRRIGATE"
    duration = 120  # seconds
else:
    decision = "SKIP"
    duration = 0
```

## Usage Example

### Python
```python
import httpx

async def get_irrigation_decision():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/agents/decide",
            json={
                "sensor_data": {
                    "soil_moisture": 25.0,
                    "temperature": 35.0,
                    "humidity": 38.0,
                    "light": 3000,
                    "rain_detected": False
                },
                "weather_data": {
                    "rain_probability_next_hour": 10,
                    "temperature_2m_max": 36.0
                }
            }
        )
        return response.json()
```

### n8n Integration
```javascript
// In n8n HTTP Request node
{
  "method": "POST",
  "url": "http://localhost:8000/agents/decide",
  "body": {
    "sensor_data": {
      "soil_moisture": "{{ $('MQTT Trigger').item.json.soil_moisture }}",
      "temperature": "{{ $('MQTT Trigger').item.json.temperature }}",
      "humidity": "{{ $('MQTT Trigger').item.json.humidity }}",
      "light": "{{ $('MQTT Trigger').item.json.light }}",
      "rain_detected": "{{ $('MQTT Trigger').item.json.rain_detected }}"
    },
    "weather_data": {
      "rain_probability_next_hour": "{{ $('Get Weather').item.json.rain_probability_next_hour }}"
    }
  }
}
```

## Configuration

Set environment variable:
```bash
export GROQ_API_KEY="your-groq-api-key"
```

Or in `.env` file:
```
GROQ_API_KEY=gsk_your_key_here
```

## Dependencies

```
fastapi
httpx
pydantic
python-dotenv
```

## Testing

```python
# Test individual agent
from agents.sensor_interpreter import SensorInterpreterAgent

agent = SensorInterpreterAgent(groq_api_key="your-key")
result = await agent.execute({
    'soil_moisture': 45,
    'temperature': 28,
    'humidity': 65,
    'light': 2000,
    'rain_detected': False
})
print(result)
```

## Logging

All agents log their activities:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Performance

- **Average decision time**: 2-4 seconds (with Groq API)
- **Fallback decision time**: <100ms (rule-based)
- **Memory footprint**: ~5MB (with 5 sensor records)
- **API calls per decision**: 5 (one per agent)

## Future Enhancements

1. **Learning Agent**: Train on historical data
2. **Predictive Agent**: Forecast soil moisture trends
3. **Multi-Zone Agent**: Handle multiple irrigation zones
4. **Cost Optimizer Agent**: Minimize water and energy costs
5. **Disease Detection Agent**: Identify crop diseases from images

## License

Part of AgroMind AI system.

## Contact

For issues or questions, refer to main project documentation.
