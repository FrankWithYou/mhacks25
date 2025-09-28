"""
Client agent implementation for the marketplace.
This agent requests services from tool agents, verifies results, and handles payments.
"""

import os
import time
import logging
import asyncio
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from aiohttp import web

from models.messages import (
    QuoteRequest, QuoteResponse, PerformRequest, Receipt, 
    TaskType, JobStatus, JobRecord, PaymentNotification
)
from utils.verifier import TaskVerifier
from utils.crypto import (
    compute_terms_hash, create_client_signature
)
from utils.state_manager import StateManager
from utils.payment import PaymentManager, PaymentError
from utils.frontend_events import send_frontend_event, discover_agents, filter_reachable_agents
from utils.asi import infer_intent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the client agent
client_agent = Agent(
    name="marketplace_client",
    port=8002,
    seed="marketplace_client_secret_seed_phrase",  # In production, use proper seed management
    endpoint=["http://127.0.0.1:8002/submit"]
)

# Initialize components
state_manager = StateManager("client_agent.db")
task_verifier = TaskVerifier.create_github_verifier()
payment_manager = PaymentManager(client_agent)  # Pass agent instance for wallet access
CLIENT_SIGNING_KEY = "client_agent_private_key_secret"  # In production, use proper key management
TOOL_PUBLIC_KEY = "tool_agent_private_key_secret"  # Should match tool's signing key for MVP

# Map job_id -> tool_pubkey for signature verification
TOOL_KEYS: dict[str, str] = {}

# Map job_id -> original request payload
PENDING_REQUESTS: dict[str, dict] = {}

# Control queue for receiving HTTP commands
CONTROL_QUEUE: asyncio.Queue = asyncio.Queue()

# Known tool agent address (in production, this would be discovered via Agentverse)
KNOWN_TOOL_AGENT = "agent1qfydudacecdkj47ac0wt4587a5w25pssllam7s4zdnaylxvtfvguwq4tfpt"  # Tool agent address from startup

# Initialize the chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    """Create a text-based chat message"""
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=client_agent.name + "_" + str(datetime.utcnow().timestamp()),
        content=content,
    )

@client_agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize the client agent on startup"""
    try:
        logger.info(f"Client agent {client_agent.address} started successfully")
        
        # Fund agent if low on tokens
        fund_agent_if_low(client_agent.wallet.address())
        
        # Ensure minimum balance for operations (best-effort)
        try:
            required_balance = payment_manager.get_default_price_amount() + payment_manager.get_default_bond_amount()
            await payment_manager.ensure_minimum_balance(ctx, required_balance)
        except Exception as e:
            ctx.logger.warning(f"Skipping minimum balance check: {e}")
        
        # Start lightweight control HTTP server for frontend commands
        asyncio.create_task(start_control_server())
        
        # Emit agent online event with Fetch-related details
        try:
            balance = await payment_manager.get_balance(ctx)
        except Exception:
            balance = 0
        # Resolve wallet address compatibly
        try:
            wallet_address = ctx.wallet.address()  # type: ignore[attr-defined]
        except Exception:
            try:
                wallet_address = ctx.agent.wallet.address()  # type: ignore[attr-defined]
            except Exception:
                wallet_address = "unknown"
        await send_frontend_event(
            source="client",
            status="AVAILABLE",
            message="Client agent online",
            extra={
                "agent_info": {
                    "address": str(client_agent.address),
                    "wallet_address": wallet_address,
                    "chat_enabled": True,
                    "manifest_published": True,
                    "balance_atestfet": balance,
                }
            },
        )

        ctx.logger.info("Client agent initialization complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize client agent: {e}")
        ctx.logger.error(f"Startup error: {e}")

async def request_github_issue(ctx: Context, tool_agent_address: str, title: str, 
                             body: str = "", labels: list = None) -> str:
    """
    Request GitHub issue creation from a tool agent
    
    Args:
        ctx: Agent context
        tool_agent_address: Address of the tool agent
        title: Issue title
        body: Issue body
        labels: Issue labels
        
    Returns:
        Job ID for tracking
    """
    try:
        # Create payload
        payload = {
            "title": title,
            "body": body or f"Issue created by marketplace client\nRequested at: {datetime.utcnow().isoformat()}",
            "labels": labels or ["innovationlab", "hackathon"]
        }
        
        # Store payload for later use
        job_id_temp = f"issue_{int(time.time() * 1000)}"
        PENDING_REQUESTS[job_id_temp] = payload
        
        # Create quote request
        quote_request = QuoteRequest(
            task=TaskType.CREATE_GITHUB_ISSUE,
            payload=payload,
            client_address=str(ctx.agent.address),
            timestamp=datetime.utcnow()
        )
        
        # Send quote request
        await ctx.send(tool_agent_address, quote_request)
        
        ctx.logger.info(f"Sent quote request to {tool_agent_address} for GitHub issue: {title}")
        return job_id_temp
        
    except Exception as e:
        ctx.logger.error(f"Error requesting GitHub issue: {e}")
        raise e

@client_agent.on_message(QuoteResponse)
async def handle_quote_response(ctx: Context, sender: str, msg: QuoteResponse):
    """Handle quote responses from tool agents"""
    ctx.logger.info(f"Received quote from {sender}: {msg.job_id} - {msg.price} {msg.denom}")
    
    try:
        # Emit frontend events to start job tracking and show quote
        task_name = msg.task.value if msg.task else "task"
        await send_frontend_event(
            source="client",
            status="REQUESTED",
            message=f"Request sent to tool {sender} for {task_name}",
            job_id=msg.job_id,
            extra={
                "price": msg.price,
                "bond_amount": msg.bond_required,
                "tool_address": sender,
                "client_address": str(ctx.agent.address),
            },
        )
        await send_frontend_event(
            source="client",
            status="QUOTED",
            message=f"Quote received: {msg.price} {msg.denom} + bond {msg.bond_required}",
            job_id=msg.job_id,
            extra={
                "price": msg.price,
                "bond_amount": msg.bond_required,
                "tool_address": sender,
                "client_address": str(ctx.agent.address),
            },
        )

        # Store tool pubkey for this job (fallback to default)
        if msg.tool_pubkey:
            TOOL_KEYS[msg.job_id] = msg.tool_pubkey
        else:
            TOOL_KEYS[msg.job_id] = TOOL_PUBLIC_KEY

        # Get the original request payload
        # Since we don't have the job_id when making the request, we need to infer it from the task type
        original_payload = {}
        if msg.task == TaskType.TRANSLATE_TEXT:
            # For translation, find the most recent translation request
            for key in list(PENDING_REQUESTS.keys()):
                if key.startswith("translate_"):
                    original_payload = PENDING_REQUESTS.pop(key)
                    break
        elif msg.task == TaskType.CREATE_GITHUB_ISSUE:
            # For GitHub issues, find the most recent issue request
            for key in list(PENDING_REQUESTS.keys()):
                if key.startswith("issue_"):
                    original_payload = PENDING_REQUESTS.pop(key)
                    break
        
        job_record = JobRecord(
            job_id=msg.job_id,
            task=msg.task or TaskType.CREATE_GITHUB_ISSUE,  # default if not provided
            payload=original_payload,  # Store original request payload
            status=JobStatus.QUOTED,
            client_address=str(ctx.agent.address),
            tool_address=sender,
            price=msg.price,
            bond_amount=msg.bond_required,
            quote_timestamp=datetime.utcnow(),
            notes=f"Quote received from {sender}"
        )
        
        # Save job record
        if not state_manager.create_job(job_record):
            ctx.logger.error(f"Failed to save job record for {msg.job_id}")
            return
        
        # Check if we have sufficient balance (best-effort; do not block demo)
        total_required = msg.price + msg.bond_required
        try:
            current_balance = await payment_manager.get_balance(ctx)
            if current_balance < total_required:
                ctx.logger.warning(f"Insufficient balance for job {msg.job_id}: need {total_required}, have {current_balance}")
                # Continue anyway for demo; payment will fail later if actually insufficient
        except Exception as e:
            ctx.logger.warning(f"Balance check unavailable, proceeding: {e}")
        
        # Auto-accept the quote for demo purposes
        # In a production system, this would be user-driven
        await accept_quote(ctx, msg, sender)
        
    except Exception as e:
        ctx.logger.error(f"Error handling quote response: {e}")

async def accept_quote(ctx: Context, quote: QuoteResponse, tool_address: str):
    """Accept a quote and send perform request"""
    try:
        ctx.logger.info(f"Accepting quote {quote.job_id} from {tool_address}")
        
        # Get the job record to retrieve the original payload
        job_record = state_manager.get_job(quote.job_id)
        if not job_record:
            ctx.logger.error(f"Job record not found for {quote.job_id}")
            return
            
        # Use the original payload from the job record or create a default one
        payload = job_record.payload if job_record.payload else {}
        
        # If no payload exists, create appropriate default based on task type
        if not payload:
            if quote.task == TaskType.CREATE_GITHUB_ISSUE:
                payload = {
                    "title": "Demo GitHub Issue from Marketplace",
                    "body": f"This issue was created through the trust-minimized agent marketplace\n\nJob ID: {quote.job_id}\nTimestamp: {datetime.utcnow().isoformat()}",
                    "labels": ["innovationlab", "hackathon", "demo"]
                }
            elif quote.task == TaskType.TRANSLATE_TEXT:
                # This shouldn't happen, but provide a fallback
                payload = {
                    "text": "Hello",
                    "source_lang": "auto",
                    "target_lang": "es"
                }
        
        # Create client signature
        timestamp = datetime.utcnow()
        client_signature = create_client_signature(
            quote.job_id, 
            quote.terms_hash, 
            timestamp, 
            CLIENT_SIGNING_KEY
        )
        
        # Create perform request
        perform_request = PerformRequest(
            job_id=quote.job_id,
            payload=payload,
            terms_hash=quote.terms_hash,
            client_signature=client_signature,
            timestamp=timestamp
        )
        
        # Update job record
        state_manager.update_job(quote.job_id, {
            "status": JobStatus.ACCEPTED,
            "perform_timestamp": timestamp,
            "payload": perform_request.payload,
            "notes": f"Quote accepted, perform request sent to {tool_address}"
        })

        # Frontend event: accepted
        await send_frontend_event(
            source="client",
            status="ACCEPTED",
            message="Quote accepted, perform request sent",
            job_id=quote.job_id,
            extra={
                "tool_address": tool_address,
                "client_address": str(ctx.agent.address),
            },
        )
        
        # Send perform request
        await ctx.send(tool_address, perform_request)
        
        ctx.logger.info(f"Sent perform request for job {quote.job_id}")
        
    except Exception as e:
        ctx.logger.error(f"Error accepting quote: {e}")
        state_manager.update_job(quote.job_id, {
            "status": JobStatus.FAILED,
            "notes": f"Error accepting quote: {str(e)}"
        })

@client_agent.on_message(Receipt)
async def handle_receipt(ctx: Context, sender: str, msg: Receipt):
    """Handle task completion receipts"""
    ctx.logger.info(f"Received receipt from {sender} for job {msg.job_id}")
    
    try:
        # Get job record
        job_record = state_manager.get_job(msg.job_id)
        if not job_record:
            ctx.logger.warning(f"Job {msg.job_id} not found")
            return
        
        # Verify sender
        if job_record.tool_address != sender:
            ctx.logger.warning(f"Receipt from unauthorized sender: {sender} != {job_record.tool_address}")
            return
        
        # Update job with receipt
        state_manager.update_job(msg.job_id, {
            "status": JobStatus.COMPLETED,
            "completion_timestamp": datetime.utcnow(),
            "receipt": msg,
            "notes": job_record.notes + f"\\nReceipt received: {msg.output_ref}"
        })

        # Frontend event: completed (receipt received)
        await send_frontend_event(
            source="client",
            status="COMPLETED",
            message="Receipt received from tool",
            job_id=msg.job_id,
            issue_url=msg.output_ref,
        )
        
        # Perform verification
        await verify_and_pay(ctx, job_record, msg)
        
    except Exception as e:
        ctx.logger.error(f"Error handling receipt: {e}")

async def verify_and_pay(ctx: Context, job_record: JobRecord, receipt: Receipt):
    """Verify task completion and process payment"""
    try:
        ctx.logger.info(f"Verifying and processing payment for job {job_record.job_id}")
        
        # Perform verification
        tool_pubkey = TOOL_KEYS.get(job_record.job_id, TOOL_PUBLIC_KEY)
        verification_result = await task_verifier.verify_task_completion(
            receipt, 
            job_record.task, 
            tool_pubkey
        )
        
        # Update job with verification result
        state_manager.update_job(job_record.job_id, {
            "verification_timestamp": datetime.utcnow(),
            "verification_result": verification_result,
            "notes": job_record.notes + f"\\nVerification: {verification_result.details}"
        })
        
        if verification_result.verified:
            ctx.logger.info(f"Verification passed for job {job_record.job_id}")

            # Frontend event: verified
            await send_frontend_event(
                source="client",
                status="VERIFIED",
                message=verification_result.details or "Verification passed",
                job_id=job_record.job_id,
            )
            
            # Send payment
            try:
                tx_hash = await payment_manager.send_job_payment(
                    ctx,
                    job_record.tool_address,
                    job_record.price,
                    job_record.job_id
                )
                
                if tx_hash:
                    # Send payment notification
                    payment_notification = PaymentNotification(
                        job_id=job_record.job_id,
                        tx_hash=tx_hash,
                        amount=job_record.price,
                        sender=str(ctx.agent.address),
                        timestamp=datetime.utcnow()
                    )
                    
                    await ctx.send(job_record.tool_address, payment_notification)
                    
                    # Update job status
                    state_manager.update_job(job_record.job_id, {
                        "status": JobStatus.PAID,
                        "payment_timestamp": datetime.utcnow(),
                        "notes": job_record.notes + f"\\nPayment sent: {tx_hash}"
                    })

                    # Frontend event: paid
                    await send_frontend_event(
                        source="client",
                        status="PAID",
                        message=f"Payment sent: {tx_hash}",
                        job_id=job_record.job_id,
                        issue_url=receipt.output_ref,
                        extra={"tx_hash": tx_hash},
                    )
                    
                    ctx.logger.info(f"Payment sent for job {job_record.job_id}: {tx_hash}")
                    ctx.logger.info(f"Task completed successfully! GitHub issue: {receipt.output_ref}")
                    
                else:
                    raise PaymentError("Payment transaction failed")
                    
            except PaymentError as e:
                # Allow simulated payment for demo when wallet/ledger is unavailable
                # Default to enabled for demo purposes
                simulate = os.getenv("SIMULATE_PAYMENT", "1").strip().lower() in ("1", "true", "yes")
                if simulate:
                    tx_hash = f"demo_tx_{job_record.job_id[:8]}_{int(time.time())}"
                    # Update job status
                    state_manager.update_job(job_record.job_id, {
                        "status": JobStatus.PAID,
                        "payment_timestamp": datetime.utcnow(),
                        "notes": job_record.notes + f"\\nPayment simulated: {tx_hash} ({str(e)})"
                    })
                    # Frontend event: paid (simulated)
                    await send_frontend_event(
                        source="client",
                        status="PAID",
                        message=f"Payment simulated: {tx_hash}",
                        job_id=job_record.job_id,
                        issue_url=receipt.output_ref,
                        extra={"tx_hash": tx_hash},
                    )
                    ctx.logger.info(f"Payment simulated for job {job_record.job_id}: {tx_hash}")
                else:
                    ctx.logger.error(f"Payment failed for job {job_record.job_id}: {e}")
                    state_manager.update_job(job_record.job_id, {
                        "status": JobStatus.FAILED,
                        "notes": job_record.notes + f"\\nPayment failed: {str(e)}"
                    })
                    await send_frontend_event(
                        source="client",
                        status="FAILED",
                        message=f"Payment failed: {str(e)}",
                        job_id=job_record.job_id,
                    )
        else:
            ctx.logger.warning(f"Verification failed for job {job_record.job_id}: {verification_result.details}")
            state_manager.update_job(job_record.job_id, {
                "status": JobStatus.FAILED,
                "notes": job_record.notes + f"\\nVerification failed: {verification_result.details}"
            })
            # Frontend event: failed
            await send_frontend_event(
                source="client",
                status="FAILED",
                message=f"Verification failed: {verification_result.details}",
                job_id=job_record.job_id,
            )
            
    except Exception as e:
        ctx.logger.error(f"Error in verify_and_pay: {e}")
        state_manager.update_job(job_record.job_id, {
            "status": JobStatus.FAILED,
            "notes": job_record.notes + f"\\nVerification error: {str(e)}"
        })
        await send_frontend_event(
            source="client",
            status="FAILED",
            message=f"Verification error: {str(e)}",
            job_id=job_record.job_id,
        )

# Chat protocol handlers for ASI:One integration
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming chat messages from ASI:One"""
    ctx.logger.info(f"Received chat message from {sender}")
    
    # Send acknowledgement
    ack = ChatAcknowledgement(
        timestamp=datetime.utcnow(),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)
    
    # Process message content
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            ctx.logger.info(f"Chat session started with {sender}")
            
        elif isinstance(item, TextContent):
            ctx.logger.info(f"Text message from {sender}: {item.text}")
            
            # Process the chat request
            response_text = await process_client_chat_request(ctx, sender, item.text)
            
            # Send response
            response_message = create_text_chat(response_text)
            await ctx.send(sender, response_message)
            
        elif isinstance(item, EndSessionContent):
            ctx.logger.info(f"Chat session ended with {sender}")
            
        else:
            ctx.logger.info(f"Received unexpected content type from {sender}")

async def process_client_chat_request(ctx: Context, sender: str, text: str) -> str:
    """Process chat requests from users"""
    text_lower = text.lower()
    
    try:
        if "create issue" in text_lower or "github issue" in text_lower:
            # Extract title from the request
            if "title:" in text_lower:
                title = text.split("title:")[1].split("\\n")[0].strip()
            else:
                title = f"Issue from chat: {text[:50]}..."

            # Discover available tool agents via frontend registry
            agents = await discover_agents(TaskType.CREATE_GITHUB_ISSUE.value)
            # Prefer reachable agents
            agents = await filter_reachable_agents(agents)
            tool_agent_address = None
            prefer_env = os.getenv("PREFER_BAD_TOOL_AGENT")
            prefer_bad = True if prefer_env is None else prefer_env.strip().lower() in ("1", "true", "yes")
            if agents:
                selected = None
                if prefer_bad:
                    for a in agents:
                        name = (a.get("name") or "").lower()
                        if "bad_tool_agent" in name:
                            selected = a
                            break
                if not selected and agents:
                    # Select the cheapest among reachable
                    selected = sorted(agents, key=lambda a: a.get("price", 10**30))[0]
                if selected:
                    tool_agent_address = selected.get("address")
            # Fallback to known tool agent
            tool_agent_address = tool_agent_address or KNOWN_TOOL_AGENT
            if not tool_agent_address:
                return "No tool agents available for GitHub issue creation."
            # Request the issue
            job_id = await request_github_issue(ctx, tool_agent_address, title)
            return f"I've requested a GitHub issue titled '{title}' from a tool agent. Job tracking ID: {job_id}"

        elif text_lower.startswith("translate"):
            # Parse format: translate: text -> lang
            # Simple parse
            content = text.split(":", 1)[-1].strip() if ":" in text else text.replace("translate", "").strip()
            parts = content.split("->")
            raw_text = parts[0].strip().strip("\"") if parts else content
            target_lang = parts[1].strip() if len(parts) > 1 else "en"

            # Discover translator tools
            agents = await discover_agents(TaskType.TRANSLATE_TEXT.value)
            if not agents:
                return "No translator tool agents available."
            agent_addr = sorted(agents, key=lambda a: a.get("price", 10**30))[0].get("address")

            # Send QuoteRequest
            payload = {"text": raw_text, "source_lang": "auto", "target_lang": target_lang}
            quote_request = QuoteRequest(
                task=TaskType.TRANSLATE_TEXT,
                payload=payload,
                client_address=str(ctx.agent.address),
                timestamp=datetime.utcnow(),
            )
            # Store payload for later use
            job_id_temp = f"translate_{int(time.time() * 1000)}"
            PENDING_REQUESTS[job_id_temp] = payload
            await ctx.send(agent_addr, quote_request)
            return f"Requested translation to {target_lang}. Tracking will appear here shortly."

        elif "status" in text_lower:
            # Get recent jobs
            jobs = state_manager.get_jobs_by_agent(str(ctx.agent.address), "client")
            if jobs:
                recent_job = jobs[0]  # Most recent
                return f"Latest job {recent_job.job_id}: {recent_job.status.value}\\n{recent_job.notes}"
            else:
                return "No jobs found."

        elif "balance" in text_lower:
            balance = await payment_manager.get_balance(ctx)
            formatted_balance = payment_manager.format_amount(balance)
            return f"Current balance: {formatted_balance} ({balance} atestfet)"

        else:
            return (
                "I'm a marketplace client using Fetch.ai uAgents. I can: "
                "• 'create issue: Your Title' (GitHub)\n"
                "• 'translate: Hello -> es' (Translation)\n"
                "• 'status' or 'balance'"
            )

    except Exception as e:
        ctx.logger.error(f"Error processing chat request: {e}")
        return f"Sorry, I encountered an error: {str(e)}"

@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle chat acknowledgements"""
    ctx.logger.info(f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}")

# Add a periodic task to check for pending jobs
@client_agent.on_interval(period=30.0)
async def check_pending_jobs(ctx: Context):
    """Periodically check for jobs that might be stuck or timed out"""
    try:
        # Get jobs that might need attention
        pending_jobs = state_manager.get_jobs_by_status(JobStatus.ACCEPTED, str(ctx.agent.address))
        pending_jobs.extend(state_manager.get_jobs_by_status(JobStatus.IN_PROGRESS, str(ctx.agent.address)))
        
        for job in pending_jobs:
            # Check if job is too old (timeout)
            if job.perform_timestamp and (datetime.utcnow() - job.perform_timestamp).seconds > 600:  # 10 minutes
                ctx.logger.warning(f"Job {job.job_id} appears to have timed out")
                state_manager.update_job(job.job_id, {
                    "status": JobStatus.FAILED,
                    "notes": job.notes + "\\nJob timed out"
                })
                await send_frontend_event(
                    source="client",
                    status="FAILED",
                    message="Job timed out",
                    job_id=job.job_id,
                )
                
    except Exception as e:
        ctx.logger.error(f"Error checking pending jobs: {e}")

# Include the chat protocol and publish manifest to Agentverse
client_agent.include(chat_proto, publish_manifest=True)

# ------------------------
# Control HTTP server impl
# ------------------------
async def start_control_server(host: str = "127.0.0.1", port: int = 8102):
    app = web.Application()

    async def handle_create_issue(request: web.Request):
        data = await request.json()
        title = data.get("title")
        body = data.get("body", "")
        labels = data.get("labels", ["innovationlab", "hackathon"]) or ["innovationlab", "hackathon"]
        prefer_bad = bool(data.get("prefer_bad", True))
        await CONTROL_QUEUE.put({
            "type": "create_issue",
            "title": title,
            "body": body,
            "labels": labels,
            "prefer_bad": prefer_bad,
        })
        return web.json_response({"ok": True})

    async def handle_translate(request: web.Request):
        data = await request.json()
        text = data.get("text", "")
        target_lang = data.get("target_lang", "en")
        await CONTROL_QUEUE.put({
            "type": "translate",
            "text": text,
            "target_lang": target_lang,
        })
        return web.json_response({"ok": True})

    async def handle_ask(request: web.Request):
        data = await request.json()
        text = data.get("text", "")
        await CONTROL_QUEUE.put({
            "type": "ask",
            "text": text,
        })
        return web.json_response({"ok": True})

    app.add_routes([
        web.post("/create-issue", handle_create_issue),
        web.post("/translate", handle_translate),
        web.post("/ask", handle_ask),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()


@client_agent.on_interval(period=1.0)
async def process_control_queue(ctx: Context):
    try:
        while not CONTROL_QUEUE.empty():
            cmd = await CONTROL_QUEUE.get()
            if cmd.get("type") == "create_issue":
                # Discover tool and send quote via existing helper
                agents = await discover_agents(TaskType.CREATE_GITHUB_ISSUE.value)
                agents = await filter_reachable_agents(agents)
                tool_agent_address = None
                prefer_bad = cmd.get("prefer_bad", True)
                if agents:
                    selected = None
                    if prefer_bad:
                        for a in agents:
                            name = (a.get("name") or "").lower()
                            if "bad_tool_agent" in name:
                                selected = a
                                break
                    if not selected and agents:
                        selected = sorted(agents, key=lambda a: a.get("price", 10**30))[0]
                    if selected:
                        tool_agent_address = selected.get("address")
                if not tool_agent_address:
                    # Fallback to known
                    tool_agent_address = KNOWN_TOOL_AGENT
                if tool_agent_address:
                    await request_github_issue(ctx, tool_agent_address, cmd.get("title") or "Issue from UI", cmd.get("body") or "", cmd.get("labels") or ["innovationlab", "hackathon"]) 
            elif cmd.get("type") == "translate":
                agents = await discover_agents(TaskType.TRANSLATE_TEXT.value)
                agents = await filter_reachable_agents(agents)
                if agents:
                    agent_addr = sorted(agents, key=lambda a: a.get("price", 10**30))[0].get("address")
                payload = {"text": cmd.get("text", ""), "source_lang": "auto", "target_lang": cmd.get("target_lang", "en")}
                quote_request = QuoteRequest(
                    task=TaskType.TRANSLATE_TEXT,
                    payload=payload,
                    client_address=str(ctx.agent.address),
                    timestamp=datetime.utcnow(),
                )
                # Store payload for later use
                job_id_temp = f"translate_{int(time.time() * 1000)}"
                PENDING_REQUESTS[job_id_temp] = payload
                await ctx.send(agent_addr, quote_request)
            elif cmd.get("type") == "ask":
                text = cmd.get("text", "")
                intent = infer_intent(text)
                task = intent.get("task")
                payload = intent.get("payload", {})
                if task == TaskType.CREATE_GITHUB_ISSUE.value:
                    # route to issue
                    title = payload.get("title") or text[:80]
                    body = payload.get("body", text)
                    agents = await discover_agents(TaskType.CREATE_GITHUB_ISSUE.value)
                    agents = await filter_reachable_agents(agents)
                    tool_agent_address = None
                    if agents:
                        selected = sorted(agents, key=lambda a: a.get("price", 10**30))[0]
                        tool_agent_address = selected.get("address")
                    if tool_agent_address:
                        await request_github_issue(ctx, tool_agent_address, title, body, payload.get("labels"))
                elif task == TaskType.TRANSLATE_TEXT.value:
                    agents = await discover_agents(TaskType.TRANSLATE_TEXT.value)
                    agents = await filter_reachable_agents(agents)
                    if agents:
                        agent_addr = sorted(agents, key=lambda a: a.get("price", 10**30))[0].get("address")
                        request_payload = {"text": payload.get("text", text), "source_lang": "auto", "target_lang": payload.get("target_lang", "en")}
                        quote_request = QuoteRequest(
                            task=TaskType.TRANSLATE_TEXT,
                            payload=request_payload,
                            client_address=str(ctx.agent.address),
                            timestamp=datetime.utcnow(),
                        )
                        # Store payload for later use
                        job_id_temp = f"translate_{int(time.time() * 1000)}"
                        PENDING_REQUESTS[job_id_temp] = request_payload
                        await ctx.send(agent_addr, quote_request)
    except Exception as e:
        ctx.logger.error(f"Control queue processing error: {e}")


if __name__ == "__main__":
    logger.info("Starting Marketplace Client Agent...")
    client_agent.run()
