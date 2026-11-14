"""WhatsApp Automation Connector for J.A.R.V.I.S.
Supports WhatsApp Web, WhatsApp Desktop protocol (whatsapp://), direct messaging, and SQLite persistent DM cortex.
"""
import asyncio
import subprocess
import sys
import urllib.parse
import webbrowser
from core.database import log_social_dm, get_recent_social_dms

WHATSAPP_WEB_URL = "https://web.whatsapp.com/"
WHATSAPP_API_SEND = "https://api.whatsapp.com/send"

def clean_phone_number(phone: str) -> str:
    """Normalize phone number to international format without spaces or symbols."""
    if not phone:
        return ""
    clean = "".join(c for c in phone if c.isdigit() or c == "+")
    if clean.startswith("+"):
        clean = clean[1:]
    return clean

def open_whatsapp_web():
    webbrowser.open(WHATSAPP_WEB_URL)
    return "Opened WhatsApp Web in your browser, Sir."

def send_whatsapp_message(recipient: str, message: str, auto_send: bool = False):
    """
    Open chat with recipient (phone number or name) and pre-fill message.
    Logs the conversation into SQLite database.
    """
    cleaned_phone = clean_phone_number(recipient)
    
    # Log to SQLite memory
    log_social_dm(
        platform="whatsapp",
        sender="Jarvis",
        recipient=cleaned_phone or recipient,
        message_text=message or "",
        thread_id=cleaned_phone or recipient,
        is_incoming=False,
        status="sent"
    )

    if cleaned_phone and len(cleaned_phone) >= 7:
        params = {"phone": cleaned_phone}
        if message:
            params["text"] = message
        url = f"{WHATSAPP_API_SEND}?{urllib.parse.urlencode(params)}"
        
        # Try launching desktop URI scheme first if on Windows, fallback to web
        if sys.platform == "win32":
            try:
                uri = f"whatsapp://send?phone={cleaned_phone}&text={urllib.parse.quote(message or '')}"
                subprocess.Popen(f'start "" "{uri}"', shell=True)
                return f"Dispatched WhatsApp message draft to +{cleaned_phone} via WhatsApp Desktop/Web and recorded in SQLite memory cortex."
            except Exception:
                pass
                
        webbrowser.open(url)
        return f"Opened WhatsApp chat with +{cleaned_phone} and prepared draft: \"{message[:60]}...\" (Logged to database)."
    else:
        # Recipient is a contact name (e.g. "Alex" or "Mom")
        if sys.platform == "win32":
            try:
                subprocess.Popen('start "" "whatsapp://"', shell=True)
            except Exception:
                webbrowser.open(WHATSAPP_WEB_URL)
        else:
            webbrowser.open(WHATSAPP_WEB_URL)
            
        return (f"Opened WhatsApp for contact '{recipient}'. Message drafted: \"{message}\". "
                "Sir, please select the chat to send. Logged to persistent memory cortex.")

def get_whatsapp_history(limit: int = 10) -> list:
    """Fetch logged WhatsApp conversations from SQLite cortex."""
    return get_recent_social_dms(platform="whatsapp", limit=limit)

def handle_whatsapp_tool(action: str = "open_chat", recipient: str = "", message: str = "") -> str:
    act = (action or "open_chat").lower()
    if act in ["send_message", "send", "compose"]:
        return send_whatsapp_message(recipient, message)
    elif act in ["open_chat", "chat"]:
        return send_whatsapp_message(recipient, message or "")
    elif act in ["history", "logs", "memory"]:
        hist = get_whatsapp_history()
        if not hist:
            return "No previous WhatsApp conversations logged in SQLite memory cortex, Sir."
        lines = [f"Found {len(hist)} WhatsApp conversation log(s) in SQLite:"]
        for h in hist:
            lines.append(f"• To {h['recipient']}: \"{h['message_text']}\" [{h['timestamp'][:16]}]")
        return "\n".join(lines)
    else:
        return open_whatsapp_web()
