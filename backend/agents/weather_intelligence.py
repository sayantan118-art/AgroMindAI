"""
Weather Intelligence Agent
Analyzes weather forecast data for irrigation planning
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class WeatherIntelligenceAgent(BaseAgent):
    """Analyzes weather forecasts and provides irrigation-relevant insights"""
    
    def __init__(self, groq_api_key: str):
        super().__init__("WeatherIntelligence", groq_api_key)
    
    def get_system_prompt(self) -> str:
        return """You are a Weather Intelligence Agent for precision agriculture.
Your role is to analyze weather forecast data and provide irrigation-relevant insights.

Analyze the weather data and respond ONLY with valid JSON in this exact format:
{
  "rain_probability": 0-100,
  "rain_expected": true | false,
  "forecast_summary": "brief summary of weather conditions",
  "irrigation_impact": "favorable" | "neutral" | "unfavorable",
  "wait_recommendation": "irrigate_now" | "wait_for_rain" | "monitor"
}

Classification rules:
- rain_expected: true if rain_probability > 60%
- irrigation_impact: favorable if no rain expected and moderate temps, unfavorable if rain expected or extreme temps, else neutral
- wait_recommendation: wait_for_rain if rain_probability >60%, irrigate_now if <30% and dry conditions, else monitor

Respond ONLY with the JSON object, no additional text."""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process weather forecast data"""
        weather_data = input_data.get('weather_data', {})
        sensor_data = input_data.get('sensor_data', {})
        
        user_message = f"""Analyze this weather forecast:
- Rain Probability: {weather_data.get('rain_probability_next_hour', 0)}%
- Max Temperature Today: {weather_data.get('temperature_2m_max', 'N/A')}°C
- Precipitation Probability Max: {weather_data.get('precipitation_probability_max', 0)}%

Current Conditions:
- Current Temperature: {sensor_data.get('temperature', 0)}°C
- Current Humidity: {sensor_data.get('humidity', 0)}%
- Rain Detected: {sensor_data.get('rain_detected', False)}

Provide weather intelligence for irrigation planning."""
        
        response = await self.call_groq(user_message)
        if response:
            result = self.extract_json(response)
            if result and self._validate_output(result):
                return result
        
        return None
    
    def fallback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback weather analysis"""
        weather_data = input_data.get('weather_data', {})
        sensor_data = input_data.get('sensor_data', {})
        
        rain_prob = weather_data.get('rain_probability_next_hour', 0)
        max_temp = weather_data.get('temperature_2m_max', sensor_data.get('temperature', 25))
        precip_prob_max = weather_data.get('precipitation_probability_max', rain_prob)
        
        # Use the higher of the two rain probabilities
        effective_rain_prob = max(rain_prob, precip_prob_max)
        
        rain_expected = effective_rain_prob > 60
        
        # Determine irrigation impact
        if rain_expected:
            irrigation_impact = "unfavorable"
        elif max_temp > 38 or max_temp < 15:
            irrigation_impact = "unfavorable"
        elif 20 <= max_temp <= 30 and not rain_expected:
            irrigation_impact = "favorable"
        else:
            irrigation_impact = "neutral"
        
        # Wait recommendation
        if effective_rain_prob > 60:
            wait_rec = "wait_for_rain"
        elif effective_rain_prob < 30 and sensor_data.get('soil_moisture', 50) < 40:
            wait_rec = "irrigate_now"
        else:
            wait_rec = "monitor"
        
        # Generate summary
        if rain_expected:
            summary = f"Rain expected ({effective_rain_prob}% probability). "
        else:
            summary = f"Low rain probability ({effective_rain_prob}%). "
        
        summary += f"Max temperature: {max_temp}°C. "
        
        if irrigation_impact == "favorable":
            summary += "Good conditions for irrigation."
        elif irrigation_impact == "unfavorable":
            summary += "Unfavorable conditions for irrigation."
        else:
            summary += "Neutral conditions for irrigation."
        
        return {
            "rain_probability": effective_rain_prob,
            "rain_expected": rain_expected,
            "forecast_summary": summary,
            "irrigation_impact": irrigation_impact,
            "wait_recommendation": wait_rec
        }
    
    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate agent output"""
        required_keys = ["rain_probability", "rain_expected", "forecast_summary"]
        if not all(key in output for key in required_keys):
            return False
        
        # Validate rain probability range
        if not (0 <= output.get("rain_probability", -1) <= 100):
            return False
        
        return True
