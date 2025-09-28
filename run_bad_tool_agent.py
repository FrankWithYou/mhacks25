#!/usr/bin/env python3
"""
Entry point for running the Bad tool agent (for trustless demo).
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv

load_dotenv()

def main():
    print("=" * 60)
    print("⚠️  BAD TOOL AGENT (DEMO)")
    print("=" * 60)
    print()
    print("This agent intentionally returns invalid/unverifiable receipts.")
    print("Use to demonstrate client-side verification and no payment on failure.")
    print()
    try:
        from tool.bad_tool_agent import bad_agent
        print("Starting agent... (Press Ctrl+C to stop)")
        print("-" * 60)
        bad_agent.run()
    except KeyboardInterrupt:
        print("\n🛑 Agent stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Error starting bad tool agent: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
