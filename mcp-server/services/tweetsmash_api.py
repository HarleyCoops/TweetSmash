"""TweetSmash API client service"""

import httpx
from typing import Dict, List, Optional, Any
from utils.logger import setup_logger
from utils.config import config

logger = setup_logger(__name__)


class TweetSmashAPI:
    """Client for TweetSmash API interactions"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or config.tweetsmash_api_key
        self.base_url = base_url or config.tweetsmash_api_url
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def fetch_bookmarks(
        self, 
        limit: int = 10, 
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch bookmarks from TweetSmash API
        
        Args:
            limit: Number of bookmarks to fetch (max 100)
            cursor: Pagination cursor for next page
            
        Returns:
            Dict containing bookmarks and pagination info
        """
        try:
            params = {"limit": min(limit, 100)}
            if cursor:
                params["cursor"] = cursor
            
            logger.info(f"Fetching bookmarks with params: {params}")
            response = await self.client.get("/bookmarks", params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('bookmarks', []))} bookmarks")
            
            return data
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Invalid API key")
                raise ValueError("Invalid TweetSmash API key")
            elif e.response.status_code == 429:
                logger.warning("Rate limit exceeded")
                raise ValueError("TweetSmash API rate limit exceeded")
            else:
                logger.error(f"HTTP error: {e}")
                raise
        except Exception as e:
            logger.error(f"Error fetching bookmarks: {e}")
            raise
    
    async def get_bookmark(self, bookmark_id: str) -> Dict[str, Any]:
        """
        Get a specific bookmark by ID
        
        Args:
            bookmark_id: The bookmark ID
            
        Returns:
            Bookmark data
        """
        try:
            logger.info(f"Fetching bookmark: {bookmark_id}")
            response = await self.client.get(f"/bookmarks/{bookmark_id}")
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Bookmark not found: {bookmark_id}")
                raise ValueError(f"Bookmark {bookmark_id} not found")
            else:
                logger.error(f"HTTP error: {e}")
                raise
        except Exception as e:
            logger.error(f"Error fetching bookmark {bookmark_id}: {e}")
            raise
    
    async def setup_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """
        Configure webhook for real-time bookmark notifications
        
        Args:
            webhook_url: URL to receive webhook notifications
            
        Returns:
            Webhook configuration response
        """
        try:
            logger.info(f"Setting up webhook: {webhook_url}")
            
            payload = {
                "url": webhook_url,
                "events": ["bookmark.created", "bookmark.updated"],
                "active": True
            }
            
            response = await self.client.post("/webhooks", json=payload)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Webhook configured: {data.get('id')}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
            raise
    
    async def verify_webhook(self, signature: str, payload: str) -> bool:
        """
        Verify webhook signature for security
        
        Args:
            signature: Webhook signature from headers
            payload: Raw webhook payload
            
        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib
        
        if not config.tweetsmash_webhook_secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True
        
        expected_signature = hmac.new(
            config.tweetsmash_webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()