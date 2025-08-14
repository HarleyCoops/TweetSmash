"""Content Analysis Agent - Analyzes tweet content for GitHub references"""

import re
import json
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ContentAnalysisAgent(BaseAgent):
    """Agent that analyzes tweet content to identify GitHub references"""
    
    def __init__(self, conf: Any = None):
        super().__init__("ContentAnalysisAgent", conf)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze tweet content for GitHub references
        
        Args:
            input_data: {
                "bookmark": TweetSmash bookmark data,
                "tweet_text": str,
                "author_details": dict
            }
            
        Returns:
            Analysis results with potential GitHub targets
        """
        try:
            self.log_step("Starting content analysis")
            
            bookmark = input_data.get("bookmark", {})
            tweet_text = input_data.get("tweet_text") or bookmark.get("tweet_details", {}).get("text", "")
            author_details = input_data.get("author_details") or bookmark.get("author_details", {})
            
            if not tweet_text:
                return self.create_result(False, error="No tweet text provided")
            
            # Extract direct GitHub URLs
            direct_urls = self._extract_github_urls(tweet_text)
            
            # Extract GitHub usernames and repo mentions
            github_mentions = self._extract_github_mentions(tweet_text)
            
            # Analyze content type and context
            content_analysis = await self._analyze_content_type(tweet_text)
            
            # Extract code-related keywords
            code_keywords = self._extract_code_keywords(tweet_text)
            
            # Get author's potential GitHub username
            author_github = self._infer_author_github(author_details, tweet_text)
            
            # Score confidence for GitHub relevance
            github_relevance_score = self._calculate_github_relevance(
                tweet_text, direct_urls, github_mentions, code_keywords
            )
            
            analysis_data = {
                "tweet_text": tweet_text,
                "author_details": author_details,
                "direct_github_urls": direct_urls,
                "github_mentions": github_mentions,
                "content_type": content_analysis.get("type"),
                "content_context": content_analysis.get("context"),
                "code_keywords": code_keywords,
                "author_github_candidate": author_github,
                "github_relevance_score": github_relevance_score,
                "requires_github_discovery": github_relevance_score > 0.3 and len(direct_urls) == 0,
                "processing_priority": self._determine_priority(github_relevance_score, direct_urls)
            }
            
            self.log_step("Content analysis complete", {
                "github_urls": len(direct_urls),
                "mentions": len(github_mentions),
                "relevance": github_relevance_score
            })
            
            return self.create_result(True, analysis_data)
            
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            return self.create_result(False, error=str(e))
    
    def _extract_github_urls(self, text: str) -> List[str]:
        """Extract direct GitHub URLs from text"""
        github_url_patterns = [
            r'https?://github\.com/[^\s]+',
            r'https?://raw\.githubusercontent\.com/[^\s]+',
            r'github\.com/[^\s]+',
        ]
        
        urls = []
        for pattern in github_url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)
        
        # Clean and deduplicate URLs
        cleaned_urls = []
        for url in urls:
            if not url.startswith('http'):
                url = 'https://' + url
            if url not in cleaned_urls:
                cleaned_urls.append(url)
        
        return cleaned_urls
    
    def _extract_github_mentions(self, text: str) -> List[Dict[str, str]]:
        """Extract GitHub username and repository mentions"""
        mentions = []
        
        # Pattern for @username/repo format
        repo_patterns = [
            r'@([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)',
            r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:\s|$)',
            r'repo:?\s*([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)',
        ]
        
        for pattern in repo_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) == 2 and len(match[0]) > 2 and len(match[1]) > 2:
                    mentions.append({
                        "type": "repository",
                        "owner": match[0],
                        "repo": match[1],
                        "full_name": f"{match[0]}/{match[1]}"
                    })
        
        # Pattern for just usernames
        username_patterns = [
            r'@([a-zA-Z0-9_-]+)(?:\s|$)',
            r'github\.com/([a-zA-Z0-9_-]+)(?:/|$)',
        ]
        
        for pattern in username_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 2:
                    mentions.append({
                        "type": "user",
                        "username": match
                    })
        
        return mentions
    
    async def _analyze_content_type(self, text: str) -> Dict[str, str]:
        """Use LLM to analyze content type and context"""
        try:
            if not self.llm_available:
                return self._basic_content_analysis(text)
            
            system_prompt = """You are an expert at analyzing tweets about software development and GitHub projects. 
            Analyze the tweet and classify its type and context."""
            
            prompt = f"""
            Analyze this tweet and return a JSON response with:
            1. "type": The type of tweet (project_announcement, tutorial, code_sharing, discussion, showcase, problem_solving, resource_sharing, other)
            2. "context": Brief description of what the tweet is about
            3. "github_likelihood": Score 0-1 for how likely this references a GitHub project
            4. "intent": What the author is trying to communicate
            
            Tweet text: "{text}"
            
            Return only valid JSON.
            """
            
            response = await self.llm_query(prompt, system_prompt, max_tokens=300)
            
            try:
                return json.loads(response)
            except:
                return self._basic_content_analysis(text)
                
        except Exception as e:
            logger.warning(f"LLM content analysis failed: {e}")
            return self._basic_content_analysis(text)
    
    def _basic_content_analysis(self, text: str) -> Dict[str, str]:
        """Basic content analysis without LLM"""
        text_lower = text.lower()
        
        # Determine type based on keywords
        if any(word in text_lower for word in ['released', 'launched', 'announcing', 'new project']):
            content_type = 'project_announcement'
        elif any(word in text_lower for word in ['tutorial', 'how to', 'guide', 'learn']):
            content_type = 'tutorial'
        elif any(word in text_lower for word in ['code', 'snippet', 'function', 'class']):
            content_type = 'code_sharing'
        elif any(word in text_lower for word in ['built', 'created', 'made', 'check out']):
            content_type = 'showcase'
        else:
            content_type = 'other'
        
        return {
            "type": content_type,
            "context": f"Tweet appears to be about {content_type.replace('_', ' ')}",
            "github_likelihood": 0.6 if any(word in text_lower for word in ['code', 'repo', 'project', 'github']) else 0.2
        }
    
    def _extract_code_keywords(self, text: str) -> List[str]:
        """Extract programming and code-related keywords"""
        code_keywords = [
            # Languages
            'python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'go', 'rust', 'php', 'ruby',
            'swift', 'kotlin', 'scala', 'clojure', 'haskell', 'elixir', 'dart', 'r', 'matlab',
            
            # Frameworks/Libraries
            'react', 'vue', 'angular', 'django', 'flask', 'express', 'fastapi', 'spring', 'rails',
            'pytorch', 'tensorflow', 'pandas', 'numpy', 'opencv', 'scikit-learn',
            
            # Technologies
            'api', 'database', 'sql', 'nosql', 'mongodb', 'postgresql', 'redis', 'docker', 'kubernetes',
            'aws', 'azure', 'gcp', 'serverless', 'microservices', 'graphql', 'rest',
            
            # Concepts
            'algorithm', 'data structure', 'machine learning', 'ai', 'blockchain', 'web3', 'nft',
            'frontend', 'backend', 'fullstack', 'devops', 'ci/cd', 'testing', 'deployment'
        ]
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in code_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _infer_author_github(self, author_details: Dict, tweet_text: str) -> str:
        """Infer author's GitHub username"""
        username = author_details.get("username", "")
        name = author_details.get("name", "")
        
        # Check if username looks like a GitHub username
        if re.match(r'^[a-zA-Z0-9_-]+$', username) and len(username) > 2:
            return username
        
        # Look for "my repo" or "I built" patterns
        my_repo_patterns = [
            r'my\s+(?:repo|project|code)',
            r'I\s+(?:built|created|made)',
            r'check\s+out\s+my'
        ]
        
        for pattern in my_repo_patterns:
            if re.search(pattern, tweet_text, re.IGNORECASE):
                return username
        
        return ""
    
    def _calculate_github_relevance(
        self, 
        text: str, 
        direct_urls: List[str], 
        mentions: List[Dict], 
        keywords: List[str]
    ) -> float:
        """Calculate relevance score for GitHub content"""
        score = 0.0
        text_lower = text.lower()
        
        # Direct GitHub URLs are highly relevant
        if direct_urls:
            score += 0.8
        
        # GitHub mentions
        if mentions:
            score += 0.6
        
        # Code keywords
        score += min(len(keywords) * 0.1, 0.4)
        
        # Explicit GitHub mentions
        if 'github' in text_lower:
            score += 0.3
        
        # Code-related terms
        code_terms = ['repo', 'repository', 'code', 'project', 'open source']
        for term in code_terms:
            if term in text_lower:
                score += 0.1
        
        # Project announcement indicators
        announcement_terms = ['released', 'launched', 'built', 'created', 'check out']
        for term in announcement_terms:
            if term in text_lower:
                score += 0.15
        
        return min(score, 1.0)
    
    def _determine_priority(self, relevance_score: float, direct_urls: List[str]) -> str:
        """Determine processing priority"""
        if direct_urls:
            return "high"
        elif relevance_score > 0.7:
            return "high"
        elif relevance_score > 0.4:
            return "medium"
        else:
            return "low"