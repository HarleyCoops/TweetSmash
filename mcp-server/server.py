#!/usr/bin/env python3
"""
TweetSmash MCP Server
Main entry point for the Model Context Protocol server
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from tools.tweetsmash import TweetSmashTools
from tools.github import GitHubTools
from tools.youtube import YouTubeTools
from tools.notion import NotionTools
from processors.router import ContentRouter
from agents.orchestrator import AgentOrchestrator
from utils.config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)


class TweetSmashMCPServer:
    def __init__(self):
        self.server = Server("tweetsmash-mcp")
        self.config = Config()
        self.router = ContentRouter(self.config)
        
        # Initialize tool handlers
        self.tweetsmash_tools = TweetSmashTools(self.config)
        self.github_tools = GitHubTools(self.config)
        self.youtube_tools = YouTubeTools(self.config)
        self.notion_tools = NotionTools(self.config)
        
        # Initialize multi-agent pipeline
        self.agent_orchestrator = AgentOrchestrator(self.config)
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Register all MCP handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List all available tools"""
            tools = []
            
            # TweetSmash tools
            tools.extend([
                types.Tool(
                    name="fetch_bookmarks",
                    description="Fetch recent bookmarks from TweetSmash",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of bookmarks to fetch",
                                "default": 10
                            },
                            "cursor": {
                                "type": "string",
                                "description": "Pagination cursor",
                                "required": False
                            }
                        }
                    }
                ),
                types.Tool(
                    name="process_bookmark",
                    description="Process a bookmark through the automation pipeline",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bookmark_id": {
                                "type": "string",
                                "description": "ID of the bookmark to process"
                            },
                            "force": {
                                "type": "boolean",
                                "description": "Force reprocessing even if already processed",
                                "default": False
                            }
                        },
                        "required": ["bookmark_id"]
                    }
                ),
                types.Tool(
                    name="analyze_url",
                    description="Analyze a URL and determine its content type",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to analyze"
                            }
                        },
                        "required": ["url"]
                    }
                ),
                types.Tool(
                    name="execute_github_repo",
                    description="Clone and execute a GitHub repository using E2B sandbox",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "repo_url": {
                                "type": "string",
                                "description": "GitHub repository URL"
                            },
                            "auto_install": {
                                "type": "boolean",
                                "description": "Automatically install dependencies",
                                "default": True
                            }
                        },
                        "required": ["repo_url"]
                    }
                ),
                types.Tool(
                    name="execute_code_snippet",
                    description="Execute a code snippet in E2B sandbox",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Code to execute"
                            },
                            "language": {
                                "type": "string",
                                "description": "Programming language (python, javascript, etc.)",
                                "default": "python"
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of what the code does"
                            }
                        },
                        "required": ["code"]
                    }
                ),
                types.Tool(
                    name="transcribe_youtube",
                    description="Transcribe and summarize a YouTube video",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "video_url": {
                                "type": "string",
                                "description": "YouTube video URL"
                            },
                            "summary_style": {
                                "type": "string",
                                "description": "Summary style (brief, detailed, action_items)",
                                "default": "brief"
                            }
                        },
                        "required": ["video_url"]
                    }
                ),
                types.Tool(
                    name="save_to_notion",
                    description="Save content to Notion database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Content title"
                            },
                            "url": {
                                "type": "string",
                                "description": "Content URL"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content body or summary"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for categorization"
                            }
                        },
                        "required": ["title", "url"]
                    }
                ),
                types.Tool(
                    name="get_processing_status",
                    description="Get status of bookmark processing jobs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "Specific job ID to check",
                                "required": False
                            }
                        }
                    }
                ),
                types.Tool(
                    name="process_bookmark_intelligent",
                    description="Process bookmark using multi-agent pipeline for intelligent GitHub discovery and analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bookmark_id": {
                                "type": "string",
                                "description": "ID of the bookmark to process"
                            },
                            "bookmark_data": {
                                "type": "object",
                                "description": "Optional bookmark data (if not provided, will fetch from TweetSmash)",
                                "required": False
                            },
                            "pipeline_config": {
                                "type": "object",
                                "description": "Pipeline configuration options",
                                "properties": {
                                    "discovery_strategy": {
                                        "type": "string",
                                        "enum": ["aggressive", "conservative"],
                                        "description": "GitHub discovery strategy",
                                        "default": "aggressive"
                                    },
                                    "execution_strategy": {
                                        "type": "string", 
                                        "enum": ["quick", "thorough"],
                                        "description": "Code execution strategy",
                                        "default": "quick"
                                    },
                                    "synthesis_style": {
                                        "type": "string",
                                        "enum": ["detailed", "summary", "actionable"],
                                        "description": "Content synthesis style",
                                        "default": "detailed"
                                    },
                                    "max_repositories": {
                                        "type": "integer",
                                        "description": "Maximum repositories to execute",
                                        "default": 3
                                    }
                                },
                                "required": False
                            }
                        },
                        "required": ["bookmark_id"]
                    }
                ),
                types.Tool(
                    name="get_pipeline_status",
                    description="Get status of the multi-agent pipeline",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                types.Tool(
                    name="test_pipeline",
                    description="Test the multi-agent pipeline with sample data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "test_bookmark": {
                                "type": "object",
                                "description": "Optional test bookmark data",
                                "required": False
                            }
                        }
                    }
                )
            ])
            
            return tools
        
        @self.server.call_tool()
        async def handle_call_tool(
            name: str, 
            arguments: Optional[Dict[str, Any]] = None
        ) -> List[types.TextContent]:
            """Handle tool execution"""
            try:
                logger.info(f"Executing tool: {name} with args: {arguments}")
                
                if name == "fetch_bookmarks":
                    result = await self.tweetsmash_tools.fetch_bookmarks(
                        limit=arguments.get("limit", 10),
                        cursor=arguments.get("cursor")
                    )
                
                elif name == "process_bookmark":
                    result = await self.router.process_bookmark(
                        bookmark_id=arguments["bookmark_id"],
                        force=arguments.get("force", False)
                    )
                
                elif name == "analyze_url":
                    result = await self.router.analyze_url(arguments["url"])
                
                elif name == "execute_github_repo":
                    result = await self.github_tools.create_codespace(
                        repo_url=arguments["repo_url"]
                    )
                
                elif name == "execute_code_snippet":
                    result = await self.github_tools.execute_code_snippet(
                        code=arguments["code"],
                        language=arguments.get("language", "python")
                    )
                
                elif name == "transcribe_youtube":
                    result = await self.youtube_tools.transcribe_and_summarize(
                        video_url=arguments["video_url"],
                        summary_style=arguments.get("summary_style", "brief")
                    )
                
                elif name == "save_to_notion":
                    result = await self.notion_tools.save_content(
                        title=arguments["title"],
                        url=arguments["url"],
                        content=arguments.get("content", ""),
                        tags=arguments.get("tags", [])
                    )
                
                elif name == "get_processing_status":
                    result = await self.router.get_job_status(
                        job_id=arguments.get("job_id")
                    )
                
                elif name == "process_bookmark_intelligent":
                    # Get bookmark data if not provided
                    bookmark_data = arguments.get("bookmark_data")
                    if not bookmark_data:
                        bookmark_result = await self.tweetsmash_tools.get_bookmark_details(
                            arguments["bookmark_id"]
                        )
                        if not bookmark_result.get("success"):
                            raise ValueError(f"Failed to fetch bookmark: {bookmark_result.get('error')}")
                        bookmark_data = bookmark_result.get("bookmark")
                    
                    # Process through multi-agent pipeline
                    result = await self.agent_orchestrator.process_bookmark(
                        bookmark_data,
                        arguments.get("pipeline_config")
                    )
                
                elif name == "get_pipeline_status":
                    result = await self.agent_orchestrator.get_pipeline_status()
                
                elif name == "test_pipeline":
                    result = await self.agent_orchestrator.test_pipeline(
                        arguments.get("test_bookmark")
                    )
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                logger.error(f"Tool execution failed: {str(e)}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]
    
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("TweetSmash MCP Server starting...")
            
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="tweetsmash-mcp",
                    server_version="1.0.0"
                )
            )


async def main():
    """Main entry point"""
    server = TweetSmashMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())