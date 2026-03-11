"""
Safety Supervisor Agent
Validates irrigation decisions before hardware execution
"""

from typing import Dict, Any
import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SafetySupervisorAgent(BaseAgent):
    """Validates and supervises irrigation commands for safety"""
    
    def __init__(self, groq_api_key: str):
        super().__init__("SafetySupervisor", groq_api_key)
        self.max_duration = 180
        self.min_interval_minutes = 10
        self.last_irrigation_time = None
        self.irrigation_count_today = 0
        self.max_daily_irrigations = 10
    
    def get_system_prompt(self) -> str:
        return """You are a Safety Supervisor Agent for irrigation systems.
Your role is to validate irrigation commands and prevent unsafe operations.

SAFETY CHECKS:
1. Duration must be 0-180 seconds
2. Sensor readings must be within valid ranges
3. No repeated irrigation loops (min 10 min between irrigations)
4. Maximum 10 irrigations per day
5. Abort if sensor readings are abnormal

Analyze the command and respond ONLY with valid JSON in this exact format:
{
  "approved": true | false,
  "validated_command": {
    "pump": "ON" | "OFF",
    "duration_sec": 0-180,
    "explanation": "reason for command"
  },
  "safety_notes": "any safety concerns or adjustments made",
  "risk_level": "safe" | "caution" | "unsafe"
}

If unsafe, set approved=false and explain why in safety_notes.

Respond ONLY with the JSON object, no additional text."""
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate irrigation plan using LLM"""
        irrigation_plan = input_data.get('irrigation_plan', {})
        sensor_data = input_data.get('sensor_data', {})
        memory = input_data.get('memory', {})
        
        user_message = f"""Validate this irrigation command:

Irrigation Plan:
- Decision: {irrigation_plan.get('decision', 'SKIP')}
- Duration: {irrigation_plan.get('irrigation_duration_sec', 0)} seconds
- Reasoning: {irrigation_plan.get('reasoning', 'N/A')}

Current Sensor Readings:
- Soil Moisture: {sensor_data.get('soil_moisture', 0)}%
- Temperature: {sensor_data.get('temperature', 0)}°C
- Humidity: {sensor_data.get('humidity', 0)}%

Recent Activity:
- Last Irrigation: {memory.get('last_irrigation_time', 'Never')}
- Irrigations Today: {self.irrigation_count_today}
- Recent Irrigation Count: {memory.get('recent_irrigation_count', 0)}

Perform safety validation."""
        
        response = await self.call_groq(user_message, temperature=0.1)
        if response:
            result = self.extract_json(response)
            if result and self._validate_output(result):
                return result
        
        return None
    
    def fallback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based fallback safety validation"""
        irrigation_plan = input_data.get('irrigation_plan', {})
        sensor_data = input_data.get('sensor_data', {})
        memory = input_data.get('memory', {})
        
        decision = irrigation_plan.get('decision', 'SKIP')
        duration = irrigation_plan.get('irrigation_duration_sec', 0)
        reasoning = irrigation_plan.get('reasoning', 'No reason provided')
        
        approved = True
        safety_notes = []
        risk_level = "safe"
        
        # Check 1: Duration limits
        if duration > self.max_duration:
            duration = self.max_duration
            safety_notes.append(f"Duration capped at {self.max_duration} seconds")
            risk_level = "caution"
        
        if duration < 0:
            duration = 0
            approved = False
            safety_notes.append("Invalid negative duration")
            risk_level = "unsafe"
        
        # Check 2: Sensor validity
        soil = sensor_data.get('soil_moisture', -1)
        temp = sensor_data.get('temperature', -999)
        humidity = sensor_data.get('humidity', -1)
        
        if not (0 <= soil <= 100):
            approved = False
            safety_notes.append(f"Abnormal soil moisture reading: {soil}%")
            risk_level = "unsafe"
        
        if not (-10 <= temp <= 60):
            approved = False
            safety_notes.append(f"Abnormal temperature reading: {temp}°C")
            risk_level = "unsafe"
        
        if not (0 <= humidity <= 100):
            approved = False
            safety_notes.append(f"Abnormal humidity reading: {humidity}%")
            risk_level = "unsafe"
        
        # Check 3: Irrigation frequency
        recent_count = memory.get('recent_irrigation_count', 0)
        if recent_count >= 3:
            approved = False
            safety_notes.append(f"Too many recent irrigations ({recent_count} in short period)")
            risk_level = "unsafe"
        
        # Check 4: Daily limit
        if self.irrigation_count_today >= self.max_daily_irrigations:
            approved = False
            safety_notes.append(f"Daily irrigation limit reached ({self.max_daily_irrigations})")
            risk_level = "unsafe"
        
        # Check 5: Soil already wet
        if decision == "IRRIGATE" and soil > 70:
            approved = False
            safety_notes.append(f"Soil already wet ({soil}%), irrigation not needed")
            risk_level = "caution"
        
        # Check 6: Extreme conditions
        if temp > 45:
            approved = False
            safety_notes.append(f"Temperature too high for safe irrigation ({temp}°C)")
            risk_level = "unsafe"
        
        # Generate command
        if approved and decision == "IRRIGATE":
            pump_command = "ON"
            explanation = f"Irrigating for {duration} seconds. {reasoning}"
        else:
            pump_command = "OFF"
            duration = 0
            if not approved:
                explanation = f"Irrigation blocked: {'; '.join(safety_notes)}"
            else:
                explanation = f"No irrigation needed. {reasoning}"
        
        if not safety_notes:
            safety_notes.append("All safety checks passed")
        
        return {
            "approved": approved,
            "validated_command": {
                "pump": pump_command,
                "duration_sec": duration,
                "explanation": explanation
            },
            "safety_notes": "; ".join(safety_notes),
            "risk_level": risk_level
        }
    
    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate agent output"""
        if "approved" not in output or "validated_command" not in output:
            return False
        
        cmd = output.get("validated_command", {})
        if "pump" not in cmd or "duration_sec" not in cmd:
            return False
        
        if cmd.get("pump") not in ["ON", "OFF"]:
            return False
        
        duration = cmd.get("duration_sec", -1)
        if not (0 <= duration <= 180):
            return False
        
        return True
    
    def update_irrigation_count(self):
        """Increment irrigation counter"""
        self.irrigation_count_today += 1
        logger.info(f"Irrigation count today: {self.irrigation_count_today}")
    
    def reset_daily_count(self):
        """Reset daily counter (call at midnight)"""
        self.irrigation_count_today = 0
        logger.info("Daily irrigation count reset")
