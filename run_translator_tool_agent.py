#!/usr/bin/env python3
"""
Entry point for running the Translator tool agent.
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv

load_dotenv()

def main():
    print("=" * 60)
    print("🈯 TRANSLATOR TOOL AGENT")
    print("=" * 60)
    print()
    print("Capabilities: TRANSLATE_TEXT (LibreTranslate or fallback)")
    print("Agent will publish manifest and announce to frontend registry.")
    print()
    try:
        from tool.translator_tool_agent import translator_agent
        print("Starting agent... (Press Ctrl+C to stop)")
        print("-" * 60)
        translator_agent.run()
    except KeyboardInterrupt:
        print("\n🛑 Agent stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Error starting translator agent: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
