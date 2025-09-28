"""
ASI:One helper for intent inference.
If ASI_ONE_API_KEY is present, uses the ASI:One chat completions API to parse user text into a task and payload.
Falls back to simple heuristics when the key is missing or the API fails.
"""
import os
import httpx
from typing import Dict, Any

ASI_URL = os.getenv("ASI_ONE_URL", "https://api.asi1.ai/v1/chat/completions")
ASI_MODEL = os.getenv("ASI_ONE_MODEL", "asi1-mini")

SYSTEM_PROMPT = (
    "You are an intent parser for an agent marketplace. "
    "Return a strict JSON object with fields: task, payload. "
    "task must be one of: create_github_issue, translate_text. "
    "For create_github_issue, payload must include title (string) and optional body. "
    "For translate_text, payload must include text (string) and target_lang (string). "
    "Do not include any other text besides the JSON."
)


def simple_heuristics(text: str) -> Dict[str, Any]:
    t = text.strip().lower()
    if "translate" in t:
        # Very naive parse: "translate: <text> -> <lang>"
        raw = text
        if ":" in raw:
            raw = raw.split(":", 1)[1]
        parts = raw.split("->")
        txt = parts[0].strip().strip('"') if parts else raw
        lang = parts[1].strip() if len(parts) > 1 else "en"
        return {"task": "translate_text", "payload": {"text": txt, "target_lang": lang}}
    # default to github issue
    title = text.strip().split("\n")[0][:120]
    return {"task": "create_github_issue", "payload": {"title": title, "body": text}}


def infer_intent(text: str) -> Dict[str, Any]:
    api_key = os.getenv("ASI_ONE_API_KEY")
    if not api_key:
        return simple_heuristics(text)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": ASI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(ASI_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            # The model should return JSON only
            import json
            parsed = json.loads(content)
            task = parsed.get("task")
            pl = parsed.get("payload", {})
            if task in ("create_github_issue", "translate_text"):
                return {"task": task, "payload": pl}
            return simple_heuristics(text)
    except Exception:
        return simple_heuristics(text)
