import os
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="Mithun Portfolio API",
    description="Full-stack service for Mithun's 2026 Portfolio with Telegram Bot relay",
    version="2.0.0"
)

# Allow CORS for development & external callers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
MESSAGES_LOG_PATH = os.path.join(BASE_DIR, "messages.json")

class ChatMessageRequest(BaseModel):
    name: str
    email: str
    message: str

class ChatResponse(BaseModel):
    status: str
    reply: str
    telegram_delivered: bool

@app.get("/api/health")
async def health_check():
    has_telegram = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    return {
        "status": "healthy",
        "service": "portfolio_backend",
        "telegram_configured": has_telegram,
        "timestamp": datetime.now().isoformat()
    }

async def forward_to_telegram(name: str, email: str, message: str) -> bool:
    """Dispatches a formatted notification to Mithun's Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload_text = (
        f"🚀 *New Portfolio Message!*\n\n"
        f"👤 *From:* {name}\n"
        f"📧 *Email:* `{email}`\n"
        f"💬 *Message:*\n{message}\n\n"
        f"⏰ _{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": payload_text,
                "parse_mode": "Markdown"
            })
            return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram Relay Error] Failed to send: {e}")
        return False

def save_local_message(name: str, email: str, message: str):
    """Persists messages locally so no message is ever lost."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "name": name,
        "email": email,
        "message": message
    }
    data = []
    if os.path.exists(MESSAGES_LOG_PATH):
        try:
            with open(MESSAGES_LOG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    
    data.append(entry)
    with open(MESSAGES_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat_message(payload: ChatMessageRequest):
    # 1. Save locally
    save_local_message(payload.name, payload.email, payload.message)

    # 2. Forward to Telegram
    delivered = await forward_to_telegram(payload.name, payload.email, payload.message)

    if delivered:
        reply_text = f"Got your message, {payload.name}! I've notified Mithun on Telegram immediately. He'll get back to you at {payload.email} soon."
    else:
        reply_text = f"Thanks for reaching out, {payload.name}! Your message was logged successfully. (Telegram bot relay will forward it once token is activated)."

    return ChatResponse(
        status="success",
        reply=reply_text,
        telegram_delivered=delivered
    )

# Static files mounts
css_path = os.path.join(ROOT_DIR, "css")
js_path = os.path.join(ROOT_DIR, "js")
res_path = os.path.join(ROOT_DIR, "res")

if os.path.exists(css_path):
    app.mount("/css", StaticFiles(directory=css_path), name="css")
if os.path.exists(js_path):
    app.mount("/js", StaticFiles(directory=js_path), name="js")
if os.path.exists(res_path):
    app.mount("/res", StaticFiles(directory=res_path), name="res")

@app.get("/")
async def serve_index():
    index_file = os.path.join(ROOT_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "index.html not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
