from pathlib import Path

path = Path("src/client/marketplace_client_agent.py")
text = path.read_text(encoding="utf-8")
old = '            "notes": f"{job_record.notes}\r\nQuote accepted, perform request sent to {job_record.tool_address}"'
if old not in text:
    raise SystemExit("pattern not found")
new = '            "notes": existing_notes + f"\\nQuote accepted, perform request sent to {job_record.tool_address}"'
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
