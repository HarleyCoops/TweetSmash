"""Content routing logic for processing bookmarks"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse
from utils.logger import setup_logger
from utils.config import config
import asyncio
import json
import redis
from datetime import datetime

logger = setup_logger(__name__)


class ContentRouter:
    """Routes bookmarks to appropriate processing pipelines"""
    
    def __init__(self, conf: Any = None):
        self.config = conf or config
        
        # Setup Redis for job tracking
        try:
            self.redis_client = redis.from_url(self.config.redis_url)
            self.job_tracking_enabled = True
        except Exception as e:
            logger.warning(f"Redis not available, job tracking disabled: {e}")
            self.redis_client = None
            self.job_tracking_enabled = False
        
        # Import processors (lazy import to avoid circular dependencies)
        self._github_processor = None
        self._youtube_processor = None
        self._notion_processor = None
    
    async def analyze_url(self, url: str) -> Dict[str, Any]:
        """
        Analyze a URL and determine its content type
        
        Args:
            url: URL to analyze
            
        Returns:
            Analysis results including content type and metadata
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            
            content_type = "general"
            metadata = {
                "domain": domain,
                "path": path,
                "full_url": url
            }
            
            # GitHub detection
            if 'github.com' in domain:
                content_type = "github"
                # Extract owner and repo from path
                parts = path.strip('/').split('/')
                if len(parts) >= 2:
                    metadata["owner"] = parts[0]
                    metadata["repo"] = parts[1]
                    metadata["is_repo"] = len(parts) == 2
                    metadata["is_file"] = len(parts) > 2
            
            # YouTube detection
            elif 'youtube.com' in domain or 'youtu.be' in domain:
                content_type = "youtube"
                # Extract video ID
                if 'youtu.be' in domain:
                    metadata["video_id"] = path.strip('/')
                elif 'watch' in path:
                    import re
                    match = re.search(r'[?&]v=([^&]+)', url)
                    if match:
                        metadata["video_id"] = match.group(1)
            
            # Twitter/X detection
            elif 'twitter.com' in domain or 'x.com' in domain:
                content_type = "twitter"
                # Extract tweet ID if present
                import re
                match = re.search(r'/status/(\d+)', path)
                if match:
                    metadata["tweet_id"] = match.group(1)
            
            # Article sites
            elif any(site in domain for site in ['medium.com', 'dev.to', 'hashnode.dev']):
                content_type = "article"
            
            # Academic papers
            elif 'arxiv.org' in domain:
                content_type = "paper"
                import re
                match = re.search(r'(\d+\.\d+)', path)
                if match:
                    metadata["paper_id"] = match.group(1)
            
            # Reddit
            elif 'reddit.com' in domain:
                content_type = "reddit"
            
            return {
                "success": True,
                "url": url,
                "content_type": content_type,
                "metadata": metadata,
                "processing_pipeline": self._get_pipeline_for_type(content_type)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing URL {url}: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    async def process_bookmark(
        self, 
        bookmark_id: str,
        bookmark_data: Optional[Dict] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Process a bookmark through the appropriate pipeline
        
        Args:
            bookmark_id: Bookmark ID
            bookmark_data: Optional bookmark data (if not provided, will fetch)
            force: Force reprocessing even if already processed
            
        Returns:
            Processing result
        """
        try:
            # Check if already processed
            if not force and self.job_tracking_enabled:
                existing_job = self._get_job_status(bookmark_id)
                if existing_job and existing_job.get("status") == "completed":
                    logger.info(f"Bookmark {bookmark_id} already processed")
                    return existing_job
            
            # Create job entry
            job_id = self._create_job(bookmark_id)
            
            # Get bookmark data if not provided
            if not bookmark_data:
                from tools.tweetsmash import TweetSmashTools
                tools = TweetSmashTools()
                result = await tools.get_bookmark_details(bookmark_id)
                if not result.get("success"):
                    raise ValueError(f"Failed to fetch bookmark: {result.get('error')}")
                bookmark_data = result.get("bookmark")
            
            # Extract URLs from bookmark
            urls = bookmark_data.get("extracted_urls", [])
            if not urls:
                # Try to extract from text
                text = bookmark_data.get("tweet_details", {}).get("text", "")
                urls = self._extract_urls(text)
            
            if not urls:
                self._update_job(job_id, "completed", {"message": "No URLs found"})
                return {
                    "success": True,
                    "job_id": job_id,
                    "message": "No URLs found in bookmark"
                }
            
            # Process primary URL
            primary_url = urls[0]
            url_analysis = await self.analyze_url(primary_url)
            
            if not url_analysis.get("success"):
                self._update_job(job_id, "failed", {"error": url_analysis.get("error")})
                return url_analysis
            
            content_type = url_analysis.get("content_type")
            
            # Route to appropriate processor
            if content_type == "github":
                result = await self._process_github(bookmark_data, primary_url, job_id)
            elif content_type == "youtube":
                result = await self._process_youtube(bookmark_data, primary_url, job_id)
            else:
                result = await self._process_general(bookmark_data, primary_url, job_id)
            
            # Update job status
            self._update_job(job_id, "completed", result)
            
            return {
                "success": True,
                "job_id": job_id,
                "bookmark_id": bookmark_id,
                "content_type": content_type,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error processing bookmark {bookmark_id}: {e}")
            if 'job_id' in locals():
                self._update_job(job_id, "failed", {"error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _process_github(
        self, 
        bookmark: Dict, 
        url: str, 
        job_id: str
    ) -> Dict[str, Any]:
        """Process GitHub repository"""
        try:
            self._update_job(job_id, "processing", {"stage": "github_codespace"})
            
            # Import GitHub processor
            if not self._github_processor:
                from tools.github import GitHubTools
                self._github_processor = GitHubTools()
            
            # Create codespace
            result = await self._github_processor.create_codespace(url)
            
            # Also save to Notion for reference
            await self._save_to_notion(
                title=f"GitHub: {result.get('repo_name', 'Repository')}",
                url=url,
                content=f"Codespace created: {result.get('codespace_url', 'N/A')}",
                tags=["github", "codespace", "development"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"GitHub processing failed: {e}")
            raise
    
    async def _process_youtube(
        self, 
        bookmark: Dict, 
        url: str, 
        job_id: str
    ) -> Dict[str, Any]:
        """Process YouTube video"""
        try:
            self._update_job(job_id, "processing", {"stage": "youtube_transcription"})
            
            # Import YouTube processor
            if not self._youtube_processor:
                from tools.youtube import YouTubeTools
                self._youtube_processor = YouTubeTools()
            
            # Transcribe and summarize
            result = await self._youtube_processor.transcribe_and_summarize(url)
            
            # Save to Notion
            await self._save_to_notion(
                title=result.get("title", "YouTube Video"),
                url=url,
                content=result.get("summary", ""),
                tags=["youtube", "video", "summary"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"YouTube processing failed: {e}")
            raise
    
    async def _process_general(
        self, 
        bookmark: Dict, 
        url: str, 
        job_id: str
    ) -> Dict[str, Any]:
        """Process general content"""
        try:
            self._update_job(job_id, "processing", {"stage": "notion_save"})
            
            # Extract content details
            tweet_text = bookmark.get("tweet_details", {}).get("text", "")
            author = bookmark.get("author_details", {}).get("name", "Unknown")
            
            # Save to Notion
            result = await self._save_to_notion(
                title=f"Bookmark from @{author}",
                url=url,
                content=tweet_text,
                tags=["bookmark", "general"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"General processing failed: {e}")
            raise
    
    async def _save_to_notion(
        self, 
        title: str, 
        url: str, 
        content: str, 
        tags: list
    ) -> Dict[str, Any]:
        """Save content to Notion"""
        try:
            if not self._notion_processor:
                from tools.notion import NotionTools
                self._notion_processor = NotionTools()
            
            return await self._notion_processor.save_content(
                title=title,
                url=url,
                content=content,
                tags=tags
            )
        except Exception as e:
            logger.warning(f"Failed to save to Notion: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_pipeline_for_type(self, content_type: str) -> str:
        """Get processing pipeline name for content type"""
        pipelines = {
            "github": "github_codespace",
            "youtube": "youtube_transcription",
            "twitter": "notion_save",
            "article": "notion_save",
            "paper": "notion_save",
            "reddit": "notion_save",
            "general": "notion_save"
        }
        return pipelines.get(content_type, "notion_save")
    
    def _extract_urls(self, text: str) -> list:
        """Extract URLs from text"""
        import re
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\-._~:/?#[\]@!$&\'()*+,;=.]*'
        return re.findall(url_pattern, text)
    
    def _create_job(self, bookmark_id: str) -> str:
        """Create a job tracking entry"""
        if not self.job_tracking_enabled:
            return f"job_{bookmark_id}_{datetime.utcnow().timestamp()}"
        
        import uuid
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "bookmark_id": bookmark_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        self.redis_client.setex(
            f"job:{job_id}",
            86400,  # 24 hour TTL
            json.dumps(job_data)
        )
        
        return job_id
    
    def _update_job(self, job_id: str, status: str, data: Dict = None):
        """Update job status"""
        if not self.job_tracking_enabled:
            return
        
        job_key = f"job:{job_id}"
        existing = self.redis_client.get(job_key)
        
        if existing:
            job_data = json.loads(existing)
        else:
            job_data = {"job_id": job_id}
        
        job_data.update({
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        if data:
            job_data["result"] = data
        
        self.redis_client.setex(
            job_key,
            86400,  # 24 hour TTL
            json.dumps(job_data)
        )
    
    def _get_job_status(self, bookmark_id: str) -> Optional[Dict]:
        """Get job status for a bookmark"""
        if not self.job_tracking_enabled:
            return None
        
        # Search for job by bookmark_id
        for key in self.redis_client.scan_iter("job:*"):
            job_data = json.loads(self.redis_client.get(key))
            if job_data.get("bookmark_id") == bookmark_id:
                return job_data
        
        return None
    
    async def get_job_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of processing jobs"""
        try:
            if not self.job_tracking_enabled:
                return {
                    "success": False,
                    "error": "Job tracking not available (Redis not connected)"
                }
            
            if job_id:
                # Get specific job
                job_data = self.redis_client.get(f"job:{job_id}")
                if job_data:
                    return {
                        "success": True,
                        "job": json.loads(job_data)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Job {job_id} not found"
                    }
            else:
                # Get all recent jobs
                jobs = []
                for key in self.redis_client.scan_iter("job:*"):
                    job_data = json.loads(self.redis_client.get(key))
                    jobs.append(job_data)
                
                # Sort by updated_at
                jobs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
                
                return {
                    "success": True,
                    "jobs": jobs[:20],  # Return last 20 jobs
                    "total": len(jobs)
                }
                
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {
                "success": False,
                "error": str(e)
            }