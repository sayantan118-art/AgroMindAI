"""
Crop Doctor Agent
Assesses crop health based on environmental conditions
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class CropDoctorAgent(BaseAgent):
    """Diagnoses crop health and stress conditions"""
    
    def __init__(self, groq_api_key: str):
        super().__init__("CropDoctor", groq_api_key)
    
    def get_system_prompt(self) -> str:
        return """You are a Crop Doctor Agent specializing in plant health assessment.
Your role is to diagnose crop health based on environmental conditions and sensor data.

Analyze the conditions and respond ONLY with valid JSON in this exact format:
{
  "health_score": 0-100,
  "diagnosis": "detailed explanation of crop condition",
  "stress_type": "dehydration" | "heat" | "humidity_imbalance" | "healthy",
  "urgency": "low" | "medium" | "high" | "critical",
  "recommendations": "actionable advice"
}

Health score guidelines:
- 90-100: Excellent conditions, thriving crop
- 70-89: Good conditions, minor stress
- 50-69: Moderate stress, intervention recommended
- 30-49: Significant stress, urgent action needed
- 0-29: Critical stress, immediate intervention required

Stress type classification:
- dehydration: Low soil moisture (<30%) or high evaporation risk
- heat: Temperature >34°C causing heat stress
- humidity_imbalance: Humidity too low (<30%) or too high (>90%)
- healthy: All parameters within optimal range

Respond ONLY with the JSON object, no additional text."""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process environmental state and sensor data"""
        env_state = input_data.get('environmental_state', {})
        sensor_data = input_data.get('sensor_data', {})
        memory = input_data.get('memory', {})
        
        user_message = f"""Diagnose crop health based on:

Environmental State:
- Soil Status: {env_state.get('soil_status', 'unknown')}
- Heat Stress: {env_state.get('heat_stress', False)}
- Evaporation Risk: {env_state.get('evaporation_risk', 'unknown')}
- Rain Status: {env_state.get('rain_status', 'unknown')}

Current Readings:
- Soil Moisture: {sensor_data.get('soil_moisture', 0)}%
- Temperature: {sensor_data.get('temperature', 0)}°C
- Humidity: {sensor_data.get('humidity', 0)}%

Recent Trends:
{memory.get('trend_summary', 'No historical data available')}

Provide health assessment."""
        
        response = await self.call_groq(user_message)
        if response:
            result = self.extract_json(response)
            if result and self._validate_output(result):
                return result
        
        return None
    
    def fallback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback diagnosis"""
        env_state = input_data.get('environmental_state', {})
        sensor_data = input_data.get('sensor_data', {})
        
        soil = sensor_data.get('soil_moisture', 50)
        temp = sensor_data.get('temperature', 25)
        humidity = sensor_data.get('humidity', 60)
        
        # Calculate health score
        health_score = 100
        stress_factors = []
        
        # Soil moisture impact
        if soil < 20:
            health_score -= 40
            stress_factors.append("severe dehydration")
        elif soil < 30:
            health_score -= 25
            stress_factors.append("dehydration")
        elif soil > 80:
            health_score -= 15
            stress_factors.append("overwatering")
        
        # Temperature impact
        if temp > 38:
            health_score -= 30
            stress_factors.append("extreme heat")
        elif temp > 34:
            health_score -= 20
            stress_factors.append("heat stress")
        elif temp < 15:
            health_score -= 15
            stress_factors.append("cold stress")
        
        # Humidity impact
        if humidity < 30:
            health_score -= 15
            stress_factors.append("low humidity")
        elif humidity > 90:
            health_score -= 10
            stress_factors.append("high humidity")
        
        # Evaporation risk impact
        if env_state.get('evaporation_risk') == 'high':
            health_score -= 10
        
        health_score = max(0, min(100, health_score))
        
        # Determine stress type
        if soil < 30 or env_state.get('evaporation_risk') == 'high':
            stress_type = "dehydration"
        elif temp > 34:
            stress_type = "heat"
        elif humidity < 30 or humidity > 90:
            stress_type = "humidity_imbalance"
        else:
            stress_type = "healthy"
        
        # Determine urgency
        if health_score < 30:
            urgency = "critical"
        elif health_score < 50:
            urgency = "high"
        elif health_score < 70:
            urgency = "medium"
        else:
            urgency = "low"
        
        # Generate diagnosis
        if stress_factors:
            diagnosis = f"Crop experiencing {', '.join(stress_factors)}. "
        else:
            diagnosis = "Crop is in good health. "
        
        diagnosis += f"Health score: {health_score}/100. "
        
        if urgency in ["critical", "high"]:
            diagnosis += "Immediate intervention recommended."
        elif urgency == "medium":
            diagnosis += "Monitor closely and prepare intervention."
        else:
            diagnosis += "Continue regular monitoring."
        
        # Generate recommendations
        recommendations = []
        if soil < 30:
            recommendations.append("Irrigate immediately")
        if temp > 34:
            recommendations.append("Provide shade or cooling")
        if humidity < 30:
            recommendations.append("Increase humidity through misting")
        if not recommendations:
            recommendations.append("Maintain current care routine")
        
        return {
            "health_score": health_score,
            "diagnosis": diagnosis,
            "stress_type": stress_type,
            "urgency": urgency,
            "recommendations": "; ".join(recommendations)
        }
    
    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate agent output"""
        required_keys = ["health_score", "diagnosis", "stress_type", "urgency"]
        if not all(key in output for key in required_keys):
            return False
        
        # Validate health score range
        if not (0 <= output.get("health_score", -1) <= 100):
            return False
        
        return True
