"""Code Execution Agent - Executes discovered GitHub repositories using E2B"""

import json
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from tools.e2b import E2BTools
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CodeExecutionAgent(BaseAgent):
    """Agent that executes GitHub repositories in E2B sandboxes"""
    
    def __init__(self, conf: Any = None):
        super().__init__("CodeExecutionAgent", conf)
        self.e2b_tools = E2BTools(conf)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute discovered GitHub repositories
        
        Args:
            input_data: {
                "github_discovery": Results from GitHubDiscoveryAgent,
                "execution_strategy": "quick" | "thorough",
                "max_repositories": int (default 3)
            }
            
        Returns:
            Execution results for all repositories
        """
        try:
            self.log_step("Starting code execution")
            
            github_discovery = input_data.get("github_discovery", {})
            strategy = input_data.get("execution_strategy", "quick")
            max_repos = input_data.get("max_repositories", 3)
            
            discovered_repos = github_discovery.get("discovered_repositories", [])
            
            if not discovered_repos:
                return self.create_result(True, {
                    "execution_results": [],
                    "message": "No repositories to execute"
                })
            
            # Select repositories to execute based on strategy
            repos_to_execute = self._select_repositories_for_execution(
                discovered_repos, 
                strategy, 
                max_repos
            )
            
            execution_results = []
            
            for repo in repos_to_execute:
                self.log_step(f"Executing repository: {repo['full_name']}")
                
                try:
                    # Execute repository
                    execution_result = await self._execute_repository(repo, strategy)
                    
                    # Enhance with repository metadata
                    enhanced_result = {
                        **execution_result,
                        "repository_metadata": {
                            "name": repo["name"],
                            "full_name": repo["full_name"],
                            "description": repo.get("description"),
                            "language": repo.get("language"),
                            "stars": repo.get("stargazers_count", 0),
                            "confidence_score": repo.get("confidence_score", 0),
                            "discovery_method": repo.get("discovery_method"),
                            "relevance_indicators": repo.get("relevance_indicators", [])
                        }
                    }
                    
                    execution_results.append(enhanced_result)
                    
                except Exception as e:
                    logger.warning(f"Failed to execute {repo['full_name']}: {e}")
                    execution_results.append({
                        "success": False,
                        "repository_metadata": {
                            "name": repo["name"],
                            "full_name": repo["full_name"]
                        },
                        "error": str(e),
                        "execution_skipped": True
                    })
            
            # Analyze execution results
            analysis = self._analyze_execution_results(execution_results)
            
            execution_data = {
                "execution_results": execution_results,
                "total_executed": len(repos_to_execute),
                "successful_executions": len([r for r in execution_results if r.get("success")]),
                "execution_strategy": strategy,
                "analysis": analysis,
                "has_runnable_code": any(r.get("analysis", {}).get("project_type") != "unknown" 
                                       for r in execution_results if r.get("success"))
            }
            
            self.log_step("Code execution complete", {
                "total_executed": len(repos_to_execute),
                "successful": execution_data["successful_executions"]
            })
            
            return self.create_result(True, execution_data)
            
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return self.create_result(False, error=str(e))
    
    def _select_repositories_for_execution(
        self, 
        repositories: List[Dict], 
        strategy: str, 
        max_repos: int
    ) -> List[Dict]:
        """Select which repositories to execute based on strategy"""
        
        if strategy == "quick":
            # Execute only high-confidence, simple repositories
            candidates = [
                repo for repo in repositories 
                if repo.get("confidence_score", 0) > 0.7 and 
                repo.get("complexity_score", 1.0) < 0.5
            ]
            return candidates[:min(max_repos, 2)]
        
        elif strategy == "thorough":
            # Execute more repositories, including complex ones
            candidates = [
                repo for repo in repositories 
                if repo.get("confidence_score", 0) > 0.5
            ]
            return candidates[:max_repos]
        
        else:  # Default
            return repositories[:max_repos]
    
    async def _execute_repository(self, repo: Dict, strategy: str) -> Dict[str, Any]:
        """Execute a single repository"""
        try:
            repo_url = repo["html_url"]
            
            # Use E2B to analyze and run the project
            result = await self.e2b_tools.analyze_and_run_project(
                repo_url=repo_url,
                auto_install=True
            )
            
            if not result.get("success"):
                return result
            
            # Enhance with additional analysis
            enhanced_result = await self._enhance_execution_result(result, repo, strategy)
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Repository execution failed for {repo.get('full_name')}: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo_url": repo.get("html_url")
            }
    
    async def _enhance_execution_result(
        self, 
        execution_result: Dict, 
        repo: Dict, 
        strategy: str
    ) -> Dict[str, Any]:
        """Enhance execution result with additional analysis"""
        try:
            analysis = execution_result.get("analysis", {})
            install_output = execution_result.get("install_output", "")
            run_output = execution_result.get("run_output", "")
            
            # Analyze the outputs for insights
            insights = await self._extract_insights(
                repo, 
                analysis, 
                install_output, 
                run_output
            )
            
            # Determine code functionality
            functionality = await self._determine_functionality(
                repo, 
                analysis, 
                run_output
            )
            
            # Extract key learnings
            learnings = self._extract_learnings(
                execution_result, 
                repo
            )
            
            enhanced_result = {
                **execution_result,
                "insights": insights,
                "functionality": functionality,
                "learnings": learnings,
                "execution_summary": self._create_execution_summary(
                    repo, 
                    analysis, 
                    insights, 
                    functionality
                )
            }
            
            return enhanced_result
            
        except Exception as e:
            logger.warning(f"Failed to enhance execution result: {e}")
            return execution_result
    
    async def _extract_insights(
        self, 
        repo: Dict, 
        analysis: Dict, 
        install_output: str, 
        run_output: str
    ) -> Dict[str, Any]:
        """Extract insights from execution"""
        insights = {
            "project_type": analysis.get("project_type", "unknown"),
            "has_dependencies": bool(analysis.get("dependencies")),
            "dependency_count": len(analysis.get("dependencies", [])),
            "installation_successful": "successfully" in install_output.lower() or "exit code: 0" in install_output,
            "execution_successful": "exit code: 0" in run_output or len(run_output.strip()) > 0,
            "has_output": bool(run_output.strip()),
            "complexity_indicators": [],
            "technology_stack": []
        }
        
        # Analyze complexity
        if insights["dependency_count"] > 10:
            insights["complexity_indicators"].append("many_dependencies")
        
        if repo.get("size", 0) > 5000:
            insights["complexity_indicators"].append("large_codebase")
        
        # Identify technology stack
        project_type = analysis.get("project_type")
        if project_type:
            insights["technology_stack"].append(project_type)
        
        dependencies = analysis.get("dependencies", [])
        for dep in dependencies[:5]:  # Top 5 dependencies
            insights["technology_stack"].append(dep)
        
        return insights
    
    async def _determine_functionality(
        self, 
        repo: Dict, 
        analysis: Dict, 
        run_output: str
    ) -> Dict[str, Any]:
        """Determine what the code actually does"""
        try:
            if not self.llm_available:
                return self._basic_functionality_analysis(repo, analysis, run_output)
            
            system_prompt = """You are an expert at analyzing code execution results to understand what a program does.
            Based on the repository information and execution output, determine the functionality."""
            
            prompt = f"""
            Analyze this code execution and determine what the program does:
            
            Repository: {repo.get('name')}
            Description: {repo.get('description', 'No description')}
            Language: {analysis.get('project_type')}
            Dependencies: {', '.join(analysis.get('dependencies', [])[:5])}
            
            Execution Output:
            {run_output[:1000]}  # Limit output for token management
            
            Return JSON with:
            1. "primary_function": What the main purpose of the code is
            2. "category": Type of application (cli_tool, web_app, library, script, game, etc.)
            3. "use_cases": List of potential use cases
            4. "notable_features": Interesting aspects discovered
            5. "complexity_level": beginner/intermediate/advanced
            
            Return only valid JSON.
            """
            
            response = await self.llm_query(prompt, system_prompt, max_tokens=400)
            
            try:
                return json.loads(response)
            except:
                return self._basic_functionality_analysis(repo, analysis, run_output)
                
        except Exception as e:
            logger.warning(f"LLM functionality analysis failed: {e}")
            return self._basic_functionality_analysis(repo, analysis, run_output)
    
    def _basic_functionality_analysis(
        self, 
        repo: Dict, 
        analysis: Dict, 
        run_output: str
    ) -> Dict[str, Any]:
        """Basic functionality analysis without LLM"""
        description = repo.get("description", "").lower()
        project_type = analysis.get("project_type", "unknown")
        
        # Determine category based on patterns
        if any(word in description for word in ['api', 'server', 'web']):
            category = 'web_app'
        elif any(word in description for word in ['cli', 'command', 'tool']):
            category = 'cli_tool'
        elif any(word in description for word in ['library', 'package', 'module']):
            category = 'library'
        elif project_type == 'python' and 'script' in description:
            category = 'script'
        else:
            category = 'application'
        
        return {
            "primary_function": repo.get("description", "Code execution and analysis"),
            "category": category,
            "use_cases": [f"Learning {project_type} development", "Code reference"],
            "notable_features": [f"Written in {project_type}"],
            "complexity_level": "intermediate"
        }
    
    def _extract_learnings(self, execution_result: Dict, repo: Dict) -> List[str]:
        """Extract key learnings from the execution"""
        learnings = []
        
        analysis = execution_result.get("analysis", {})
        project_type = analysis.get("project_type")
        
        if project_type and project_type != "unknown":
            learnings.append(f"Project uses {project_type}")
        
        dependencies = analysis.get("dependencies", [])
        if dependencies:
            learnings.append(f"Uses {len(dependencies)} dependencies including {dependencies[0] if dependencies else 'none'}")
        
        if execution_result.get("install_output"):
            learnings.append("Has automated dependency installation")
        
        if execution_result.get("run_output"):
            learnings.append("Code executes successfully")
        
        stars = repo.get("stargazers_count", 0)
        if stars > 100:
            learnings.append(f"Popular project with {stars} stars")
        
        return learnings
    
    def _create_execution_summary(
        self, 
        repo: Dict, 
        analysis: Dict, 
        insights: Dict, 
        functionality: Dict
    ) -> str:
        """Create a human-readable execution summary"""
        repo_name = repo["name"]
        project_type = analysis.get("project_type", "unknown")
        primary_function = functionality.get("primary_function", "Unknown functionality")
        category = functionality.get("category", "application")
        
        summary = f"{repo_name} is a {project_type} {category}. {primary_function}"
        
        if insights.get("execution_successful"):
            summary += " The code executed successfully"
            if insights.get("has_output"):
                summary += " and produced output"
            summary += "."
        else:
            summary += " There were issues during execution."
        
        if insights.get("dependency_count", 0) > 0:
            summary += f" It has {insights['dependency_count']} dependencies."
        
        return summary
    
    def _analyze_execution_results(self, execution_results: List[Dict]) -> Dict[str, Any]:
        """Analyze overall execution results"""
        if not execution_results:
            return {"message": "No execution results to analyze"}
        
        successful_results = [r for r in execution_results if r.get("success")]
        
        # Aggregate insights
        project_types = [r.get("insights", {}).get("project_type") for r in successful_results]
        categories = [r.get("functionality", {}).get("category") for r in successful_results]
        
        technology_stacks = []
        for result in successful_results:
            tech_stack = result.get("insights", {}).get("technology_stack", [])
            technology_stacks.extend(tech_stack)
        
        analysis = {
            "total_repositories": len(execution_results),
            "successful_executions": len(successful_results),
            "success_rate": len(successful_results) / len(execution_results) if execution_results else 0,
            "project_types_found": list(set(filter(None, project_types))),
            "categories_found": list(set(filter(None, categories))),
            "technologies_used": list(set(technology_stacks)),
            "has_runnable_code": any(r.get("insights", {}).get("execution_successful") for r in successful_results),
            "complexity_distribution": self._analyze_complexity(successful_results)
        }
        
        return analysis
    
    def _analyze_complexity(self, results: List[Dict]) -> Dict[str, int]:
        """Analyze complexity distribution of executed projects"""
        complexity_levels = [
            r.get("functionality", {}).get("complexity_level", "unknown") 
            for r in results
        ]
        
        distribution = {}
        for level in complexity_levels:
            distribution[level] = distribution.get(level, 0) + 1
        
        return distribution