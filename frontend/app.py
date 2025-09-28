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
import httpx

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, HTTPException, Body
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

# Simple in-memory tool agent registry for demo
# address -> info dict
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}

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

# Helper: parse status string to JobStatus
_STATUS_MAP = {s.name: s for s in JobStatus}
_STATUS_VALUE_MAP = {s.value: s for s in JobStatus}

def _parse_status(status_in: str) -> JobStatus:
    if not status_in:
        return JobStatus.REQUESTED
    s = status_in.strip()
    # Accept names like "IN_PROGRESS" and values like "in_progress"
    if s.upper() in _STATUS_MAP:
        return _STATUS_MAP[s.upper()]
    if s.lower() in _STATUS_VALUE_MAP:
        return _STATUS_VALUE_MAP[s.lower()]
    # Fallback
    try:
        return JobStatus(s.lower())
    except Exception:
        return JobStatus.REQUESTED

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
    """Proxy: ask the client agent to create a GitHub issue (real agent flow)"""
    try:
        # Parse labels
        label_list = [label.strip() for label in labels.split(",") if label.strip()]
        # Post command to client agent control server
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8102/create-issue",
                json={"title": title, "body": body, "labels": label_list, "prefer_bad": True},
            )
            if resp.status_code >= 300:
                raise HTTPException(status_code=500, detail=f"Client control error: {resp.text}")
        # Let the WebSocket stream actual progress from agents
        await manager.broadcast({
            "type": "job_update",
            "status": "REQUESTED",
            "source": "frontend",
            "message": f"Client instructed to request GitHub issue: {title}",
        })
        return {"success": True}
    except Exception as e:
        await manager.broadcast({"type": "error", "message": f"Client control error: {e}"})
        raise

@app.post("/agent-event")
async def receive_agent_event(payload: Dict[str, Any] = Body(...)):
    """Receive events from agents and broadcast to dashboard.
    Expected JSON payload fields:
      - source: 'client' | 'tool' | 'frontend'
      - status: REQUESTED|QUOTED|ACCEPTED|BONDED|IN_PROGRESS|COMPLETED|VERIFIED|PAID|FAILED|AVAILABLE
      - message: human-readable log
      - job_id: optional job identifier
      - issue_url: optional URL
      - payload, price, bond_amount, client_address, tool_address: optional
      - agent_info or tool_info: optional registration dictionaries
    """
    try:
        source = str(payload.get("source", "agent")).lower()
        status_str = str(payload.get("status", "REQUESTED"))
        message = str(payload.get("message", ""))
        job_id = payload.get("job_id")
        issue_url = payload.get("issue_url")
        job_payload = payload.get("payload") or {}
        price = payload.get("price")
        bond_amount = payload.get("bond_amount")
        client_address = payload.get("client_address")
        tool_address = payload.get("tool_address")
        agent_info = payload.get("agent_info")
        tool_info = payload.get("tool_info")
        
        status_enum = _parse_status(status_str)

        # Registry updates
        if tool_info and isinstance(tool_info, dict):
            addr = tool_info.get("address") or tool_address
            if addr:
                TOOL_REGISTRY[addr] = {
                    **TOOL_REGISTRY.get(addr, {}),
                    **tool_info,
                }
                # Broadcast agent update
                await manager.broadcast({
                    "type": "agent_update",
                    "source": source,
                    "agent": TOOL_REGISTRY[addr],
                })
        if agent_info and isinstance(agent_info, dict):
            # client or other agent info; optionally track if useful
            await manager.broadcast({
                "type": "agent_update",
                "source": source,
                "agent": agent_info,
            })

        # Upsert job in local dashboard DB if we have a job_id
        if job_id:
            existing = state_manager.get_job(job_id)
            if not existing:
                # Create a minimal JobRecord
                jr = JobRecord(
                    job_id=job_id,
                    task=TaskType.CREATE_GITHUB_ISSUE,  # default for now
                    payload=job_payload if isinstance(job_payload, dict) else {},
                    status=status_enum,
                    client_address=client_address,
                    tool_address=tool_address,
                    price=price,
                    bond_amount=bond_amount,
                    quote_timestamp=datetime.utcnow(),
                    notes=f"Created via agent-event from {source}"
                )
                state_manager.create_job(jr)
            else:
                # Update existing
                updates: Dict[str, Any] = {
                    "status": status_enum,
                    "notes": (existing.notes or "") + f"\n[{source}] {message}",
                }
                if price is not None:
                    updates["price"] = price
                if bond_amount is not None:
                    updates["bond_amount"] = bond_amount
                if job_payload:
                    updates["payload"] = job_payload
                if client_address:
                    updates["client_address"] = client_address
                if tool_address:
                    updates["tool_address"] = tool_address
                if status_enum == JobStatus.IN_PROGRESS:
                    updates["perform_timestamp"] = datetime.utcnow()
                elif status_enum == JobStatus.COMPLETED:
                    updates["completion_timestamp"] = datetime.utcnow()
                elif status_enum == JobStatus.VERIFIED:
                    updates["verification_timestamp"] = datetime.utcnow()
                elif status_enum == JobStatus.PAID:
                    updates["payment_timestamp"] = datetime.utcnow()
                state_manager.update_job(job_id, updates)

        # Broadcast to clients (job updates)
        broadcast_payload = {
            "type": "job_update",
            "source": source,
            "job_id": job_id or "",
            "status": status_enum.name,
            "message": message,
            "issue_url": issue_url,
        }
        # Pass through common extra fields for UI
        if payload.get("tx_hash"):
            broadcast_payload["tx_hash"] = payload.get("tx_hash")
        if price is not None:
            broadcast_payload["price"] = price
        if bond_amount is not None:
            broadcast_payload["bond_amount"] = bond_amount

        await manager.broadcast(broadcast_payload)
        return {"ok": True}
    except Exception as e:
        await manager.broadcast({
            "type": "error",
            "message": f"Agent event error: {str(e)}"
        })
        raise HTTPException(status_code=400, detail=str(e))


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

@app.get("/agents")
async def get_agents(task: Optional[str] = None):
    """Return tool agents from registry, optionally filtered by task capability"""
    try:
        agents = list(TOOL_REGISTRY.values())
        if task:
            task_lower = task.lower()
            agents = [a for a in agents if task_lower in [c.lower() for c in a.get("capabilities", [])]]
        return {"agents": agents}
    except Exception as e:
        return {"agents": [], "error": str(e)}


@app.post("/translate")
async def translate_endpoint(
    text: str = Form(...),
    target_lang: str = Form(default="en")
):
    """Proxy: ask the client agent to translate text"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8102/translate",
                json={"text": text, "target_lang": target_lang},
            )
            if resp.status_code >= 300:
                raise HTTPException(status_code=500, detail=f"Client control error: {resp.text}")
        await manager.broadcast({
            "type": "job_update",
            "status": "REQUESTED",
            "source": "frontend",
            "message": f"Client instructed to translate to {target_lang}",
        })
        return {"success": True}
    except Exception as e:
        await manager.broadcast({"type": "error", "message": f"Client control error: {e}"})
        raise


@app.post("/ask-client")
async def ask_client_endpoint(text: str = Form(...)):
    """Proxy: ask the client agent to infer intent (via ASI) and route the task"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8102/ask",
                json={"text": text},
            )
            if resp.status_code >= 300:
                raise HTTPException(status_code=500, detail=f"Client control error: {resp.text}")
        await manager.broadcast({
            "type": "job_update",
            "status": "REQUESTED",
            "source": "frontend",
            "message": f"Client instructed (ASI) to handle: {text[:80]}...",
        })
        return {"success": True}
    except Exception as e:
        await manager.broadcast({"type": "error", "message": f"Client control error: {e}"})
        raise


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