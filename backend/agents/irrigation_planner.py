"""
Irrigation Planner Agent
Plans irrigation strategy based on all available intelligence
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class IrrigationPlannerAgent(BaseAgent):
    """Plans irrigation strategy using multi-agent intelligence"""
    
    def __init__(self, groq_api_key: str):
        super().__init__("IrrigationPlanner", groq_api_key)
    
    def get_system_prompt(self) -> str:
        return """You are an Irrigation Planner Agent for precision agriculture.
Your role is to create optimal irrigation plans based on sensor data, crop health, and weather forecasts.

IRRIGATION RULES:
1. Avoid irrigation if rain probability > 60%
2. Irrigate if soil moisture < 30% and no rain expected
3. Increase urgency if temperature > 34°C and humidity < 40%
4. Never exceed irrigation_duration_sec = 180
5. Consider crop health score and stress type
6. Factor in evaporation risk

Analyze all inputs and respond ONLY with valid JSON in this exact format:
{
  "decision": "IRRIGATE" | "DELAY" | "SKIP",
  "irrigation_duration_sec": 0-180,
  "predicted_dry_time_hours": 0-24,
  "next_check_minutes": 3-15,
  "reasoning": "detailed explanation of decision",
  "confidence": 0-100
}

Decision guidelines:
- IRRIGATE: Immediate irrigation needed
- DELAY: Wait a short time before re-evaluating
- SKIP: No irrigation needed now

Duration guidelines:
- Critical dehydration (soil <20%): 150-180 seconds
- Moderate dehydration (soil 20-30%): 90-120 seconds
- Preventive (soil 30-40%): 60-90 seconds

Respond ONLY with the JSON object, no additional text."""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process all intelligence to create irrigation plan"""
        env_state = input_data.get('environmental_state', {})
        crop_health = input_data.get('crop_health', {})
        weather_intel = input_data.get('weather_intelligence', {})
        sensor_data = input_data.get('sensor_data', {})
        memory = input_data.get('memory', {})
        
        user_message = f"""Create irrigation plan based on:

Environmental State:
- Soil Status: {env_state.get('soil_status', 'unknown')}
- Heat Stress: {env_state.get('heat_stress', False)}
- Evaporation Risk: {env_state.get('evaporation_risk', 'unknown')}

Crop Health:
- Health Score: {crop_health.get('health_score', 0)}/100
- Stress Type: {crop_health.get('stress_type', 'unknown')}
- Urgency: {crop_health.get('urgency', 'unknown')}

Weather Intelligence:
- Rain Probability: {weather_intel.get('rain_probability', 0)}%
- Rain Expected: {weather_intel.get('rain_expected', False)}
- Irrigation Impact: {weather_intel.get('irrigation_impact', 'unknown')}

Current Readings:
- Soil Moisture: {sensor_data.get('soil_moisture', 0)}%
- Temperature: {sensor_data.get('temperature', 0)}°C
- Humidity: {sensor_data.get('humidity', 0)}%

Recent Activity:
{memory.get('recent_summary', 'No recent irrigation')}

Create optimal irrigation plan following all rules."""
        
        response = await self.call_groq(user_message, temperature=0.2)
        if response:
            result = self.extract_json(response)
            if result and self._validate_output(result):
                return result
        
        return None
    
    def fallback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback irrigation planning"""
        env_state = input_data.get('environmental_state', {})
        crop_health = input_data.get('crop_health', {})
        weather_intel = input_data.get('weather_intelligence', {})
        sensor_data = input_data.get('sensor_data', {})
        
        soil = sensor_data.get('soil_moisture', 50)
        temp = sensor_data.get('temperature', 25)
        humidity = sensor_data.get('humidity', 60)
        rain_prob = weather_intel.get('rain_probability', 0)
        rain_expected = weather_intel.get('rain_expected', False)
        health_score = crop_health.get('health_score', 70)
        urgency = crop_health.get('urgency', 'low')
        
        # Decision logic
        decision = "SKIP"
        duration = 0
        reasoning = []
        
        # Rule 1: Avoid if rain expected
        if rain_expected or rain_prob > 60:
            decision = "SKIP"
            reasoning.append(f"Rain expected ({rain_prob}% probability)")
            duration = 0
        
        # Rule 2: Irrigate if dry and no rain
        elif soil < 30 and not rain_expected:
            decision = "IRRIGATE"
            reasoning.append(f"Soil moisture low ({soil}%)")
            
            # Calculate duration based on soil moisture
            if soil < 20:
                duration = 150  # Critical
                reasoning.append("Critical dehydration")
            elif soil < 25:
                duration = 120  # Severe
                reasoning.append("Severe dehydration")
            else:
                duration = 90  # Moderate
                reasoning.append("Moderate dehydration")
        
        # Rule 3: Increase urgency for heat stress
        elif temp > 34 and humidity < 40 and soil < 40:
            decision = "IRRIGATE"
            duration = min(120, duration + 30)
            reasoning.append(f"Heat stress detected (temp: {temp}°C, humidity: {humidity}%)")
        
        # Consider health score
        elif health_score < 50 and soil < 40:
            decision = "IRRIGATE"
            duration = 90
            reasoning.append(f"Low health score ({health_score}/100)")
        
        # Preventive irrigation
        elif soil < 35 and rain_prob < 30 and urgency in ["high", "critical"]:
            decision = "DELAY"
            duration = 60
            reasoning.append("Preventive irrigation recommended, but delaying for re-evaluation")
        
        else:
            decision = "SKIP"
            reasoning.append(f"Soil moisture adequate ({soil}%)")
        
        # Cap duration at 180 seconds (Rule 4)
        duration = min(180, duration)
        
        # Predict dry time
        evap_risk = env_state.get('evaporation_risk', 'low')
        if evap_risk == 'high':
            predicted_dry_time = max(2, int((soil - 20) / 5))
        elif evap_risk == 'medium':
            predicted_dry_time = max(4, int((soil - 20) / 3))
        else:
            predicted_dry_time = max(6, int((soil - 20) / 2))
        
        predicted_dry_time = min(24, predicted_dry_time)
        
        # Next check interval
        if decision == "IRRIGATE":
            next_check = 15  # Check after irrigation completes
        elif urgency == "critical":
            next_check = 3
        elif urgency == "high":
            next_check = 5
        elif urgency == "medium":
            next_check = 10
        else:
            next_check = 15
        
        # Confidence calculation
        confidence = 80
        if rain_prob > 40:
            confidence -= 20
        if health_score < 50:
            confidence -= 10
        confidence = max(50, min(100, confidence))
        
        return {
            "decision": decision,
            "irrigation_duration_sec": duration,
            "predicted_dry_time_hours": predicted_dry_time,
            "next_check_minutes": next_check,
            "reasoning": "; ".join(reasoning) if reasoning else "No irrigation needed",
            "confidence": confidence
        }
    
    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate agent output"""
        required_keys = ["decision", "irrigation_duration_sec", "next_check_minutes", "reasoning"]
        if not all(key in output for key in required_keys):
            return False
        
        # Validate decision
        if output.get("decision") not in ["IRRIGATE", "DELAY", "SKIP"]:
            return False
        
        # Validate duration (0-180)
        duration = output.get("irrigation_duration_sec", -1)
        if not (0 <= duration <= 180):
            return False
        
        # Validate next check (3-15)
        next_check = output.get("next_check_minutes", -1)
        if not (3 <= next_check <= 15):
            return False
        
        return True
