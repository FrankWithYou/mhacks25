#!/usr/bin/env python3
"""
Launch script for the Trust-Minimized AI Agent Marketplace demo frontend.
Runs the FastAPI web application with real-time dashboard.
"""

import sys
import os
import uvicorn
from pathlib import Path

# Add frontend to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'frontend'))

def main():
    """Main entry point for the frontend"""
    print("=" * 70)
    print("🌐 TRUST-MINIMIZED MARKETPLACE - DEMO FRONTEND")
    print("=" * 70)
    print()
    
    # Check environment
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        print("⚠️  Warning: .env file not found")
        print("   The demo may not work properly without GitHub configuration")
        print()
    
    print("🚀 Starting Demo Frontend Server...")
    print("   - Real-time job tracking")
    print("   - Live agent interaction visualization")  
    print("   - GitHub issue creation demo")
    print("   - Trust-minimized workflow display")
    print()
    print("📋 Features:")
    print("   • WebSocket real-time updates")
    print("   • Interactive job submission")
    print("   • Live activity feed")
    print("   • Progress visualization") 
    print("   • Agent status monitoring")
    print()
    print("🎯 Open your browser to: http://localhost:8000")
    print("🎪 Perfect for hackathon demonstrations!")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 70)
    
    try:
        # Import and run the FastAPI app
        from app import app
        
        # Run with uvicorn
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            reload=False,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Frontend server stopped by user")
        return 0
    except Exception as e:
        print(f"\n💥 Error starting frontend server: {e}")
        return 1

if __name__ == "__main__":
    exit(main())