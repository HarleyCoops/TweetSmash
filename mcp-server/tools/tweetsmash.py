"""TweetSmash MCP tools implementation"""

from typing import Dict, Any, Optional
from services.tweetsmash_api import TweetSmashAPI
from utils.logger import setup_logger
from utils.config import config
import redis
import json

logger = setup_logger(__name__)


class TweetSmashTools:
    """MCP tools for TweetSmash integration"""
    
    def __init__(self, conf: Any = None):
        self.config = conf or config
        self.api = TweetSmashAPI()
        
        # Setup Redis for caching
        try:
            self.redis_client = redis.from_url(self.config.redis_url)
            self.cache_enabled = True
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {e}")
            self.redis_client = None
            self.cache_enabled = False
    
    async def fetch_bookmarks(
        self, 
        limit: int = 10, 
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch recent bookmarks from TweetSmash
        
        Args:
            limit: Number of bookmarks to fetch
            cursor: Pagination cursor
            
        Returns:
            Dictionary with bookmarks and metadata
        """
        try:
            # Check cache first
            cache_key = f"bookmarks:{limit}:{cursor or 'none'}"
            if self.cache_enabled:
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info("Returning cached bookmarks")
                    return json.loads(cached)
            
            # Fetch from API
            result = await self.api.fetch_bookmarks(limit, cursor)
            
            # Process bookmarks to extract URLs
            bookmarks = result.get("bookmarks", [])
            for bookmark in bookmarks:
                bookmark["extracted_urls"] = self._extract_urls(
                    bookmark.get("tweet_details", {}).get("text", "")
                )
            
            # Cache result (5 minute TTL)
            if self.cache_enabled:
                self.redis_client.setex(
                    cache_key, 
                    300,  # 5 minutes
                    json.dumps(result)
                )
            
            return {
                "success": True,
                "bookmarks": bookmarks,
                "count": len(bookmarks),
                "next_cursor": result.get("next_cursor"),
                "has_more": result.get("has_more", False)
            }
            
        except Exception as e:
            logger.error(f"Error fetching bookmarks: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_bookmark_details(self, bookmark_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific bookmark
        
        Args:
            bookmark_id: The bookmark ID
            
        Returns:
            Bookmark details
        """
        try:
            bookmark = await self.api.get_bookmark(bookmark_id)
            
            # Extract URLs and analyze content type
            urls = self._extract_urls(
                bookmark.get("tweet_details", {}).get("text", "")
            )
            
            bookmark["extracted_urls"] = urls
            bookmark["content_types"] = [
                self._identify_content_type(url) for url in urls
            ]
            
            return {
                "success": True,
                "bookmark": bookmark
            }
            
        except Exception as e:
            logger.error(f"Error getting bookmark {bookmark_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def setup_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """
        Configure webhook for real-time bookmark notifications
        
        Args:
            webhook_url: URL to receive notifications
            
        Returns:
            Webhook configuration status
        """
        try:
            result = await self.api.setup_webhook(webhook_url)
            
            return {
                "success": True,
                "webhook_id": result.get("id"),
                "webhook_url": webhook_url,
                "active": result.get("active", True)
            }
            
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_urls(self, text: str) -> list:
        """Extract URLs from tweet text"""
        import re
        
        # Regex pattern for URLs
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\-._~:/?#[\]@!$&\'()*+,;=.]*'
        urls = re.findall(url_pattern, text)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _identify_content_type(self, url: str) -> str:
        """Identify content type from URL"""
        from urllib.parse import urlparse
        
        domain = urlparse(url).netloc.lower()
        
        if 'github.com' in domain:
            return 'github'
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        elif 'twitter.com' in domain or 'x.com' in domain:
            return 'twitter'
        elif 'medium.com' in domain:
            return 'article'
        elif 'arxiv.org' in domain:
            return 'paper'
        elif 'reddit.com' in domain:
            return 'reddit'
        else:
            return 'general'
    
    async def mark_processed(self, bookmark_id: str, status: str) -> Dict[str, Any]:
        """
        Mark a bookmark as processed in cache
        
        Args:
            bookmark_id: The bookmark ID
            status: Processing status
            
        Returns:
            Status update result
        """
        try:
            if self.cache_enabled:
                key = f"processed:{bookmark_id}"
                value = json.dumps({
                    "status": status,
                    "timestamp": __import__('datetime').datetime.utcnow().isoformat()
                })
                self.redis_client.setex(key, 86400, value)  # 24 hour TTL
            
            return {
                "success": True,
                "bookmark_id": bookmark_id,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Error marking bookmark as processed: {e}")
            return {
                "success": False,
                "error": str(e)
            }