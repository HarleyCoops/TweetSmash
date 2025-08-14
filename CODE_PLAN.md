# TweetSmash Automation - Implementation Plan

## Phase 1: Project Setup & MCP Server Foundation

### Directory Structure
```
TweetSmash/
├── mcp-server/
│   ├── src/
│   │   ├── index.ts           # MCP server entry point
│   │   ├── tools/             # MCP tool implementations
│   │   │   ├── tweetsmash.ts  # TweetSmash API tools
│   │   │   ├── github.ts      # GitHub Codespace tools
│   │   │   ├── youtube.ts     # YouTube processing tools
│   │   │   └── notion.ts      # Notion integration tools
│   │   ├── processors/        # Content processing logic
│   │   │   ├── urlParser.ts   # URL extraction and classification
│   │   │   ├── router.ts      # Content routing logic
│   │   │   └── queue.ts       # Job queue management
│   │   ├── services/          # External service integrations
│   │   │   ├── tweetsmashApi.ts
│   │   │   ├── githubApi.ts
│   │   │   ├── youtubeApi.ts
│   │   │   └── notionApi.ts
│   │   └── utils/
│   │       ├── config.ts      # Configuration management
│   │       ├── logger.ts      # Logging utilities
│   │       └── cache.ts       # Caching layer
│   ├── package.json
│   ├── tsconfig.json
│   └── .env.example
├── n8n-workflows/
│   ├── main-workflow.json     # Primary routing workflow
│   ├── github-workflow.json   # GitHub processing workflow
│   ├── youtube-workflow.json  # YouTube processing workflow
│   └── notion-workflow.json   # Notion integration workflow
├── docker/
│   ├── docker-compose.yml     # Full stack composition
│   ├── n8n/
│   │   └── Dockerfile         # Custom n8n image if needed
│   └── mcp-server/
│       └── Dockerfile         # MCP server container
├── scripts/
│   ├── setup.sh               # Initial setup script
│   ├── test-api.ts            # API testing utilities
│   └── migrate-bookmarks.ts   # Bulk migration tool
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── API.md                 # API documentation
│   ├── SETUP.md              # Setup instructions
│   └── TROUBLESHOOTING.md    # Common issues
├── .env.example
├── .gitignore
├── package.json
└── README.md
```

## Phase 2: Core MCP Server Implementation

### 2.1 MCP Server Setup
```typescript
// mcp-server/src/index.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

const server = new Server({
  name: 'tweetsmash-mcp',
  version: '1.0.0',
});

// Register tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'fetch_bookmarks',
      description: 'Fetch bookmarks from TweetSmash',
      inputSchema: { /* ... */ }
    },
    {
      name: 'process_bookmark',
      description: 'Process a bookmark through the automation pipeline',
      inputSchema: { /* ... */ }
    },
    // Additional tools...
  ]
}));
```

### 2.2 TweetSmash Integration
```typescript
// mcp-server/src/services/tweetsmashApi.ts
export class TweetSmashAPI {
  private apiKey: string;
  private baseUrl = 'https://api.tweetsmash.com/v1';
  
  async fetchBookmarks(cursor?: string) {
    // Implementation with rate limiting and caching
  }
  
  async setupWebhook(url: string) {
    // Webhook configuration
  }
}
```

### 2.3 Content Router
```typescript
// mcp-server/src/processors/router.ts
export class ContentRouter {
  async route(bookmark: Bookmark) {
    const urls = this.extractUrls(bookmark.text);
    const primaryUrl = urls[0];
    
    if (this.isGitHub(primaryUrl)) {
      return this.processGitHub(bookmark, primaryUrl);
    } else if (this.isYouTube(primaryUrl)) {
      return this.processYouTube(bookmark, primaryUrl);
    } else {
      return this.processGeneral(bookmark, primaryUrl);
    }
  }
}
```

## Phase 3: Service Integrations

### 3.1 GitHub Codespace Creation
```typescript
// mcp-server/src/services/githubApi.ts
export class GitHubAPI {
  async createCodespace(repoUrl: string) {
    const { owner, repo } = this.parseRepoUrl(repoUrl);
    
    const response = await this.client.post('/user/codespaces', {
      repository_id: await this.getRepoId(owner, repo),
      machine: 'basicLinux32gb',
      display_name: `TweetSmash-${repo}`,
    });
    
    return response.data;
  }
}
```

### 3.2 YouTube Processing
```typescript
// mcp-server/src/services/youtubeApi.ts
export class YouTubeProcessor {
  async processVideo(videoUrl: string) {
    const videoId = this.extractVideoId(videoUrl);
    
    // Step 1: Get video metadata
    const metadata = await this.getVideoMetadata(videoId);
    
    // Step 2: Download and transcribe audio
    const transcript = await this.transcribeVideo(videoUrl);
    
    // Step 3: Generate summary
    const summary = await this.summarizeTranscript(transcript);
    
    return { metadata, transcript, summary };
  }
}
```

## Phase 4: n8n Workflow Templates

### 4.1 Main Workflow Structure
```json
{
  "nodes": [
    {
      "type": "n8n-nodes-base.webhook",
      "name": "Webhook",
      "position": [250, 300],
      "webhookId": "tweetsmash-trigger"
    },
    {
      "type": "n8n-nodes-base.switch",
      "name": "URL Router",
      "position": [450, 300],
      "parameters": {
        "dataType": "string",
        "value1": "={{$json.url}}",
        "rules": {
          "rules": [
            {
              "value2": "github.com",
              "operation": "contains"
            },
            {
              "value2": "youtube.com",
              "operation": "contains"
            }
          ]
        }
      }
    }
  ]
}
```

## Phase 5: Docker Configuration

### 5.1 Docker Compose
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: n8n
      POSTGRES_USER: n8n
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
    volumes:
      - n8n_data:/home/node/.n8n
      - ./n8n-workflows:/workflows
    depends_on:
      - postgres

  mcp-server:
    build: ./docker/mcp-server
    ports:
      - "3000:3000"
    environment:
      - TWEETSMASH_API_KEY=${TWEETSMASH_API_KEY}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - NOTION_TOKEN=${NOTION_TOKEN}
    volumes:
      - ./mcp-server:/app
    command: npm run dev

volumes:
  postgres_data:
  n8n_data:
```

## Phase 6: Environment Configuration

### 6.1 Environment Variables
```bash
# .env.example

# TweetSmash
TWEETSMASH_API_KEY=your_api_key_here
TWEETSMASH_WEBHOOK_SECRET=webhook_secret

# GitHub
GITHUB_TOKEN=ghp_your_token_here

# OpenAI (for transcription and summarization)
OPENAI_API_KEY=sk-your_key_here

# Notion
NOTION_TOKEN=secret_your_token_here
NOTION_DATABASE_ID=your_database_id

# n8n
N8N_USER=admin
N8N_PASSWORD=secure_password
N8N_WEBHOOK_BASE_URL=http://localhost:5678

# Database
POSTGRES_PASSWORD=secure_db_password

# MCP Server
MCP_SERVER_PORT=3000
MCP_SERVER_LOG_LEVEL=info
```

## Phase 7: Testing Strategy

### 7.1 Unit Tests
- URL parser validation
- API client mocking
- Content router logic
- Cache functionality

### 7.2 Integration Tests
- End-to-end bookmark processing
- API rate limit handling
- Webhook delivery
- Error recovery

### 7.3 Load Testing
- Concurrent bookmark processing
- API rate limit compliance
- Queue performance

## Phase 8: Deployment Steps

1. **Local Development**
   ```bash
   # Clone repository
   git clone <repo-url>
   cd TweetSmash
   
   # Setup environment
   cp .env.example .env
   # Edit .env with your API keys
   
   # Install dependencies
   npm install
   cd mcp-server && npm install
   
   # Start services
   docker-compose up -d
   npm run dev:mcp-server
   ```

2. **Configure n8n Workflows**
   - Import workflow templates
   - Configure webhook URLs
   - Test each workflow path

3. **Test Integration**
   ```bash
   npm run test:integration
   ```

## Phase 9: Monitoring & Maintenance

### 9.1 Health Checks
- MCP server status endpoint
- n8n workflow execution monitoring
- API rate limit tracking
- Queue depth monitoring

### 9.2 Logging
- Structured JSON logs
- Log aggregation with Docker
- Error alerting setup

### 9.3 Backup Strategy
- n8n workflow exports
- Database backups
- Configuration versioning

## Success Metrics

1. **Functional Requirements**
   - ✅ Bookmarks fetched from TweetSmash
   - ✅ GitHub repos trigger Codespace creation
   - ✅ YouTube videos are transcribed and summarized
   - ✅ Other content saved to Notion
   - ✅ Webhook integration for real-time processing

2. **Performance Requirements**
   - Process bookmark within 30 seconds
   - Handle 100 bookmarks/hour
   - 99% uptime for local deployment
   - <5% error rate

3. **Security Requirements**
   - API keys stored securely
   - No sensitive data in logs
   - Network isolation via Docker
   - Input validation on all endpoints

## Next Steps

1. **Immediate Actions**
   - Set up development environment
   - Obtain all required API keys
   - Initialize Git repository
   - Create MCP server skeleton

2. **Week 1 Goals**
   - Complete MCP server basic implementation
   - Test TweetSmash API integration
   - Set up Docker environment
   - Create first n8n workflow

3. **Week 2 Goals**
   - Implement all content processors
   - Complete n8n workflow suite
   - Add error handling and retries
   - Begin integration testing

4. **Future Enhancements**
   - Add more content sources
   - Implement ML categorization
   - Create web dashboard
   - Add browser extension