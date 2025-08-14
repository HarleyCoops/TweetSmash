"""Logging configuration for TweetSmash MCP Server"""

import sys
from loguru import logger
from utils.config import config


def setup_logger(name: str = None):
    """Setup and configure logger"""
    
    # Remove default logger
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=config.mcp_log_level,
        colorize=True
    )
    
    # Add file handler for production
    if config.environment == "production":
        logger.add(
            "logs/tweetsmash_{time}.log",
            rotation="500 MB",
            retention="7 days",
            level=config.mcp_log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )
    
    if name:
        return logger.bind(name=name)
    
    return logger


# Create default logger
default_logger = setup_logger()