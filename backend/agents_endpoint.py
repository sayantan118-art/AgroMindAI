"""
Multi-Agent System Endpoint
FastAPI endpoint for autonomous irrigation control
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from agents.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/agents", tags=["Multi-Agent System"])

# Initialize orchestrator (singleton)
# load Groq API key from environment; do not include a default in source control
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is required for AI reasoning")

orchestrator = AgentOrchestrator(GROQ_API_KEY)


class SensorInput(BaseModel):
    """Sensor data input model"""
    soil_moisture: float
    temperature: float
    humidity: float
    light: Optional[int] = 0
    rain_detected: Optional[bool] = False


class WeatherInput(BaseModel):
    """Weather data input model"""
    rain_probability_next_hour: Optional[float] = 0
    temperature_2m_max: Optional[float] = None
    precipitation_probability_max: Optional[float] = 0


class AgentDecisionRequest(BaseModel):
    """Complete request for agent decision"""
    sensor_data: SensorInput
    weather_data: Optional[WeatherInput] = None


@router.post("/decide")
async def agent_decision(request: AgentDecisionRequest) -> Dict[str, Any]:
    """
    Main endpoint for autonomous irrigation decision
    
    Processes sensor data through multi-agent system and returns
    validated irrigation command
    """
    try:
        logger.info("Received agent decision request")
        
        # Convert Pydantic models to dicts
        sensor_dict = request.sensor_data.model_dump()
        weather_dict = request.weather_data.model_dump() if request.weather_data else {}
        
        # Process through agent pipeline
        result = await orchestrator.process_sensor_data(
            sensor_data=sensor_dict,
            weather_data=weather_dict
        )
        
        logger.info(f"Agent decision complete: {result['final_command']['pump']}")
        
        return {
            "status": "success",
            "decision": result
        }
        
    except Exception as e:
        logger.error(f"Agent decision error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def agent_health() -> Dict[str, Any]:
    """Health check for agent system"""
    return {
        "status": "healthy",
        "agents": {
            "sensor_interpreter": "active",
            "crop_doctor": "active",
            "weather_intelligence": "active",
            "irrigation_planner": "active",
            "safety_supervisor": "active",
            "memory": "active"
        },
        "memory_stats": orchestrator.memory.get_context()
    }


@router.post("/memory/clear")
async def clear_memory() -> Dict[str, str]:
    """Clear agent memory (for testing)"""
    orchestrator.memory.clear_history()
    return {"status": "memory cleared"}


@router.get("/memory/context")
async def get_memory_context() -> Dict[str, Any]:
    """Get current memory context"""
    return orchestrator.memory.get_context()
