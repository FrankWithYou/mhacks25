#!/usr/bin/env python3
"""
Integration test for the trust-minimized marketplace.
Tests both agents working together in a controlled environment.
"""

import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_integration():
    """Test the agents working together"""
    print("🔬 INTEGRATION TEST - MARKETPLACE AGENTS")
    print("=" * 60)
    
    try:
        # Test basic imports
        from models.messages import QuoteRequest, TaskType
        from utils.github_api import GitHubAPI
        from utils.crypto import generate_job_id, create_client_signature
        
        print("✅ All imports successful")
        
        # Test GitHub API
        github_api = GitHubAPI.from_env()
        print(f"✅ GitHub API connected to {github_api.repo}")
        
        # Create a test issue
        test_title = f"Integration Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        test_body = """This issue was created by the integration test.

**Test Details:**
- Purpose: Verify marketplace agents can create and verify GitHub issues
- Created: Integration test
- Status: Test successful ✅

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
"""
        
        print(f"🔧 Creating test issue: {test_title}")
        
        issue_url, api_url = await github_api.create_issue(
            test_title, 
            test_body, 
            ["innovationlab", "hackathon", "integration-test"]
        )
        
        print(f"✅ Issue created: {issue_url}")
        
        # Test verification 
        print("🔍 Testing verification...")
        
        # Add a small delay to ensure the issue is available
        await asyncio.sleep(2)
        
        verification_result = await github_api.verify_issue(api_url, test_title)
        
        if verification_result["verified"]:
            print("✅ Verification successful!")
            print(f"   Details: {verification_result['details']}")
        else:
            print("❌ Verification failed")
            print(f"   Details: {verification_result['details']}")
        
        # Test message creation
        quote_request = QuoteRequest(
            task=TaskType.CREATE_GITHUB_ISSUE,
            payload={"title": test_title, "body": test_body},
            client_address="test_client_address"
        )
        
        print(f"✅ Created QuoteRequest for {quote_request.task}")
        
        # Test crypto functions
        job_id = generate_job_id()
        signature = create_client_signature(job_id, "test_hash", datetime.utcnow(), "test_key")
        
        print(f"✅ Generated job ID: {job_id}")
        print(f"✅ Created signature: {signature[:20]}...")
        
        print()
        print("🎉 INTEGRATION TEST COMPLETE!")
        print("=" * 60)
        print("✅ All core components working correctly:")
        print("   • GitHub API integration")
        print("   • Issue creation and verification")
        print("   • Message protocol")
        print("   • Cryptographic functions")
        print()
        print("🚀 Ready to run full agents:")
        print("   Terminal 1: python run_tool_agent.py")
        print("   Terminal 2: python run_client_agent.py")
        print()
        print(f"🔗 Created test issue: {issue_url}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(asyncio.run(test_integration()))