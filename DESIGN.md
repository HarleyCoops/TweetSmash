# TweetSmash Automation & MCP Server - Design

## 1) Overview
Goal: Automate processing of Tweetsmash bookmarks by classifying primary URLs and routing to actions:
- GitHub repos → create Codespaces.
- YouTube videos → get transcript (captions/transcription) → summarize.
- Everything else → create Notion knowledge entry.

We will implement:
- An MCP server exposing tools for Tweetsmash access, URL analysis, provider actions, and idempotent bookkeeping.
- n8n workflows that orchestrate triggers, routing, retries, and writing to Notion.

Non-goals (initially): rich ML content extraction for articles, full-text storage/search, or complex user interfaces.

## 2) Architecture (high level)
- Source: Tweetsmash (Webhook preferred; polling fallback).
- Orchestration: n8n workflow(s).
- Logic/Tools: MCP server providing composable actions.
- Destinations: GitHub Codespaces, Notion DB, optional Slack/email notifications.
- State: lightweight local cache (e.g., SQLite/JSON) for idempotency; Notion as source of truth for finalized records.

Data flow:
Tweetsmash → (Webhook/Poll) → n8n → MCP.analyze_url → Router
  → GitHub: MCP.create_codespace → Notion log (optional) → Notify
  → YouTube: MCP.get_transcript → MCP.summarize → Notion entry
  → Other: MCP.create_notion_entry (with minimal summary optional)

## 3) MCP Server
Language/runtime: TBD (Node/TypeScript or Python). Must be easy to dockerize, expose MCP tools, and integrate with n8n via HTTP nodes.

### 3.1 Tools (interfaces)
- get_bookmarks(params?) → {items: Bookmark[], next?: Cursor}
- get_bookmark(id) → Bookmark
- analyze_url(url) → {type: github|youtube|article|unknown, metadata}
- create_codespace(repo_url, options?) → {codespace_id, status_url}
- get_youtube_captions(url) → {text, source: captions}
- transcribe_audio(url_or_id) → {text, source: transcription}
- summarize(text, profile?) → {summary}
- create_notion_entry(payload) → {page_id}
- upsert_content_record(record) → {ok: true}

Notes:
- Prefer captions for YouTube; fallback to transcription provider.
- Idempotency keys derived from Tweet ID or URL hash; tools should be safe to retry.

### 3.2 Data Models (draft)
- Bookmark: { id, tweet_id, tweet_text, author_handle, urls: [string], created_at, raw }
- ResolvedUrl: { original, canonical, domain, type, repo?: {owner,name}, yt?: {videoId}, article?: {title?} }
- Transcript: { text, source, duration_sec? }
- Summary: { text, model, tokens? }
- NotionEntry: { title, url, type, source, tweet_id, bookmark_id, author, summary?, transcript_ref?, tags?, created_at }

These are placeholders; align with actual Tweetsmash/Notion payloads during implementation.

### 3.3 Storage & Idempotency
- Local: cache.db (SQLite) or cache.json to track processed bookmark_id or url_hash, with outcome and timestamps.
- Notion: final state; store Tweet/Bookmark IDs as properties to prevent duplicates when re-running.

### 3.4 Error Handling
- Standardize tool errors with codes (rate_limit, auth, not_found, transient).
- Retries with exponential backoff + jitter for transient errors; no retry for auth/4xx.

## 4) n8n Workflows

### 4.1 Trigger
- Preferred: HTTP Webhook node (Tweetsmash → n8n). Configure signature verification if available.
- Fallback: Schedule + HTTP Request node to poll Tweetsmash API/RSS.

### 4.2 Main Workflow Outline (nodes)
1. Trigger (Webhook or Poll)
2. Parse payload → extract Tweet ID, text, primary URL
3. Idempotency check (HTTP → MCP.upsert_content_record in dry-run/check mode)
4. Analyze URL (HTTP → MCP.analyze_url)
5. Router (Switch node on type)
   - Case: github
     a. HTTP → MCP.create_codespace(repo_url)
     b. Optional: Notify (Slack/Email)
     c. Optional: Notion log entry (type=GitHub, status)
   - Case: youtube
     a. Try HTTP → MCP.get_youtube_captions
     b. If empty → HTTP → MCP.transcribe_audio
     c. HTTP → MCP.summarize(transcript)
     d. HTTP → MCP.create_notion_entry
   - Case: article/other
     a. Optional: HTTP → MCP.summarize(short) using basic readability extraction
     b. HTTP → MCP.create_notion_entry
6. Success path → mark processed (MCP.upsert_content_record)
7. Global error → Failure handler (see below)

### 4.3 Failure Handling
- Error workflow: capture input + error, push to Notion "Errors" DB or S3, and send Slack/Email alert.
- Include a manual reprocess link (n8n webhook) with original payload.

### 4.4 Idempotency
- Primary key: bookmark_id if provided; fallback: tweet_id; fallback: hash(url + text).
- n8n checks MCP before actions; MCP returns already_processed flag when appropriate.

## 5) Integrations (implementation notes)

### 5.1 Tweetsmash
- Auth: API key from env.
- Trigger: webhook recommended; if unavailable, poll endpoint or RSS.
- Map incoming fields to Bookmark model; store raw payload for traceability.

### 5.2 GitHub Codespaces
- Auth: PAT with codespaces scope.
- Inputs: repo_url, machine type, retention policy, devcontainer use (default).
- Output: codespace_id, web_url/status.
- Consider quota/limits; avoid auto-start storms.

### 5.3 YouTube
- Captions: try official captions API if available, else provider libraries.
- Transcription: service like Whisper API or AssemblyAI.
- Cost/latency controls: length guardrails, skip on very long videos unless flagged.

### 5.4 LLM Summarization
- Provider: configurable (OpenAI/Anthropic/etc.).
- Profiles: "brief", "detailed", "action-items"; default brief.

### 5.5 Notion
- A single database "Bookmarks" (or separate by type). Properties:
  - Title (title)
  - URL (url)
  - Type (select: GitHub, YouTube, Article, Other)
  - Source (select: Tweetsmash)
  - Author/Handle (text or people)
  - Tweet ID (text)
  - Bookmark ID (text)
  - Summary (rich text)
  - Transcript Ref or URL (rich text or files)
  - Tags (multi-select)
  - Status (select: New, Processed, Actioned, Archived)
  - CreatedAt (date)
  - ProcessedAt (date)

## 6) Configuration
Environment variables (examples):
- TWEETSMASH_API_KEY
- N8N_WEBHOOK_SECRET (if verifying)
- NOTION_TOKEN, NOTION_DB_ID
- GITHUB_TOKEN
- YOUTUBE_API_KEY (optional)
- TRANSCRIPTION_API_KEY
- LLM_API_KEY
- CACHE_BACKEND (sqlite|json)

Deployment: docker-compose with services for n8n and MCP server; mount volume for cache.

## 7) Security
- Store secrets in env or secret manager; never in repo.
- Validate inbound webhooks (signature/time-window) if Tweetsmash supports it.
- Principle of least privilege for tokens; rotate regularly.

## 8) Observability
- Structured logs (JSON) from MCP.
- n8n execution logs + success/failure metrics.
- Optional Slack notifications on failures/highlights.

## 9) Testing Plan
- Unit: URL classification, dedupe key generation, Notion payload mapping.
- Integration: sandbox Notion DB; mock Codespaces call; mock YouTube transcript.
- E2E dry-run: replay captured Tweetsmash payloads through n8n with side effects pointing to test targets.

## 10) Milestones & Acceptance Criteria
- M1 Foundations: finalize design, env skeleton, sample fixtures; AC: DESIGN.md approved, sample payloads checked in.
- M2 MCP MVP: implement analyze_url, Notion create, cache; AC: process "Other" path end-to-end via n8n.
- M3 YouTube Path: captions/transcription + summarization; AC: Notion entry with summary from YouTube link.
- M4 GitHub Path: Codespaces creation; AC: Codespace created from GitHub bookmark and logged.
- M5 Hardening: retries, logging, docs, dashboards; AC: errors recoverable, idempotent reruns verified.

## 11) Open Questions
- Tweetsmash: webhook availability and payload shape? auth and rate limits?
- Notion: confirm database structure and workspace.
- Providers: choose transcription + LLM vendors; budgets and latency targets.
- Codespaces: permissions, default machine size, retention policy.
- Hosting: where to run n8n + MCP; secret management standard.
- Notifications: Slack/Email targets and channel preferences.

## 12) Sample Payloads (placeholders)
- Tweetsmash webhook (minimal):
  {
    "bookmark_id": "bk_123",
    "tweet_id": "t_456",
    "tweet_text": "Check this out https://github.com/org/repo",
    "author_handle": "@user",
    "urls": ["https://github.com/org/repo"],
    "created_at": "2025-08-13T18:00:00Z",
    "raw": {...}
  }

- Notion entry payload (to MCP.create_notion_entry):
  {
    "title": "org/repo",
    "url": "https://github.com/org/repo",
    "type": "GitHub",
    "source": "Tweetsmash",
    "tweet_id": "t_456",
    "bookmark_id": "bk_123",
    "author": "@user",
    "summary": "",
    "tags": ["dev"],
    "created_at": "2025-08-13T18:00:00Z"
  }

