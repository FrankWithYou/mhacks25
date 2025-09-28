"""
FastAPI web application for the Trust-Minimized AI Agent Marketplace demo.
Provides a real-time dashboard showing agent interactions and job status.
"""

import sys
import os
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from dotenv import load_dotenv

from models.messages import QuoteRequest, TaskType, JobStatus, JobRecord
from utils.github_api import GitHubAPI, GitHubAPIError
from utils.state_manager import StateManager
from utils.crypto import generate_job_id
from utils.payment import PaymentManager

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

app = FastAPI(title="Marketplace Demo Dashboard", version="1.0.0")

# Setup static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

# Global state
github_api = None
state_manager = StateManager("frontend_demo.db")
payment_manager = PaymentManager()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                # Remove disconnected clients
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    global github_api
    try:
        github_api = GitHubAPI.from_env()
        print(f"✅ GitHub API initialized for {github_api.repo}")
    except Exception as e:
        print(f"⚠️  GitHub API not configured: {e}")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    # Get recent jobs
    all_jobs = []
    try:
        # Get jobs from database
        recent_jobs = state_manager.get_jobs_by_agent("demo_client", role="any")[:10]
        all_jobs = recent_jobs
    except:
        pass
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "github_repo": os.getenv("GITHUB_REPO", "Not configured"),
        "recent_jobs": all_jobs
    })

@app.post("/create-issue")
async def create_issue_endpoint(
    title: str = Form(...),
    body: str = Form(default=""),
    labels: str = Form(default="innovationlab,hackathon,demo")
):
    """Create a GitHub issue through the marketplace workflow"""
    if not github_api:
        raise HTTPException(status_code=500, detail="GitHub API not configured")
    
    try:
        # Parse labels
        label_list = [label.strip() for label in labels.split(",") if label.strip()]
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Create job record
        job_record = JobRecord(
            job_id=job_id,
            task=TaskType.CREATE_GITHUB_ISSUE,
            payload={
                "title": title,
                "body": body or f"Created via marketplace demo at {datetime.now().isoformat()}",
                "labels": label_list
            },
            status=JobStatus.REQUESTED,
            client_address="demo_client",
            tool_address="demo_tool",
            price=5000000000000000000,  # 5 testFET
            bond_amount=1000000000000000000,  # 1 testFET
            quote_timestamp=datetime.utcnow(),
            notes="Demo issue creation request"
        )
        
        # Save to database
        state_manager.create_job(job_record)
        
        # Broadcast status update
        await manager.broadcast({
            "type": "job_update",
            "job_id": job_id,
            "status": "REQUESTED",
            "message": f"Job {job_id} created - requesting quote from tool agent"
        })
        
        # Simulate quote phase
        await asyncio.sleep(1)
        state_manager.update_job(job_id, {
            "status": JobStatus.QUOTED,
            "notes": job_record.notes + "\\nQuote received from tool agent"
        })
        
        await manager.broadcast({
            "type": "job_update",
            "job_id": job_id,
            "status": "QUOTED",
            "message": f"Quote received: 5.0 testFET + 1.0 testFET bond"
        })
        
        # Simulate acceptance
        await asyncio.sleep(1)
        state_manager.update_job(job_id, {
            "status": JobStatus.IN_PROGRESS,
            "perform_timestamp": datetime.utcnow(),
            "notes": job_record.notes + "\\nQuote accepted, execution started"
        })
        
        await manager.broadcast({
            "type": "job_update",
            "job_id": job_id,
            "status": "IN_PROGRESS",
            "message": f"Executing task: Creating GitHub issue..."
        })
        
        # Actually create the GitHub issue
        issue_url, api_url = await github_api.create_issue(
            title,
            job_record.payload["body"],
            label_list
        )
        
        # Update job as completed
        state_manager.update_job(job_id, {
            "status": JobStatus.COMPLETED,
            "completion_timestamp": datetime.utcnow(),
            "notes": job_record.notes + f"\\nGitHub issue created: {issue_url}"
        })
        
        await manager.broadcast({
            "type": "job_update",
            "job_id": job_id,
            "status": "COMPLETED",
            "message": f"GitHub issue created successfully!",
            "issue_url": issue_url
        })
        
        # Simulate verification
        await asyncio.sleep(2)
        
        try:
            verification_result = await github_api.verify_issue(api_url, title)
            
            if verification_result["verified"]:
                state_manager.update_job(job_id, {
                    "status": JobStatus.VERIFIED,
                    "verification_timestamp": datetime.utcnow(),
                    "notes": job_record.notes + f"\\nVerification passed: {verification_result['details']}"
                })
                
                await manager.broadcast({
                    "type": "job_update",
                    "job_id": job_id,
                    "status": "VERIFIED",
                    "message": "✅ Verification passed! Processing payment..."
                })
                
                # Simulate payment
                await asyncio.sleep(1)
                state_manager.update_job(job_id, {
                    "status": JobStatus.PAID,
                    "payment_timestamp": datetime.utcnow(),
                    "notes": job_record.notes + f"\\nPayment sent: demo_tx_hash_{job_id[-8:]}"
                })
                
                await manager.broadcast({
                    "type": "job_update",
                    "job_id": job_id,
                    "status": "PAID",
                    "message": "💰 Payment sent! Job completed successfully!",
                    "issue_url": issue_url,
                    "final": True
                })
                
            else:
                state_manager.update_job(job_id, {
                    "status": JobStatus.FAILED,
                    "notes": job_record.notes + f"\\nVerification failed: {verification_result['details']}"
                })
                
                await manager.broadcast({
                    "type": "job_update",
                    "job_id": job_id,
                    "status": "FAILED",
                    "message": f"❌ Verification failed: {verification_result['details']}"
                })
                
        except Exception as e:
            state_manager.update_job(job_id, {
                "status": JobStatus.FAILED,
                "notes": job_record.notes + f"\\nVerification error: {str(e)}"
            })
            
            await manager.broadcast({
                "type": "job_update",
                "job_id": job_id,
                "status": "FAILED",
                "message": f"❌ Verification error: {str(e)}"
            })
        
        return {"success": True, "job_id": job_id, "issue_url": issue_url}
        
    except GitHubAPIError as e:
        await manager.broadcast({
            "type": "error",
            "message": f"GitHub API error: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")
        
    except Exception as e:
        await manager.broadcast({
            "type": "error",
            "message": f"Unexpected error: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/jobs")
async def get_jobs():
    """Get all jobs from database"""
    try:
        jobs = state_manager.get_jobs_by_agent("demo_client", role="any")
        return {
            "jobs": [
                {
                    "job_id": job.job_id,
                    "task": job.task.value,
                    "status": job.status.value,
                    "title": job.payload.get("title", "N/A"),
                    "created_at": job.quote_timestamp.isoformat() if job.quote_timestamp else None,
                    "completed_at": job.completion_timestamp.isoformat() if job.completion_timestamp else None,
                    "notes": job.notes
                }
                for job in jobs[:20]  # Latest 20 jobs
            ]
        }
    except Exception as e:
        return {"error": str(e), "jobs": []}

@app.get("/agent-status")
async def get_agent_status():
    """Get status of agents"""
    return {
        "tool_agent": {
            "address": "agent1qfydudacecdkj47ac0wt4587a5w25pssllam7s4zdnaylxvtfvguwq4tfpt",
            "status": "Available",
            "port": 8001,
            "services": ["GitHub Issue Creation"]
        },
        "client_agent": {
            "address": "agent1qgpc60trhz6unzzgtjykw8nwtfzak780r3pu96kl73ffcnv5kfdtsvtf906",
            "status": "Available", 
            "port": 8002,
            "services": ["Task Verification", "Payment Processing"]
        },
        "github_api": {
            "configured": github_api is not None,
            "repo": os.getenv("GITHUB_REPO", "Not configured")
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        # Send initial status
        await manager.send_personal_message({
            "type": "connected",
            "message": "Connected to marketplace demo"
        }, websocket)
        
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await manager.send_personal_message({
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)