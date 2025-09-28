"""
Client agent implementation for the marketplace.
This agent requests services from tool agents, verifies results, and handles payments.
"""

import asyncio
import os
import logging
from datetime import datetime, timedelta
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
payment_manager = PaymentManager()
CLIENT_SIGNING_KEY = "client_agent_private_key_secret"  # In production, use proper key management
TOOL_PUBLIC_KEY = "tool_agent_private_key_secret"  # Should match tool's signing key for MVP

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
        
        # Ensure minimum balance for operations
        required_balance = payment_manager.get_default_price_amount() + payment_manager.get_default_bond_amount()
        await payment_manager.ensure_minimum_balance(ctx, required_balance)
        
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
        # Create quote request
        quote_request = QuoteRequest(
            task=TaskType.CREATE_GITHUB_ISSUE,
            payload={
                "title": title,
                "body": body or f"Issue created by marketplace client\\nRequested at: {datetime.utcnow().isoformat()}",
                "labels": labels or ["innovationlab", "hackathon"]
            },
            client_address=str(ctx.agent.address),
            timestamp=datetime.utcnow()
        )
        
        # Send quote request
        await ctx.send(tool_agent_address, quote_request)
        
        ctx.logger.info(f"Sent quote request to {tool_agent_address} for GitHub issue: {title}")
        return f"quote_request_{datetime.utcnow().timestamp()}"
        
    except Exception as e:
        ctx.logger.error(f"Error requesting GitHub issue: {e}")
        raise e

@client_agent.on_message(QuoteResponse)
async def handle_quote_response(ctx: Context, sender: str, msg: QuoteResponse):
    """Handle quote responses from tool agents"""
    ctx.logger.info(f"Received quote from {sender}: {msg.job_id} - {msg.price} {msg.denom}")
    
    try:
        # Create job record
        job_record = JobRecord(
            job_id=msg.job_id,
            task=TaskType.CREATE_GITHUB_ISSUE,  # Inferred from context
            payload={},  # Will be filled when we accept
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
        
        # Check if we have sufficient balance
        total_required = msg.price + msg.bond_required
        current_balance = await payment_manager.get_balance(ctx)
        
        if current_balance < total_required:
            ctx.logger.warning(f"Insufficient balance for job {msg.job_id}: need {total_required}, have {current_balance}")
            state_manager.update_job(msg.job_id, {
                "status": JobStatus.FAILED,
                "notes": job_record.notes + f"\\nInsufficient balance: {current_balance} < {total_required}"
            })
            return
        
        # Auto-accept the quote for demo purposes
        # In a production system, this would be user-driven
        await accept_quote(ctx, msg, sender)
        
    except Exception as e:
        ctx.logger.error(f"Error handling quote response: {e}")

async def accept_quote(ctx: Context, quote: QuoteResponse, tool_address: str):
    """Accept a quote and send perform request"""
    try:
        ctx.logger.info(f"Accepting quote {quote.job_id} from {tool_address}")
        
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
            payload={
                "title": "Demo GitHub Issue from Marketplace",
                "body": f"This issue was created through the trust-minimized agent marketplace\\n\\nJob ID: {quote.job_id}\\nTimestamp: {timestamp.isoformat()}",
                "labels": ["innovationlab", "hackathon", "demo"]
            },
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
        
        # Perform verification
        await verify_and_pay(ctx, job_record, msg)
        
    except Exception as e:
        ctx.logger.error(f"Error handling receipt: {e}")

async def verify_and_pay(ctx: Context, job_record: JobRecord, receipt: Receipt):
    """Verify task completion and process payment"""
    try:
        ctx.logger.info(f"Verifying and processing payment for job {job_record.job_id}")
        
        # Perform verification
        verification_result = await task_verifier.verify_task_completion(
            receipt, 
            job_record.task, 
            TOOL_PUBLIC_KEY
        )
        
        # Update job with verification result
        state_manager.update_job(job_record.job_id, {
            "verification_timestamp": datetime.utcnow(),
            "verification_result": verification_result,
            "notes": job_record.notes + f"\\nVerification: {verification_result.details}"
        })
        
        if verification_result.verified:
            ctx.logger.info(f"Verification passed for job {job_record.job_id}")
            
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
                    
                    ctx.logger.info(f"Payment sent for job {job_record.job_id}: {tx_hash}")
                    ctx.logger.info(f"Task completed successfully! GitHub issue: {receipt.output_ref}")
                    
                else:
                    raise PaymentError("Payment transaction failed")
                    
            except PaymentError as e:
                ctx.logger.error(f"Payment failed for job {job_record.job_id}: {e}")
                state_manager.update_job(job_record.job_id, {
                    "status": JobStatus.FAILED,
                    "notes": job_record.notes + f"\\nPayment failed: {str(e)}"
                })
        else:
            ctx.logger.warning(f"Verification failed for job {job_record.job_id}: {verification_result.details}")
            state_manager.update_job(job_record.job_id, {
                "status": JobStatus.FAILED,
                "notes": job_record.notes + f"\\nVerification failed: {verification_result.details}"
            })
            
    except Exception as e:
        ctx.logger.error(f"Error in verify_and_pay: {e}")
        state_manager.update_job(job_record.job_id, {
            "status": JobStatus.FAILED,
            "notes": job_record.notes + f"\\nVerification error: {str(e)}"
        })

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
            
            # Find a tool agent (in production, this would search Agentverse)
            # For now, use a hardcoded address or search for available agents
            tool_agent_address = KNOWN_TOOL_AGENT
            
            if not tool_agent_address:
                return "No tool agents available for GitHub issue creation."
            
            # Request the issue
            job_id = await request_github_issue(ctx, tool_agent_address, title)
            
            return f"I've requested a GitHub issue titled '{title}' from a tool agent. Job tracking ID: {job_id}"
            
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
            return ("I'm a marketplace client that can request GitHub issue creation from tool agents. "
                   "Try: 'create issue: Your Title Here', 'status', or 'balance'")
            
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
                
    except Exception as e:
        ctx.logger.error(f"Error checking pending jobs: {e}")

# Include the chat protocol and publish manifest to Agentverse
client_agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    logger.info("Starting Marketplace Client Agent...")
    # Set the tool agent address (you would get this from discovery in production)
    print("\\nNOTE: Set KNOWN_TOOL_AGENT to the tool agent's address before running")
    print("You can get this by running the tool agent first and copying its address")
    client_agent.run()