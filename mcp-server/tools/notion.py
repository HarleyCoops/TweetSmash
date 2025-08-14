"""Notion MCP tools implementation"""

from typing import Dict, Any, List, Optional
from notion_client import Client
from utils.logger import setup_logger
from utils.config import config
from datetime import datetime

logger = setup_logger(__name__)


class NotionTools:
    """MCP tools for Notion integration"""
    
    def __init__(self, conf: Any = None):
        self.config = conf or config
        self.notion_client = None
        
        if self.config.notion_token:
            self.notion_client = Client(auth=self.config.notion_token)
        else:
            logger.warning("Notion token not configured")
    
    async def save_content(
        self,
        title: str,
        url: str,
        content: str = "",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Save content to Notion database
        
        Args:
            title: Content title
            url: Content URL
            content: Content body or summary
            tags: Tags for categorization
            metadata: Additional metadata
            
        Returns:
            Save result
        """
        try:
            if not self.notion_client:
                return {
                    "success": False,
                    "error": "Notion token not configured. Please add NOTION_TOKEN to .env",
                    "fallback": self._create_fallback_content(title, url, content, tags)
                }
            
            if not self.config.notion_database_id:
                return {
                    "success": False,
                    "error": "Notion database ID not configured. Please add NOTION_DATABASE_ID to .env",
                    "fallback": self._create_fallback_content(title, url, content, tags)
                }
            
            # Prepare page properties
            properties = {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": title[:100]  # Notion title limit
                            }
                        }
                    ]
                },
                "URL": {
                    "url": url
                },
                "Created": {
                    "date": {
                        "start": datetime.utcnow().isoformat()
                    }
                }
            }
            
            # Add tags if the database has a Tags property
            if tags:
                properties["Tags"] = {
                    "multi_select": [{"name": tag} for tag in tags[:10]]  # Limit tags
                }
            
            # Add source property if available
            properties["Source"] = {
                "select": {
                    "name": "TweetSmash"
                }
            }
            
            # Prepare page content blocks
            children = []
            
            # Add URL as bookmark block
            children.append({
                "object": "block",
                "type": "bookmark",
                "bookmark": {
                    "url": url
                }
            })
            
            # Add content as paragraph blocks
            if content:
                # Split content into chunks (Notion has a 2000 char limit per block)
                content_chunks = self._split_content(content, 2000)
                for chunk in content_chunks[:10]:  # Limit to 10 blocks
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": chunk
                                    }
                                }
                            ]
                        }
                    })
            
            # Add metadata as code block if provided
            if metadata:
                import json
                metadata_str = json.dumps(metadata, indent=2)[:2000]
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": metadata_str
                                }
                            }
                        ],
                        "language": "json"
                    }
                })
            
            # Create the page
            response = self.notion_client.pages.create(
                parent={"database_id": self.config.notion_database_id},
                properties=properties,
                children=children
            )
            
            logger.info(f"Created Notion page: {response['id']}")
            
            return {
                "success": True,
                "page_id": response["id"],
                "page_url": response["url"],
                "title": title,
                "tags": tags
            }
            
        except Exception as e:
            logger.error(f"Error saving to Notion: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": self._create_fallback_content(title, url, content, tags)
            }
    
    async def search_content(
        self,
        query: str,
        filter_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search content in Notion database
        
        Args:
            query: Search query
            filter_type: Filter by content type
            
        Returns:
            Search results
        """
        try:
            if not self.notion_client:
                return {
                    "success": False,
                    "error": "Notion token not configured"
                }
            
            # Build filter
            filter_obj = None
            if filter_type:
                filter_obj = {
                    "property": "Tags",
                    "multi_select": {
                        "contains": filter_type
                    }
                }
            
            # Search pages
            response = self.notion_client.databases.query(
                database_id=self.config.notion_database_id,
                filter=filter_obj,
                page_size=20
            )
            
            results = []
            for page in response["results"]:
                try:
                    # Extract properties
                    title = ""
                    if "Name" in page["properties"]:
                        title_prop = page["properties"]["Name"]
                        if title_prop["type"] == "title" and title_prop["title"]:
                            title = title_prop["title"][0]["text"]["content"]
                    
                    url = ""
                    if "URL" in page["properties"]:
                        url_prop = page["properties"]["URL"]
                        if url_prop["type"] == "url" and url_prop["url"]:
                            url = url_prop["url"]
                    
                    tags = []
                    if "Tags" in page["properties"]:
                        tags_prop = page["properties"]["Tags"]
                        if tags_prop["type"] == "multi_select":
                            tags = [tag["name"] for tag in tags_prop["multi_select"]]
                    
                    results.append({
                        "page_id": page["id"],
                        "title": title,
                        "url": url,
                        "tags": tags,
                        "created_time": page["created_time"],
                        "last_edited_time": page["last_edited_time"]
                    })
                except Exception as e:
                    logger.warning(f"Error parsing page: {e}")
                    continue
            
            return {
                "success": True,
                "query": query,
                "count": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error searching Notion: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_database(
        self,
        title: str = "TweetSmash Bookmarks"
    ) -> Dict[str, Any]:
        """
        Create a new Notion database for bookmarks
        
        Args:
            title: Database title
            
        Returns:
            Database creation result
        """
        try:
            if not self.notion_client:
                return {
                    "success": False,
                    "error": "Notion token not configured"
                }
            
            # Get the first page as parent (you might want to specify a specific page)
            search_response = self.notion_client.search(
                filter={"property": "object", "value": "page"},
                page_size=1
            )
            
            if not search_response["results"]:
                return {
                    "success": False,
                    "error": "No parent page found. Please create a page in Notion first."
                }
            
            parent_page_id = search_response["results"][0]["id"]
            
            # Create database
            database = self.notion_client.databases.create(
                parent={"page_id": parent_page_id},
                title=[
                    {
                        "type": "text",
                        "text": {
                            "content": title
                        }
                    }
                ],
                properties={
                    "Name": {
                        "title": {}
                    },
                    "URL": {
                        "url": {}
                    },
                    "Tags": {
                        "multi_select": {
                            "options": [
                                {"name": "github", "color": "green"},
                                {"name": "youtube", "color": "red"},
                                {"name": "article", "color": "blue"},
                                {"name": "twitter", "color": "purple"},
                                {"name": "general", "color": "gray"},
                                {"name": "bookmark", "color": "yellow"},
                                {"name": "codespace", "color": "orange"},
                                {"name": "summary", "color": "pink"}
                            ]
                        }
                    },
                    "Source": {
                        "select": {
                            "options": [
                                {"name": "TweetSmash", "color": "blue"},
                                {"name": "Manual", "color": "gray"}
                            ]
                        }
                    },
                    "Created": {
                        "date": {}
                    },
                    "Status": {
                        "select": {
                            "options": [
                                {"name": "New", "color": "gray"},
                                {"name": "Processing", "color": "yellow"},
                                {"name": "Processed", "color": "green"},
                                {"name": "Failed", "color": "red"}
                            ]
                        }
                    }
                }
            )
            
            logger.info(f"Created Notion database: {database['id']}")
            
            return {
                "success": True,
                "database_id": database["id"],
                "database_url": database["url"],
                "title": title,
                "message": f"Database created! Add this ID to your .env: NOTION_DATABASE_ID={database['id']}"
            }
            
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _split_content(self, content: str, max_length: int) -> List[str]:
        """
        Split content into chunks for Notion blocks
        
        Args:
            content: Content to split
            max_length: Maximum length per chunk
            
        Returns:
            List of content chunks
        """
        chunks = []
        current_chunk = ""
        
        for line in content.split('\n'):
            if len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _create_fallback_content(
        self,
        title: str,
        url: str,
        content: str,
        tags: List[str]
    ) -> Dict[str, Any]:
        """
        Create fallback content when Notion is not available
        
        Args:
            title: Content title
            url: Content URL
            content: Content body
            tags: Content tags
            
        Returns:
            Fallback content structure
        """
        return {
            "title": title,
            "url": url,
            "content": content,
            "tags": tags,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Notion not configured. Content saved locally."
        }