"""
Base Agent Class
All specialized agents inherit from this base class
"""

import json
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import httpx

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all AI agents in the system"""
    
    def __init__(self, name: str, groq_api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.name = name
        self.groq_api_key = groq_api_key
        self.model = model
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent"""
        pass
    
    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return output"""
        pass
    
    @abstractmethod
    def fallback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback logic if LLM fails"""
        pass
    
    async def call_groq(self, user_message: str, temperature: float = 0.3) -> Optional[str]:
        """Call Groq API with error handling"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.groq_url,
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.get_system_prompt()},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": temperature,
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"{self.name} Groq API error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"{self.name} Groq API exception: {e}")
            return None
    
    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response"""
        try:
            # Try to find JSON in the response
            import re
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                return json.loads(match.group(0))
            return None
        except Exception as e:
            logger.error(f"{self.name} JSON extraction error: {e}")
            return None
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent with fallback"""
        try:
            result = await self.process(input_data)
            if result:
                logger.info(f"{self.name} executed successfully")
                return result
            else:
                logger.warning(f"{self.name} failed, using fallback")
                return self.fallback(input_data)
        except Exception as e:
            logger.error(f"{self.name} execution error: {e}")
            return self.fallback(input_data)
