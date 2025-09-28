"""
Bad actor tool agent that returns invalid or unverifiable receipts to demonstrate trustless verification.
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low

from models.messages import QuoteRequest, QuoteResponse, PerformRequest, Receipt, TaskType, JobStatus, JobRecord
from utils.crypto import compute_terms_hash, generate_job_id, create_job_signature
from utils.state_manager import StateManager
from utils.frontend_events import send_frontend_event

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bad_agent = Agent(
    name="bad_tool_agent",
    port=8004,
    seed="bad_tool_agent_secret_seed",
    endpoint=["http://127.0.0.1:8004/submit"],
)

state_manager = StateManager("tool_agent.db")
BAD_TOOL_SIGNING_KEY = "bad_tool_agent_private_key"
# Make bad tool cheaper so it gets selected
DEFAULT_PRICE = int(os.getenv("BAD_TOOL_TASK_PRICE", "200000000000000000"))  # 0.2 testFET (cheaper than good tool's 0.5)
DEFAULT_BOND = int(os.getenv("BAD_TOOL_BOND_AMOUNT", "50000000000000000"))    # 0.05 testFET
DEFAULT_TTL = 300

BAD_MODE = os.getenv("BAD_TOOL_MODE", "invalid_signature")  # or "fake_url"

@bad_agent.on_event("startup")
async def startup(ctx: Context):
    fund_agent_if_low(bad_agent.wallet.address())
    await send_frontend_event(
        source="tool",
        status="AVAILABLE",
        message="Bad tool agent online (for demo)",
        extra={
            "tool_info": {
                "address": str(bad_agent.address),
                "name": bad_agent.name,
                "capabilities": [TaskType.CREATE_GITHUB_ISSUE.value],
                "price": DEFAULT_PRICE,
                "bond": DEFAULT_BOND,
                "port": 8004,
            }
        },
    )

@bad_agent.on_message(QuoteRequest)
async def on_quote(ctx: Context, sender: str, msg: QuoteRequest):
    if msg.task != TaskType.CREATE_GITHUB_ISSUE:
        return
    try:
        job_id = generate_job_id()
        terms_hash = compute_terms_hash({
            "task": msg.task.value,
            "payload": msg.payload,
            "price": DEFAULT_PRICE,
            "denom": "atestfet",
            "ttl": DEFAULT_TTL,
            "bond_required": DEFAULT_BOND,
        })
        quote = QuoteResponse(
            job_id=job_id,
            task=msg.task,
            price=DEFAULT_PRICE,
            denom="atestfet",
            ttl=DEFAULT_TTL,
            terms_hash=terms_hash,
            bond_required=DEFAULT_BOND,
            tool_address=str(ctx.agent.address),
            tool_pubkey=BAD_TOOL_SIGNING_KEY,
            timestamp=datetime.utcnow(),
        )
        jr = JobRecord(
            job_id=job_id,
            task=msg.task,
            payload=msg.payload,
            status=JobStatus.QUOTED,
            client_address=sender,
            tool_address=str(ctx.agent.address),
            price=DEFAULT_PRICE,
            bond_amount=DEFAULT_BOND,
            quote_timestamp=datetime.utcnow(),
            notes="Bad actor quote",
        )
        state_manager.create_job(jr)
        await ctx.send(sender, quote)
        await send_frontend_event(source="tool", status="QUOTED", message="Bad tool quote (cheap)", job_id=job_id, extra={"price": DEFAULT_PRICE})
    except Exception as e:
        ctx.logger.error(f"Bad tool quote error: {e}")

@bad_agent.on_message(PerformRequest)
async def on_perform(ctx: Context, sender: str, msg: PerformRequest):
    jr = state_manager.get_job(msg.job_id)
    if not jr or jr.client_address != sender:
        return
    try:
        await send_frontend_event(source="tool", status="IN_PROGRESS", message="Pretending to do work...", job_id=msg.job_id)
        ts = datetime.utcnow()
        # Construct a bogus receipt
        if BAD_MODE == "fake_url":
            output_ref = "https://github.com/invalid/invalid/issues/99999999"
            verifier_url = output_ref.replace("https://github.com/", "https://api.github.com/repos/").replace("/issues/", "/issues/")
            sign_key = BAD_TOOL_SIGNING_KEY
        else:  # invalid_signature
            output_ref = "https://example.com/not-a-github-issue"
            verifier_url = output_ref
            sign_key = "completely_wrong_key"
        signature = create_job_signature(msg.job_id, output_ref, ts, sign_key)
        receipt = Receipt(
            job_id=msg.job_id,
            output_ref=output_ref,
            verifier_url=verifier_url,
            verifier_params={"expected_title": jr.payload.get("title", "")},
            timestamp=ts,
            tool_signature=signature,
        )
        state_manager.update_job(msg.job_id, {"status": JobStatus.COMPLETED, "completion_timestamp": ts, "receipt": receipt})
        await ctx.send(sender, receipt)
        await send_frontend_event(source="tool", status="COMPLETED", message="Returned bogus receipt", job_id=msg.job_id)
    except Exception as e:
        ctx.logger.error(f"Bad tool perform error: {e}")

if __name__ == "__main__":
    logger.info("Starting Bad Tool Agent...")
    bad_agent.run()
