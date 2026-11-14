"""
Instagram Integration & Automated DM Response Engine for J.A.R.V.I.S.
Powered by instagrapi and SQLite persistent DM cortex.
"""
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from core.database import log_social_dm, get_recent_social_dms, update_dm_ai_response

load_dotenv()

HERE = Path(__file__).resolve().parent.parent
DATA_DIR = HERE / "data"
SESSION_PATH = DATA_DIR / "instagram_session.json"

logger = logging.getLogger("jarvis.instagram")

_cl = None

def get_instagram_client(force_new: bool = False):
    """
    Initialize and return an authenticated instagrapi Client.
    Supports sessionid cookie (bypasses 2FA & ClientNeedsUpgradeError) or username/password.
    Caches session in data/instagram_session.json to avoid checkpoint/2FA blocks.
    """
    global _cl
    if _cl is not None and not force_new:
        return _cl

    try:
        from instagrapi import Client
    except ImportError:
        logger.error("instagrapi is not installed. Install via: pip install instagrapi")
        return None

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cl = Client()
    cl.delay_range = [1, 3]

    sessionid = os.getenv("INSTAGRAM_SESSIONID", "").strip()
    username = os.getenv("INSTAGRAM_USERNAME", "").strip()
    password = os.getenv("INSTAGRAM_PASSWORD", "").strip()

    # 1. Try restoring existing saved session
    if SESSION_PATH.exists() and not force_new:
        try:
            cl.load_settings(str(SESSION_PATH))
            if sessionid:
                try:
                    cl.login_by_sessionid(sessionid)
                except Exception:
                    pass
            elif username and password:
                try:
                    cl.login(username, password)
                except Exception:
                    pass
            _cl = cl
            return _cl
        except Exception as e:
            logger.warning(f"Could not restore Instagram session: {e}. Attempting fresh login.")

    # 2. High-reliability authentication via Session ID cookie
    if sessionid:
        try:
            cl.login_by_sessionid(sessionid)
            cl.dump_settings(str(SESSION_PATH))
            _cl = cl
            logger.info(f"Instagram authenticated via sessionid as @{cl.username}")
            return _cl
        except Exception as e:
            logger.error(f"Instagram sessionid authentication failed: {e}")

    # 3. Direct username & password authentication
    if not username or not password:
        logger.info("Instagram credentials not found in environment (INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_SESSIONID).")
        return None

    try:
        cl.login(username, password)
        cl.dump_settings(str(SESSION_PATH))
        _cl = cl
        return _cl
    except Exception as e:
        logger.error(f"Instagram authentication failed: {e}")
        return None

def check_instagram_status() -> dict:
    """Check Instagram connection state and configuration."""
    username = os.getenv("INSTAGRAM_USERNAME", "").strip()
    sessionid = os.getenv("INSTAGRAM_SESSIONID", "").strip()
    has_creds = bool((username and os.getenv("INSTAGRAM_PASSWORD")) or sessionid)
    has_session = SESSION_PATH.exists()
    
    return {
        "configured": has_creds or has_session,
        "username": username or (_cl.username if _cl else "Not Set"),
        "has_sessionid": bool(sessionid),
        "has_session_file": has_session,
        "session_path": str(SESSION_PATH)
    }

def format_thread_transcript(thread, current_user_id) -> str:
    """
    Format the last 6-10 messages of a direct message thread into a clean
    chronological transcript (oldest -> newest).
    """
    messages = list(reversed((thread.messages or [])[:8]))
    users_by_id = {str(u.pk): u.username for u in (thread.users or [])}
    
    transcript_lines = []
    for m in messages:
        sender_id = str(getattr(m, "user_id", ""))
        if sender_id == str(current_user_id):
            sender_name = "Sir (@redonxd)"
        else:
            sender_name = f"@{users_by_id.get(sender_id, 'Friend')}"

        item_type = getattr(m, "item_type", "text")
        text = getattr(m, "text", "") or ""
        
        if item_type == "text" and text:
            content = text
        elif "clip" in item_type or item_type == "xma_clip":
            content = "[Shared a Reel / Video Clip]"
        elif "media" in item_type or item_type == "xma_media_share":
            content = "[Shared a Post / Media Photo]"
        elif item_type == "voice_media":
            content = "[Voice Audio Note]"
        elif item_type == "like":
            content = "[Liked the message ❤️]"
        elif item_type == "animated_media":
            content = "[Sent a GIF / Sticker]"
        else:
            content = text if text else f"[{item_type}]"

        transcript_lines.append(f"{sender_name}: {content}")

    return "\n".join(transcript_lines)

def generate_ai_friend_reply(friend_username: str, conversation_transcript: str) -> str:
    """
    Generate an intelligent, polite, witty conversational reply as J.A.R.V.I.S.,
    speaking on behalf of Sir to a friend on Instagram, continuing the ongoing conversation.
    """
    from google import genai
    from google.genai import types
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return f"Greetings @{friend_username}. Sir is currently away from his terminal, but I have logged your message in our memory cortex."

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""You are J.A.R.V.I.S., Sir's sophisticated, loyal, and witty AI assistant operating on his personal workstation.
Sir's Instagram handle is @redonxd.
You are messaging Sir's friend @{friend_username} in their Instagram direct message thread on Sir's behalf.
Sir is currently focused at his workstation terminal.

Here is the recent conversation transcript between Sir and @{friend_username}:
\"\"\"
{conversation_transcript}
\"\"\"

Your goal is to continue the conversation naturally and properly:
1. Speak in J.A.R.V.I.S.'s charming, articulate, dryly witty British persona (Tony Stark's JARVIS).
2. Directly respond to what @{friend_username} just said or shared (e.g. if they sent a reel/clip, acknowledge it; if they asked a question, answer helpfully or note that Sir will follow up).
3. Do NOT send a generic template. Engage with the actual topic of conversation so it feels like a real, seamless dialogue.
4. Keep it concise (1 to 2 sentences max) so it reads naturally in an Instagram chat.
5. Do NOT include quotation marks around the entire message, and do not use hashtags or excessive emojis."""

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=150, temperature=0.7)
        )
        if response and response.text:
            return response.text.strip().strip('"')
    except Exception as e:
        logger.error(f"Error generating AI friend reply: {e}")

    return f"Greetings @{friend_username}. Sir is currently indisposed at his workstation, but I have noted your message and will ensure he sees it."

def auto_reply_instagram_dms(target_friend: str = None) -> list:
    """
    Automated conversational response engine for Instagram DMs.
    Scans threads, checks if the friend sent the last message, reconstructs
    the full conversational thread context, and replies contextually using Gemini AI.
    """
    cl = get_instagram_client()
    if not cl:
        return ["Instagram client offline. Please ensure INSTAGRAM_SESSIONID is configured in .env, Sir."]

    replies_sent = []
    try:
        threads = cl.direct_threads(amount=10)
        for t in threads:
            # We focus on 1-on-1 friend conversations
            if not t.users or len(t.users) > 3:
                continue

            friend_user = t.users[0]
            friend_username = friend_user.username

            # If user specified a specific friend (e.g. 'suhi._.ji' or 'ut.sav_')
            if target_friend:
                target_clean = target_friend.lstrip("@").lower().strip()
                if friend_username.lower() != target_clean:
                    continue

            if not t.messages:
                continue

            last_msg = t.messages[0]
            # Don't reply if Sir or J.A.R.V.I.S. sent the last message
            if str(last_msg.user_id) == str(cl.user_id):
                continue

            # Reconstruct the conversation thread transcript
            transcript = format_thread_transcript(t, cl.user_id)
            
            # Generate the conversational continuation using Gemini
            reply_text = generate_ai_friend_reply(friend_username, transcript)

            # Send reply to Instagram direct thread
            cl.direct_answer(t.id, reply_text)

            # Log to SQLite cortex
            log_social_dm(
                platform="instagram",
                sender=friend_username,
                recipient=cl.username,
                message_text=getattr(last_msg, "text", "") or "[Media/Reel]",
                thread_id=str(t.id),
                is_incoming=True,
                ai_response=reply_text,
                status="replied",
                raw_payload={"transcript": transcript}
            )

            replies_sent.append(f"Replied to @{friend_username}:\n\"{reply_text}\"")

        return replies_sent if replies_sent else ["All friend conversations are currently up-to-date (no pending unread messages waiting for a reply), Sir."]
    except Exception as e:
        logger.error(f"Auto-reply exception: {e}")
        return [f"Conversational dispatch encountered an issue: {str(e)}"]

def get_unread_dms(limit: int = 10) -> list:
    """
    Fetch pending / unread direct message threads.
    Logs each message into the SQLite social_dms database.
    """
    cl = get_instagram_client()
    if not cl:
        return [{
            "status": "error",
            "message": "Instagram client offline. Please configure INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env, Sir."
        }]

    try:
        threads = cl.direct_threads(amount=limit, selected_filter="unread")
        if not threads:
            threads = cl.direct_threads(amount=limit)

        results = []
        for t in threads:
            thread_id = str(t.id)
            users = [u.username for u in t.users if u]
            recipient_label = ", ".join(users) or "Unknown Contact"
            
            messages = t.messages or []
            last_msg = messages[0] if messages else None
            msg_text = getattr(last_msg, "text", "") or ""
            sender_id = str(getattr(last_msg, "user_id", ""))
            
            # Log into SQLite DM memory
            log_social_dm(
                platform="instagram",
                sender=recipient_label,
                recipient=cl.username or "Jarvis",
                message_text=msg_text,
                thread_id=thread_id,
                is_incoming=True,
                status="unread"
            )

            results.append({
                "thread_id": thread_id,
                "users": users,
                "last_message": msg_text,
                "timestamp": str(getattr(last_msg, "timestamp", ""))
            })

        return results
    except Exception as e:
        logger.error(f"Failed to fetch Instagram DMs: {e}")
        return [{"status": "error", "message": f"Instagram API Error: {str(e)}"}]

def send_instagram_dm(target_username: str, message: str) -> dict:
    """
    Send a direct message to an Instagram username and log it into SQLite.
    """
    cl = get_instagram_client()
    if not cl:
        return {
            "status": "error",
            "message": "Instagram client offline. Please configure INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env, Sir."
        }

    try:
        target_username = target_username.lstrip("@").strip()
        user_id = cl.user_id_from_username(target_username)
        res = cl.direct_send(message, user_ids=[user_id])
        
        # Log to SQLite
        log_social_dm(
            platform="instagram",
            sender=cl.username or "Jarvis",
            recipient=target_username,
            message_text=message,
            thread_id=str(getattr(res, "thread_id", "")),
            is_incoming=False,
            status="sent"
        )

        return {
            "status": "success",
            "message": f"Direct message dispatched to @{target_username} on Instagram.",
            "recipient": target_username,
            "text": message
        }
    except Exception as e:
        logger.error(f"Failed to send Instagram DM to {target_username}: {e}")
        return {
            "status": "error",
            "message": f"Instagram transmission failed: {str(e)}"
        }

def get_friend_thread(target_username: str = "") -> str:
    """Fetch and display the conversational history with a specific friend."""
    cl = get_instagram_client()
    if not cl:
        return "Instagram client offline, Sir."
    target_clean = (target_username or "").lstrip("@").lower().strip()
    try:
        threads = cl.direct_threads(amount=15)
        # First priority: 1-on-1 direct message thread
        if target_clean:
            for t in threads:
                if len(t.users) == 1 and t.users[0].username.lower() == target_clean:
                    friend_name = t.users[0].username
                    transcript = format_thread_transcript(t, cl.user_id)
                    return f"Direct Conversation History with @{friend_name}:\n\n{transcript}"

        # Second priority: any thread containing target or first thread
        for t in threads:
            users = [u.username.lower() for u in t.users]
            if not target_clean or target_clean in users:
                friend_name = ", ".join([u.username for u in t.users])
                transcript = format_thread_transcript(t, cl.user_id)
                return f"Direct Conversation History with @{friend_name}:\n\n{transcript}"
        return f"No direct message thread found with '@{target_username}', Sir."
    except Exception as e:
        return f"Failed to retrieve thread history: {e}"

def create_story_card(text: str = None, title: str = "◈ J.A.R.V.I.S. // AUTONOMOUS NEURAL AGENT ◈") -> str:
    """Generate a sleek 1080x1920 black Stark-themed story image."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 1080, 1920
        img = Image.new('RGB', (W, H), color='#000000')
        draw = ImageDraw.Draw(img)

        font_badge = ImageFont.truetype('C:/Windows/Fonts/consolab.ttf', 28)
        font_head = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 54)
        font_body = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 42)
        font_sub = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 26)

        # Top cyan border line
        draw.line([(140, 480), (940, 480)], fill='#00f0ff', width=2)
        draw.text((W/2, 540), title, fill='#00f0ff', font=font_badge, anchor='mm')

        # Body lines
        content = text or "Hello, I am JARVIS and I am the personal AI agent of Radon.\nI am currently in testing phase."
        lines = content.split('\n')
        start_y = 860
        for idx, l in enumerate(lines):
            f = font_head if idx == 0 else font_body
            c = '#ffffff' if idx == 0 else '#e0f7fa'
            draw.text((W/2, start_y), l.strip(), fill=c, font=f, anchor='mm')
            start_y += 85

        # Bottom line
        draw.line([(140, start_y + 80), (940, start_y + 80)], fill='#00f0ff', width=2)
        draw.text((W/2, start_y + 140), '[ SYSTEM OPERATIONAL // ONLINE ]', fill='#00ff88', font=font_sub, anchor='mm')

        os.makedirs('data', exist_ok=True)
        out_path = os.path.abspath('data/story_jarvis.jpg')
        img.save(out_path, quality=95)
        return out_path
    except Exception as e:
        logger.error(f"Failed to create story card: {e}")
        return ""

def upload_story(image_path: str = None, text: str = None) -> str:
    """Upload a photo story to Instagram."""
    cl = get_instagram_client()
    if not cl:
        return "Instagram client offline, Sir."
    import pathlib
    if not image_path or not os.path.exists(image_path):
        image_path = create_story_card(text)
    if not image_path or not os.path.exists(image_path):
        return "Failed to prepare story visual asset, Sir."
    try:
        story = cl.photo_upload_to_story(pathlib.Path(image_path).resolve(), caption=text or "")
        return f"Instagram story successfully broadcasted to @{cl.username}'s profile, Sir."
    except Exception as e:
        logger.error(f"Story upload error: {e}")
        return f"Failed to upload story: {e}"

def handle_instagram_tool(action: str, target: str = "", message: str = "") -> str:
    """Entry point for J.A.R.V.I.S. neural tool execution."""
    act = (action or "check").lower().strip()
    status_info = check_instagram_status()

    if not status_info["configured"]:
        return (
            "Instagram is not yet connected, Sir.\n"
            "Please configure your Instagram credentials or session ID in .env:\n"
            "INSTAGRAM_USERNAME=your_handle\n"
            "INSTAGRAM_PASSWORD=your_password\n"
            "Or for instant bypass of Meta's mobile blocks:\n"
            "INSTAGRAM_SESSIONID=your_sessionid_cookie\n"
        )

    cl = get_instagram_client()
    if not cl:
        return (
            "Sir, Instagram's login server intercepted the connection with Meta's mobile security wall:\n"
            "• Error: ClientNeedsUpgradeError (Meta blocks third-party mobile app emulation).\n\n"
            "To connect J.A.R.V.I.S. in 30 seconds without password or 2FA blocks:\n"
            "1. Open https://www.instagram.com in your browser (where you are already logged in).\n"
            "2. Press F12 -> Go to 'Application' (or 'Storage') tab -> expand 'Cookies' -> click 'https://www.instagram.com'.\n"
            "3. Copy the value of the 'sessionid' cookie.\n"
            "4. Add to .env: INSTAGRAM_SESSIONID=your_copied_sessionid\n\n"
            "Once saved, J.A.R.V.I.S. will immediately connect, monitor unread direct messages, and chat with friends on your behalf using neural AI."
        )

    if act in ["read", "check", "inbox", "get_dms"]:
        dms = get_unread_dms(limit=5)
        if not dms:
            return "No recent Instagram direct messages found, Sir."
        if isinstance(dms, list) and dms and "status" in dms[0] and dms[0]["status"] == "error":
            return dms[0]["message"]
        
        lines = [f"Found {len(dms)} Instagram DM thread(s):"]
        for d in dms:
            users = ", ".join(d.get("users", []))
            lines.append(f"• @{users}: \"{d.get('last_message', '')}\"")
        return "\n".join(lines)

    elif act in ["thread", "history", "view_conversation"]:
        return get_friend_thread(target)

    elif act in ["send", "reply", "dm", "message"]:
        if not target or not message:
            return "Sir, please specify the target username (e.g. '@username') and the message to transmit."
        res = send_instagram_dm(target, message)
        return res.get("message", "Transmission processed.")

    elif act in ["auto_reply", "automate", "talk_to_friends", "reply_friends", "chat_friends"]:
        replies = auto_reply_instagram_dms(target_friend=target)
        return "\n".join(replies)

    elif act in ["story", "upload_story", "post_story"]:
        return upload_story(text=message)

    return f"Instagram status: {json.dumps(status_info, indent=2)}"
