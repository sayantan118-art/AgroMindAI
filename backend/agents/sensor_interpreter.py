"""
Sensor Interpreter Agent
Translates raw sensor data into meaningful environmental insights
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class SensorInterpreterAgent(BaseAgent):
    """Interprets raw sensor readings into environmental state"""
    
    def __init__(self, groq_api_key: str):
        super().__init__("SensorInterpreter", groq_api_key)
    
    def get_system_prompt(self) -> str:
        return """You are a Sensor Interpreter Agent for precision agriculture.
Your role is to analyze raw sensor data and translate it into meaningful environmental insights.

Analyze the sensor readings and respond ONLY with valid JSON in this exact format:
{
  "soil_status": "dry" | "optimal" | "wet",
  "heat_stress": true | false,
  "evaporation_risk": "low" | "medium" | "high",
  "light_condition": "dark" | "dim" | "bright",
  "rain_status": "raining" | "dry",
  "interpretation": "brief explanation of current conditions"
}

Classification rules:
- soil_status: dry if <30%, optimal if 30-70%, wet if >70%
- heat_stress: true if temp >34°C
- evaporation_risk: high if temp >32°C AND humidity <40%, medium if temp >28°C OR humidity <50%, else low
- light_condition: dark if <500, dim if 500-2000, bright if >2000
- rain_status: raining if rain_detected is true, else dry

Respond ONLY with the JSON object, no additional text."""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process sensor data using LLM"""
        user_message = f"""Analyze these sensor readings:
- Soil Moisture: {input_data.get('soil_moisture', 0)}%
- Temperature: {input_data.get('temperature', 0)}°C
- Humidity: {input_data.get('humidity', 0)}%
- Light Level: {input_data.get('light', 0)} (raw ADC)
- Rain Detected: {input_data.get('rain_detected', False)}

Provide environmental interpretation."""
        
        response = await self.call_groq(user_message)
        if response:
            result = self.extract_json(response)
            if result and self._validate_output(result):
                return result
        
        return None
    
    def fallback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback interpretation"""
        soil = input_data.get('soil_moisture', 50)
        temp = input_data.get('temperature', 25)
        humidity = input_data.get('humidity', 60)
        light = input_data.get('light', 1000)
        rain = input_data.get('rain_detected', False)
        
        # Rule-based classification
        if soil < 30:
            soil_status = "dry"
        elif soil > 70:
            soil_status = "wet"
        else:
            soil_status = "optimal"
        
        heat_stress = temp > 34
        
        if temp > 32 and humidity < 40:
            evap_risk = "high"
        elif temp > 28 or humidity < 50:
            evap_risk = "medium"
        else:
            evap_risk = "low"
        
        if light < 500:
            light_cond = "dark"
        elif light < 2000:
            light_cond = "dim"
        else:
            light_cond = "bright"
        
        rain_status = "raining" if rain else "dry"
        
        interpretation = f"Soil is {soil_status} ({soil}%). "
        if heat_stress:
            interpretation += "Heat stress detected. "
        interpretation += f"Evaporation risk is {evap_risk}. "
        interpretation += f"Weather is {rain_status}."
        
        return {
            "soil_status": soil_status,
            "heat_stress": heat_stress,
            "evaporation_risk": evap_risk,
            "light_condition": light_cond,
            "rain_status": rain_status,
            "interpretation": interpretation
        }
    
    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate agent output"""
        required_keys = ["soil_status", "heat_stress", "evaporation_risk", "interpretation"]
        return all(key in output for key in required_keys)
