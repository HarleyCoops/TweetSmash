"""GitHub MCP tools implementation using E2B for code execution"""

from typing import Dict, Any, Optional
from tools.e2b import E2BTools
from utils.logger import setup_logger
from utils.config import config

logger = setup_logger(__name__)


class GitHubTools:
    """MCP tools for GitHub integration via E2B"""
    
    def __init__(self, conf: Any = None):
        self.config = conf or config
        self.e2b_tools = E2BTools(conf)
    
    async def create_codespace(
        self, 
        repo_url: str,
        machine_type: str = None
    ) -> Dict[str, Any]:
        """
        Execute GitHub repository code using E2B sandbox (replaces Codespace)
        
        Args:
            repo_url: GitHub repository URL
            machine_type: Ignored (E2B template auto-detected)
            
        Returns:
            E2B execution result
        """
        try:
            logger.info(f"Executing GitHub repo via E2B: {repo_url}")
            
            # Use E2B to clone and execute the repository
            result = await self.e2b_tools.analyze_and_run_project(
                repo_url=repo_url,
                auto_install=True
            )
            
            if result.get("success"):
                return {
                    "success": True,
                    "repo_url": repo_url,
                    "execution_method": "E2B Sandbox",
                    "project_analysis": result.get("analysis", {}),
                    "install_output": result.get("install_output", ""),
                    "run_output": result.get("run_output", ""),
                    "template": result.get("template", "python3"),
                    "message": "Repository cloned and executed in E2B sandbox"
                }
            else:
                return result
            
        except Exception as e:
            logger.error(f"Error executing repo via E2B: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_code_snippet(
        self,
        code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Execute a code snippet using E2B
        
        Args:
            code: Code to execute
            language: Programming language
            
        Returns:
            Execution result
        """
        return await self.e2b_tools.execute_code_snippet(
            code=code,
            language=language,
            description="Code snippet from GitHub bookmark"
        )