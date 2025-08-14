"""GitHub Discovery Agent - Discovers and validates GitHub repositories from tweet references"""

import httpx
import json
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent
from utils.logger import setup_logger

logger = setup_logger(__name__)


class GitHubDiscoveryAgent(BaseAgent):
    """Agent that discovers GitHub repositories from content analysis"""
    
    def __init__(self, conf: Any = None):
        super().__init__("GitHubDiscoveryAgent", conf)
        self.github_client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TweetSmash-Bot/1.0"
            },
            timeout=30.0
        )
        
        # Add GitHub token if available for higher rate limits
        if hasattr(self.config, 'github_token') and self.config.github_token:
            self.github_client.headers["Authorization"] = f"token {self.config.github_token}"
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Discover GitHub repositories from content analysis
        
        Args:
            input_data: {
                "content_analysis": Results from ContentAnalysisAgent,
                "discovery_strategy": "aggressive" | "conservative"
            }
            
        Returns:
            Discovered repositories with validation
        """
        try:
            self.log_step("Starting GitHub discovery")
            
            content_analysis = input_data.get("content_analysis", {})
            strategy = input_data.get("discovery_strategy", "aggressive")
            
            discovered_repos = []
            
            # Process direct GitHub URLs first
            direct_urls = content_analysis.get("direct_github_urls", [])
            for url in direct_urls:
                repo_info = await self._validate_github_url(url)
                if repo_info:
                    discovered_repos.append(repo_info)
            
            # Search for mentioned repositories
            github_mentions = content_analysis.get("github_mentions", [])
            for mention in github_mentions:
                if mention["type"] == "repository":
                    repo_info = await self._validate_repository(
                        mention["owner"], 
                        mention["repo"]
                    )
                    if repo_info:
                        discovered_repos.append(repo_info)
                elif mention["type"] == "user":
                    user_repos = await self._discover_user_repositories(
                        mention["username"],
                        content_analysis,
                        strategy
                    )
                    discovered_repos.extend(user_repos)
            
            # Try to discover author's repositories
            author_github = content_analysis.get("author_github_candidate")
            if author_github and not any(r["owner"]["login"] == author_github for r in discovered_repos):
                author_repos = await self._discover_author_repositories(
                    author_github,
                    content_analysis,
                    strategy
                )
                discovered_repos.extend(author_repos)
            
            # Use LLM for intelligent discovery if no repos found
            if not discovered_repos and strategy == "aggressive":
                llm_discovered = await self._llm_discovery(content_analysis)
                for repo_candidate in llm_discovered:
                    repo_info = await self._validate_repository(
                        repo_candidate["owner"],
                        repo_candidate["repo"]
                    )
                    if repo_info:
                        discovered_repos.append(repo_info)
            
            # Rank repositories by relevance
            ranked_repos = self._rank_repositories(discovered_repos, content_analysis)
            
            discovery_data = {
                "discovered_repositories": ranked_repos,
                "total_found": len(ranked_repos),
                "discovery_strategy": strategy,
                "direct_urls_processed": len(direct_urls),
                "mentions_processed": len(github_mentions),
                "has_high_confidence_repos": any(r["confidence_score"] > 0.8 for r in ranked_repos)
            }
            
            self.log_step("GitHub discovery complete", {
                "repos_found": len(ranked_repos),
                "strategy": strategy
            })
            
            return self.create_result(True, discovery_data)
            
        except Exception as e:
            logger.error(f"GitHub discovery failed: {e}")
            return self.create_result(False, error=str(e))
    
    async def _validate_github_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Validate and get info for a GitHub URL"""
        try:
            # Parse repository from URL
            import re
            match = re.search(r'github\.com/([^/]+)/([^/\s?#]+)', url)
            if not match:
                return None
            
            owner, repo = match.groups()
            repo = repo.rstrip('.git')
            
            return await self._validate_repository(owner, repo)
            
        except Exception as e:
            logger.warning(f"Failed to validate GitHub URL {url}: {e}")
            return None
    
    async def _validate_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Validate a repository exists and get its metadata"""
        try:
            response = await self.github_client.get(f"/repos/{owner}/{repo}")
            
            if response.status_code == 200:
                repo_data = response.json()
                
                # Enrich with additional data
                enriched_data = {
                    **repo_data,
                    "confidence_score": 0.9,  # High confidence for direct validation
                    "discovery_method": "direct_validation",
                    "last_activity": repo_data.get("pushed_at"),
                    "is_active": self._is_repository_active(repo_data),
                    "complexity_score": self._calculate_complexity(repo_data),
                    "relevance_indicators": self._extract_relevance_indicators(repo_data)
                }
                
                return enriched_data
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to validate repository {owner}/{repo}: {e}")
            return None
    
    async def _discover_user_repositories(
        self, 
        username: str, 
        content_analysis: Dict, 
        strategy: str
    ) -> List[Dict[str, Any]]:
        """Discover repositories for a specific user"""
        try:
            # Get user's repositories
            response = await self.github_client.get(
                f"/users/{username}/repos",
                params={
                    "sort": "updated",
                    "per_page": 20 if strategy == "aggressive" else 5
                }
            )
            
            if response.status_code != 200:
                return []
            
            repos = response.json()
            relevant_repos = []
            
            for repo in repos:
                relevance_score = self._calculate_repository_relevance(repo, content_analysis)
                
                if relevance_score > 0.3:  # Threshold for relevance
                    enriched_repo = {
                        **repo,
                        "confidence_score": relevance_score,
                        "discovery_method": "user_repository_search",
                        "is_active": self._is_repository_active(repo),
                        "complexity_score": self._calculate_complexity(repo),
                        "relevance_indicators": self._extract_relevance_indicators(repo)
                    }
                    relevant_repos.append(enriched_repo)
            
            # Sort by relevance and return top results
            relevant_repos.sort(key=lambda x: x["confidence_score"], reverse=True)
            return relevant_repos[:5]  # Limit to top 5
            
        except Exception as e:
            logger.warning(f"Failed to discover repositories for user {username}: {e}")
            return []
    
    async def _discover_author_repositories(
        self, 
        author_github: str, 
        content_analysis: Dict, 
        strategy: str
    ) -> List[Dict[str, Any]]:
        """Discover repositories that the tweet author might be referring to"""
        try:
            # Look for recent repositories that match content
            recent_repos = await self._discover_user_repositories(
                author_github, 
                content_analysis, 
                strategy
            )
            
            # Filter for repos that might be "my project" references
            my_project_indicators = [
                'built', 'created', 'made', 'my', 'new', 'latest', 'just', 'working on'
            ]
            
            tweet_text = content_analysis.get("tweet_text", "").lower()
            has_personal_reference = any(indicator in tweet_text for indicator in my_project_indicators)
            
            if has_personal_reference:
                # Boost confidence for recent repositories
                for repo in recent_repos:
                    if self._is_recent_repository(repo):
                        repo["confidence_score"] = min(repo["confidence_score"] + 0.3, 1.0)
                        repo["discovery_method"] = "author_personal_project"
            
            return recent_repos
            
        except Exception as e:
            logger.warning(f"Failed to discover author repositories: {e}")
            return []
    
    async def _llm_discovery(self, content_analysis: Dict) -> List[Dict[str, str]]:
        """Use LLM to infer potential GitHub repositories"""
        try:
            if not self.llm_available:
                return []
            
            tweet_text = content_analysis.get("tweet_text", "")
            code_keywords = content_analysis.get("code_keywords", [])
            content_type = content_analysis.get("content_type", "")
            
            system_prompt = """You are an expert at inferring GitHub repositories from tweets. 
            Based on the tweet content, suggest potential GitHub repositories that might be relevant."""
            
            prompt = f"""
            Analyze this tweet and suggest up to 3 potential GitHub repositories that might be referenced:
            
            Tweet: "{tweet_text}"
            Content type: {content_type}
            Keywords: {', '.join(code_keywords)}
            
            For each suggestion, provide:
            1. owner: GitHub username (your best guess)
            2. repo: Repository name (based on project/tool mentioned)
            3. reasoning: Why you think this repository might exist
            
            Return as JSON array of objects with owner, repo, and reasoning fields.
            Only suggest repositories that seem likely to exist based on the tweet content.
            """
            
            response = await self.llm_query(prompt, system_prompt, max_tokens=500)
            
            try:
                suggestions = json.loads(response)
                return suggestions if isinstance(suggestions, list) else []
            except:
                return []
                
        except Exception as e:
            logger.warning(f"LLM discovery failed: {e}")
            return []
    
    def _calculate_repository_relevance(self, repo: Dict, content_analysis: Dict) -> float:
        """Calculate how relevant a repository is to the tweet content"""
        score = 0.0
        
        tweet_text = content_analysis.get("tweet_text", "").lower()
        code_keywords = content_analysis.get("code_keywords", [])
        
        # Check repository name similarity
        repo_name = repo.get("name", "").lower()
        if any(keyword in repo_name for keyword in code_keywords):
            score += 0.3
        
        # Check description similarity
        description = repo.get("description", "").lower()
        if description:
            keyword_matches = sum(1 for keyword in code_keywords if keyword in description)
            score += min(keyword_matches * 0.1, 0.4)
        
        # Check language match
        repo_language = repo.get("language", "").lower()
        if repo_language in code_keywords:
            score += 0.2
        
        # Recent activity bonus
        if self._is_repository_active(repo):
            score += 0.1
        
        # Size and popularity indicators
        stars = repo.get("stargazers_count", 0)
        if stars > 10:
            score += min(stars / 1000, 0.2)
        
        return min(score, 1.0)
    
    def _is_repository_active(self, repo: Dict) -> bool:
        """Check if repository is recently active"""
        import datetime
        
        pushed_at = repo.get("pushed_at")
        if not pushed_at:
            return False
        
        try:
            pushed_date = datetime.datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            days_since_push = (now - pushed_date).days
            
            return days_since_push < 180  # Active if pushed in last 6 months
        except:
            return False
    
    def _is_recent_repository(self, repo: Dict) -> bool:
        """Check if repository was created recently"""
        import datetime
        
        created_at = repo.get("created_at")
        if not created_at:
            return False
        
        try:
            created_date = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            days_since_creation = (now - created_date).days
            
            return days_since_creation < 30  # Recent if created in last month
        except:
            return False
    
    def _calculate_complexity(self, repo: Dict) -> float:
        """Calculate repository complexity score"""
        score = 0.0
        
        # Size indicators
        size = repo.get("size", 0)
        score += min(size / 10000, 0.3)  # Larger repos are more complex
        
        # Language diversity (if available)
        if repo.get("language"):
            score += 0.2
        
        # Activity indicators
        forks = repo.get("forks_count", 0)
        score += min(forks / 100, 0.2)
        
        # Has documentation
        if repo.get("has_wiki") or "readme" in repo.get("description", "").lower():
            score += 0.1
        
        return min(score, 1.0)
    
    def _extract_relevance_indicators(self, repo: Dict) -> List[str]:
        """Extract indicators of why this repo is relevant"""
        indicators = []
        
        if self._is_repository_active(repo):
            indicators.append("recently_active")
        
        if repo.get("stargazers_count", 0) > 100:
            indicators.append("popular")
        
        if repo.get("language"):
            indicators.append(f"language_{repo['language'].lower()}")
        
        if repo.get("has_issues"):
            indicators.append("has_issues")
        
        if repo.get("description"):
            indicators.append("documented")
        
        return indicators
    
    def _rank_repositories(
        self, 
        repositories: List[Dict], 
        content_analysis: Dict
    ) -> List[Dict[str, Any]]:
        """Rank repositories by overall relevance and confidence"""
        # Sort by confidence score and other factors
        def ranking_score(repo):
            confidence = repo.get("confidence_score", 0)
            stars = min(repo.get("stargazers_count", 0) / 1000, 0.2)
            activity_bonus = 0.1 if repo.get("is_active") else 0
            
            return confidence + stars + activity_bonus
        
        repositories.sort(key=ranking_score, reverse=True)
        
        # Add ranking metadata
        for i, repo in enumerate(repositories):
            repo["rank"] = i + 1
            repo["ranking_score"] = ranking_score(repo)
        
        return repositories
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.github_client.aclose()