"""
Tool agent implementation for GitHub issue creation.
This agent advertises GitHub issue creation services and handles quotes, execution, and receipts.
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
    QuoteRequest, QuoteResponse, PerformRequest, Receipt, BondNotification,
    TaskType, JobStatus, JobRecord, VerificationResult
)
from utils.github_api import GitHubAPI, GitHubAPIError
from utils.crypto import (
    compute_terms_hash, generate_job_id, create_job_signature,
    verify_client_signature
)
from utils.state_manager import StateManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the tool agent
tool_agent = Agent(
    name="github_tool_agent",
    port=8001,
    seed="github_tool_agent_secret_seed_phrase",  # In production, use proper seed management
    endpoint=["http://127.0.0.1:8001/submit"]
)

# Initialize components
state_manager = StateManager("tool_agent.db")
github_api = None
TOOL_SIGNING_KEY = "tool_agent_private_key_secret"  # In production, use proper key management

# Default pricing and terms
DEFAULT_PRICE = int(os.getenv("DEFAULT_TASK_PRICE", "5000000000000000000"))  # 5 testFET in atestfet
DEFAULT_BOND = int(os.getenv("DEFAULT_BOND_AMOUNT", "1000000000000000000"))  # 1 testFET in atestfet
DEFAULT_TTL = 300  # 5 minutes

# Initialize the chat protocol
chat_proto = Protocol(spec=chat_protocol_spec)

def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    """Create a text-based chat message"""
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=tool_agent.name + "_" + str(datetime.utcnow().timestamp()),
        content=content,
    )

@tool_agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize the tool agent on startup"""
    global github_api
    
    try:
        # Initialize GitHub API
        github_api = GitHubAPI.from_env()
        logger.info(f"Tool agent {tool_agent.address} started successfully")
        logger.info(f"GitHub API configured for repo: {github_api.repo}")
        
        # Fund agent if low on tokens
        fund_agent_if_low(tool_agent.wallet.address())
        
    except Exception as e:
        logger.error(f"Failed to initialize tool agent: {e}")
        ctx.logger.error(f"Startup error: {e}")

@tool_agent.on_message(QuoteRequest)
async def handle_quote_request(ctx: Context, sender: str, msg: QuoteRequest):
    """Handle incoming quote requests"""
    ctx.logger.info(f"Received quote request from {sender} for task: {msg.task}")
    
    # Check if we support this task type
    if msg.task != TaskType.CREATE_GITHUB_ISSUE:
        ctx.logger.warning(f"Unsupported task type: {msg.task}")
        return
    
    # Validate payload
    required_fields = ["title"]
    if not all(field in msg.payload for field in required_fields):
        ctx.logger.warning(f"Invalid payload, missing required fields: {required_fields}")
        return
    
    try:
        # Generate job ID and terms
        job_id = generate_job_id()
        
        quote_data = {
            "task": msg.task.value,
            "payload": msg.payload,
            "price": DEFAULT_PRICE,
            "denom": "atestfet",
            "ttl": DEFAULT_TTL,
            "bond_required": DEFAULT_BOND
        }
        terms_hash = compute_terms_hash(quote_data)
        
        # Create quote response
        quote = QuoteResponse(
            job_id=job_id,
            price=DEFAULT_PRICE,
            denom="atestfet",
            ttl=DEFAULT_TTL,
            terms_hash=terms_hash,
            bond_required=DEFAULT_BOND,
            tool_address=str(ctx.agent.address),
            timestamp=datetime.utcnow()
        )
        
        # Save job record
        job_record = JobRecord(
            job_id=job_id,
            task=msg.task,
            payload=msg.payload,
            status=JobStatus.QUOTED,
            client_address=sender,
            tool_address=str(ctx.agent.address),
            price=DEFAULT_PRICE,
            bond_amount=DEFAULT_BOND,
            quote_timestamp=datetime.utcnow(),
            notes=f"Quote sent to {sender}"
        )
        
        if state_manager.create_job(job_record):
            # Send quote response
            await ctx.send(sender, quote)
            ctx.logger.info(f"Sent quote {job_id} to {sender}: {DEFAULT_PRICE} atestfet")
        else:
            ctx.logger.error(f"Failed to save job record for {job_id}")
            
    except Exception as e:
        ctx.logger.error(f"Error handling quote request: {e}")

@tool_agent.on_message(PerformRequest)
async def handle_perform_request(ctx: Context, sender: str, msg: PerformRequest):
    """Handle incoming perform requests"""
    ctx.logger.info(f"Received perform request from {sender} for job: {msg.job_id}")
    
    # Get job record
    job_record = state_manager.get_job(msg.job_id)
    if not job_record:
        ctx.logger.warning(f"Job {msg.job_id} not found")
        return
    
    # Verify sender is the original client
    if job_record.client_address != sender:
        ctx.logger.warning(f"Unauthorized perform request for {msg.job_id} from {sender}")
        return
    
    # Check job status
    if job_record.status != JobStatus.QUOTED:
        ctx.logger.warning(f"Job {msg.job_id} in invalid status: {job_record.status}")
        return
    
    # Verify terms hash
    quote_data = {
        "task": job_record.task.value,
        "payload": job_record.payload,
        "price": job_record.price,
        "denom": "atestfet",
        "ttl": DEFAULT_TTL,
        "bond_required": job_record.bond_amount
    }
    expected_terms_hash = compute_terms_hash(quote_data)
    
    if msg.terms_hash != expected_terms_hash:
        ctx.logger.warning(f"Terms hash mismatch for {msg.job_id}")
        return
    
    # TODO: Verify client signature (simplified for MVP)
    # In production, verify msg.client_signature against sender's public key
    
    try:
        # Update job status
        state_manager.update_job(msg.job_id, {
            "status": JobStatus.IN_PROGRESS,
            "perform_timestamp": datetime.utcnow(),
            "notes": job_record.notes + f"\\nPerform request received from {sender}"
        })
        
        # Execute the task
        await execute_github_issue_task(ctx, job_record, msg)
        
    except Exception as e:
        ctx.logger.error(f"Error handling perform request: {e}")
        # Mark job as failed
        state_manager.update_job(msg.job_id, {
            "status": JobStatus.FAILED,
            "notes": job_record.notes + f"\\nExecution failed: {str(e)}"
        })

async def execute_github_issue_task(ctx: Context, job_record: JobRecord, perform_msg: PerformRequest):
    """Execute the GitHub issue creation task"""
    global github_api
    
    if not github_api:
        raise Exception("GitHub API not initialized")
    
    try:
        # Extract parameters
        title = job_record.payload.get("title")
        body = job_record.payload.get("body", "")
        labels = job_record.payload.get("labels", ["innovationlab", "hackathon"])
        
        ctx.logger.info(f"Creating GitHub issue: {title}")
        
        # Create the issue
        issue_url, api_url = await github_api.create_issue(title, body, labels)
        
        # Create receipt
        timestamp = datetime.utcnow()
        signature = create_job_signature(job_record.job_id, issue_url, timestamp, TOOL_SIGNING_KEY)
        
        receipt = Receipt(
            job_id=job_record.job_id,
            output_ref=issue_url,
            verifier_url=api_url,
            verifier_params={
                "expected_title": title,
                "expected_repo": github_api.repo
            },
            timestamp=timestamp,
            tool_signature=signature
        )
        
        # Update job record
        state_manager.update_job(job_record.job_id, {
            "status": JobStatus.COMPLETED,
            "completion_timestamp": timestamp,
            "receipt": receipt,
            "notes": job_record.notes + f"\\nGitHub issue created: {issue_url}"
        })
        
        # Send receipt to client
        await ctx.send(job_record.client_address, receipt)
        
        ctx.logger.info(f"Task completed successfully for job {job_record.job_id}")
        ctx.logger.info(f"Created GitHub issue: {issue_url}")
        
    except GitHubAPIError as e:
        ctx.logger.error(f"GitHub API error: {e}")
        raise e
    except Exception as e:
        ctx.logger.error(f"Unexpected error during task execution: {e}")
        raise e

@tool_agent.on_message(BondNotification)
async def handle_bond_notification(ctx: Context, sender: str, msg: BondNotification):
    """Handle bond payment notifications"""
    ctx.logger.info(f"Received bond notification for job {msg.job_id}: {msg.tx_hash}")
    
    # Get job record
    job_record = state_manager.get_job(msg.job_id)
    if job_record and job_record.client_address == sender:
        # Update job status
        state_manager.update_job(msg.job_id, {
            "status": JobStatus.BONDED,
            "notes": job_record.notes + f"\\nBond received: {msg.tx_hash}"
        })
        ctx.logger.info(f"Bond confirmed for job {msg.job_id}")

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
            
            # Parse the text for GitHub issue creation requests
            response_text = await process_chat_request(ctx, sender, item.text)
            
            # Send response
            response_message = create_text_chat(response_text)
            await ctx.send(sender, response_message)
            
        elif isinstance(item, EndSessionContent):
            ctx.logger.info(f"Chat session ended with {sender}")
            
        else:
            ctx.logger.info(f"Received unexpected content type from {sender}")

async def process_chat_request(ctx: Context, sender: str, text: str) -> str:
    """Process chat requests and potentially create GitHub issues"""
    text_lower = text.lower()
    
    # Check if this looks like a GitHub issue creation request
    if any(phrase in text_lower for phrase in ["create issue", "github issue", "new issue", "make issue"]):
        try:
            # Simple text parsing for title
            # In a production system, you'd use NLP or more sophisticated parsing
            if "title:" in text_lower:
                title = text.split("title:")[1].split("\\n")[0].strip()
            elif "create issue" in text_lower:
                title = text.replace("create issue", "").replace("Create issue", "").strip()
                if title.startswith("\"") and title.endswith("\""):
                    title = title[1:-1]
            else:
                title = f"Issue from chat: {text[:50]}..."
            
            if not title:
                return "I need a title for the GitHub issue. Please specify a title."
            
            # Create a simple quote request
            quote_request = QuoteRequest(
                task=TaskType.CREATE_GITHUB_ISSUE,
                payload={"title": title, "body": f"Created via chat from {sender}\\n\\nOriginal request: {text}"},
                client_address=sender,
                timestamp=datetime.utcnow()
            )
            
            # Process the quote request
            await handle_quote_request(ctx, sender, quote_request)
            
            return f"I can create a GitHub issue titled '{title}' for {DEFAULT_PRICE} atestfet (with a {DEFAULT_BOND} atestfet bond). Would you like to proceed?"
            
        except Exception as e:
            ctx.logger.error(f"Error processing chat request: {e}")
            return f"Sorry, I encountered an error processing your request: {str(e)}"
    else:
        return f"I specialize in creating GitHub issues. I can create an issue for {DEFAULT_PRICE} atestfet. Just ask me to 'create issue: Your Title Here' or describe what you need!"

@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle chat acknowledgements"""
    ctx.logger.info(f"Received acknowledgement from {sender} for message {msg.acknowledged_msg_id}")

# Include the chat protocol and publish manifest to Agentverse
tool_agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    logger.info("Starting GitHub Tool Agent...")
    tool_agent.run()