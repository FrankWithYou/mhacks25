#!/usr/bin/env python3
"""
Entry point for running the GitHub tool agent.
This agent provides GitHub issue creation services to the marketplace.
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main entry point for the tool agent"""
    print("=" * 60)
    print("🔧 GITHUB TOOL AGENT")
    print("=" * 60)
    print()
    
    # Check required environment variables
    required_vars = ["GITHUB_TOKEN", "GITHUB_REPO"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var) or os.getenv(var) == f"your_{var.lower()}_here":
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("Please update your .env file with:")
        print("- GITHUB_TOKEN: Your GitHub personal access token")
        print("- GITHUB_REPO: Repository in format 'owner/repo' (e.g., 'your-username/test-repo')")
        print()
        print("To create a GitHub token:")
        print("1. Go to GitHub Settings → Developer settings → Personal access tokens")
        print("2. Create a new token with 'public_repo' or 'repo' permissions")
        print("3. Copy the token to your .env file")
        print()
        return 1
    
    print("✅ Environment variables configured")
    print(f"📁 Repository: {os.getenv('GITHUB_REPO')}")
    print(f"🔑 GitHub token: {'*' * 20}{os.getenv('GITHUB_TOKEN')[-4:]}")
    print()
    
    print("🚀 Starting GitHub Tool Agent...")
    print("   - Specializes in creating GitHub issues")
    print("   - Accepts quotes and executes tasks")
    print("   - Provides signed receipts for verification")
    print()
    print("📋 Compatible with hackathon requirements:")
    print("   - Registered on Agentverse (with publish_manifest=True)")
    print("   - Chat protocol enabled for ASI:One integration")
    print("   - Uses innovation lab badges in issues")
    print()
    print("🎯 Agent will be discoverable at: http://127.0.0.1:8001")
    print()
    
    try:
        # Import and run the tool agent
        from tool.github_tool_agent import tool_agent
        print("Starting agent... (Press Ctrl+C to stop)")
        print("Agent address will be displayed below:")
        print("-" * 60)
        tool_agent.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Agent stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Error starting agent: {e}")
        return 1

if __name__ == "__main__":
    exit(main())