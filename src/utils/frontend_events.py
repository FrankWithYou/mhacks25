"""
Utility to emit agent events to the demo frontend so every step is visible in the dashboard.
"""

import os
import logging
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000")
EVENT_ENDPOINT = "/agent-event"


async def send_frontend_event(
    *,
    source: str,
    status: str,
    message: str,
    job_id: Optional[str] = None,
    issue_url: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Post an event to the frontend for broadcasting to all dashboard clients.

    Args:
        source: "client" or "tool" (or another identifier)
        status: One of REQUESTED, QUOTED, ACCEPTED, BONDED, IN_PROGRESS, COMPLETED, VERIFIED, PAID, FAILED
        message: Human-readable message
        job_id: Optional job identifier for correlating events
        issue_url: Optional URL to created resource (e.g., GitHub issue)
        extra: Additional fields to include (dict)
    """
    url = FRONTEND_URL.rstrip("/") + EVENT_ENDPOINT
    payload: Dict[str, Any] = {
        "source": source,
        "status": status,
        "message": message,
    }
    if job_id:
        payload["job_id"] = job_id
    if issue_url:
        payload["issue_url"] = issue_url
    if extra:
        payload.update(extra)

    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 300:
                logger.debug(f"Frontend event post non-OK: {resp.status_code} {resp.text}")
    except Exception as e:
        # Never fail agent logic due to UI; just log debug
        logger.debug(f"Failed to post frontend event: {e}")


async def discover_agents(task: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Query the frontend registry for available tool agents.

    Args:
        task: Optional task string (e.g., "create_github_issue") to filter capabilities

    Returns:
        List of agent dicts with keys like address, name, capabilities, price, bond.
    """
    base = FRONTEND_URL.rstrip("/")
    url = f"{base}/agents"
    params = {}
    if task:
        params["task"] = task
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("agents", [])
            else:
                logger.debug(f"Agent discovery non-OK: {resp.status_code} {resp.text}")
                return []
    except Exception as e:
        logger.debug(f"Agent discovery failed: {e}")
        return []


async def filter_reachable_agents(agents: List[Dict[str, Any]], timeout: float = 0.5) -> List[Dict[str, Any]]:
    """
    Filter agents to those reachable on their advertised local port (demo/local only).
    Assumes agents run on 127.0.0.1 and provide a 'port' field in tool_info.
    """
    reachable: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for a in agents:
            port = a.get("port")
            if not port:
                # If no port info, keep agent (could be remote)
                reachable.append(a)
                continue
            url = f"http://127.0.0.1:{port}/"
            try:
                # Any response (even 404) means the port is open and reachable
                await client.get(url)
                reachable.append(a)
            except Exception:
                # Not reachable; skip
                continue
    return reachable
