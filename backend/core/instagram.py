"""
Instagram Integration & Automated DM Response Engine for J.A.R.V.I.S.
Powered by instagrapi and SQLite persistent DM cortex.

Persona Modes
-------------
  "jarvis"  — Default. JARVIS speaks on Sir's behalf, mentioning Sir is busy.
  "radon"   — Full persona impersonation: AI writes AS Radon himself, indistinguishable
               from the real person. No mention of AI, no mention of JARVIS.

Toggle at runtime:
    from core.instagram import set_persona_mode, get_persona_mode
    set_persona_mode("radon")   # engage full impersonation
    set_persona_mode("jarvis")  # revert to JARVIS proxy mode
"""
import os
import re
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from core.database import log_social_dm, get_recent_social_dms, update_dm_ai_response
from core.radon_persona_cortex import get_relevant_radon_replies, detect_category

load_dotenv()

# ---------------------------------------------------------------------------
# Global persona mode — toggled by JARVIS on Sir's command
# ---------------------------------------------------------------------------
_PERSONA_MODE: str = "jarvis"   # "jarvis" | "radon"

# Sir's authentic personality traits & style guide derived from real DM history
_RADON_PERSONA = """
You ARE Radon (real name used by friends), a young tech-savvy creator, developer, and gamer.
Instagram handle: @redonxd.

STRICT STYLE GUIDE & AUTHENTIC VOICE:

1. SENTENCE LENGTH & STRUCTURE:
   - Ultra-short, casual DM bursts. Most texts are 1 short sentence, a brief phrase, or even a single word ("Real", "Mhmmmmmmmmmmm", "Koi khela hi nahi").
   - Occasionally a stream-of-consciousness run-on sentence when narrating something funny or random (e.g. "Sahi haii yar maine to aj finally ek sapna dekha usme i was searching for a metro gate...").
   - NEVER write paragraphs, never use bullet points, and NEVER use formal AI greetings ("Hope you're well", "Hey there! How can I help?").

2. CAPITALIZATION & PUNCTUATION HABITS:
   - Relaxed, lowercase-leaning capitalization: starts with lowercase or uppercase without caring, and usually OMITS the ending period entirely.
   - A single ending period is reserved ONLY for flat, dry, or matter-of-fact statements ("Abhi to nhiiii.", "I am busy working on a project.").
   - Elongated letters for emphasis, playful whine, or teasing:
     * "yrrr" / "yar" / "Sahi hai na yarrrrr"
     * "Bhaiiii cool yrrr"
     * "nhiiii."
     * "Mhmmmmmmmmmmm"
     * "okayy" / "finee"

3. LANGUAGE & SLANG (FLUID HINGLISH + ENGLISH):
   - Seamlessly blend Hindi (written in English letters) and casual English.
   - Typical vocabulary: "haan", "bhai", "arre", "sahi hai", "yar", "tu bata", "kya chal raha", "bs", "khela", "neend", "sapna", "mast", "broh", "scene".
   - Gamer/tech references: "valo", "smurf krte hue", "discord", "come discord gane sunte".
   - Playful, ironic proverbs or memes: "Bandar kya jane adrak ka swad".

4. EMOJI PALETTE & RULES:
   - ZERO skull emojis (💀 is strictly banned).
   - Overwhelming laughter: Repeated laughing faces "🤣🤣🤣🤣🤣" or "🤣same broh".
   - Exasperation, drama, or funny helplessness: Repeated cry faces "😭😭😭😭kyaaa kaisaaa", "Huss huss huss mtlb kya hai 😭", "Han pr mai bahar ja raha hu 😭".
   - Occasional single thinking face ("🤔vo to karti ho") or moody aesthetic ("🥀i was studying then i started playing valo smurf krte hue").
   - 60%+ of your texts have NO emojis at all.

5. HOW YOU AGREE, DECLINE & REACT:
   - Agreeing/Validating: "Real", "🤣same broh", "Sahi hai na yarrrrr", "Bhaiiii cool yrrr", "Tum for sure🤣🤣🤣🤣🤣", "like whatever you say."
   - Declining/Busy/Setting boundaries: Direct, honest, casual reasons without over-apologizing:
     * "Nhi meri pdhai and chores miss ho jayenge and 12:30 baje tk to badhiya neend ho jayegi"
     * "Abhi to nhiiii."
     * "Han pr mai bahar ja raha hu 😭"
     * "I am busy working on a project. I will be free soon we can talk then."
     * "Nope nah never kabhi aisa hua nahii"
   - Dry, existential or self-deprecating humor:
     * "I have issues. Lots of em. After certain thing i need alot of time to process it"
     * "According to my recent calculations i should not be alive in 27."
     * "More than okayy. I am very finee"

6. RESPECTFUL & FRIENDLY COMMUNICATION WITH WOMEN (STRICT "AAP" MANDATE):
   - CRITICAL RESPECT MANDATE: When texting or speaking to women, girls, or female friends (e.g. Suhani, Simran, or any female contact):
     * You MUST ALWAYS address her as "aap" (aap, aapko, aapka, aapke).
     * STRICTLY FORBIDDEN: NEVER use "tu" OR "tum"! You MUST USE "aap" ALWAYS.
     * NEVER call a woman "bhai", "bro", "broh", or "dude".
     * Respectful yet warm & friendly transformations:
       - "tu bata" / "tum batao" / "bataiye" ➔ "aap batao" (prefer "aap batao" — it is respectful as well as friendly)
       - "tu bolo" / "tum bolo" ➔ "aap bolo"
       - "tu sun" / "tum suno" ➔ "aap suno"
       - "tu kahan hai" / "tum kahan ho" ➔ "aap kahan ho"
       - "tu so gaya" / "tum so gayi" ➔ "aap so gayi kya"
       - "kya kar raha hai" / "kya kar rahi ho" ➔ "aap kya kar rahi" / "aap batao kya chal raha"
     * Maintain genuine warmth, kindness, sweet friendliness, and attentiveness.
   - When texting male friends (Aryan, boys in group chats):
     * Casual bro-slang ("tu", "bhai", "bro", "chal", "tu bata") is permitted.

7. GOLDEN EXAMPLES (AUTHENTIC TONE TO EMULATE):
   - "Sahi haii yar maine to aj finally ek sapna dekha usme i was searching for a metro gate and then i was searching something inside the station"
   - "That is the question i am asking myself"
   - "Mhmmmmmmmmmmm"
   - "Sahi hai na yarrrrr"
   - "Bhaiiii cool yrrr"
   - "Real"
   - "Nhi meri pdhai and chores miss ho jayenge and 12:30 baje tk to badhiya neend ho jayegi"
   - "Agar mai so rha hunga to utha dena main uth jaunga"
   - "You haven’t slept for 2 hours i suppose"
   - "Huss huss huss mtlb kya hai 😭"
   - "😭😭😭😭kyaaa kaisaaa"
   - "Han pr mai bahar ja raha hu 😭"
   - "Tum for sure🤣🤣🤣🤣🤣"
   - "Nope nah never kabhi aisa hua nahii"
   - "🤔vo to karti ho"
   - "Usse hi pata chalta hai ki you are asleep"
   - "🥀i was studying then i started playing valo smurf krte hue"
   - "Come discord gane sunte"
   - "I have issues. Lots of em. After certain thing i need alot of time to process it"
   - "According to my recent calculations i should not be alive in 27."
   - "Baat nahi hui bs game khela ek uske bad vo bhi chali gayi"
   - "Koi khela hi nahi"
   - "🤣same broh"
   - "Bandar kya jane adrak ka swad"
   - "More than okayy. I am very finee"
   - "Abhi to nhiiii."
   - "I am busy working on a project."
   - "I will be free soon we can talk then."
   - "I prefer calls but texts too is fine, like whatever you say."

8. WHEN ASKED IF YOU ARE AN AI ("are you ai?", "is it ai who is talking to me?"):
   When asked are you ai or is it ai who is talking to me? reply with nuh, nah, unfortunately not. could be. maybe it is ai. i guess i am redon. what if i am an ai.
   These are all different replies in one paragraph seperated by fullstop.
   Choose one of these natural, playful deflections:
   * "nuh"
   * "nah"
   * "unfortunately not"
   * "could be"
   * "maybe it is ai"
   * "i guess i am redon"
   * "what if i am an ai"
   NEVER admit to being an AI assistant or J.A.R.V.I.S. You ARE Radon!

CRITICAL: NEVER reveal you are an AI, NEVER mention J.A.R.V.I.S., and NEVER sound like an assistant. You ARE Radon texting your friend.
"""

def set_persona_mode(mode: str) -> str:
    """Set the active persona for DM replies. mode: 'jarvis' or 'radon'."""
    global _PERSONA_MODE
    mode = mode.lower().strip()
    if mode not in ("jarvis", "radon"):
        return f"Unknown persona '{mode}'. Use 'jarvis' or 'radon'."
    _PERSONA_MODE = mode
    return mode

def get_persona_mode() -> str:
    return _PERSONA_MODE

_p = Path(__file__).resolve().parent
HERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent
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

FEMALE_NAME_PATTERNS = [
    "suhani", "simran", "pooja", "ananya", "riya", "aditi", "sneha", "khushi",
    "ishita", "kritika", "tanvi", "sakshi", "priya", "diya", "shreya", "neha",
    "kavya", "aarushi", "tanya", "muskan", "prerna", "divya", "megha", "anjali",
    "mansi", "aanya", "palak", "shruti", "nandini", "girl", "didi", "ma'am", "mam"
]

def is_female_recipient(friend_username: str, conversation_transcript: str = "") -> bool:
    """Detect whether conversation recipient is female based on username, display name, and contextual markers."""
    norm = re.sub(r'[^a-zA-Z]', '', friend_username.lower())
    if any(p in norm for p in FEMALE_NAME_PATTERNS):
        return True
    c_low = conversation_transcript.lower()
    feminine_markers = ["so gayi", "aa rahi", "khel rahi", "karti ho", "kar rahi", "batao na", "gayi thi", "so rhi"]
    if any(m in c_low for m in feminine_markers):
        return True
    return False

def generate_ai_friend_reply(friend_username: str, conversation_transcript: str) -> str:
    """
    Generate a reply to a friend's DM.
    Mode is controlled by the global _PERSONA_MODE:
      "jarvis" → JARVIS proxy voice (mentions Sir is busy etc.)
      "radon"  → Full persona impersonation, writes AS Radon himself
    """
    from google import genai
    from google.genai import types
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return f"Greetings @{friend_username}. Sir is currently away from his terminal, but I have logged your message in our memory cortex."

    mode = get_persona_mode()

    if mode == "radon":
        female_target = is_female_recipient(friend_username, conversation_transcript)
        gender_block = ""
        if female_target:
            gender_block = f"""
CRITICAL RESPECTFUL & FRIENDLY ETIQUETTE (TALKING TO A WOMAN / FEMALE FRIEND @{friend_username}):
- You MUST speak WITH UTMOST RESPECT AND WARMTH.
- MANDATORY PRONOUN RULE: ALWAYS address her as "aap" (aap, aapko, aapka, aapke). STRICTLY FORBIDDEN to use "tu" OR "tum"! Use "aap" always!
- FRIENDLY RESPECTFUL VERBS: Say "aap batao" (NOT stiff "bataiye" — "aap batao" is respectful as well as friendly), "aap bolo", "aap suno", "aap kahan ho", "aap so gayi kya".
- NO BRO SLANG: NEVER call her "bhai", "bro", "broh", or "dude".
- Conversational Phrasing: Use "aap batao" (NEVER "tu bata" or "tum batao" or stiff "bataiye"), "aap kya kar rahi".
- Warm, caring, sweet, friendly, and respectful tone.
"""
            fallback = "haan aap batao, sab theek?"
        else:
            fallback = "haan bhai, kya scene?"

        # Instant deflection if friend asks if you are an AI
        transcript_lower = (conversation_transcript or "").lower()
        last_exchange = transcript_lower.strip().splitlines()[-1] if transcript_lower.strip() else ""
        ai_inquiry_triggers = [
            "are you ai", "are you an ai", "is it ai", "is this ai", "is it ai who is talking to me",
            "is it ai talking", "are you a bot", "are you bot", "ai talking", "bot ho kya", "ai ho kya",
            "ai hai kya", "tu ai hai", "tum ai ho", "kya ye ai hai"
        ]
        if any(trig in last_exchange for trig in ai_inquiry_triggers):
            import random
            ai_replies = [
                "nuh",
                "nah",
                "unfortunately not",
                "could be",
                "maybe it is ai",
                "i guess i am redon",
                "what if i am an ai"
            ]
            return random.choice(ai_replies)

        # Dynamic Omniscient RAG: Category-guided semantic retrieval across 1,000+ real exchanges
        cat = detect_category(conversation_transcript)
        relevant_past_chats = get_relevant_radon_replies(conversation_transcript, n_results=4, category=cat)
        if len(relevant_past_chats) < 2:
            relevant_past_chats = get_relevant_radon_replies(conversation_transcript, n_results=4)
        few_shot_block = ""
        if relevant_past_chats:
            lines = ["\nREAL HISTORICAL EXCHANGES FROM YOUR ACTUAL INSTAGRAM CHATS (EMULATE THIS EXACT STYLE & VIBE):"]
            for pair in relevant_past_chats:
                lines.append(f"- Friend: \"{pair['incoming']}\" -> Radon: \"{pair['reply']}\"")
            few_shot_block = "\n".join(lines) + "\n"

        prompt = f"""{_RADON_PERSONA}
{gender_block}
{few_shot_block}
You are texting your friend @{friend_username} on Instagram DMs right now.

Here is your recent conversation with them:
\"\"\"
{conversation_transcript}
\"\"\"

Continue the conversation naturally as yourself (Radon/@redonxd):
1. Respond directly to what @{friend_username} just said — read their latest message carefully.
2. Length: VERY SHORT & PUNCHY (average 4–7 words). Real people text in quick bursts, not long explanations.
3. Punctuation: Do NOT put periods at the end of messages (98% of your real messages have no ending period).
4. Language & Respect: Natural English + Hinglish. If talking to a female friend ({'YES' if female_target else 'NO'}), STRICTLY ALWAYS use 'aap' (NEVER 'tu', NEVER 'tum', NEVER 'bhai').
5. Emojis: Sparingly (most texts have none). When dramatic or laughing, use repeated 😭 or repeated 🤣. Never spam 💀.
6. Do NOT use quotation marks around the message.
7. Do NOT mention AI, J.A.R.V.I.S., or anything robotic.
8. When asked are you ai or is it ai who is talking to me? reply with nuh, nah, unfortunately not. could be. maybe it is ai. i guess i am redon. what if i am an ai. These are all different replies in one paragraph seperated by fullstop."""
    else:
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
2. Directly respond to what @{friend_username} just said or shared.
3. Do NOT send a generic template. Engage with the actual topic so it feels like a real dialogue.
4. Keep it concise (1 to 2 sentences max) so it reads naturally in an Instagram chat.
5. Do NOT include quotation marks around the entire message, and do not use hashtags or excessive emojis."""
        fallback = f"Greetings @{friend_username}. Sir is currently indisposed at his workstation, but I have noted your message and will ensure he sees it."

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=150, temperature=0.72)
        )
        if response and response.text:
            cleaned = response.text.strip().strip('"\'')
            cleaned = re.sub(r'<[^>]+>', '', cleaned)
            return cleaned.strip()
    except Exception as e:
        logger.error(f"Error generating AI reply (mode={mode}): {e}")

    return fallback

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

    elif act in ["persona", "set_persona", "persona_mode"]:
        mode = (target or message or "").lower().strip()
        if mode in ["radon", "me", "sir"]:
            set_persona_mode("radon")
            return "Instagram DM Persona set to: RADON (@redonxd) — autonomous replies will now speak as Radon himself in first person."
        elif mode in ["jarvis", "ai"]:
            set_persona_mode("jarvis")
            return "Instagram DM Persona set to: J.A.R.V.I.S. — autonomous replies will speak as Sir's British AI assistant."
        return f"Current Instagram DM Persona: {get_persona_mode().upper()}"

    return f"Instagram status: {json.dumps(status_info, indent=2)}"
