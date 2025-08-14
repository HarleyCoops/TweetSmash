"""Content Synthesis Agent - Synthesizes all pipeline results into actionable content"""

import json
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ContentSynthesisAgent(BaseAgent):
    """Agent that synthesizes all pipeline results into rich, actionable content"""
    
    def __init__(self, conf: Any = None):
        super().__init__("ContentSynthesisAgent", conf)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize all pipeline results into final content
        
        Args:
            input_data: {
                "original_bookmark": TweetSmash bookmark data,
                "content_analysis": Results from ContentAnalysisAgent,
                "github_discovery": Results from GitHubDiscoveryAgent,
                "code_execution": Results from CodeExecutionAgent,
                "synthesis_style": "detailed" | "summary" | "actionable"
            }
            
        Returns:
            Synthesized content ready for storage/presentation
        """
        try:
            self.log_step("Starting content synthesis")
            
            original_bookmark = input_data.get("original_bookmark", {})
            content_analysis = input_data.get("content_analysis", {})
            github_discovery = input_data.get("github_discovery", {})
            code_execution = input_data.get("code_execution", {})
            synthesis_style = input_data.get("synthesis_style", "detailed")
            
            # Extract key information
            tweet_info = self._extract_tweet_info(original_bookmark, content_analysis)
            github_info = self._extract_github_info(github_discovery, code_execution)
            execution_insights = self._extract_execution_insights(code_execution)
            
            # Generate synthesized content
            synthesized_content = await self._generate_synthesized_content(
                tweet_info,
                github_info,
                execution_insights,
                synthesis_style
            )
            
            # Create actionable items
            actionable_items = self._generate_actionable_items(
                tweet_info,
                github_info,
                execution_insights
            )
            
            # Generate tags and metadata
            tags = self._generate_tags(content_analysis, github_discovery, code_execution)
            metadata = self._generate_metadata(input_data)
            
            synthesis_data = {
                "title": self._generate_title(tweet_info, github_info),
                "synthesized_content": synthesized_content,
                "actionable_items": actionable_items,
                "tags": tags,
                "metadata": metadata,
                "tweet_info": tweet_info,
                "github_summary": github_info,
                "execution_summary": execution_insights,
                "synthesis_style": synthesis_style,
                "content_ready_for_notion": True
            }
            
            self.log_step("Content synthesis complete", {
                "title_length": len(synthesis_data["title"]),
                "content_length": len(synthesized_content),
                "actionable_items": len(actionable_items),
                "tags": len(tags)
            })
            
            return self.create_result(True, synthesis_data)
            
        except Exception as e:
            logger.error(f"Content synthesis failed: {e}")
            return self.create_result(False, error=str(e))
    
    def _extract_tweet_info(self, bookmark: Dict, content_analysis: Dict) -> Dict[str, Any]:
        """Extract and structure tweet information"""
        tweet_details = bookmark.get("tweet_details", {})
        author_details = bookmark.get("author_details", {})
        
        return {
            "text": tweet_details.get("text", ""),
            "author_name": author_details.get("name", "Unknown"),
            "author_username": author_details.get("username", ""),
            "posted_at": tweet_details.get("posted_at"),
            "link": tweet_details.get("link"),
            "content_type": content_analysis.get("content_type", "unknown"),
            "github_relevance_score": content_analysis.get("github_relevance_score", 0),
            "code_keywords": content_analysis.get("code_keywords", []),
            "processing_priority": content_analysis.get("processing_priority", "low")
        }
    
    def _extract_github_info(self, github_discovery: Dict, code_execution: Dict) -> Dict[str, Any]:
        """Extract and summarize GitHub information"""
        discovered_repos = github_discovery.get("discovered_repositories", [])
        execution_results = code_execution.get("execution_results", [])
        
        github_summary = {
            "repositories_found": len(discovered_repos),
            "repositories_executed": len(execution_results),
            "successful_executions": code_execution.get("successful_executions", 0),
            "has_runnable_code": code_execution.get("has_runnable_code", False),
            "top_repositories": []
        }
        
        # Get top 3 repositories with their execution results
        for i, repo in enumerate(discovered_repos[:3]):
            repo_summary = {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description", ""),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "confidence_score": repo.get("confidence_score", 0),
                "discovery_method": repo.get("discovery_method", ""),
                "executed": False,
                "execution_summary": ""
            }
            
            # Find corresponding execution result
            for exec_result in execution_results:
                exec_metadata = exec_result.get("repository_metadata", {})
                if exec_metadata.get("full_name") == repo["full_name"]:
                    repo_summary["executed"] = True
                    repo_summary["execution_summary"] = exec_result.get("execution_summary", "")
                    repo_summary["functionality"] = exec_result.get("functionality", {})
                    repo_summary["insights"] = exec_result.get("insights", {})
                    break
            
            github_summary["top_repositories"].append(repo_summary)
        
        return github_summary
    
    def _extract_execution_insights(self, code_execution: Dict) -> Dict[str, Any]:
        """Extract key insights from code execution"""
        analysis = code_execution.get("analysis", {})
        execution_results = code_execution.get("execution_results", [])
        
        successful_results = [r for r in execution_results if r.get("success")]
        
        insights = {
            "total_executed": len(execution_results),
            "successful_count": len(successful_results),
            "success_rate": analysis.get("success_rate", 0),
            "technologies_discovered": analysis.get("technologies_used", []),
            "project_types": analysis.get("project_types_found", []),
            "categories": analysis.get("categories_found", []),
            "key_learnings": [],
            "notable_projects": []
        }
        
        # Extract key learnings from successful executions
        for result in successful_results:
            learnings = result.get("learnings", [])
            insights["key_learnings"].extend(learnings)
            
            # Add notable projects
            repo_metadata = result.get("repository_metadata", {})
            functionality = result.get("functionality", {})
            
            if repo_metadata.get("stars", 0) > 50 or functionality.get("complexity_level") == "advanced":
                insights["notable_projects"].append({
                    "name": repo_metadata.get("name"),
                    "description": functionality.get("primary_function", ""),
                    "category": functionality.get("category", ""),
                    "stars": repo_metadata.get("stars", 0)
                })
        
        return insights
    
    async def _generate_synthesized_content(
        self,
        tweet_info: Dict,
        github_info: Dict,
        execution_insights: Dict,
        style: str
    ) -> str:
        """Generate the main synthesized content"""
        try:
            if not self.llm_available:
                return self._generate_basic_content(tweet_info, github_info, execution_insights)
            
            system_prompt = """You are an expert at synthesizing technical content from tweets and code analysis. 
            Create comprehensive, well-structured content that combines tweet context with code execution insights."""
            
            prompt = f"""
            Create a {style} synthesis of this tweet and its associated GitHub repositories:
            
            TWEET INFORMATION:
            Author: @{tweet_info['author_username']} ({tweet_info['author_name']})
            Content: "{tweet_info['text']}"
            Type: {tweet_info['content_type']}
            Keywords: {', '.join(tweet_info['code_keywords'])}
            
            GITHUB ANALYSIS:
            Repositories found: {github_info['repositories_found']}
            Successfully executed: {github_info['successful_executions']}
            
            TOP REPOSITORIES:
            {self._format_repositories_for_llm(github_info['top_repositories'])}
            
            EXECUTION INSIGHTS:
            Technologies: {', '.join(execution_insights['technologies_discovered'])}
            Project types: {', '.join(execution_insights['project_types'])}
            Success rate: {execution_insights['success_rate']:.1%}
            
            KEY LEARNINGS:
            {chr(10).join(f"- {learning}" for learning in execution_insights['key_learnings'][:5])}
            
            Create a comprehensive synthesis that:
            1. Explains what the tweet was about
            2. Describes the discovered repositories and their functionality
            3. Highlights key technical insights from code execution
            4. Provides context on why this content is valuable
            5. Connects the tweet content to the actual code functionality
            
            Style: {style}
            Length: {"Detailed (3-4 paragraphs)" if style == "detailed" else "Summary (1-2 paragraphs)" if style == "summary" else "Actionable (bullet points and next steps)"}
            """
            
            response = await self.llm_query(prompt, system_prompt, max_tokens=600, temperature=0.7)
            return response
            
        except Exception as e:
            logger.warning(f"LLM content synthesis failed: {e}")
            return self._generate_basic_content(tweet_info, github_info, execution_insights)
    
    def _generate_basic_content(
        self,
        tweet_info: Dict,
        github_info: Dict,
        execution_insights: Dict
    ) -> str:
        """Generate basic synthesized content without LLM"""
        content_parts = []
        
        # Tweet summary
        author = tweet_info['author_name']
        content_type = tweet_info['content_type'].replace('_', ' ')
        content_parts.append(f"@{tweet_info['author_username']} ({author}) shared a {content_type} tweet about: {tweet_info['text'][:100]}...")
        
        # GitHub findings
        repos_found = github_info['repositories_found']
        if repos_found > 0:
            content_parts.append(f"Analysis discovered {repos_found} related GitHub repositories.")
            
            top_repo = github_info['top_repositories'][0] if github_info['top_repositories'] else None
            if top_repo:
                content_parts.append(f"The primary repository '{top_repo['name']}' {top_repo.get('description', '')}.")
        
        # Execution results
        if execution_insights['successful_count'] > 0:
            technologies = ', '.join(execution_insights['technologies_discovered'][:3])
            content_parts.append(f"Code execution revealed projects using {technologies}.")
        
        return ' '.join(content_parts)
    
    def _format_repositories_for_llm(self, repositories: List[Dict]) -> str:
        """Format repository information for LLM prompt"""
        formatted = []
        for repo in repositories:
            repo_info = f"- {repo['full_name']}: {repo.get('description', 'No description')}"
            if repo.get('executed'):
                repo_info += f" (Executed: {repo.get('execution_summary', 'No summary')})"
            formatted.append(repo_info)
        return '\n'.join(formatted)
    
    def _generate_actionable_items(
        self,
        tweet_info: Dict,
        github_info: Dict,
        execution_insights: Dict
    ) -> List[str]:
        """Generate actionable items from the analysis"""
        actionable_items = []
        
        # Repository-based actions
        for repo in github_info['top_repositories']:
            if repo.get('executed') and repo.get('insights', {}).get('execution_successful'):
                actionable_items.append(f"✅ Explore {repo['name']} - {repo.get('functionality', {}).get('primary_function', 'functional code')}")
            elif repo['confidence_score'] > 0.8:
                actionable_items.append(f"🔍 Investigate {repo['name']} - high-confidence discovery")
        
        # Technology learning opportunities
        technologies = execution_insights['technologies_discovered']
        for tech in technologies[:2]:
            if tech not in ['unknown', '']:
                actionable_items.append(f"📚 Learn more about {tech}")
        
        # Code pattern analysis
        if execution_insights['successful_count'] > 1:
            actionable_items.append("🔗 Compare implementation patterns across discovered repositories")
        
        # Follow-up actions
        if tweet_info['author_username'] and github_info['repositories_found'] > 0:
            actionable_items.append(f"👤 Follow @{tweet_info['author_username']} for more {tweet_info['content_type'].replace('_', ' ')} content")
        
        # Tutorial or documentation creation
        if execution_insights['key_learnings']:
            actionable_items.append("📝 Document learnings for future reference")
        
        return actionable_items[:6]  # Limit to 6 actionable items
    
    def _generate_tags(
        self,
        content_analysis: Dict,
        github_discovery: Dict,
        code_execution: Dict
    ) -> List[str]:
        """Generate tags for categorization"""
        tags = set()
        
        # Base tags
        tags.add("tweetsmash")
        tags.add("bookmark")
        
        # Content type tags
        content_type = content_analysis.get("content_type", "")
        if content_type:
            tags.add(content_type)
        
        # Technology tags
        code_keywords = content_analysis.get("code_keywords", [])
        for keyword in code_keywords[:5]:
            tags.add(keyword)
        
        # GitHub tags
        if github_discovery.get("discovered_repositories"):
            tags.add("github")
            
            for repo in github_discovery["discovered_repositories"][:3]:
                language = repo.get("language")
                if language:
                    tags.add(language.lower())
        
        # Execution tags
        analysis = code_execution.get("analysis", {})
        project_types = analysis.get("project_types_found", [])
        for project_type in project_types:
            tags.add(project_type)
        
        categories = analysis.get("categories_found", [])
        for category in categories:
            tags.add(category)
        
        # Success indicators
        if code_execution.get("has_runnable_code"):
            tags.add("executable")
        
        if analysis.get("success_rate", 0) > 0.8:
            tags.add("high_quality")
        
        # Priority tags
        priority = content_analysis.get("processing_priority", "low")
        tags.add(f"priority_{priority}")
        
        return sorted(list(tags))[:15]  # Limit to 15 tags
    
    def _generate_metadata(self, input_data: Dict) -> Dict[str, Any]:
        """Generate metadata for the synthesized content"""
        return {
            "pipeline_version": "1.0",
            "processing_timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "agents_used": ["ContentAnalysisAgent", "GitHubDiscoveryAgent", "CodeExecutionAgent", "ContentSynthesisAgent"],
            "original_bookmark_id": input_data.get("original_bookmark", {}).get("post_id"),
            "github_repositories_count": len(input_data.get("github_discovery", {}).get("discovered_repositories", [])),
            "execution_success_rate": input_data.get("code_execution", {}).get("analysis", {}).get("success_rate", 0),
            "content_analysis_score": input_data.get("content_analysis", {}).get("github_relevance_score", 0),
            "synthesis_style": input_data.get("synthesis_style", "detailed")
        }
    
    def _generate_title(self, tweet_info: Dict, github_info: Dict) -> str:
        """Generate a title for the synthesized content"""
        author = tweet_info['author_name']
        content_type = tweet_info['content_type'].replace('_', ' ').title()
        
        # Try to use the top repository name
        top_repos = github_info.get('top_repositories', [])
        if top_repos:
            repo_name = top_repos[0]['name']
            return f"{content_type} by {author}: {repo_name}"
        
        # Fallback to content keywords
        keywords = tweet_info.get('code_keywords', [])
        if keywords:
            primary_keyword = keywords[0].title()
            return f"{content_type} by {author}: {primary_keyword} Project"
        
        # Final fallback
        return f"{content_type} by {author}"