"""Agent Orchestrator - Coordinates the multi-agent pipeline"""

import asyncio
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from agents.content_analysis_agent import ContentAnalysisAgent
from agents.github_discovery_agent import GitHubDiscoveryAgent
from agents.code_execution_agent import CodeExecutionAgent
from agents.content_synthesis_agent import ContentSynthesisAgent
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AgentOrchestrator(BaseAgent):
    """Orchestrates the multi-agent pipeline for processing TweetSmash bookmarks"""
    
    def __init__(self, conf: Any = None):
        super().__init__("AgentOrchestrator", conf)
        
        # Initialize agents
        self.content_analysis_agent = ContentAnalysisAgent(conf)
        self.github_discovery_agent = GitHubDiscoveryAgent(conf)
        self.code_execution_agent = CodeExecutionAgent(conf)
        self.content_synthesis_agent = ContentSynthesisAgent(conf)
    
    async def process_bookmark(
        self,
        bookmark_data: Dict[str, Any],
        pipeline_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a bookmark through the full multi-agent pipeline
        
        Args:
            bookmark_data: TweetSmash bookmark data
            pipeline_config: Optional configuration for pipeline behavior
            
        Returns:
            Final synthesized content ready for storage
        """
        try:
            self.log_step("Starting multi-agent bookmark processing")
            
            # Default pipeline configuration
            config = {
                "discovery_strategy": "aggressive",  # or "conservative"
                "execution_strategy": "quick",       # or "thorough"
                "synthesis_style": "detailed",       # or "summary" or "actionable"
                "max_repositories": 3,
                "enable_parallel_execution": True,
                "timeout_per_agent": 60,  # seconds
                **(pipeline_config or {})
            }
            
            pipeline_results = {
                "bookmark_id": bookmark_data.get("post_id"),
                "pipeline_config": config,
                "agent_results": {},
                "timing": {},
                "errors": []
            }
            
            # Step 1: Content Analysis
            start_time = self._get_timestamp()
            content_analysis_result = await self._run_with_timeout(
                self.content_analysis_agent.process({
                    "bookmark": bookmark_data,
                    "tweet_text": bookmark_data.get("tweet_details", {}).get("text", ""),
                    "author_details": bookmark_data.get("author_details", {})
                }),
                config["timeout_per_agent"],
                "ContentAnalysisAgent"
            )
            
            pipeline_results["agent_results"]["content_analysis"] = content_analysis_result
            pipeline_results["timing"]["content_analysis"] = self._get_timestamp() - start_time
            
            if not content_analysis_result.get("success"):
                return self._create_error_result("Content analysis failed", pipeline_results)
            
            content_analysis_data = content_analysis_result["data"]
            
            # Check if GitHub processing is needed
            if not content_analysis_data.get("requires_github_discovery", False) and \
               content_analysis_data.get("github_relevance_score", 0) < 0.3:
                
                self.log_step("Low GitHub relevance, skipping GitHub processing")
                return await self._process_non_github_content(bookmark_data, content_analysis_data, config)
            
            # Step 2: GitHub Discovery
            start_time = self._get_timestamp()
            github_discovery_result = await self._run_with_timeout(
                self.github_discovery_agent.process({
                    "content_analysis": content_analysis_data,
                    "discovery_strategy": config["discovery_strategy"]
                }),
                config["timeout_per_agent"],
                "GitHubDiscoveryAgent"
            )
            
            pipeline_results["agent_results"]["github_discovery"] = github_discovery_result
            pipeline_results["timing"]["github_discovery"] = self._get_timestamp() - start_time
            
            if not github_discovery_result.get("success"):
                return self._create_error_result("GitHub discovery failed", pipeline_results)
            
            github_discovery_data = github_discovery_result["data"]
            
            # Check if any repositories were found
            discovered_repos = github_discovery_data.get("discovered_repositories", [])
            if not discovered_repos:
                self.log_step("No GitHub repositories discovered, proceeding with analysis only")
                return await self._process_without_execution(
                    bookmark_data, 
                    content_analysis_data, 
                    github_discovery_data, 
                    config
                )
            
            # Step 3: Code Execution
            start_time = self._get_timestamp()
            code_execution_result = await self._run_with_timeout(
                self.code_execution_agent.process({
                    "github_discovery": github_discovery_data,
                    "execution_strategy": config["execution_strategy"],
                    "max_repositories": config["max_repositories"]
                }),
                config["timeout_per_agent"] * 2,  # Code execution may take longer
                "CodeExecutionAgent"
            )
            
            pipeline_results["agent_results"]["code_execution"] = code_execution_result
            pipeline_results["timing"]["code_execution"] = self._get_timestamp() - start_time
            
            if not code_execution_result.get("success"):
                # Continue without execution results
                self.log_step("Code execution failed, continuing with available data")
                code_execution_data = {"execution_results": [], "analysis": {}}
            else:
                code_execution_data = code_execution_result["data"]
            
            # Step 4: Content Synthesis
            start_time = self._get_timestamp()
            synthesis_result = await self._run_with_timeout(
                self.content_synthesis_agent.process({
                    "original_bookmark": bookmark_data,
                    "content_analysis": content_analysis_data,
                    "github_discovery": github_discovery_data,
                    "code_execution": code_execution_data,
                    "synthesis_style": config["synthesis_style"]
                }),
                config["timeout_per_agent"],
                "ContentSynthesisAgent"
            )
            
            pipeline_results["agent_results"]["content_synthesis"] = synthesis_result
            pipeline_results["timing"]["content_synthesis"] = self._get_timestamp() - start_time
            
            if not synthesis_result.get("success"):
                return self._create_error_result("Content synthesis failed", pipeline_results)
            
            # Final results
            synthesis_data = synthesis_result["data"]
            
            final_result = {
                "success": True,
                "bookmark_id": bookmark_data.get("post_id"),
                "title": synthesis_data.get("title"),
                "content": synthesis_data.get("synthesized_content"),
                "actionable_items": synthesis_data.get("actionable_items", []),
                "tags": synthesis_data.get("tags", []),
                "metadata": {
                    **synthesis_data.get("metadata", {}),
                    "pipeline_timing": pipeline_results["timing"],
                    "total_processing_time": sum(pipeline_results["timing"].values()),
                    "repositories_discovered": len(discovered_repos),
                    "repositories_executed": len(code_execution_data.get("execution_results", [])),
                    "github_relevance_score": content_analysis_data.get("github_relevance_score", 0)
                },
                "pipeline_results": pipeline_results  # Full pipeline details for debugging
            }
            
            self.log_step("Multi-agent processing complete", {
                "total_time": final_result["metadata"]["total_processing_time"],
                "repos_found": final_result["metadata"]["repositories_discovered"],
                "repos_executed": final_result["metadata"]["repositories_executed"]
            })
            
            return final_result
            
        except Exception as e:
            logger.error(f"Pipeline orchestration failed: {e}")
            return self._create_error_result(f"Pipeline failed: {str(e)}", pipeline_results)
    
    async def _process_non_github_content(
        self,
        bookmark_data: Dict,
        content_analysis_data: Dict,
        config: Dict
    ) -> Dict[str, Any]:
        """Process content that doesn't require GitHub analysis"""
        try:
            self.log_step("Processing non-GitHub content")
            
            # Skip GitHub discovery and execution, go straight to synthesis
            synthesis_result = await self.content_synthesis_agent.process({
                "original_bookmark": bookmark_data,
                "content_analysis": content_analysis_data,
                "github_discovery": {"discovered_repositories": []},
                "code_execution": {"execution_results": [], "analysis": {}},
                "synthesis_style": config["synthesis_style"]
            })
            
            if synthesis_result.get("success"):
                synthesis_data = synthesis_result["data"]
                return {
                    "success": True,
                    "bookmark_id": bookmark_data.get("post_id"),
                    "title": synthesis_data.get("title"),
                    "content": synthesis_data.get("synthesized_content"),
                    "actionable_items": synthesis_data.get("actionable_items", []),
                    "tags": synthesis_data.get("tags", []),
                    "metadata": {
                        **synthesis_data.get("metadata", {}),
                        "processing_type": "non_github_content",
                        "github_relevance_score": content_analysis_data.get("github_relevance_score", 0)
                    }
                }
            else:
                return self._create_error_result("Synthesis failed for non-GitHub content")
                
        except Exception as e:
            return self._create_error_result(f"Non-GitHub content processing failed: {str(e)}")
    
    async def _process_without_execution(
        self,
        bookmark_data: Dict,
        content_analysis_data: Dict,
        github_discovery_data: Dict,
        config: Dict
    ) -> Dict[str, Any]:
        """Process content when GitHub discovery found no repositories"""
        try:
            self.log_step("Processing without code execution")
            
            # Synthesize with empty execution results
            synthesis_result = await self.content_synthesis_agent.process({
                "original_bookmark": bookmark_data,
                "content_analysis": content_analysis_data,
                "github_discovery": github_discovery_data,
                "code_execution": {"execution_results": [], "analysis": {}},
                "synthesis_style": config["synthesis_style"]
            })
            
            if synthesis_result.get("success"):
                synthesis_data = synthesis_result["data"]
                return {
                    "success": True,
                    "bookmark_id": bookmark_data.get("post_id"),
                    "title": synthesis_data.get("title"),
                    "content": synthesis_data.get("synthesized_content"),
                    "actionable_items": synthesis_data.get("actionable_items", []),
                    "tags": synthesis_data.get("tags", []),
                    "metadata": {
                        **synthesis_data.get("metadata", {}),
                        "processing_type": "github_analysis_only",
                        "github_relevance_score": content_analysis_data.get("github_relevance_score", 0)
                    }
                }
            else:
                return self._create_error_result("Synthesis failed for GitHub analysis")
                
        except Exception as e:
            return self._create_error_result(f"GitHub analysis processing failed: {str(e)}")
    
    async def _run_with_timeout(
        self,
        coroutine,
        timeout_seconds: int,
        agent_name: str
    ) -> Dict[str, Any]:
        """Run an agent with timeout protection"""
        try:
            result = await asyncio.wait_for(coroutine, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"{agent_name} timed out after {timeout_seconds} seconds")
            return {
                "success": False,
                "error": f"Agent timed out after {timeout_seconds} seconds",
                "agent": agent_name
            }
        except Exception as e:
            logger.error(f"{agent_name} failed with error: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent": agent_name
            }
    
    def _get_timestamp(self) -> float:
        """Get current timestamp"""
        import time
        return time.time()
    
    def _create_error_result(
        self,
        error_message: str,
        pipeline_results: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create standardized error result"""
        return {
            "success": False,
            "error": error_message,
            "pipeline_results": pipeline_results or {},
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
    
    async def get_pipeline_status(self) -> Dict[str, Any]:
        """Get status of all agents in the pipeline"""
        status = {
            "orchestrator": "ready",
            "agents": {},
            "pipeline_info": {
                "total_agents": 4,
                "agent_names": [
                    "ContentAnalysisAgent",
                    "GitHubDiscoveryAgent", 
                    "CodeExecutionAgent",
                    "ContentSynthesisAgent"
                ]
            }
        }
        
        # Check each agent's configuration
        agents = [
            ("content_analysis", self.content_analysis_agent),
            ("github_discovery", self.github_discovery_agent),
            ("code_execution", self.code_execution_agent),
            ("content_synthesis", self.content_synthesis_agent)
        ]
        
        for agent_name, agent in agents:
            try:
                agent_status = {
                    "status": "ready",
                    "llm_available": getattr(agent, 'llm_available', False),
                    "config_valid": hasattr(agent, 'config') and agent.config is not None
                }
                
                # Special checks for specific agents
                if agent_name == "github_discovery":
                    agent_status["github_api_ready"] = hasattr(agent, 'github_client')
                elif agent_name == "code_execution":
                    agent_status["e2b_available"] = hasattr(agent, 'e2b_tools') and \
                                                   getattr(agent.e2b_tools.config, 'e2b_api_key', None) is not None
                
                status["agents"][agent_name] = agent_status
                
            except Exception as e:
                status["agents"][agent_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return status
    
    async def test_pipeline(self, test_bookmark: Optional[Dict] = None) -> Dict[str, Any]:
        """Test the pipeline with a sample bookmark"""
        if not test_bookmark:
            test_bookmark = {
                "post_id": "test_123",
                "tweet_details": {
                    "text": "Just built an awesome Python CLI tool for developers! Check it out: github.com/user/awesome-tool",
                    "posted_at": "2024-01-01T12:00:00Z",
                    "link": "https://twitter.com/test/status/123"
                },
                "author_details": {
                    "name": "Test User",
                    "username": "testuser"
                }
            }
        
        try:
            self.log_step("Testing pipeline with sample bookmark")
            
            result = await self.process_bookmark(
                test_bookmark,
                {
                    "discovery_strategy": "conservative",
                    "execution_strategy": "quick",
                    "synthesis_style": "summary",
                    "max_repositories": 1,
                    "timeout_per_agent": 30
                }
            )
            
            test_result = {
                "test_successful": result.get("success", False),
                "processing_time": result.get("metadata", {}).get("total_processing_time", 0),
                "agents_completed": len([
                    k for k, v in result.get("pipeline_results", {}).get("agent_results", {}).items()
                    if v.get("success", False)
                ]),
                "error": result.get("error") if not result.get("success") else None
            }
            
            return test_result
            
        except Exception as e:
            return {
                "test_successful": False,
                "error": str(e)
            }