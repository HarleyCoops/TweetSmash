"""Configuration management for TweetSmash MCP Server"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration"""
    
    # TweetSmash
    tweetsmash_api_key: str
    tweetsmash_api_url: str = "https://api.tweetsmash.com/v1"
    tweetsmash_webhook_secret: Optional[str] = None
    
    # E2B
    e2b_api_key: Optional[str] = None
    
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    whisper_model: str = "whisper-1"
    
    # Notion
    notion_token: Optional[str] = None
    notion_database_id: Optional[str] = None
    
    # YouTube
    youtube_api_key: Optional[str] = None
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    
    # Server
    mcp_server_name: str = "tweetsmash-mcp"
    mcp_server_version: str = "1.0.0"
    mcp_log_level: str = "INFO"
    
    # Webhook Server
    webhook_server_port: int = 8000
    webhook_server_host: str = "0.0.0.0"
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables"""
        return cls(
            # TweetSmash
            tweetsmash_api_key=os.getenv("TWEETSMASH_API_KEY", ""),
            tweetsmash_api_url=os.getenv("TWEETSMASH_API_URL", "https://api.tweetsmash.com/v1"),
            tweetsmash_webhook_secret=os.getenv("TWEETSMASH_WEBHOOK_SECRET"),
            
            # E2B
            e2b_api_key=os.getenv("E2B_API_KEY"),
            
            # OpenAI
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            
            # Notion
            notion_token=os.getenv("NOTION_TOKEN"),
            notion_database_id=os.getenv("NOTION_DATABASE_ID"),
            
            # YouTube
            youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
            
            # Redis
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            
            # Celery
            celery_broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
            celery_result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
            
            # Server
            mcp_server_name=os.getenv("MCP_SERVER_NAME", "tweetsmash-mcp"),
            mcp_server_version=os.getenv("MCP_SERVER_VERSION", "1.0.0"),
            mcp_log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
            
            # Webhook
            webhook_server_port=int(os.getenv("WEBHOOK_SERVER_PORT", "8000")),
            webhook_server_host=os.getenv("WEBHOOK_SERVER_HOST", "0.0.0.0"),
            
            # Environment
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "true").lower() == "true"
        )
    
    def validate(self) -> bool:
        """Validate required configuration"""
        if not self.tweetsmash_api_key:
            raise ValueError("TWEETSMASH_API_KEY is required")
        
        return True


# Global config instance
config = Config.from_env()