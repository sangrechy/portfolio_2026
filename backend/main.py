import os
import re
import json
import uuid
import time
import random
import smtplib
import asyncio
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

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Mithun Portfolio API",
    description="Full-stack service for Mithun's 2026 Portfolio with 2-Way Telegram Chat, Telemetry, and OTP Verification",
    version="2.3.0"
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

# Resend Email API Settings
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Mithun Portfolio <onboarding@resend.dev>").strip()

# Optional SMTP Settings for Email delivery
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
MESSAGES_LOG_PATH = os.path.join(BASE_DIR, "messages.json")

# In-memory stores
outbound_replies: dict[str, list[dict]] = {}
otp_store: dict[str, dict] = {}           # email -> { "otp": str, "name": str, "expires_at": float }
verified_sessions: dict[str, dict] = {}   # email -> { "token": str, "name": str, "expires_at": float }
recent_telemetry_visits: dict[str, float] = {} # ip -> last_visit_timestamp

def save_chat_id_to_env(chat_id: str):
    """Saves discovered chat ID to gitignored .env files while preserving other keys."""
    for env_path in [os.path.join(ROOT_DIR, ".env"), os.path.join(BASE_DIR, ".env")]:
        try:
            content = f"TELEGRAM_BOT_TOKEN={TELEGRAM_BOT_TOKEN}\nTELEGRAM_CHAT_ID={chat_id}\nRESEND_API_KEY={RESEND_API_KEY}\n"
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

async def send_telegram_msg(text: str) -> bool:
    """Sends formatted notification to Mithun's Telegram."""
    chat_id = await resolve_chat_id()
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            })
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

async def send_resend_email(to_email: str, name: str, otp_code: str) -> tuple[bool, Optional[str]]:
    """Sends OTP verification code via Resend API directly to visitor's email."""
    if not RESEND_API_KEY:
        return False, "Resend API key not configured"

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    html_content = f"""
    <!DOCTYPE html>
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
    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": f"{otp_code} is your Mithun Portfolio Verification Code",
        "html": html_content
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (200, 201):
                return True, None
            else:
                try:
                    data = resp.json()
                    err_msg = data.get("message") or resp.text
                except Exception:
                    err_msg = resp.text
                print(f"[Resend Error {resp.status_code}]: {err_msg}")
                return False, err_msg
    except Exception as e:
        print(f"[Resend Exception]: {e}")
        return False, str(e)

def send_smtp_email(to_email: str, name: str, otp_code: str):
    """Sends OTP code via SMTP if configured."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = f"Mithun Portfolio <{SMTP_FROM}>"
        msg["To"] = to_email
        msg["Subject"] = f"{otp_code} is your Mithun Portfolio Verification Code"
        
        body = f"""Hello {name},

Your one-time verification code for chatting on Mithun's Developer Portfolio is:

  {otp_code}

This code expires in 10 minutes. Please enter it to activate your 10-day verified chat session.

Best regards,
Mithun Portfolio Relay
"""
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[SMTP Send Error]: {e}")
        return False

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

                        # Pattern 1: @<email> <message> or @email <message>
                        email_prefix_match = re.search(
                            r"^@\s*<?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>?\s*(.*)",
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
    return {"status": "ok"}

# ============================================================================
# EMAIL OTP VERIFICATION ENDPOINTS
# ============================================================================
@app.post("/api/otp/send")
async def send_otp(payload: OtpSendRequest, request: Request):
    """Generates 6-digit OTP and dispatches directly to visitor's email via Resend."""
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

    # 1. Attempt delivery directly to visitor's email inbox via Resend
    email_delivered, error_reason = await send_resend_email(email, name, otp_code)

    # 2. Fallback to SMTP if Resend fails and SMTP is configured
    if not email_delivered and SMTP_HOST:
        smtp_sent = send_smtp_email(email, name, otp_code)
        if smtp_sent:
            email_delivered = True
            error_reason = None

    client_ip = get_client_ip(request)
    geo_data = await get_ip_location(client_ip)
    ip_display = geo_data.get("public_ip") or client_ip
    loc_display = geo_data.get("location_str") or "Unknown Location"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If email delivery succeeded:
    # Do NOT send OTP code to Telegram! The code remains completely private to the visitor.
    if email_delivered:
        print(f"[OTP Dispatch] Successfully sent OTP code via Resend to {email}")
        return {
            "status": "success",
            "message": "Verification code sent directly to your email inbox.",
            "email": email,
            "email_delivered": True
        }

    # If email delivery failed (e.g. Resend free test mode restriction on unverified external domains):
    # Dispatch fallback security alert to Telegram so development and testing are not blocked
    telegram_fallback_alert = (
        f"🔐 *{{security - otp fallback*\n"
        f"*action:* otp_generated\n"
        f"*timestamp:* {now_str}\n"
        f"*user:* {name}\n"
        f"*email:* `{email}`\n"
        f"*otp_code:* `{otp_code}`\n"
        f"*notice:* Resend test mode: verify domain at resend.com to send to public emails\n"
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

    # Format Telegram message matching exact requested template
    telegram_text = (
        f"💬 *{{chat*\n"
        f"*action:* message\n"
        f"*timestamp:* {now_str}\n"
        f"*ip:* {ip_display}\n"
        f"*location:* {loc_display}\n"
        f"*messege:* {payload.message}\n"
        f"*reply by:* @{payload.email}*}}*"
    )
    delivered = await send_telegram_msg(telegram_text)

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
