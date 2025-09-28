#!/usr/bin/env python3
"""
Demo script for the trust-minimized AI agent marketplace.
This script demonstrates the complete workflow: quote → perform → verify → pay
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_banner():
    """Print demo banner"""
    print("=" * 80)
    print("🎯 TRUST-MINIMIZED AI AGENT MARKETPLACE DEMO")
    print("=" * 80)
    print()
    print("This demo shows the complete marketplace workflow:")
    print("1. Client requests GitHub issue creation (QuoteRequest)")
    print("2. Tool agent provides price quote (QuoteResponse)")
    print("3. Client accepts and sends task details (PerformRequest)")
    print("4. Tool agent creates GitHub issue and returns receipt (Receipt)")
    print("5. Client verifies issue independently and pays (PaymentNotification)")
    print()

async def run_demo():
    """Run the marketplace demo"""
    try:
        print_banner()
        
        # Check environment
        required_vars = ["GITHUB_TOKEN", "GITHUB_REPO"]
        missing_vars = [var for var in required_vars 
                       if not os.getenv(var) or os.getenv(var).startswith("your_")]
        
        if missing_vars:
            print("❌ Demo requires GitHub configuration:")
            for var in missing_vars:
                print(f"   - {var}")
            print("\nPlease update your .env file with valid GitHub credentials.")
            return 1
        
        print("✅ GitHub configuration found")
        print(f"📁 Target repository: {os.getenv('GITHUB_REPO')}")
        print()
        
        # Import components after path setup
        from models.messages import QuoteRequest, TaskType
        from utils.github_api import GitHubAPI
        from utils.crypto import generate_job_id, compute_terms_hash
        
        print("🔧 Testing GitHub API connection...")
        try:
            github_api = GitHubAPI.from_env()
            print(f"   ✅ Connected to GitHub API for {github_api.repo}")
        except Exception as e:
            print(f"   ❌ GitHub API connection failed: {e}")
            return 1
        
        print()
        print("🎭 DEMO SCENARIO")
        print("-" * 40)
        
        # Demo parameters
        demo_title = f"Demo Issue from Marketplace - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        demo_body = f"""This issue was created by the trust-minimized AI agent marketplace demo.

**Demo Details:**
- Created at: {datetime.now().isoformat()}
- Job type: GitHub issue creation
- Verification: Independent API call
- Payment: FET tokens (simulated)

**Hackathon Tags:**
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

This demonstrates the complete trust-minimized workflow where:
1. A client agent pays a tool agent for task execution
2. Payment only occurs after independent verification
3. Both agents are registered on Agentverse with chat protocol support
"""
        
        print(f"📋 Demo task: Create GitHub issue")
        print(f"   Title: {demo_title}")
        print(f"   Repository: {github_api.repo}")
        print()
        
        # Step 1: Quote Phase
        print("1️⃣  QUOTE PHASE")
        print("-" * 20)
        
        quote_request = QuoteRequest(
            task=TaskType.CREATE_GITHUB_ISSUE,
            payload={
                "title": demo_title,
                "body": demo_body,
                "labels": ["innovationlab", "hackathon", "demo"]
            },
            client_address="demo_client_address",
            timestamp=datetime.utcnow()
        )
        
        print(f"   📤 QuoteRequest created:")
        print(f"      Task: {quote_request.task}")
        print(f"      Title: {quote_request.payload['title'][:50]}...")
        print()
        
        # Step 2: Simulate tool response
        job_id = generate_job_id()
        price = 5000000000000000000  # 5 testFET in atestfet
        terms_data = {
            "task": quote_request.task.value,
            "payload": quote_request.payload,
            "price": price,
            "denom": "atestfet",
            "ttl": 300,
            "bond_required": 1000000000000000000
        }
        terms_hash = compute_terms_hash(terms_data)
        
        print("   📥 Tool agent would respond with:")
        print(f"      Job ID: {job_id}")
        print(f"      Price: {price} atestfet (5.0 testFET)")
        print(f"      Terms hash: {terms_hash[:16]}...")
        print()
        
        # Step 3: Execution Phase
        print("2️⃣  EXECUTION PHASE")
        print("-" * 20)
        
        print("   🔨 Tool agent executing task...")
        
        try:
            # Actually create the GitHub issue
            issue_url, api_url = await github_api.create_issue(
                demo_title,
                demo_body,
                ["innovationlab", "hackathon", "demo"]
            )
            
            print(f"   ✅ GitHub issue created successfully!")
            print(f"      Issue URL: {issue_url}")
            print(f"      API URL: {api_url}")
            print()
            
        except Exception as e:
            print(f"   ❌ Failed to create GitHub issue: {e}")
            return 1
        
        # Step 4: Verification Phase
        print("3️⃣  VERIFICATION PHASE")
        print("-" * 20)
        
        print("   🔍 Client agent verifying task completion...")
        
        try:
            verification_result = await github_api.verify_issue(
                api_url,
                demo_title
            )
            
            if verification_result["verified"]:
                print("   ✅ Verification passed!")
                print(f"      {verification_result['details']}")
            else:
                print("   ❌ Verification failed!")
                print(f"      {verification_result['details']}")
                return 1
        
        except Exception as e:
            print(f"   ❌ Verification error: {e}")
            return 1
        
        print()
        
        # Step 5: Payment Phase
        print("4️⃣  PAYMENT PHASE")
        print("-" * 20)
        
        print("   💰 Client agent would now:")
        print(f"      1. Send {price} atestfet to tool agent")
        print(f"      2. Include transaction hash in PaymentNotification")
        print(f"      3. Update job status to PAID")
        print()
        
        # Demo Summary
        print("🎉 DEMO COMPLETE!")
        print("=" * 40)
        print()
        print("✅ Successfully demonstrated:")
        print("   • GitHub issue creation via tool agent")
        print("   • Independent verification by client agent")
        print("   • Trust-minimized workflow (payment after verification)")
        print()
        print("🔗 Created GitHub issue:")
        print(f"   {issue_url}")
        print()
        print("📋 Real implementation features:")
        print("   • Both agents registered on Agentverse")
        print("   • Chat protocol for ASI:One integration")
        print("   • FET token payments on testnet")
        print("   • Cryptographic signatures for authenticity")
        print("   • SQLite state management")
        print("   • Proper error handling and timeouts")
        print()
        print("🏆 This meets all hackathon requirements:")
        print("   • Best Use of Fetch.ai: Full tech stack integration")
        print("   • Best Deployment on Agentverse: Discoverable agents")
        print("   • Best Use of ASI:One: Agentic reasoning engine")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n💥 Demo error: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main entry point"""
    return asyncio.run(run_demo())

if __name__ == "__main__":
    exit(main())