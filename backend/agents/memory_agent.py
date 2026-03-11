"""
Memory Agent
Maintains short-term memory of sensor readings and irrigation events
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


class MemoryAgent:
    """Maintains short-term memory for trend analysis"""
    
    def __init__(self, max_records: int = 5):
        self.max_records = max_records
        self.sensor_history = deque(maxlen=max_records)
        self.irrigation_history = deque(maxlen=10)
        self.last_irrigation_time = None
    
    def add_sensor_reading(self, sensor_data: Dict[str, Any]):
        """Add new sensor reading to memory"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "soil_moisture": sensor_data.get('soil_moisture', 0),
            "temperature": sensor_data.get('temperature', 0),
            "humidity": sensor_data.get('humidity', 0),
            "light": sensor_data.get('light', 0),
            "rain_detected": sensor_data.get('rain_detected', False)
        }
        self.sensor_history.append(record)
        logger.debug(f"Added sensor reading to memory. Total records: {len(self.sensor_history)}")
    
    def add_irrigation_event(self, decision: str, duration: int, reasoning: str):
        """Add irrigation event to memory"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "duration_sec": duration,
            "reasoning": reasoning
        }
        self.irrigation_history.append(event)
        
        if decision == "IRRIGATE" and duration > 0:
            self.last_irrigation_time = datetime.now()
        
        logger.info(f"Added irrigation event: {decision} for {duration}s")
    
    def get_trend_summary(self) -> str:
        """Generate trend summary from recent readings"""
        if len(self.sensor_history) < 2:
            return "Insufficient data for trend analysis"
        
        records = list(self.sensor_history)
        
        # Calculate trends
        soil_values = [r['soil_moisture'] for r in records]
        temp_values = [r['temperature'] for r in records]
        humidity_values = [r['humidity'] for r in records]
        
        soil_trend = self._calculate_trend(soil_values)
        temp_trend = self._calculate_trend(temp_values)
        humidity_trend = self._calculate_trend(humidity_values)
        
        # Check for rain
        rain_detected = any(r['rain_detected'] for r in records)
        
        summary = []
        summary.append(f"Soil moisture {soil_trend} (current: {soil_values[-1]}%)")
        summary.append(f"Temperature {temp_trend} (current: {temp_values[-1]}°C)")
        summary.append(f"Humidity {humidity_trend} (current: {humidity_values[-1]}%)")
        
        if rain_detected:
            summary.append("Rain detected in recent readings")
        
        return "; ".join(summary)
    
    def get_recent_summary(self) -> str:
        """Get summary of recent irrigation activity"""
        if not self.irrigation_history:
            return "No recent irrigation activity"
        
        recent_events = list(self.irrigation_history)[-3:]
        
        irrigations = [e for e in recent_events if e['decision'] == 'IRRIGATE']
        
        if not irrigations:
            return "No recent irrigations"
        
        last_irrigation = irrigations[-1]
        time_str = last_irrigation['timestamp']
        duration = last_irrigation['duration_sec']
        
        summary = f"Last irrigation: {time_str} for {duration}s"
        
        if len(irrigations) > 1:
            summary += f"; Total recent irrigations: {len(irrigations)}"
        
        return summary
    
    def get_recent_irrigation_count(self) -> int:
        """Count irrigations in last hour"""
        if not self.irrigation_history:
            return 0
        
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        count = 0
        for event in self.irrigation_history:
            if event['decision'] == 'IRRIGATE':
                event_time = datetime.fromisoformat(event['timestamp'])
                if event_time > one_hour_ago:
                    count += 1
        
        return count
    
    def get_context(self) -> Dict[str, Any]:
        """Get full memory context for agents"""
        return {
            "trend_summary": self.get_trend_summary(),
            "recent_summary": self.get_recent_summary(),
            "recent_irrigation_count": self.get_recent_irrigation_count(),
            "last_irrigation_time": self.last_irrigation_time.isoformat() if self.last_irrigation_time else "Never",
            "sensor_history_count": len(self.sensor_history),
            "irrigation_history_count": len(self.irrigation_history)
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction"""
        if len(values) < 2:
            return "stable"
        
        # Compare first half to second half
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / mid
        second_half_avg = sum(values[mid:]) / (len(values) - mid)
        
        diff = second_half_avg - first_half_avg
        
        if diff > 2:
            return "increasing"
        elif diff < -2:
            return "decreasing"
        else:
            return "stable"
    
    def clear_history(self):
        """Clear all history (for testing)"""
        self.sensor_history.clear()
        self.irrigation_history.clear()
        self.last_irrigation_time = None
        logger.info("Memory cleared")
