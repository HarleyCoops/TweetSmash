#!/usr/bin/env python3
"""
Test script to verify TweetSmash MCP Server components
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp-server'))

from utils.config import Config
from utils.logger import setup_logger
from services.tweetsmash_api import TweetSmashAPI
from tools.tweetsmash import TweetSmashTools
from processors.router import ContentRouter

logger = setup_logger(__name__)


async def test_tweetsmash_api():
    """Test TweetSmash API connection"""
    print("\n=== Testing TweetSmash API ===")
    try:
        config = Config.from_env()
        if not config.tweetsmash_api_key:
            print("❌ TweetSmash API key not configured")
            return False
        
        api = TweetSmashAPI()
        result = await api.fetch_bookmarks(limit=1)
        
        if 'bookmarks' in result:
            print(f"✅ TweetSmash API working - Found {len(result.get('bookmarks', []))} bookmarks")
            return True
        else:
            print(f"❌ TweetSmash API error: {result}")
            return False
    except Exception as e:
        print(f"❌ TweetSmash API error: {e}")
        return False


async def test_url_routing():
    """Test URL routing logic"""
    print("\n=== Testing URL Routing ===")
    
    router = ContentRouter()
    
    test_urls = [
        ("https://github.com/anthropics/claude-code", "github"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://medium.com/article", "article"),
        ("https://twitter.com/status/123456", "twitter"),
        ("https://example.com", "general")
    ]
    
    all_passed = True
    for url, expected_type in test_urls:
        result = await router.analyze_url(url)
        actual_type = result.get("content_type")
        if actual_type == expected_type:
            print(f"✅ {url[:40]} -> {actual_type}")
        else:
            print(f"❌ {url[:40]} -> Expected {expected_type}, got {actual_type}")
            all_passed = False
    
    return all_passed


async def test_configuration():
    """Test configuration loading"""
    print("\n=== Testing Configuration ===")
    
    config = Config.from_env()
    
    checks = [
        ("TweetSmash API Key", bool(config.tweetsmash_api_key)),
        ("OpenAI API Key", bool(config.openai_api_key)),
        ("GitHub Token", bool(config.github_token)),
        ("Notion Token", bool(config.notion_token)),
        ("Redis URL", bool(config.redis_url))
    ]
    
    all_configured = True
    for name, is_configured in checks:
        if is_configured:
            print(f"✅ {name} configured")
        else:
            print(f"⚠️  {name} not configured")
            if name in ["TweetSmash API Key"]:
                all_configured = False
    
    return all_configured


async def test_redis_connection():
    """Test Redis connection"""
    print("\n=== Testing Redis Connection ===")
    
    try:
        import redis
        config = Config.from_env()
        r = redis.from_url(config.redis_url)
        r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"⚠️  Redis not available: {e}")
        print("   (Redis is optional for caching)")
        return False


async def main():
    """Run all tests"""
    print("=" * 50)
    print("TweetSmash MCP Server System Test")
    print("=" * 50)
    
    results = []
    
    # Test configuration
    results.append(("Configuration", await test_configuration()))
    
    # Test Redis
    await test_redis_connection()
    
    # Test TweetSmash API
    results.append(("TweetSmash API", await test_tweetsmash_api()))
    
    # Test URL routing
    results.append(("URL Routing", await test_url_routing()))
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All critical tests passed! System is ready.")
    else:
        print("\n⚠️  Some tests failed. Check configuration above.")
    
    print("\nNext steps:")
    print("1. Start Docker services: docker-compose up -d")
    print("2. Run MCP server: python mcp-server/server.py")
    print("3. Configure n8n workflows at http://localhost:5678")


if __name__ == "__main__":
    asyncio.run(main())