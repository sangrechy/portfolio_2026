import os
import re
import json
import uuid
import time
import random
import smtplib
import asyncio
import hmac
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Mithun Portfolio API",
    description="Full-stack service for Mithun's 2026 Portfolio with 2-Way Telegram Chat, Telemetry, and OTP Verification",
    version="2.4.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No-cache response middleware to prevent stale frontend scripts
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith((".js", ".css", ".html")) or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# SMTP Settings for Email OTP Delivery
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
MESSAGES_LOG_PATH = os.path.join(BASE_DIR, "messages.json")

# Firebase Cloud Firestore Settings & Safe Backend Initialization
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()

firestore_db = None
try:
    sa_path = FIREBASE_SERVICE_ACCOUNT_PATH
    if not sa_path:
        sa_path = os.path.join(BASE_DIR, "firebase_service_account.json")
    elif not os.path.isabs(sa_path):
        p1 = os.path.join(ROOT_DIR, sa_path)
        p2 = os.path.join(BASE_DIR, sa_path)
        sa_path = p1 if os.path.exists(p1) else p2

    if os.path.exists(sa_path):
        cred = credentials.Certificate(sa_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        firestore_db = firestore.client()
        print(f"[Firestore] Successfully initialized Firebase Admin for project: {firestore_db.project}")
    else:
        print(f"[Firestore Notice] Service account not found at {sa_path}. Firestore logging disabled.")
except Exception as e:
    print(f"[Firestore Init Error]: {e}")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

# In-memory stores
outbound_replies: dict[str, list[dict]] = {}
otp_store: dict[str, dict] = {}           # email -> { "otp": str, "name": str, "expires_at": float }
verified_sessions: dict[str, dict] = {}   # email -> { "token": str, "name": str, "expires_at": float }
admin_sessions: dict[str, float] = {}     # admin_token -> expires_at
recent_telemetry_visits: dict[str, float] = {} # ip -> last_visit_timestamp

def save_chat_id_to_env(chat_id: str):
    """Saves discovered chat ID to gitignored .env files while preserving other keys."""
    for env_path in [os.path.join(ROOT_DIR, ".env"), os.path.join(BASE_DIR, ".env")]:
        try:
            content = (
                f"TELEGRAM_BOT_TOKEN={TELEGRAM_BOT_TOKEN}\n"
                f"TELEGRAM_CHAT_ID={chat_id}\n"
                f"SMTP_HOST={SMTP_HOST}\n"
                f"SMTP_PORT={SMTP_PORT}\n"
                f"SMTP_USER={SMTP_USER}\n"
                f"SMTP_PASS={SMTP_PASS}\n"
                f"SMTP_FROM={SMTP_FROM}\n"
                f"FIREBASE_SERVICE_ACCOUNT_PATH={FIREBASE_SERVICE_ACCOUNT_PATH or 'backend/firebase_service_account.json'}\n"
                f"ADMIN_PASSWORD={ADMIN_PASSWORD}\n"
            )
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"[Env Save Error]: {e}")

def get_client_ip(request: Request) -> str:
    """Extracts the client IP from proxy headers or client socket."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

async def get_ip_location(ip: str) -> dict:
    """Resolves client IP to approximate geographic location using ip-api.com."""
    is_local = (
        ip in ("127.0.0.1", "::1", "localhost") or
        ip.startswith("192.168.") or
        ip.startswith("10.") or
        ip.startswith("172.16.")
    )
    
    lookup_ip = ip
    if is_local:
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                resp = await client.get("https://api.ipify.org?format=json")
                if resp.status_code == 200:
                    lookup_ip = resp.json().get("ip", ip)
        except Exception:
            lookup_ip = ip

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{lookup_ip}?fields=status,country,regionName,city,zip,isp,query"
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    city = data.get("city", "")
                    region = data.get("regionName", "")
                    country = data.get("country", "")
                    isp = data.get("isp", "")
                    location_parts = [p for p in [city, region, country] if p]
                    loc_str = ", ".join(location_parts) if location_parts else "Unknown Location"
                    if isp:
                        loc_str += f" ({isp})"
                    return {
                        "ip": ip,
                        "public_ip": lookup_ip,
                        "location_str": loc_str,
                        "city": city,
                        "region": region,
                        "country": country,
                        "isp": isp
                    }
    except Exception as e:
        print(f"[GeoIP Lookup Error]: {e}")
    
    return {
        "ip": ip,
        "public_ip": lookup_ip,
        "location_str": "Unknown Location",
        "city": "",
        "region": "",
        "country": "",
        "isp": ""
    }

async def send_telegram_msg(text: str, reply_markup: Optional[dict] = None) -> bool:
    """Sends formatted notification to Mithun's Telegram with optional inline buttons or ForceReply."""
    chat_id = await resolve_chat_id()
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram Error]: {e}")
        return False

def save_local_message(name: str, email: str, message: str, direction: str = "inbound", ip: str = None, location: str = None):
    """Persists message log locally so history is never lost."""
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "direction": direction,
        "name": name,
        "email": email,
        "message": message,
        "ip": ip,
        "location": location
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

# ============================================================================
# CLOUD FIRESTORE LOGGING HELPERS (Non-blocking & Error Resilient)
# ============================================================================
def _sync_add_firestore_doc(collection_name: str, data: dict) -> bool:
    """Synchronous worker to write a document to Firestore with SERVER_TIMESTAMP."""
    if firestore_db is None:
        return False
    try:
        payload = {**data, "timestamp": firestore.SERVER_TIMESTAMP}
        firestore_db.collection(collection_name).add(payload)
        return True
    except Exception as e:
        print(f"[Firestore Write Error] Failed to write to '{collection_name}': {e}")
        return False

async def record_firestore_event(collection_name: str, data: dict) -> bool:
    """Asynchronously dispatches Firestore document creation without blocking."""
    if firestore_db is None:
        return False
    try:
        return await asyncio.to_thread(_sync_add_firestore_doc, collection_name, data)
    except Exception as e:
        print(f"[Firestore Async Error]: {e}")
        return False

async def log_activity(
    action: str,
    request: Optional[Request] = None,
    ip: str = "",
    location: str = "",
    geo_data: Optional[dict] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    page: str = "/"
):
    """Helper to log website activity into the 'logs' Firestore collection."""
    geo = geo_data or {}
    user_agent = "Unknown"
    if request:
        user_agent = request.headers.get("user-agent", "Unknown")

    log_doc = {
        "action": action,
        "ip": ip or geo.get("public_ip") or "Unknown",
        "location": location or geo.get("location_str") or "Unknown Location",
        "city": geo.get("city", ""),
        "region": geo.get("region", ""),
        "country": geo.get("country", ""),
        "isp": geo.get("isp", ""),
        "user_agent": user_agent,
        "page": page
    }
    if email:
        log_doc["email"] = email
    if name:
        log_doc["name"] = name

    await record_firestore_event("logs", log_doc)

async def log_chat(
    action: str,
    email: str,
    name: str,
    message: str,
    reply_by: str,
    ip: str,
    location: str,
    user_agent: str = "Unknown"
):
    """Helper to log chat activity into the 'chat' Firestore collection."""
    chat_doc = {
        "action": action,
        "email": email,
        "name": name,
        "message": message,
        "reply_by": reply_by,
        "ip": ip,
        "location": location,
        "user_agent": user_agent
    }
    await record_firestore_event("chat", chat_doc)

async def resolve_chat_id() -> Optional[str]:
    """Returns TELEGRAM_CHAT_ID from env, or queries Telegram getUpdates to auto-detect it."""
    global TELEGRAM_CHAT_ID
    if TELEGRAM_CHAT_ID:
        return TELEGRAM_CHAT_ID
    
    if not TELEGRAM_BOT_TOKEN:
        return None
        
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates")
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                for item in reversed(results):
                    chat = item.get("message", {}).get("chat", {}) or item.get("my_chat_member", {}).get("chat", {})
                    if "id" in chat:
                        found_id = str(chat["id"])
                        TELEGRAM_CHAT_ID = found_id
                        save_chat_id_to_env(found_id)
                        return found_id
    except Exception as e:
        print(f"[Telegram Auto-Detect Error]: {e}")
    
    return None

def _send_smtp_sync(to_email: str, name: str, otp_code: str) -> tuple[bool, Optional[str]]:
    """Synchronous worker to send OTP verification email via SMTP."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False, "SMTP credentials not configured"
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Mithun Portfolio <{SMTP_FROM}>"
        msg["To"] = to_email
        msg["Subject"] = f"{otp_code} is your Mithun Portfolio Verification Code"
        
        plain_body = (
            f"Hello {name},\n\n"
            f"Your one-time verification code for chatting on Mithun's Developer Portfolio is:\n\n"
            f"  {otp_code}\n\n"
            f"This code expires in 10 minutes. Enter it on the website to activate your 10-day verified session.\n\n"
            f"Best regards,\n"
            f"Mithun Portfolio Relay"
        )
        
        html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#0b0f19;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#0b0f19;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width:500px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.12);border-radius:16px;padding:32px;color:#f8fafc;box-shadow:0 12px 30px rgba(0,0,0,0.5);">
          <tr>
            <td>
              <div style="font-size:12px;font-weight:700;letter-spacing:2px;color:#38bdf8;margin-bottom:8px;text-transform:uppercase;">Mithun Portfolio // Security</div>
              <h1 style="font-size:22px;font-weight:700;color:#ffffff;margin:0 0 16px 0;">Verify Your Email</h1>
              <p style="font-size:15px;color:#94a3b8;line-height:1.6;margin:0 0 24px 0;">
                Hello <strong style="color:#ffffff;">{name}</strong>,<br>
                Use the following one-time code to activate your direct 10-day chat session with Mithun:
              </p>
              <div style="background:rgba(56,189,248,0.08);border:1px dashed rgba(56,189,248,0.4);border-radius:12px;padding:20px;text-align:center;margin:0 0 24px 0;">
                <span style="font-family:'Courier New',Courier,monospace;font-size:36px;font-weight:700;letter-spacing:10px;color:#38bdf8;">{otp_code}</span>
              </div>
              <p style="font-size:13px;color:#64748b;line-height:1.5;margin:0 0 24px 0;">
                This code is valid for <strong>10 minutes</strong>. If you did not request this verification code, you can safely ignore this email.
              </p>
              <div style="border-top:1px solid rgba(255,255,255,0.08);padding-top:16px;font-size:12px;color:#475569;">
                &copy; 2026 Mithun &bull; Full-Stack Portfolio &amp; Direct Telegram Relay
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True, None
    except Exception as e:
        print(f"[SMTP Send Error]: {e}")
        return False, str(e)

async def send_smtp_email(to_email: str, name: str, otp_code: str) -> tuple[bool, Optional[str]]:
    """Asynchronously dispatches OTP verification email via SMTP."""
    return await asyncio.to_thread(_send_smtp_sync, to_email, name, otp_code)

# ============================================================================
# TELEGRAM POLLING WORKER (Listens for Mithun's replies to post in web chat)
# ============================================================================
async def telegram_polling_worker():
    """Continuously polls Telegram for Mithun's replies to visitors."""
    global TELEGRAM_CHAT_ID
    offset = 0
    print("[Telegram Poller] Starting Telegram reply listener worker...")

    while True:
        try:
            if not TELEGRAM_BOT_TOKEN:
                await asyncio.sleep(4)
                continue

            async with httpx.AsyncClient(timeout=25.0) as client:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                params = {"offset": offset, "timeout": 15}
                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    updates = data.get("result", [])
                    for update in updates:
                        offset = max(offset, update["update_id"] + 1)
                        msg = update.get("message")
                        if not msg or not msg.get("text"):
                            continue

                        sender_chat_id = str(msg.get("chat", {}).get("id", ""))
                        if not TELEGRAM_CHAT_ID:
                            TELEGRAM_CHAT_ID = sender_chat_id
                            save_chat_id_to_env(sender_chat_id)

                        text = msg["text"].strip()
                        reply_to = msg.get("reply_to_message", {})

                        target_email = None
                        reply_content = None

                        # Pattern 1: @<email> <message> or @bot_name @<email> <message>
                        email_prefix_match = re.search(
                            r"^(?:@\w+\s+)?@\s*<?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>?\s*(.*)",
                            text,
                            re.DOTALL
                        )
                        if email_prefix_match:
                            target_email = email_prefix_match.group(1).lower().strip()
                            reply_content = email_prefix_match.group(2).strip()

                        # Pattern 2: Telegram Reply swipe on forwarded message
                        elif reply_to and reply_to.get("text"):
                            quoted_text = reply_to.get("text", "")
                            email_search = re.search(
                                r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
                                quoted_text
                            )
                            if email_search:
                                target_email = email_search.group(1).lower().strip()
                                reply_content = text

                        if target_email and reply_content:
                            reply_item = {
                                "id": str(uuid.uuid4()),
                                "sender": "Mithun",
                                "message": reply_content,
                                "timestamp": datetime.now().isoformat(),
                                "time_display": datetime.now().strftime("%I:%M %p")
                            }
                            if target_email not in outbound_replies:
                                outbound_replies[target_email] = []
                            outbound_replies[target_email].append(reply_item)

                            # Persist reply to messages.json
                            save_local_message(
                                name="Mithun (via Telegram)",
                                email=target_email,
                                message=reply_content,
                                direction="outbound"
                            )

                            print(f"[Telegram Relay] Dispatched reply for {target_email}: {reply_content}")

                            # Confirmation format in Telegram matching requested format
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ack_text = (
                                f"💬 *{{chat*\n"
                                f"*action:* reply\n"
                                f"*timestamp:* {now_str}\n"
                                f"*ip:* Telegram\n"
                                f"*location:* Mithun Relay\n"
                                f"*messege:* {reply_content}\n"
                                f"*reply by:* @{target_email}*}}*"
                            )
                            await send_telegram_msg(ack_text)

                            # Record reply event in Firestore chat collection
                            await log_chat(
                                action="reply",
                                email=target_email,
                                name="Mithun",
                                message=reply_content,
                                reply_by=f"@{target_email}",
                                ip="Telegram",
                                location="Mithun Relay",
                                user_agent="Telegram Bot"
                            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(3)

        await asyncio.sleep(0.5)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(telegram_polling_worker())

# ============================================================================
# DATA MODELS
# ============================================================================
class OtpSendRequest(BaseModel):
    name: str
    email: str

class OtpVerifyRequest(BaseModel):
    name: str
    email: str
    otp: str

class ChatMessageRequest(BaseModel):
    name: str
    email: str
    message: str

class ChatStatusRequest(BaseModel):
    name: str
    email: str
    action: str  # "logout", "reload", "exit"

class TelemetryRequest(BaseModel):
    session_id: Optional[str] = None
    page: Optional[str] = "/"

class ResumeTrackRequest(BaseModel):
    action: Optional[str] = "resume_download"
    page: Optional[str] = "/#resume"

# ============================================================================
# TELEMETRY ENDPOINTS (Visitor Location & Exit Tracking)
# ============================================================================
@app.post("/api/telemetry/visit")
async def track_visit(payload: TelemetryRequest, request: Request):
    """Tracks when a visitor lands on the portfolio."""
    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Anti-spam: throttle visit notification if same IP visited in last 5 minutes
    last_visit = recent_telemetry_visits.get(ip_display, 0)
    current_time = time.time()
    if (current_time - last_visit) > 300:
        recent_telemetry_visits[ip_display] = current_time
        log_text = (
            f"🌐 *{{log*\n"
            f"*action:* visited\n"
            f"*timestamp:* {now_str}\n"
            f"*ip:* {ip_display}\n"
            f"*loc:* {loc_display}*}}*"
        )
        await send_telegram_msg(log_text)

        # Record event in Firestore logs collection
        await log_activity(
            action="visited",
            request=request,
            ip=ip_display,
            location=loc_display,
            geo_data=geo_data,
            page=payload.page or "/"
        )

    return {"status": "ok", "location": loc_display, "ip": ip_display}

@app.post("/api/telemetry/exit")
async def track_exit(payload: TelemetryRequest, request: Request):
    """Tracks when a visitor closes or leaves the portfolio."""
    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_text = (
        f"🌐 *{{log*\n"
        f"*action:* exit\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* {ip_display}\n"
        f"*loc:* {loc_display}*}}*"
    )
    await send_telegram_msg(log_text)

    # Record event in Firestore logs collection
    await log_activity(
        action="exit",
        request=request,
        ip=ip_display,
        location=loc_display,
        geo_data=geo_data,
        page=payload.page or "/"
    )
    return {"status": "ok"}

@app.post("/api/telemetry/resume")
async def track_resume(request: Request, payload: Optional[ResumeTrackRequest] = None):
    """Tracks when a visitor downloads or views Mithun's resume."""
    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    page_val = payload.page if payload and payload.page else "/#resume"
    log_text = (
        f"🌐 *{{log*\n"
        f"*action:* resume_download\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* {ip_display}\n"
        f"*loc:* {loc_display}*}}*"
    )
    await send_telegram_msg(log_text)

    # Record event in Firestore logs collection
    await log_activity(
        action="resume_download",
        request=request,
        ip=ip_display,
        location=loc_display,
        geo_data=geo_data,
        page=page_val
    )
    return {"status": "ok"}

# ============================================================================
# EMAIL OTP VERIFICATION ENDPOINTS
# ============================================================================
@app.post("/api/otp/send")
async def send_otp(payload: OtpSendRequest, request: Request):
    """Generates 6-digit OTP and dispatches directly to visitor's email via SMTP."""
    name = payload.name.strip()
    email = payload.email.lower().strip()
    if not name or not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid name and email are required")

    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = time.time() + 600 # 10 minutes expiry

    otp_store[email] = {
        "otp": otp_code,
        "name": name,
        "expires_at": expires_at,
        "attempts": 0
    }

    # Dispatch OTP directly to visitor's email inbox via SMTP
    email_delivered, error_reason = await send_smtp_email(email, name, otp_code)

    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If email delivery succeeded:
    # Do NOT send OTP code to Telegram! The code remains completely private to the visitor.
    if email_delivered:
        print(f"[OTP Dispatch] Successfully sent OTP code via SMTP to {email}")
        return {
            "status": "success",
            "message": "Verification code sent directly to your email inbox.",
            "email": email,
            "email_delivered": True
        }

    # If email delivery failed:
    # Dispatch fallback security alert to Telegram so development and testing are not blocked
    telegram_fallback_alert = (
        f"🔐 *{{security - otp fallback*\n"
        f"*action:* otp_generated\n"
        f"*timestamp:* {now_str}\n"
        f"*user:* {name}\n"
        f"*email:* `{email}`\n"
        f"*otp_code:* `{otp_code}`\n"
        f"*notice:* SMTP delivery error: {error_reason}\n"
        f"*ip:* {ip_display}\n"
        f"*loc:* {loc_display}*}}*"
    )
    await send_telegram_msg(telegram_fallback_alert)

    return {
        "status": "success",
        "message": "Verification code generated and dispatched.",
        "email": email,
        "email_delivered": False,
        "note": error_reason
    }

@app.post("/api/otp/verify")
async def verify_otp(payload: OtpVerifyRequest, request: Request):
    """Validates 6-digit OTP and establishes 10-day verified session."""
    email = payload.email.lower().strip()
    code = payload.otp.strip()

    record = otp_store.get(email)
    if not record:
        raise HTTPException(status_code=400, detail="No pending verification code found for this email. Please request a new code.")

    if time.time() > record["expires_at"]:
        otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new code.")

    if record["otp"] != code:
        record["attempts"] += 1
        if record["attempts"] >= 5:
            otp_store.pop(email, None)
            raise HTTPException(status_code=400, detail="Too many invalid attempts. Please request a new code.")
        raise HTTPException(status_code=400, detail="Invalid verification code. Please check and try again.")

    # Successful Verification! Issue 10-day session token
    otp_store.pop(email, None)
    session_token = str(uuid.uuid4())
    ten_days_sec = 10 * 86400
    verified_sessions[email] = {
        "token": session_token,
        "name": payload.name,
        "expires_at": time.time() + ten_days_sec
    }

    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Dispatch [CHAT LOG] with action: logged in
    chat_login_alert = (
        f"💬 *{{chat*\n"
        f"*action:* logged in\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* {ip_display}\n"
        f"*location:* {loc_display}\n"
        f"*messege:* User verified email OTP and activated 10-day chat session\n"
        f"*reply by:* @{email}*}}*"
    )
    await send_telegram_msg(chat_login_alert)

    # Record login event in Firestore chat and logs collections
    user_agent = request.headers.get("user-agent", "Unknown")
    await log_chat(
        action="logged in",
        email=email,
        name=payload.name,
        message="User verified email OTP and activated 10-day chat session",
        reply_by=f"@{email}",
        ip=ip_display,
        location=loc_display,
        user_agent=user_agent
    )
    await log_activity(
        action="login",
        request=request,
        ip=ip_display,
        location=loc_display,
        geo_data=geo_data,
        email=email,
        name=payload.name,
        page="/#chat"
    )

    return {
        "status": "success",
        "verified": True,
        "token": session_token,
        "name": payload.name,
        "email": email,
        "expires_in_days": 10
    }

# ============================================================================
# CHAT MESSAGE & STATUS ENDPOINTS
# ============================================================================
@app.post("/api/chat")
async def handle_chat_message(payload: ChatMessageRequest, request: Request):
    """Dispatches chat message to Telegram with requested [CHAT LOG] formatting."""
    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save message locally
    save_local_message(
        name=payload.name,
        email=payload.email,
        message=payload.message,
        direction="inbound",
        ip=ip_display,
        location=loc_display
    )

    # Format Telegram message matching exact requested template (with tap-to-copy email code)
    telegram_text = (
        f"💬 *{{chat*\n"
        f"*action:* message\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* {ip_display}\n"
        f"*location:* {loc_display}\n"
        f"*messege:* {payload.message}\n"
        f"*reply by:* `@{payload.email}`*}}*"
    )
    # Auto-activate Telegram native reply bar so Mithun can reply immediately without copying
    reply_markup = {
        "force_reply": True,
        "input_field_placeholder": f"Reply to {payload.name}..."
    }
    delivered = await send_telegram_msg(telegram_text, reply_markup=reply_markup)

    # Record message in Firestore chat collection
    user_agent = request.headers.get("user-agent", "Unknown")
    await log_chat(
        action="message",
        email=payload.email,
        name=payload.name,
        message=payload.message,
        reply_by=f"@{payload.email}",
        ip=ip_display,
        location=loc_display,
        user_agent=user_agent
    )

    return {
        "status": "success",
        "telegram_delivered": delivered,
        "location": loc_display
    }

@app.post("/api/chat/status")
async def handle_chat_status(payload: ChatStatusRequest, request: Request):
    """Notifies Mithun on Telegram when user logs out or leaves."""
    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    action_label = "out" if payload.action == "logout" else "exit"
    msg_label = "User logged out of chat session" if payload.action == "logout" else "User left / reloaded page"

    status_text = (
        f"💬 *{{chat*\n"
        f"*action:* {action_label}\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* {ip_display}\n"
        f"*location:* {loc_display}\n"
        f"*messege:* {msg_label}\n"
        f"*reply by:* @{payload.email}*}}*"
    )
    await send_telegram_msg(status_text)

    # Record status in Firestore chat and logs collections
    user_agent = request.headers.get("user-agent", "Unknown")
    await log_chat(
        action=action_label,
        email=payload.email,
        name=payload.name,
        message=msg_label,
        reply_by=f"@{payload.email}",
        ip=ip_display,
        location=loc_display,
        user_agent=user_agent
    )
    if payload.action == "logout":
        await log_activity(
            action="logout",
            request=request,
            ip=ip_display,
            location=loc_display,
            geo_data=geo_data,
            email=payload.email,
            name=payload.name,
            page="/#chat"
        )

    return {"status": "ok"}

@app.get("/api/chat/poll")
async def poll_chat_messages(email: str):
    """Endpoint for web frontend to retrieve live replies from Mithun."""
    if not email:
        return {"status": "error", "messages": []}

    email_key = email.lower().strip()
    pending = outbound_replies.get(email_key, [])
    return {
        "status": "success",
        "messages": pending
    }

@app.get("/api/chat/history")
async def get_chat_history(email: str):
    """Retrieves conversation history for returning verified user."""
    if not email:
        return {"status": "error", "history": []}

    email_key = email.lower().strip()
    history = []

    if os.path.exists(MESSAGES_LOG_PATH):
        try:
            with open(MESSAGES_LOG_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
                for r in records:
                    if r.get("email", "").lower().strip() == email_key:
                        history.append({
                            "id": r.get("id", str(uuid.uuid4())),
                            "sender": "Mithun" if r.get("direction") == "outbound" else "You",
                            "type": "received" if r.get("direction") == "outbound" else "sent",
                            "message": r.get("message", ""),
                            "timestamp": r.get("timestamp", "")
                        })
        except Exception as e:
            print(f"[History Error]: {e}")

    return {"status": "success", "history": history}

# ============================================================================
# ADMIN DASHBOARD ENDPOINTS (Authenticated & Server-Side Firestore Access)
# ============================================================================
class AdminLoginRequest(BaseModel):
    password: str

class AdminReplyRequest(BaseModel):
    email: str
    message: str

def require_admin(request: Request) -> str:
    """Verifies that the incoming request has a valid, non-expired admin session token."""
    auth_header = request.headers.get("x-admin-token") or request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token or token not in admin_sessions:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or expired admin session")
    if time.time() > admin_sessions[token]:
        admin_sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Unauthorized: Admin session has expired")
    return token

@app.post("/api/admin/login")
async def admin_login(payload: AdminLoginRequest):
    """Validates admin password and generates an isolated 12-hour admin session token."""
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="Admin authentication is not configured on server")
    pwd = payload.password.strip()
    if not hmac.compare_digest(pwd, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    
    session_token = str(uuid.uuid4())
    admin_sessions[session_token] = time.time() + (12 * 3600)
    return {
        "status": "success",
        "token": session_token,
        "expires_in_hours": 12
    }

@app.post("/api/admin/logout")
async def admin_logout(request: Request):
    """Invalidates the admin session token immediately."""
    auth_header = request.headers.get("x-admin-token") or request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if token in admin_sessions:
        admin_sessions.pop(token, None)
    return {"status": "success", "message": "Admin session terminated"}

@app.get("/api/admin/session")
async def check_admin_session(request: Request):
    """Validates if the active admin session is still valid."""
    require_admin(request)
    return {"status": "authenticated"}

@app.get("/api/admin/chats")
async def get_admin_chats(request: Request):
    """Returns WhatsApp-style conversations grouped by visitor from Firestore."""
    require_admin(request)
    conversations: dict[str, dict] = {}

    # Query Firestore chat collection
    if firestore_db:
        try:
            docs = list(firestore_db.collection("chat").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(300).stream())
            for doc in docs:
                data = doc.to_dict()
                email = (data.get("email") or "").lower().strip()
                if not email or "@" not in email:
                    continue

                ts = data.get("timestamp")
                ts_iso = ""
                ts_epoch = 0.0
                time_str = ""
                if hasattr(ts, "isoformat"):
                    ts_iso = ts.isoformat()
                    ts_epoch = ts.timestamp()
                    time_str = ts.strftime("%I:%M %p")
                elif isinstance(ts, (int, float)):
                    ts_epoch = float(ts)
                    time_str = datetime.fromtimestamp(ts_epoch).strftime("%I:%M %p")

                name = data.get("name") or "Visitor"
                action = data.get("action") or "message"
                msg_text = data.get("message") or ""
                loc = data.get("location") or "Unknown Location"
                ip = data.get("ip") or "Unknown"

                if email not in conversations:
                    conversations[email] = {
                        "email": email,
                        "name": name if name != "Mithun" else "Visitor",
                        "location": loc if loc != "Mithun Relay" else "",
                        "ip": ip if ip != "Telegram" else "",
                        "last_message": msg_text,
                        "last_action": action,
                        "last_timestamp": ts_iso,
                        "last_epoch": ts_epoch,
                        "last_time_str": time_str,
                        "last_sender": "Mithun" if (action == "reply" or name == "Mithun") else "visitor",
                        "messages_count": 1,
                        "online": email in verified_sessions and verified_sessions[email].get("expires_at", 0) > time.time()
                    }
                else:
                    conv = conversations[email]
                    conv["messages_count"] += 1
                    if conv["name"] in ("Visitor", "") and name not in ("Mithun", "Visitor"):
                        conv["name"] = name
                    if not conv["location"] and loc != "Mithun Relay":
                        conv["location"] = loc
                    if not conv["ip"] and ip != "Telegram":
                        conv["ip"] = ip
        except Exception as e:
            print(f"[Admin Chats Error]: {e}")

    # Fallback/supplement from local messages.json
    if os.path.exists(MESSAGES_LOG_PATH):
        try:
            with open(MESSAGES_LOG_PATH, "r", encoding="utf-8") as f:
                local_msgs = json.load(f)
            for m in reversed(local_msgs):
                email = (m.get("email") or "").lower().strip()
                if not email or "@" not in email:
                    continue
                if email not in conversations:
                    name = m.get("name", "Visitor")
                    conversations[email] = {
                        "email": email,
                        "name": name if "Mithun" not in name else "Visitor",
                        "location": m.get("location", "Unknown Location"),
                        "ip": m.get("ip", "Unknown"),
                        "last_message": m.get("message", ""),
                        "last_action": "message",
                        "last_timestamp": m.get("timestamp", ""),
                        "last_epoch": 0.0,
                        "last_time_str": "",
                        "last_sender": "Mithun" if m.get("direction") == "outbound" else "visitor",
                        "messages_count": 1,
                        "online": email in verified_sessions and verified_sessions[email].get("expires_at", 0) > time.time()
                    }
        except Exception:
            pass

    chat_list = sorted(conversations.values(), key=lambda x: x["last_epoch"], reverse=True)
    return {"status": "success", "chats": chat_list}

@app.get("/api/admin/chat/{email:path}")
async def get_admin_chat_thread(email: str, request: Request):
    """Returns chronological conversation history between Mithun and a specific visitor."""
    require_admin(request)
    clean_email = email.lower().strip()
    messages = []
    visitor_info = {
        "email": clean_email,
        "name": "Visitor",
        "location": "Unknown Location",
        "ip": "Unknown",
        "online": clean_email in verified_sessions and verified_sessions[clean_email].get("expires_at", 0) > time.time()
    }

    if firestore_db:
        try:
            docs = list(firestore_db.collection("chat").where("email", "==", clean_email).stream())
            def get_doc_epoch(d):
                data = d.to_dict()
                ts = data.get("timestamp")
                if hasattr(ts, "timestamp"):
                    return ts.timestamp()
                elif isinstance(ts, (int, float)):
                    return float(ts)
                return 0.0

            docs.sort(key=get_doc_epoch)
            for doc in docs:
                d = doc.to_dict()
                ts = d.get("timestamp")
                ts_str = ""
                if hasattr(ts, "strftime"):
                    ts_str = ts.strftime("%b %d, %I:%M %p")
                elif isinstance(ts, (int, float)):
                    ts_str = datetime.fromtimestamp(ts).strftime("%b %d, %I:%M %p")

                name = d.get("name") or "Visitor"
                action = d.get("action") or "message"
                is_admin_reply = (action == "reply" or name == "Mithun")

                if not is_admin_reply and name not in ("Visitor", ""):
                    visitor_info["name"] = name
                if d.get("location") and d.get("location") != "Mithun Relay":
                    visitor_info["location"] = d.get("location")
                if d.get("ip") and d.get("ip") != "Telegram":
                    visitor_info["ip"] = d.get("ip")

                messages.append({
                    "id": doc.id,
                    "action": action,
                    "sender": "Mithun" if is_admin_reply else (name or "Visitor"),
                    "is_admin": is_admin_reply,
                    "message": d.get("message", ""),
                    "timestamp": ts_str,
                    "reply_by": d.get("reply_by", "")
                })
        except Exception as e:
            print(f"[Admin Thread Error]: {e}")

    # Fallback to local messages if needed
    if not messages and os.path.exists(MESSAGES_LOG_PATH):
        try:
            with open(MESSAGES_LOG_PATH, "r", encoding="utf-8") as f:
                local_msgs = json.load(f)
            for m in local_msgs:
                if (m.get("email") or "").lower().strip() == clean_email:
                    is_out = m.get("direction") == "outbound"
                    messages.append({
                        "id": m.get("id", str(uuid.uuid4())),
                        "action": "reply" if is_out else "message",
                        "sender": "Mithun" if is_out else m.get("name", "Visitor"),
                        "is_admin": is_out,
                        "message": m.get("message", ""),
                        "timestamp": m.get("timestamp", ""),
                        "reply_by": f"@{clean_email}"
                    })
        except Exception:
            pass

    return {
        "status": "success",
        "visitor": visitor_info,
        "messages": messages
    }

@app.post("/api/admin/chat/reply")
async def admin_send_reply(payload: AdminReplyRequest, request: Request):
    """Dispatches reply from Admin Dashboard to visitor's active session, Firestore, and Telegram."""
    require_admin(request)
    target_email = payload.email.lower().strip()
    reply_content = payload.message.strip()
    if not target_email or not reply_content:
        raise HTTPException(status_code=400, detail="Target email and message content are required")

    reply_item = {
        "id": str(uuid.uuid4()),
        "sender": "Mithun",
        "message": reply_content,
        "timestamp": datetime.now().isoformat(),
        "time_display": datetime.now().strftime("%I:%M %p")
    }

    # 1. Enqueue to visitor's active web polling session
    if target_email not in outbound_replies:
        outbound_replies[target_email] = []
    outbound_replies[target_email].append(reply_item)

    # 2. Persist locally to messages.json
    save_local_message(
        name="Mithun (via Admin Dashboard)",
        email=target_email,
        message=reply_content,
        direction="outbound",
        ip="Admin Dashboard",
        location="Admin Console"
    )

    # 3. Persist to Firestore chat collection
    await log_chat(
        action="reply",
        email=target_email,
        name="Mithun",
        message=reply_content,
        reply_by=f"@{target_email}",
        ip="Admin Dashboard",
        location="Admin Console",
        user_agent="Admin Dashboard"
    )

    # 4. Notify Telegram so Mithun's Telegram stays 100% synchronized
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ack_text = (
        f"💬 *{{chat*\n"
        f"*action:* reply\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* Admin Dashboard\n"
        f"*location:* Admin Console\n"
        f"*messege:* {reply_content}\n"
        f"*reply by:* @{target_email}*}}*"
    )
    await send_telegram_msg(ack_text)

    return {"status": "success", "reply": reply_item}

@app.get("/api/admin/logs")
async def get_admin_logs(
    request: Request,
    action: Optional[str] = "ALL",
    search: Optional[str] = None,
    limit: int = 60
):
    """Retrieves structured event logs from Firestore for the Admin Logs dashboard."""
    require_admin(request)
    limit = max(10, min(limit, 100))
    logs = []

    if firestore_db:
        try:
            query = firestore_db.collection("logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
            docs = list(query.stream())
            for doc in docs:
                d = doc.to_dict()
                act = d.get("action", "")

                if action and action != "ALL" and act.lower() != action.lower():
                    continue

                ts = d.get("timestamp")
                ts_str = "Recent"
                if hasattr(ts, "strftime"):
                    ts_str = ts.strftime("%d %b %Y · %H:%M:%S")
                elif isinstance(ts, (int, float)):
                    ts_str = datetime.fromtimestamp(ts).strftime("%d %b %Y · %H:%M:%S")

                if search:
                    s_low = search.lower().strip()
                    searchable = " ".join([
                        str(d.get("ip", "")),
                        str(d.get("location", "")),
                        str(d.get("city", "")),
                        str(d.get("region", "")),
                        str(d.get("country", "")),
                        str(d.get("isp", "")),
                        str(d.get("email", "")),
                        str(d.get("name", "")),
                        str(d.get("page", "")),
                        str(act)
                    ]).lower()
                    if s_low not in searchable:
                        continue

                logs.append({
                    "id": doc.id,
                    "action": act,
                    "timestamp": ts_str,
                    "ip": d.get("ip", "Unknown"),
                    "location": d.get("location", "Unknown Location"),
                    "city": d.get("city", ""),
                    "region": d.get("region", ""),
                    "country": d.get("country", ""),
                    "isp": d.get("isp", ""),
                    "page": d.get("page", "/"),
                    "email": d.get("email", ""),
                    "name": d.get("name", ""),
                    "user_agent": d.get("user_agent", "")
                })
        except Exception as e:
            print(f"[Admin Logs Error]: {e}")

    return {"status": "success", "logs": logs}

@app.get("/api/health")
async def health_check():
    chat_id = await resolve_chat_id()
    return {
        "status": "healthy",
        "service": "portfolio_backend",
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN and chat_id),
        "chat_id_detected": bool(chat_id),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def serve_index():
    index_file = os.path.join(ROOT_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "index.html not found"}

# Static file mounts
css_path = os.path.join(ROOT_DIR, "css")
js_path = os.path.join(ROOT_DIR, "js")
res_path = os.path.join(ROOT_DIR, "res")

if os.path.exists(css_path):
    app.mount("/css", StaticFiles(directory=css_path), name="css")
if os.path.exists(js_path):
    app.mount("/js", StaticFiles(directory=js_path), name="js")
if os.path.exists(res_path):
    app.mount("/res", StaticFiles(directory=res_path), name="res")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
