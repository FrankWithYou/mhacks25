#!/usr/bin/env python3
"""
Entry point for running the marketplace client agent.
This agent requests services from tool agents and handles payments.
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main entry point for the client agent"""
    print("\n" + "="*60)
    print("💳 CLIENT AGENT (MARKETPLACE)")
    print("="*60)
    print()
    
    print("🚀 Starting Marketplace Client Agent...")
    print("   - Requests services from tool agents")
    print("   - Verifies task completion independently")
    print("   - Handles FET token payments")
    print()
    print("📋 Compatible with hackathon requirements:")
    print("   - Registered on Agentverse (with publish_manifest=True)")
    print("   - Chat protocol enabled for ASI:One integration")
    print("   - Trust-minimized verification system")
    print()
    print("🎯 Agent will be discoverable at: http://127.0.0.1:8002")
    print()
    
    print("💡 To use this agent:")
    print("   1. Make sure the tool agent is running first")
    print("   2. Copy the tool agent's address from its startup logs")
    print("   3. Either update KNOWN_TOOL_AGENT in the code or use chat commands")
    print()
    
    print("🗨️  Chat commands you can try:")
    print("   - 'create issue: Your Title Here'")
    print("   - 'status' (check latest job status)")
    print("   - 'balance' (check FET balance)")
    print()
    
    try:
        # Import and run the client agent
        from client.marketplace_client_agent import client_agent
        print("Starting agent... (Press Ctrl+C to stop)")
        print("Agent address will be displayed below:")
        print("-" * 60)
        client_agent.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Agent stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Error starting agent: {e}")
        return 1

if __name__ == "__main__":
    exit(main())