"""
Translator tool agent using LibreTranslate (or a fallback) to translate text.
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional

import httpx
from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents import Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from models.messages import QuoteRequest, QuoteResponse, PerformRequest, Receipt, TaskType, JobStatus, JobRecord
from utils.crypto import compute_terms_hash, generate_job_id, create_job_signature
from utils.state_manager import StateManager
from utils.frontend_events import send_frontend_event

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

translator_agent = Agent(
    name="translator_tool_agent",
    port=8003,
    seed="translator_tool_agent_secret_seed",
    endpoint=["http://127.0.0.1:8003/submit"],
)

state_manager = StateManager("tool_agent.db")
TRANSLATOR_SIGNING_KEY = "translator_tool_agent_private_key"
DEFAULT_PRICE = int(os.getenv("TRANSLATOR_TASK_PRICE", "3000000000000000000"))  # 3 testFET
DEFAULT_BOND = int(os.getenv("TRANSLATOR_BOND_AMOUNT", "500000000000000000"))   # 0.5 testFET
DEFAULT_TTL = 300

chat_proto = Protocol(spec=chat_protocol_spec)

def create_text_chat(text: str) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=translator_agent.name + "_" + str(datetime.utcnow().timestamp()),
        content=content,
    )

# Chat protocol handlers (minimal) to satisfy protocol verification
@chat_proto.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    # Acknowledge
    ack = ChatAcknowledgement(timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id)
    await ctx.send(sender, ack)
    # If text contains 'translate:', send simple guidance
    for item in msg.content:
        if isinstance(item, TextContent) and item.text:
            if 'translate' in item.text.lower():
                response = create_text_chat(
                    "Use: translate: <text> -> <lang>. Or send a QuoteRequest for TRANSLATE_TEXT."
                )
                await ctx.send(sender, response)

@chat_proto.on_message(ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # No-op but required for completeness
    pass

@translator_agent.on_event("startup")
async def startup(ctx: Context):
    try:
        fund_agent_if_low(translator_agent.wallet.address())
        await send_frontend_event(
            source="tool",
            status="AVAILABLE",
            message="Translator tool agent online",
            extra={
                "tool_info": {
                    "address": str(translator_agent.address),
                    "name": translator_agent.name,
                    "capabilities": [TaskType.TRANSLATE_TEXT.value],
                    "price": DEFAULT_PRICE,
                    "bond": DEFAULT_BOND,
                    "port": 8003,
                }
            },
        )
    except Exception as e:
        logger.error(f"Translator startup error: {e}")

@translator_agent.on_message(QuoteRequest)
async def on_quote(ctx: Context, sender: str, msg: QuoteRequest):
    if msg.task != TaskType.TRANSLATE_TEXT:
        return
    try:
        job_id = generate_job_id()
        quote_data = {
            "task": msg.task.value,
            "payload": msg.payload,
            "price": DEFAULT_PRICE,
            "denom": "atestfet",
            "ttl": DEFAULT_TTL,
            "bond_required": DEFAULT_BOND,
        }
        terms_hash = compute_terms_hash(quote_data)
        quote = QuoteResponse(
            job_id=job_id,
            task=msg.task,
            price=DEFAULT_PRICE,
            denom="atestfet",
            ttl=DEFAULT_TTL,
            terms_hash=terms_hash,
            bond_required=DEFAULT_BOND,
            tool_address=str(ctx.agent.address),
            tool_pubkey=TRANSLATOR_SIGNING_KEY,
            timestamp=datetime.utcnow(),
        )
        # Save job
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
            notes=f"Translator quote sent to {sender}",
        )
        state_manager.create_job(jr)
        await ctx.send(sender, quote)
        await send_frontend_event(
            source="tool",
            status="QUOTED",
            message=f"Translator quote: {DEFAULT_PRICE} atestfet",
            job_id=job_id,
            extra={"tool_address": str(ctx.agent.address), "client_address": sender, "price": DEFAULT_PRICE, "bond_amount": DEFAULT_BOND},
        )
    except Exception as e:
        ctx.logger.error(f"Quote error: {e}")

@translator_agent.on_message(PerformRequest)
async def on_perform(ctx: Context, sender: str, msg: PerformRequest):
    jr = state_manager.get_job(msg.job_id)
    if not jr or jr.client_address != sender:
        return
    try:
        state_manager.update_job(msg.job_id, {"status": JobStatus.IN_PROGRESS, "perform_timestamp": datetime.utcnow()})
        await send_frontend_event(source="tool", status="IN_PROGRESS", message="Translating text...", job_id=msg.job_id)
        # Perform translation
        text = jr.payload.get("text") or ""
        source_lang = jr.payload.get("source_lang", "auto")
        target_lang = jr.payload.get("target_lang", "en")
        translated = await translate_text(text, source_lang, target_lang)
        # Build receipt
        ts = datetime.utcnow()
        signature = create_job_signature(msg.job_id, translated, ts, TRANSLATOR_SIGNING_KEY)
        receipt = Receipt(
            job_id=msg.job_id,
            output_ref=translated,
            verifier_url="libretranslate://result",
            verifier_params={"expected_lang": target_lang},
            timestamp=ts,
            tool_signature=signature,
        )
        state_manager.update_job(msg.job_id, {"status": JobStatus.COMPLETED, "completion_timestamp": ts, "receipt": receipt})
        await ctx.send(sender, receipt)
        await send_frontend_event(source="tool", status="COMPLETED", message="Translation ready", job_id=msg.job_id)
    except Exception as e:
        ctx.logger.error(f"Perform error: {e}")

async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text using LibreTranslate or fallback to mock translation"""
    
    # Try using the public LibreTranslate API
    urls = [
        os.getenv("LIBRETRANSLATE_URL", "https://libretranslate.com/translate"),
        "https://translate.terraprint.co/translate",  # Alternative public instance
        "https://translate.argosopentech.com/translate",  # Another alternative
    ]
    
    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Prepare the request data
                data = {
                    "q": text,
                    "source": source_lang if source_lang != "auto" else "en",  # Use 'en' as default if auto
                    "target": target_lang,
                    "format": "text"
                }
                
                logger.info(f"Trying translation service at {url}")
                resp = await client.post(url, json=data)  # Use json instead of data
                
                if resp.status_code == 200:
                    result = resp.json()
                    translated = result.get("translatedText", "")
                    if translated:
                        logger.info(f"Translation successful: {text[:30]}... -> {translated[:30]}...")
                        return f"Translated to {target_lang}: {translated}"
                else:
                    logger.warning(f"Translation service returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Translation service {url} failed: {e}")
            continue
    
    # Fallback to mock translation with some basic transformations
    logger.info("Using mock translation as fallback")
    
    # Simple mock translations
    mock_translations = {
        "es": {"hello": "hola", "world": "mundo", "thank you": "gracias"},
        "fr": {"hello": "bonjour", "world": "monde", "thank you": "merci"},
        "de": {"hello": "hallo", "world": "welt", "thank you": "danke"},
    }
    
    if target_lang in mock_translations:
        text_lower = text.lower()
        for eng, trans in mock_translations[target_lang].items():
            if eng in text_lower:
                text = text.replace(eng, trans)
                text = text.replace(eng.capitalize(), trans.capitalize())
    
    return f"[Mock] Translated to {target_lang}: {text}"

# Publish manifest can be disabled if chat protocol verification mismatches
translator_agent.include(chat_proto, publish_manifest=False)

if __name__ == "__main__":
    logger.info("Starting Translator Tool Agent...")
    translator_agent.run()
