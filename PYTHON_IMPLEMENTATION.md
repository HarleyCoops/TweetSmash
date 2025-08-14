# TweetSmash Python Implementation Guide

## Why Python?

Python is ideal for this project because:
- **MCP SDK**: Native Python support with `mcp` and `fastmcp` libraries
- **API Integration**: Excellent libraries for GitHub, YouTube, Notion APIs
- **AI/ML Tools**: Direct access to OpenAI, Whisper, and other ML services
- **n8n Compatibility**: Easy webhook integration with FastAPI
- **Docker Friendly**: Simple containerization with Python

## Project Structure (Python-based)

```
TweetSmash/
├── mcp-server/
│   ├── server.py              # Main MCP server entry point
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tweetsmash.py     # TweetSmash API integration
│   │   ├── github.py          # GitHub Codespace creation
│   │   ├── youtube.py         # YouTube transcription/summary
│   │   └── notion.py          # Notion database integration
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── router.py          # Content routing logic
│   │   └── queue.py           # Celery task queue
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tweetsmash_api.py # TweetSmash API client
│   │   ├── github_api.py     # GitHub API client
│   │   ├── youtube_api.py    # YouTube processing
│   │   └── notion_api.py     # Notion API client
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration management
│   │   ├── logger.py          # Logging setup
│   │   └── cache.py           # Redis caching
│   └── webhook_server.py      # FastAPI webhook receiver
├── tests/
│   ├── test_tools.py
│   ├── test_processors.py
│   └── test_integration.py
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile.mcp
├── n8n-workflows/
│   └── *.json                 # n8n workflow exports
├── scripts/
│   ├── setup.py               # Setup script
│   └── test_api.py           # API testing utility
├── .env.example
├── requirements.txt           # Python dependencies
├── pyproject.toml            # Python project config
└── README.md
```

## Core Components

### 1. MCP Server (Python)
The main MCP server uses the Python MCP SDK to expose tools to AI assistants.

**Key Features:**
- Async/await for efficient I/O operations
- Tool registration and handling
- Error handling and logging
- Caching with Redis

### 2. FastAPI Webhook Server
Separate webhook endpoint for receiving TweetSmash notifications.

```python
# webhook_server.py
from fastapi import FastAPI, BackgroundTasks
from celery import Celery

app = FastAPI()
celery_app = Celery('tasks', broker='redis://localhost:6379')

@app.post("/webhook/tweetsmash")
async def receive_bookmark(bookmark: dict, background_tasks: BackgroundTasks):
    # Queue for processing
    background_tasks.add_task(process_bookmark_task, bookmark)
    return {"status": "queued"}
```

### 3. Celery Task Queue
Handles async processing of bookmarks to avoid blocking.

```python
# processors/queue.py
from celery import Celery

app = Celery('tweetsmash', broker='redis://localhost:6379')

@app.task
def process_bookmark_task(bookmark_data):
    router = ContentRouter()
    return router.process(bookmark_data)
```

### 4. Service Clients

**TweetSmash API Client:**
```python
# services/tweetsmash_api.py
import httpx

class TweetSmashAPI:
    def __init__(self, api_key: str):
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def fetch_bookmarks(self, limit=10, cursor=None):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        response = await self.client.get(
            "https://api.tweetsmash.com/v1/bookmarks",
            params=params
        )
        return response.json()
```

**GitHub Integration:**
```python
# services/github_api.py
from github import Github

class GitHubService:
    def __init__(self, token: str):
        self.github = Github(token)
    
    async def create_codespace(self, repo_url: str):
        # Parse repo URL
        # Create codespace via API
        pass
```

**YouTube Processing:**
```python
# services/youtube_api.py
import openai
from yt_dlp import YoutubeDL

class YouTubeService:
    async def transcribe_video(self, url: str):
        # Download audio with yt-dlp
        # Transcribe with Whisper API
        # Summarize with GPT-4
        pass
```

### 5. Content Router
```python
# processors/router.py
from urllib.parse import urlparse

class ContentRouter:
    def analyze_url(self, url: str):
        domain = urlparse(url).netloc
        
        if 'github.com' in domain:
            return 'github'
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        else:
            return 'general'
    
    async def process(self, bookmark):
        url_type = self.analyze_url(bookmark['url'])
        
        if url_type == 'github':
            return await self.process_github(bookmark)
        elif url_type == 'youtube':
            return await self.process_youtube(bookmark)
        else:
            return await self.process_general(bookmark)
```

## Docker Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  
  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
    depends_on:
      - postgres
  
  mcp-server:
    build: 
      context: .
      dockerfile: docker/Dockerfile.mcp
    volumes:
      - ./mcp-server:/app
    environment:
      - TWEETSMASH_API_KEY=${TWEETSMASH_API_KEY}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    command: python server.py
  
  webhook-server:
    build:
      context: .
      dockerfile: docker/Dockerfile.mcp
    ports:
      - "8000:8000"
    command: uvicorn webhook_server:app --host 0.0.0.0
  
  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.mcp
    command: celery -A processors.queue worker --loglevel=info
    depends_on:
      - redis
```

## Dockerfile for Python MCP Server

```dockerfile
# docker/Dockerfile.mcp
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-server/ .

CMD ["python", "server.py"]
```

## Running the System

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Services:**
   ```bash
   docker-compose up -d redis postgres n8n
   ```

3. **Run MCP Server:**
   ```bash
   cd mcp-server
   python server.py
   ```

4. **Run Webhook Server:**
   ```bash
   uvicorn mcp-server.webhook_server:app --reload
   ```

5. **Start Celery Worker:**
   ```bash
   celery -A mcp-server.processors.queue worker --loglevel=info
   ```

## Testing

```python
# tests/test_integration.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_bookmark_processing():
    # Test full pipeline
    pass

@pytest.mark.asyncio  
async def test_github_codespace_creation():
    # Test GitHub integration
    pass
```

## Benefits of Python Implementation

1. **Simplicity**: One language for entire backend
2. **Libraries**: Rich ecosystem for all integrations
3. **Async Support**: Modern async/await patterns
4. **MCP Native**: Direct MCP SDK support
5. **Testing**: Excellent testing frameworks
6. **Deployment**: Easy containerization
7. **Maintenance**: Single language to maintain

## Next Steps

1. Set up Python virtual environment
2. Install MCP SDK and dependencies
3. Implement core MCP server
4. Add service integrations one by one
5. Create n8n workflow templates
6. Test with real TweetSmash bookmarks