#!/usr/bin/env python3
"""
Test script for the TweetSmash multi-agent pipeline
"""

import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp-server'))

from agents.orchestrator import AgentOrchestrator
from utils.config import Config
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_content_analysis():
    """Test content analysis with sample tweets"""
    print("\n=== Testing Content Analysis ===")
    
    test_cases = [
        {
            "name": "GitHub project announcement",
            "tweet": "Just released my new Python CLI tool for developers! Built with Click and rich for beautiful terminal output. Check it out: github.com/user/awesome-cli",
            "author": "dev_user"
        },
        {
            "name": "Code tutorial reference",
            "tweet": "Great tutorial on building REST APIs with FastAPI. The author's repository has excellent examples and documentation.",
            "author": "tutorial_fan"
        },
        {
            "name": "Library recommendation",
            "tweet": "If you're working with data visualization in Python, definitely check out Plotly. The interactive charts are amazing!",
            "author": "data_scientist"
        },
        {
            "name": "Non-code content",
            "tweet": "Beautiful sunset today! Perfect weather for a walk in the park.",
            "author": "nature_lover"
        }
    ]
    
    orchestrator = AgentOrchestrator()
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        
        bookmark_data = {
            "post_id": f"test_{test_case['name'].replace(' ', '_')}",
            "tweet_details": {
                "text": test_case["tweet"],
                "posted_at": "2024-01-01T12:00:00Z",
                "link": "https://twitter.com/test/status/123"
            },
            "author_details": {
                "name": test_case["author"].replace("_", " ").title(),
                "username": test_case["author"]
            }
        }
        
        try:
            # Test with conservative pipeline to avoid long execution times
            config = {
                "discovery_strategy": "conservative",
                "execution_strategy": "quick",
                "synthesis_style": "summary",
                "max_repositories": 1,
                "timeout_per_agent": 30
            }
            
            result = await orchestrator.process_bookmark(bookmark_data, config)
            
            if result.get("success"):
                print(f"✅ Processing successful")
                print(f"   Title: {result.get('title', 'No title')}")
                print(f"   Tags: {', '.join(result.get('tags', [])[:5])}")
                print(f"   GitHub repos found: {result.get('metadata', {}).get('repositories_discovered', 0)}")
                print(f"   Processing time: {result.get('metadata', {}).get('total_processing_time', 0):.2f}s")
                
                # Show content preview
                content = result.get("content", "")
                if content:
                    preview = content[:150] + "..." if len(content) > 150 else content
                    print(f"   Content preview: {preview}")
                
            else:
                print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Test failed: {e}")


async def test_pipeline_status():
    """Test pipeline status check"""
    print("\n=== Testing Pipeline Status ===")
    
    orchestrator = AgentOrchestrator()
    
    try:
        status = await orchestrator.get_pipeline_status()
        
        print(f"Orchestrator: {status.get('orchestrator', 'unknown')}")
        print(f"Total agents: {status.get('pipeline_info', {}).get('total_agents', 0)}")
        
        agents = status.get('agents', {})
        for agent_name, agent_status in agents.items():
            status_indicator = "✅" if agent_status.get('status') == 'ready' else "❌"
            print(f"  {status_indicator} {agent_name}: {agent_status.get('status', 'unknown')}")
            
            if agent_status.get('llm_available') is not None:
                llm_indicator = "✅" if agent_status['llm_available'] else "⚠️"
                print(f"     {llm_indicator} LLM available: {agent_status['llm_available']}")
        
    except Exception as e:
        print(f"❌ Status check failed: {e}")


async def test_individual_agents():
    """Test individual agents with sample data"""
    print("\n=== Testing Individual Agents ===")
    
    from agents.content_analysis_agent import ContentAnalysisAgent
    from agents.github_discovery_agent import GitHubDiscoveryAgent
    
    # Test content analysis
    print("\n--- Content Analysis Agent ---")
    content_agent = ContentAnalysisAgent()
    
    sample_input = {
        "tweet_text": "Just open-sourced my Python web scraper! Uses requests and BeautifulSoup. github.com/user/webscraper",
        "author_details": {"name": "Developer", "username": "dev_user"}
    }
    
    try:
        result = await content_agent.process(sample_input)
        if result.get("success"):
            data = result.get("data", {})
            print(f"✅ Content analysis successful")
            print(f"   GitHub relevance: {data.get('github_relevance_score', 0):.2f}")
            print(f"   Content type: {data.get('content_type', 'unknown')}")
            print(f"   Direct URLs: {len(data.get('direct_github_urls', []))}")
            print(f"   Keywords: {', '.join(data.get('code_keywords', [])[:3])}")
        else:
            print(f"❌ Content analysis failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Content analysis error: {e}")
    
    # Test GitHub discovery if content analysis found GitHub relevance
    if result.get("success") and result.get("data", {}).get("github_relevance_score", 0) > 0.3:
        print("\n--- GitHub Discovery Agent ---")
        github_agent = GitHubDiscoveryAgent()
        
        try:
            discovery_result = await github_agent.process({
                "content_analysis": result.get("data"),
                "discovery_strategy": "conservative"
            })
            
            if discovery_result.get("success"):
                data = discovery_result.get("data", {})
                print(f"✅ GitHub discovery successful")
                print(f"   Repositories found: {data.get('total_found', 0)}")
                print(f"   High confidence repos: {data.get('has_high_confidence_repos', False)}")
            else:
                print(f"❌ GitHub discovery failed: {discovery_result.get('error')}")
                
        except Exception as e:
            print(f"❌ GitHub discovery error: {e}")


async def test_configuration():
    """Test configuration and dependencies"""
    print("\n=== Testing Configuration ===")
    
    config = Config.from_env()
    
    checks = [
        ("TweetSmash API Key", bool(config.tweetsmash_api_key)),
        ("Anthropic API Key", bool(config.anthropic_api_key)), 
        ("OpenAI API Key", bool(config.openai_api_key)),
        ("E2B API Key", bool(config.e2b_api_key)),
        ("Notion Token", bool(config.notion_token)),
    ]
    
    all_configured = True
    for name, is_configured in checks:
        if is_configured:
            print(f"✅ {name} configured")
        else:
            print(f"⚠️  {name} not configured")
            if name in ["TweetSmash API Key", "Anthropic API Key", "OpenAI API Key"]:
                all_configured = False
    
    if all_configured:
        print("\n🎉 All critical components configured!")
    else:
        print("\n⚠️  Some components need configuration for full functionality")
    
    return all_configured


async def main():
    """Run all pipeline tests"""
    print("=" * 60)
    print("TweetSmash Multi-Agent Pipeline Test")
    print("=" * 60)
    
    # Test configuration first
    config_ok = await test_configuration()
    
    # Test pipeline status
    await test_pipeline_status()
    
    # Test individual agents
    await test_individual_agents()
    
    # Test full pipeline with sample content
    if config_ok:
        await test_content_analysis()
    else:
        print("\n⚠️  Skipping full pipeline tests due to missing configuration")
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("- Configuration: ✅ Complete" if config_ok else "- Configuration: ⚠️  Partial")
    print("- Pipeline components: Ready for testing")
    print("- Multi-agent workflow: Implemented")
    
    print("\nNext steps:")
    print("1. Complete API key configuration")
    print("2. Start MCP server: python mcp-server/server.py")
    print("3. Test with real TweetSmash bookmarks")
    print("4. Configure Notion integration")


if __name__ == "__main__":
    asyncio.run(main())