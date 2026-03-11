"""
Agent Orchestrator
Coordinates all agents in the autonomous control loop
"""

import logging
from typing import Dict, Any
from .sensor_interpreter import SensorInterpreterAgent
from .crop_doctor import CropDoctorAgent
from .weather_intelligence import WeatherIntelligenceAgent
from .irrigation_planner import IrrigationPlannerAgent
from .safety_supervisor import SafetySupervisorAgent
from .memory_agent import MemoryAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates multi-agent decision pipeline"""
    
    def __init__(self, groq_api_key: str):
        self.groq_api_key = groq_api_key
        
        # Initialize all agents
        self.sensor_interpreter = SensorInterpreterAgent(groq_api_key)
        self.crop_doctor = CropDoctorAgent(groq_api_key)
        self.weather_intelligence = WeatherIntelligenceAgent(groq_api_key)
        self.irrigation_planner = IrrigationPlannerAgent(groq_api_key)
        self.safety_supervisor = SafetySupervisorAgent(groq_api_key)
        self.memory = MemoryAgent(max_records=5)
        
        logger.info("AgentOrchestrator initialized with all agents")
    
    async def process_sensor_data(
        self,
        sensor_data: Dict[str, Any],
        weather_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main autonomous control loop
        Processes sensor data through all agents and returns irrigation command
        """
        logger.info("=== Starting Autonomous Control Loop ===")
        
        # Step 1: Update memory
        self.memory.add_sensor_reading(sensor_data)
        memory_context = self.memory.get_context()
        logger.info(f"Memory updated: {memory_context['sensor_history_count']} records")
        
        # Step 2: Interpret environment
        logger.info("Step 1: Interpreting sensor data...")
        env_state = await self.sensor_interpreter.execute({
            'soil_moisture': sensor_data.get('soil_moisture', 0),
            'temperature': sensor_data.get('temperature', 0),
            'humidity': sensor_data.get('humidity', 0),
            'light': sensor_data.get('light', 0),
            'rain_detected': sensor_data.get('rain_detected', False)
        })
        logger.info(f"Environmental state: {env_state.get('soil_status')}, "
                   f"Heat stress: {env_state.get('heat_stress')}")
        
        # Step 3: Evaluate crop health
        logger.info("Step 2: Evaluating crop health...")
        crop_health = await self.crop_doctor.execute({
            'environmental_state': env_state,
            'sensor_data': sensor_data,
            'memory': memory_context
        })
        logger.info(f"Crop health: {crop_health.get('health_score')}/100, "
                   f"Stress: {crop_health.get('stress_type')}")
        
        # Step 4: Analyze weather forecast
        logger.info("Step 3: Analyzing weather forecast...")
        weather_intel = await self.weather_intelligence.execute({
            'weather_data': weather_data,
            'sensor_data': sensor_data
        })
        logger.info(f"Weather: Rain probability {weather_intel.get('rain_probability')}%, "
                   f"Expected: {weather_intel.get('rain_expected')}")
        
        # Step 5: Generate irrigation plan
        logger.info("Step 4: Planning irrigation strategy...")
        irrigation_plan = await self.irrigation_planner.execute({
            'environmental_state': env_state,
            'crop_health': crop_health,
            'weather_intelligence': weather_intel,
            'sensor_data': sensor_data,
            'memory': memory_context
        })
        logger.info(f"Irrigation plan: {irrigation_plan.get('decision')}, "
                   f"Duration: {irrigation_plan.get('irrigation_duration_sec')}s")
        
        # Step 6: Validate safety
        logger.info("Step 5: Validating safety...")
        safety_result = await self.safety_supervisor.execute({
            'irrigation_plan': irrigation_plan,
            'sensor_data': sensor_data,
            'memory': memory_context
        })
        logger.info(f"Safety check: Approved={safety_result.get('approved')}, "
                   f"Risk={safety_result.get('risk_level')}")
        
        # Step 7: Update memory with decision
        validated_cmd = safety_result.get('validated_command', {})
        self.memory.add_irrigation_event(
            decision=irrigation_plan.get('decision', 'SKIP'),
            duration=validated_cmd.get('duration_sec', 0),
            reasoning=validated_cmd.get('explanation', '')
        )
        
        # Update irrigation counter if approved
        if safety_result.get('approved') and validated_cmd.get('pump') == 'ON':
            self.safety_supervisor.update_irrigation_count()
        
        logger.info("=== Control Loop Complete ===")
        
        # Return complete decision package
        return {
            'environmental_state': env_state,
            'crop_health': crop_health,
            'weather_intelligence': weather_intel,
            'irrigation_plan': irrigation_plan,
            'safety_validation': safety_result,
            'final_command': validated_cmd,
            'memory_context': memory_context
        }
