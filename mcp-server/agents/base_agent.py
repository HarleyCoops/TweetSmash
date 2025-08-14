"""Base agent class for TweetSmash multi-agent pipeline"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from utils.logger import setup_logger
from utils.config import config
import openai

logger = setup_logger(__name__)


class BaseAgent(ABC):
    """Base class for all agents in the pipeline"""
    
    def __init__(self, agent_name: str, conf: Any = None):
        self.agent_name = agent_name
        self.config = conf or config
        
        # Initialize OpenAI client (using Anthropic API key for Claude via OpenAI-compatible endpoint)
        if self.config.anthropic_api_key:
            # Use Anthropic's Claude via OpenAI-compatible API
            openai.api_key = self.config.anthropic_api_key
            openai.api_base = "https://api.anthropic.com/v1"
            self.llm_available = True
            self.model = "claude-3-sonnet-20240229"
        elif self.config.openai_api_key:
            # Fallback to OpenAI
            openai.api_key = self.config.openai_api_key
            self.llm_available = True
            self.model = self.config.openai_model
        else:
            logger.warning(f"No LLM API key configured for {agent_name}")
            self.llm_available = False
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return results"""
        pass
    
    async def llm_query(
        self, 
        prompt: str, 
        system_prompt: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Query the LLM with a prompt"""
        try:
            if not self.llm_available:
                raise ValueError("No LLM API key configured")
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM query failed in {self.agent_name}: {e}")
            raise
    
    def log_step(self, step: str, data: Any = None):
        """Log agent processing step"""
        logger.info(f"[{self.agent_name}] {step}")
        if data and self.config.debug:
            logger.debug(f"[{self.agent_name}] Data: {data}")
    
    def create_result(
        self, 
        success: bool, 
        data: Dict[str, Any] = None, 
        error: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create standardized result format"""
        result = {
            "success": success,
            "agent": self.agent_name,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
        
        if data:
            result["data"] = data
        if error:
            result["error"] = error
        if metadata:
            result["metadata"] = metadata
            
        return result