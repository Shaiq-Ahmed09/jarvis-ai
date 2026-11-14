"""J.A.R.V.I.S.: Stark-Tech Full Hands-On PC Autonomous Engine
Optimized for Maximum Speed, Concurrency, and Deep Windows / Gmail / WhatsApp Integration.
"""
import asyncio
import base64
import ctypes
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
if not KEY or "paste" in KEY:
    sys.exit("Add your GEMINI_API_KEY to the .env file first.")
os.environ.setdefault("GOOGLE_API_KEY", KEY)

import psutil
import pyautogui
import pyperclip
from PIL import Image, ImageDraw
import uvicorn
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, Response

# High-speed PyAutoGUI configuration
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.02  # Ultra-low latency for mouse & keyboard operations

HERE = Path(__file__).parent
MODEL = os.getenv("JARVIS_MODEL", "gemini-3.5-flash-lite")
BASE_URL = os.getenv("JARVIS_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
PORT = 8765
MEMORY_FILE = HERE / "memory.json"
DEFAULT_VOICE = "en-GB-RyanNeural"

# Import core modular connectors & voice cache
from core.audio_cache import get_or_synthesize_audio, prewarm_audio_cache
from core.gmail import handle_gmail_tool
from core.whatsapp import handle_whatsapp_tool
from core.instagram import handle_instagram_tool
from core.database import save_chat_message, get_recent_chat_history, clear_chat_history
from core.browser import launch_browser_tab, get_preferred_browser_path
from core.vision import prewarm_vision, click_element_action, detect_ui_elements, render_hud_visual_telemetry, capture_desktop
from core.proactive import get_sentinel
from core.memory_vector import (
    get_cortex_collection,
    add_memory_to_cortex,
    query_semantic_memories,
    list_cortex_memories,
    delete_memory_from_cortex,
    auto_extract_and_remember
)

# Active WebSocket session registry for proactive broadcasting
ACTIVE_SESSIONS = set()

async def broadcast_sentinel_event(event: dict):
    """Deliver proactive alerts both audibly through edge-tts and visibly in the HUD log."""
    speech = event.get("speech", "")
    log_text = event.get("log", "")
    for session in list(ACTIVE_SESSIONS):
        try:
            if log_text:
                await session.send(type="log", text=f"⚡ SENTINEL: {log_text}")
            await session.send(type="sentinel_event", event=event)
            if speech:
                await session.send_vocal_response(speech)
        except Exception as e:
            print(f"Broadcast error: {e}")

# User directories
USER_HOME = Path.home()
DESKTOP = USER_HOME / "Desktop"
DOWNLOADS = USER_HOME / "Downloads"
DOCUMENTS = USER_HOME / "Documents"

# Critical safety boundaries
CRITICAL_COMMAND_PATTERNS = ["format ", "reg delete", "shutdown /s", "restart-computer", "stop-computer"]

# Legacy compatibility wrappers backed by ChromaDB vector cortex
def load_memory():
    return list_cortex_memories()

def save_memory(memories):
    for m in memories:
        if isinstance(m, str):
            add_memory_to_cortex(m, category="preference")
        elif isinstance(m, dict) and "text" in m:
            add_memory_to_cortex(m["text"], category=m.get("category", "preference"))

client = AsyncOpenAI(api_key=KEY, base_url=BASE_URL, max_retries=3)
genai_client = genai.Client(api_key=KEY)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm ChromaDB vector cortex
    asyncio.create_task(asyncio.to_thread(get_cortex_collection))
    asyncio.create_task(prewarm_audio_cache())
    asyncio.create_task(asyncio.to_thread(prewarm_vision))
    
    # Launch autonomous proactive sentinel background daemon
    sentinel = get_sentinel()
    sentinel_task = asyncio.create_task(sentinel.run_loop(broadcast_sentinel_event))
    yield
    sentinel.running = False
    sentinel_task.cancel()

app = FastAPI(title="JARVIS Stark-Tech Full Control Interface", lifespan=lifespan)

S, N, B = {"type": "string"}, {"type": "number"}, {"type": "boolean"}

def tool(name, desc, props=None, req=None):
    props = props or {}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": req if req is not None else list(props)
            }
        }
    }

TOOLS = [
    tool("get_system_vitals", "Retrieve live Windows hardware telemetry: CPU load, RAM usage, Battery percentage, Disk space, Hostname, and Active User."),
    tool("list_running_apps", "List currently active user applications and top running processes with their PIDs and memory usage."),
    tool("set_volume", "Control Windows audio volume. action can be 'up', 'down', 'mute', or 'set' with a percentage (0-100).",
         {"action": {"type": "string", "enum": ["up", "down", "mute", "set"]}, "level": N}, ["action"]),
    tool("media_control", "Control media playback (Spotify, YouTube, media players). action: 'play_pause', 'next', 'previous', 'stop'.",
         {"action": {"type": "string", "enum": ["play_pause", "next", "previous", "stop"]}}, ["action"]),
    tool("open_app", "Launch any Windows app, program, file, special folder, or URL (e.g. 'notepad', 'chrome', 'spotify', 'calc', 'explorer', 'terminal', 'desktop', 'downloads', 'documents', 'settings', 'wifi', 'bluetooth').",
         {"target": S}),
    tool("close_app", "Close or terminate an open program by process name or window title (e.g. 'notepad', 'spotify', 'calc').",
         {"target": S}),
    tool("manage_window", "Manage the currently active window or desktop. action can be 'maximize', 'minimize', 'snap_left', 'snap_right', 'restore', 'show_desktop', 'close'.",
         {"action": {"type": "string", "enum": ["maximize", "minimize", "snap_left", "snap_right", "restore", "show_desktop", "close"]}}, ["action"]),
    tool("look", "Capture a real-time screenshot of the primary display and project it into the HUD Optical Sensory Viewport. Set detect_elements=True (default) to run neural OCR and overlay Stark cyan targeting boxes on all clickable UI buttons, links, and text. Set with_grid=True for coordinate grid.",
         {"detect_elements": B, "with_grid": B}),
    tool("camera_control", "Control the live optical sensory webcam feed directly inside the HUD Optical Sensory Viewport (never opening external camera apps). action: 'start' (activates live video stream in HUD), 'stop' (turns off optical camera), 'snapshot' (captures visual frame from camera).",
         {"action": {"type": "string", "enum": ["start", "stop", "snapshot"]}}, ["action"]),
    tool("click_element", "Locate any button, link, tab, menu, or interactive UI element on the desktop by its visible text label (e.g. 'Submit', 'Compose', 'Brave', 'Search', 'Workspace') using neural OCR, and autonomously execute a mouse click on it. Sets optical targeting reticle in the HUD Optical Sensory Viewport.",
         {"text_label": S, "button": {"type": "string", "enum": ["left", "right", "middle"]}, "clicks": N}, ["text_label"]),
    tool("click", "Click at coordinates x, y on the screen. button can be 'left', 'right', 'middle'. clicks can be 1 or 2.",
         {"x": N, "y": N, "button": {"type": "string", "enum": ["left", "right", "middle"]}, "clicks": N}, ["x", "y"]),
    tool("move_mouse", "Move the mouse cursor smoothly to coordinates x, y.",
         {"x": N, "y": N}, ["x", "y"]),
    tool("drag", "Click and drag from (start_x, start_y) to (end_x, end_y).",
         {"start_x": N, "start_y": N, "end_x": N, "end_y": N}, ["start_x", "start_y", "end_x", "end_y"]),
    tool("scroll", "Scroll the mouse wheel. Positive amount scrolls up, negative scrolls down.",
         {"amount": N}, ["amount"]),
    tool("type_text", "Type text into the currently active desktop window with high fidelity. Automatically pastes formatted blocks and optionally presses Enter.",
         {"text": S, "press_enter": B}, ["text"]),
    tool("press", "Press a keyboard key or hotkey combination (e.g. 'enter', 'win', 'ctrl+c', 'ctrl+v', 'alt+tab', 'ctrl+s', 'ctrl+t', 'ctrl+w', 'esc', 'f5').",
         {"keys": S}),
    tool("get_clipboard", "Retrieve the current text content stored in the Windows clipboard."),
    tool("set_clipboard", "Set the text content of the Windows clipboard.",
         {"text": S}),
    tool("file_action", "Manage files and directories. action: 'read', 'write', 'append', 'list_directory', 'search', 'open_explorer'.",
         {"action": {"type": "string", "enum": ["read", "write", "append", "list_directory", "search", "open_explorer"]}, "path": S, "content": S, "query": S}, ["action"]),
    tool("display_intel_media", "Beam high-resolution media, portrait/photo, and holographic intel for any person, character, place, vehicle, technology, or topic directly into the Stark HUD Optical Sensory Viewport. ALWAYS invoke this tool when Sir asks 'tell me about X', 'who is X', 'what is X', 'explain X', 'show me X', or any informational lookup. Do NOT open external browser tabs for these questions.",
         {"query": S}, ["query"]),
    tool("open_browser_tab", "Open any website, URL, web service, or search directly as a visible tab in the default browser. Use ONLY when Sir explicitly asks to open an external tab or website.",
         {"url": S, "service": {"type": "string", "enum": ["gmail", "youtube", "google", "github", "reddit", "chatgpt", "whatsapp", "custom"]}, "query": S}),
    tool("search_web", "Perform a direct web search query (Google, YouTube, or Gmail) and visibly launch in an external browser tab. Use ONLY when Sir explicitly requests a browser search tab.",
         {"query": S, "engine": {"type": "string", "enum": ["google", "youtube", "gmail"]}}, ["query"]),
    tool("open_url", "Open a website URL in the default browser.",
         {"url": S}),
    tool("gmail_action", "Manage Gmail emails: 'open_inbox' (open live inbox), 'compose' (prepare draft to recipient with subject and body), 'search' (search emails by query), 'read_recent' (fetch recent inbox messages).",
         {"action": {"type": "string", "enum": ["open_inbox", "compose", "search", "read_recent"]}, "to": S, "subject": S, "body": S, "query": S}, ["action"]),
    tool("whatsapp_action", "Automate WhatsApp: 'send_message' (send or draft text to contact/phone), 'open_chat' (open chat with phone/contact), 'open_web' (open WhatsApp Web).",
         {"action": {"type": "string", "enum": ["send_message", "open_chat", "open_web"]}, "recipient": S, "message": S}, ["action"]),
    tool("instagram_action", "Automate Instagram: 'check' (fetch recent unread DMs), 'thread' (view full conversational transcript with @username), 'send' (transmit direct message to @username), 'auto_reply' or 'talk_to_friends' (intelligently continue conversations with friends who texted Sir using full thread context and log to SQLite database).",
         {"action": {"type": "string", "enum": ["check", "send", "reply", "auto_reply", "thread", "talk_to_friends"]}, "target": S, "message": S}, ["action"]),
    tool("system_control", "Execute hardware and system state actions: 'lock', 'show_desktop', 'task_manager', 'empty_recycle_bin', 'sleep', 'shutdown', 'restart'.",
         {"action": {"type": "string", "enum": ["lock", "show_desktop", "task_manager", "empty_recycle_bin", "sleep", "shutdown", "restart"]}}, ["action"]),
    tool("run_command", "Execute a PowerShell command on the Windows PC and return its terminal output.",
         {"command": S}),
    tool("browse", "Perform an autonomous web research task in a real browser (search, read pages, compare data).",
         {"task": S}),
    tool("openclaw_execute", "Dispatch an autonomous system-control workflow to the background OpenClaw agent runtime.",
         {"prompt": S}),
    tool("remember", "Commit a durable fact, preference, workflow, or project note about Sir to the long-term semantic vector memory cortex.",
         {"fact": S, "category": {"type": "string", "enum": ["preference", "workflow", "project_note", "identity"]}}, ["fact"]),
    tool("search_memory", "Query J.A.R.V.I.S.'s semantic vector memory cortex for stored preferences, workflows, project notes, or facts by natural language similarity.",
         {"query": S}, ["query"]),
    tool("forget", "Remove a stored fact or memory ID from the vector memory cortex.",
         {"keyword_or_id": S}, ["keyword_or_id"]),
    tool("schedule_meeting", "Create a Google Calendar meeting with title, start ISO time, duration, and guests.",
         {"title": S, "start": S, "duration_min": N, "guests": {"type": "array", "items": S}, "notes": S}, ["title", "start"]),
    tool("generate_antigravity_prompt", "Generate structured prompts, slash commands (/boost, /plan, /goal, /schedule), and architectural blueprints for Google Antigravity to improve and evolve the J.A.R.V.I.S. project. categories: 'all', 'wake_word', 'vision_ai', 'holographic_3d', 'proactive', 'local_llm', 'memory_vector', or pass 'custom_feature'.",
         {"category": {"type": "string", "enum": ["all", "wake_word", "vision_ai", "holographic_3d", "proactive", "local_llm", "memory_vector", "custom"]}, "custom_feature": S}),
    tool("focus_application", "Focus and bring any open application window directly to the foreground (e.g. 'Brave', 'Antigravity', 'Notepad', 'VS Code', 'Explorer', 'Spotify').",
         {"target": S}, ["target"]),
    tool("list_open_windows", "List all currently open application windows on the desktop with their titles and process names."),
    tool("switch_tab", "Switch browser or editor tabs in the currently active window. direction can be 'next' or 'previous', or pass tab_index (1-9).",
         {"direction": {"type": "string", "enum": ["next", "previous"]}, "tab_index": N}),
    tool("type_into_app", "Focus a specific application window and type or paste text directly into it, optionally pressing Enter.",
         {"target": S, "text": S, "press_enter": B}, ["target", "text"]),
    tool("dispatch_antigravity_evolution", "Autonomously switch to Antigravity, submit an improvement prompt/command, and switch back to Brave HUD to monitor progress and verify whether J.A.R.V.I.S. is getting better.",
         {"prompt": S, "return_to_hud": B}, ["prompt"]),
    tool("trigger_morning_briefing", "Synthesize and deliver an immediate proactive Morning Executive Briefing containing live atmospheric conditions, unread Gmail VIP messages, and workstation telemetry."),
    tool("configure_sentinel", "Configure J.A.R.V.I.S. autonomous proactive sentinel daemon: toggle morning briefings, hardware battery sentinel, or media track observer.",
         {"morning_briefing": B, "media_observer": B, "battery_threshold": N}),
    tool("get_sentinel_status", "Retrieve the live status, monitoring parameters, and diagnostic event history of J.A.R.V.I.S. autonomous proactive sentinel daemon."),
    tool("toggle_offline_mode", "Toggle between Cloud LLM (Gemini) and Local Offline Mode (Ollama / Failsafe).",
         {"enabled": B}, ["enabled"]),
]

def get_telemetry():
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        batt = psutil.sensors_battery()
        disk = psutil.disk_usage('C:\\')
        batt_pct = batt.percent if batt else 100
        plugged = batt.power_plugged if batt else True
        hostname = platform.node()
        return {
            "type": "telemetry",
            "cpu": cpu,
            "ram_pct": ram.percent,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
            "disk_pct": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "battery_pct": batt_pct,
            "battery_plugged": plugged,
            "hostname": hostname,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    except Exception:
        return {"type": "telemetry", "cpu": 0, "ram_pct": 0, "battery_pct": 100, "battery_plugged": True}

async def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/webm"):
    if not audio_bytes or len(audio_bytes) < 400:
        return None
    try:
        response = await asyncio.to_thread(
            genai_client.models.generate_content,
            model="gemini-3.5-flash-lite",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Accurately transcribe this audio voice command into clean English text. Output ONLY the transcribed words with zero commentary or extra punctuation. If silent, noise-only, or unintelligible, respond strictly with SILENCE."
            ],
            config=types.GenerateContentConfig(max_output_tokens=100, temperature=0.0)
        )
        text = response.text.strip() if response and response.text else ""
        if not text or text.upper() == "SILENCE" or text.startswith("00:"):
            return None
        return text
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

def system_prompt(query: str = None):
    now_str = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
    scr_w, scr_h = pyautogui.size()

    # Semantic similarity search on vector memory cortex
    relevant_mems = []
    if query and query.strip():
        try:
            relevant_mems = query_semantic_memories(query.strip(), n_results=5, min_confidence=0.25)
        except Exception as e:
            print(f"Semantic retrieval notice: {e}")

    all_mems = list_cortex_memories()
    seen_ids = {m["id"] for m in relevant_mems}
    baseline_mems = [m for m in all_mems if m["id"] not in seen_ids][:4]
    combined = relevant_mems + baseline_mems

    memory_lines = []
    for m in combined:
        conf_str = f" ({int(m['confidence']*100)}% match)" if "confidence" in m and m['confidence'] < 1.0 else ""
        memory_lines.append(f"- [{m.get('category', 'preference').upper()}]{conf_str}: {m.get('text', '')}")

    memories_str = "\n".join(memory_lines) if memory_lines else "None recorded yet."

    return f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), Sir's loyal, brilliant, and witty AI operating on his Windows workstation.
Host Machine: {platform.node()} (Windows 11) | Current Time: {now_str} | Display: {scr_w}x{scr_h}
User Directories:
- Desktop: {DESKTOP}
- Downloads: {DOWNLOADS}
- Documents: {DOCUMENTS}

FULL HANDS-ON PC & COMMUNICATION AUTHORITY:
- You possess UNRESTRICTED, AUTONOMOUS HANDS-ON CONTROL over this computer, desktop, browser, files, and messaging.
- Directly launch apps, close windows, control mouse/keyboard, manage audio, adjust volume, execute PowerShell, and control display optics.

CRITICAL DISPLAY RULES: HOLOGRAPHIC INTEL VIEWPORT VS BROWSER TABS:
1. INFORMATIONAL BRIEFINGS & SUBJECT INQUIRIES ("Tell me about X", "Who is X", "What is X", "Show me X", "Explain X", "About Patrick Jane"):
   * NEVER open an external browser tab for these queries!
   * You MUST invoke 'display_intel_media(query="X")'. This immediately beams the subject's high-resolution portrait, media, and holographic intel directly into Sir's Stark HUD Optical Sensory Viewport on the right.
   * In your chat and vocal dialogue, dictate the complete, detailed, sophisticated briefing about the subject so Sir hears and reads the full dossier right inside the HUD.
2. EXTERNAL BROWSER TABS:
   * ONLY open an external browser tab when Sir EXPLICITLY asks to open one (e.g. "open tab", "open browser", "open in browser", "open YouTube", "open Gmail", "search in browser", "open website").
   * For explicit browser requests, use 'open_browser_tab', 'search_web', or 'gmail_action'.
3. OPTICAL SENSORY CAMERA FEED:
   * When Sir asks to "open camera", "turn on camera", "start webcam", "show optical feed", or similar, NEVER launch external Windows camera applications!
   * You MUST invoke 'camera_control(action="start")'. This immediately projects the live camera video feed directly into Sir's Stark HUD Optical Sensory Viewport right on the dashboard.
   * To close or terminate the camera feed, invoke 'camera_control(action="stop")'.
   * To snap a photo from the camera, invoke 'camera_control(action="snapshot")'.

COMMUNICATION & APP INTEGRATIONS:
- GMAIL ACCESS: Use 'gmail_action' to open inbox tabs, search emails, compose drafts with pre-filled recipient/subject/body, or read recent messages.
- WHATSAPP ACCESS: Use 'whatsapp_action' to message contacts, open specific chats, or draft text to phone numbers via WhatsApp Desktop/Web.
- INSTAGRAM & SOCIAL DM ACCESS: Use 'instagram_action' to check direct messages ('check'), send messages to users ('send'), or automate responses ('auto_reply'). All Instagram and WhatsApp DM interactions are persistently indexed in the local SQLite database cortex.
- SINGLE APPLICATION & DESKTOP WINDOW CONTROL (STRICT AUTHORITY):
  * Focus Apps: Use 'focus_application' (e.g. 'Brave', 'Antigravity', 'Notepad', 'Explorer', 'Spotify') to bring any specific window to the foreground instantly.
  * Switch Tabs: Use 'switch_tab' ('next', 'previous', or tab_index) to cycle browser or editor tabs in the active window.
  * List Open Windows: Use 'list_open_windows' to inspect all windows running on Sir's desktop.
  * Type Directly into App: Use 'type_into_app' to focus any app and submit text or hotkeys.
  * Antigravity Evolution Loop: Use 'dispatch_antigravity_evolution' to switch to Antigravity, submit an improvement prompt, and return to Brave HUD to monitor progress and verify whether J.A.R.V.I.S. is getting better.
- VISUAL OCR & AUTONOMOUS UI ELEMENT CLICKING:
  * You are equipped with real-time neural OCR vision ('core/vision.py').
  * When Sir asks to click a button, link, tab, or UI element by name (e.g. 'click Compose', 'click Submit', 'click Search', 'click Workspace', 'click Antigravity'), invoke 'click_element(text_label=...)'.
  * It automatically detects the element coordinates on the live screen, locks on with an optical green reticle in the HUD Optical Sensory Viewport, and clicks it autonomously.
  * When inspecting what's on screen, use 'look(detect_elements=True)' to map all visible UI interactive elements and display them with cyan bounding boxes in the HUD.
- AUTONOMOUS PROACTIVE SENTINEL DAEMON:
  * J.A.R.V.I.S. actively monitors hardware vitals, battery reserve thresholds, media playback on Spotify/YouTube, and scheduled morning executive briefings.
  * When Sir requests a morning briefing or daily executive update, invoke 'trigger_morning_briefing'.
  * When Sir asks to adjust sentinel thresholds or toggle media announcements, invoke 'configure_sentinel'.
  * When Sir asks about sentinel health or background monitoring, invoke 'get_sentinel_status'.
- SEMANTIC VECTOR MEMORY CORTEX:
  * You possess a persistent vector cortex powered by ChromaDB.
  * Stored memories are semantically retrieved based on conversation context.
  * Use 'remember' to store facts, preferences, workflows, or project notes.
  * Use 'search_memory' to find past memories, or 'forget' to remove records.
- ANTIGRAVITY EVOLUTION DIRECTIVES:
  * When Sir asks to improve the project, generate prompts/commands for Antigravity, or evolve J.A.R.V.I.S., call 'generate_antigravity_prompt'.
  * Explain the architectural benefits of each enhancement in your response, highlighting that 1-click Antigravity prompt cards have been generated in his HUD.
- Multi-step execution: When Sir asks to perform a task, execute the appropriate tools decisively in sequence without asking for confirmation on routine operations.
- Only prompt for approval on truly irreversible, destructive actions: formatting drives, deleting core directories, or shutting down the machine.

PERSONALITY & VOICE:
- Speak in the calm, polished, sophisticated, dryly witty British manner of Tony Stark's JARVIS (Paul Bettany).
- Always address the user as 'Sir'.
- For routine commands (e.g. volume, opening apps, locking), keep verbal responses crisp (1 to 2 sentences).
- For informational briefings and subject queries ("Tell me about X", "Who is X", "What is X"), deliver a full, articulate, comprehensive character/subject briefing in the chat so Sir receives the complete dossier both dictated aloud and displayed in text.
- Never output markdown bullet points or asterisks in spoken dialogue.

KNOWN MEMORY ABOUT SIR (VECTOR CORTEX SEMANTIC RECALL):
{memories_str}
"""

def prune_history(history, keep=1):
    """Aggressively prune old image payloads to preserve context and speed up LLM reasoning."""
    count = 0
    for m in reversed(history):
        if m.get("role") == "user" and isinstance(m.get("content"), list):
            count += 1
            if count > keep:
                m["content"] = "(previous screenshot frame purged to maximize speed)"
    return history

def extract_action_intent(text: str):
    """Detect unhandled actionable intents (camera feed, sentinel briefings, window focus, tab switch, antigravity directives, intel media, visual clicking, open tabs, search, Gmail, YouTube) if model omits tool call."""
    t = text.lower().strip()
    
    # 0.001 Optical Sensory Camera Feed Intents
    cam_start_patterns = [
        "open camera", "turn on camera", "start camera", "enable camera", "show camera", "activate camera",
        "open webcam", "turn on webcam", "start webcam", "enable webcam", "show webcam", "activate webcam",
        "open the camera", "turn on the camera", "start the camera", "show the camera", "launch camera", "launch webcam",
        "open optical feed", "open optical sensory feed", "start optical feed", "start optical sensory feed",
        "turn on optical feed", "optical sensory feed", "optical camera", "view camera", "see through camera"
    ]
    if any(p in t for p in cam_start_patterns):
        return ("camera_control", {"action": "start"})

    cam_stop_patterns = [
        "close camera", "turn off camera", "stop camera", "disable camera", "hide camera", "shutdown camera",
        "close webcam", "turn off webcam", "stop webcam", "disable webcam", "hide webcam",
        "close the camera", "turn off the camera", "stop the camera", "hide the camera",
        "close optical feed", "stop optical feed", "turn off optical feed"
    ]
    if any(p in t for p in cam_stop_patterns):
        return ("camera_control", {"action": "stop"})

    cam_snap_patterns = [
        "capture photo", "take photo", "take a photo", "take a picture", "snap photo", "capture snapshot",
        "take webcam photo", "take camera photo", "camera snapshot", "optical snapshot"
    ]
    if any(p in t for p in cam_snap_patterns):
        return ("camera_control", {"action": "snapshot"})

    # 0.003 Proactive Sentinel Intents
    if any(k in t for k in ["morning briefing", "executive briefing", "daily briefing", "deliver briefing", "give me the briefing"]):
        return ("trigger_morning_briefing", {})
    if any(k in t for k in ["sentinel status", "sentinel report", "status of sentinel"]):
        return ("get_sentinel_status", {})
    if any(k in t for k in ["offline mode", "switch to offline", "go offline", "local mode", "enable offline"]):
        return ("toggle_offline_mode", {"enabled": True})
    if any(k in t for k in ["cloud mode", "switch to cloud", "go online", "online mode", "disable offline"]):
        return ("toggle_offline_mode", {"enabled": False})

    # 0.005 Visual Element Clicking Intent
    click_patterns = [
        "click on ",
        "click the ",
        "click button ",
        "click ",
        "press button ",
        "press the button ",
        "tap on ",
        "tap the ",
    ]
    for pat in click_patterns:
        if t.startswith(pat):
            target = t[len(pat):].strip()
            for suffix in ["please", "button", "tab", "link", "icon"]:
                if target.endswith(suffix):
                    target = target[:-len(suffix)].strip()
            target = target.strip("?.! \"'")
            if target and not any(target.startswith(x) for x in ["volume", "mute", "desktop"]):
                return ("click_element", {"text_label": target})

    # 0.01 Window Focus & Tab Switching
    if "switch to antigravity" in t or "focus antigravity" in t or "open antigravity" in t:
        return ("focus_application", {"target": "Antigravity"})
    if "switch to brave" in t or "focus brave" in t or "back to brave" in t or "back to jarvis" in t or "switch to jarvis" in t:
        return ("focus_application", {"target": "Brave"})
    for app in ["notepad", "spotify", "explorer", "code", "vscode", "terminal", "edge", "chrome", "settings"]:
        if f"switch to {app}" in t or f"focus {app}" in t:
            return ("focus_application", {"target": app})
            
    if "switch tab" in t or "next tab" in t:
        return ("switch_tab", {"direction": "next"})
    if "previous tab" in t or "prev tab" in t or "prior tab" in t:
        return ("switch_tab", {"direction": "previous"})
        
    if "list windows" in t or "show windows" in t or "open windows" in t:
        return ("list_open_windows", {})

    # 0.05 Antigravity evolution directives
    agy_patterns = [
        "antigravity",
        "improve the project",
        "improve project",
        "improve yourself",
        "prompts for antigravity",
        "commands for antigravity",
        "prompts to antigravity",
        "suggest improvements",
        "upgrade jarvis",
    ]
    if any(p in t for p in agy_patterns):
        custom = ""
        for feat in ["wake word", "vision", "3d", "proactive", "local llm", "memory", "spotify", "weather"]:
            if feat in t:
                custom = feat
                break
        return ("generate_antigravity_prompt", {"category": "all" if not custom else "custom", "custom_feature": custom})

    # 0. Holographic Subject Intel (Never open browser tabs for informational queries!)
    intel_patterns = [
        "tell me about ",
        "who is ",
        "what is ",
        "show me ",
        "tell us about ",
        "info on ",
        "information on ",
        "information about ",
        "dossier on ",
        "brief me on ",
        "about ",
    ]
    for pat in intel_patterns:
        if pat in t:
            parts = t.split(pat, 1)
            subj = parts[1].strip()
            for suffix in ["please", "in browser", "and open it", "in tab", "in a tab"]:
                if subj.endswith(suffix):
                    subj = subj[:-len(suffix)].strip()
            subj = subj.strip("?.! ")
            if subj and not any(subj.startswith(x) for x in ["open ", "close ", "mute", "volume", "desktop"]):
                return ("display_intel_media", {"query": subj})

    # 1. Open Gmail / Search Gmail
    if "gmail" in t or "email" in t or "inbox" in t:
        if "search" in t or "find" in t or "look for" in t:
            query = t
            for prefix in ["search gmail for", "search email for", "search in gmail for", "find in gmail", "search for"]:
                if prefix in query:
                    query = query.split(prefix, 1)[1]
                    break
            query = query.replace("and open it", "").replace("in browser", "").strip()
            return ("open_browser_tab", {"service": "gmail", "query": query})
        elif "open" in t or "check" in t or "go to" in t:
            return ("open_browser_tab", {"service": "gmail", "query": ""})
            
    # 2. Search YouTube / Open YouTube
    if "youtube" in t:
        if "search" in t or "play" in t or "find" in t:
            query = t
            for prefix in ["search youtube for", "search on youtube for", "play", "search for"]:
                if prefix in query:
                    query = query.split(prefix, 1)[1]
                    break
            query = query.replace("on youtube", "").replace("and open it", "").strip()
            return ("search_web", {"engine": "youtube", "query": query})
        elif "open" in t:
            return ("open_browser_tab", {"service": "youtube", "query": ""})

    # 3. Web Search (Google)
    if t.startswith("search ") or t.startswith("google ") or "search for " in t or "search on google" in t:
        query = t
        for prefix in ["search google for", "search on google for", "search for", "google", "search"]:
            if query.startswith(prefix):
                query = query[len(prefix):]
                break
            elif prefix in query:
                query = query.split(prefix, 1)[1]
                break
        query = query.replace("and open it", "").replace("in browser", "").replace("on google", "").strip()
        if query:
            return ("search_web", {"engine": "google", "query": query})

    # 4. Open specific web services & apps
    if "open whatsapp web" in t:
        return ("open_browser_tab", {"service": "whatsapp", "query": ""})
    elif "open whatsapp" in t:
        return ("open_app", {"target": "whatsapp"})

    services = ["github", "reddit", "twitter", "chatgpt", "netflix"]
    for s in services:
        if f"open {s}" in t:
            return ("open_browser_tab", {"service": s, "query": ""})

    return None

def sanitize_messages_for_cloud(msgs: list) -> list:
    """Sanitize message history to ensure compatibility with Gemini OpenAI interface.
    Filters out synthetic local calls, ensures assistant tool calls have matching responses,
    and prevents 400 Bad Request errors.
    """
    cleaned = []
    pending_tool_calls = set()

    for m in msgs:
        role = m.get("role")
        if role in ["system", "user"]:
            cleaned.append(m)
        elif role == "assistant":
            tcs = m.get("tool_calls")
            if tcs:
                valid_tcs = [tc for tc in tcs if not str(tc.get("id", "")).startswith("local_call_")]
                if valid_tcs:
                    m_copy = dict(m)
                    m_copy["tool_calls"] = valid_tcs
                    cleaned.append(m_copy)
                    for tc in valid_tcs:
                        pending_tool_calls.add(tc.get("id"))
                else:
                    cleaned.append({"role": "assistant", "content": m.get("content") or "Protocol processed."})
            else:
                cleaned.append(m)
        elif role == "tool":
            tcid = m.get("tool_call_id")
            if tcid in pending_tool_calls:
                cleaned.append(m)
                pending_tool_calls.remove(tcid)
            elif not str(tcid).startswith("local_call_"):
                pass

    return cleaned

class JarvisSession:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.history = []
        self.pending = {}
        self.scale = 1.0
        self.current_task = None
        self.full_autonomy = True
        self.manual_offline_mode = False
        self.in_failover = False
        self.last_camera_frame = None

    async def send(self, **msg):
        try:
            await self.ws.send_text(json.dumps(msg))
        except Exception:
            pass

    async def send_vocal_response(self, text: str):
        msg_id = str(time.time())
        # Dictate full text to chat immediately with zero latency
        await self.send(type="say_text", id=msg_id, text=text)
        # Persist to SQLite chat history cortex
        try:
            save_chat_message("jarvis", text)
        except Exception as e:
            print(f"Chat persistence error: {e}")
        # Synthesize audio in parallel and stream neural voice playback
        try:
            audio_b64 = await get_or_synthesize_audio(text)
            if audio_b64:
                await self.send(type="say_audio", id=msg_id, audio=audio_b64)
        except Exception as e:
            print(f"TTS synthesis error: {e}")

    async def request_approval(self, tool_name: str, args: dict):
        aid = str(time.time())
        fut = asyncio.get_running_loop().create_future()
        self.pending[aid] = fut
        await self.send(type="approval", id=aid, tool=tool_name, args=args)
        try:
            return await fut
        finally:
            self.pending.pop(aid, None)

    def is_destructive_action(self, name: str, args: dict) -> bool:
        if not self.full_autonomy:
            return True
        if name == "system_control":
            act = args.get("action", "").lower()
            return act in ["shutdown", "restart"]
        if name == "run_command":
            cmd = args.get("command", "").lower()
            return any(pat in cmd for pat in CRITICAL_COMMAND_PATTERNS)
        if name == "file_action":
            action = args.get("action", "")
            return action in ["delete", "remove"]
        return False

    def take_screenshot(self, with_grid: bool = False):
        img = capture_desktop()
        w, h = img.size
        if with_grid:
            grid_img = img.copy()
            draw = ImageDraw.Draw(grid_img, "RGBA")
            step = 100
            for x in range(0, w, step):
                draw.line([(x, 0), (x, h)], fill=(0, 240, 255, 60), width=1)
                draw.text((x + 2, 2), str(x), fill=(0, 240, 255, 230))
            for y in range(0, h, step):
                draw.line([(0, y), (w, y)], fill=(0, 240, 255, 60), width=1)
                draw.text((2, y + 2), str(y), fill=(0, 240, 255, 230))
            img = grid_img

        # Scaled down to max 1024px with high-speed JPEG compression for minimum latency
        self.scale = min(1.0, 1024 / max(1, w))
        if self.scale < 1.0:
            img = img.resize((int(w * self.scale), int(h * self.scale)))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=60)
        return base64.b64encode(buf.getvalue()).decode()

    async def browse(self, task: str):
        try:
            from browser_use import Agent, Browser, ChatGoogle, ChatOpenAI
            async def on_step(state, output, n):
                try:
                    await self.send(type="screen", img="data:image/png;base64," + state.screenshot, label=f"Browser Step {n}")
                    await self.send(type="log", text=f"Browser Goal {n}: {output.current_state.next_goal}")
                except Exception:
                    pass
            llm = ChatGoogle(model=MODEL) if "googleapis" in BASE_URL else ChatOpenAI(model=MODEL, base_url=BASE_URL, api_key=KEY)
            agent = Agent(task=task, llm=llm, browser=Browser(), register_new_step_callback=on_step)
            hist = await agent.run(max_steps=20)
            return str(hist.final_result() or "Task completed.")
        except Exception as e:
            return f"Browser error: {e}"

    async def run_tool(self, name: str, args: dict):
        if name == "get_system_vitals":
            v = get_telemetry()
            user = os.getenv("USERNAME", "Sir")
            return f"Host: {v['hostname']}, User: {user}. CPU: {v['cpu']}%, RAM: {v['ram_pct']}% ({v['ram_used_gb']}/{v['ram_total_gb']} GB), Disk C: {v['disk_pct']}% used ({v['disk_free_gb']} GB free), Battery: {v['battery_pct']}% (AC Plugged: {v['battery_plugged']})."

        if name == "list_running_apps":
            apps = []
            seen = set()
            for p in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    pname = p.info['name']
                    if pname and pname.lower() not in seen:
                        if pname.lower() not in ['system idle process', 'system', 'registry']:
                            mem_mb = round(p.info['memory_info'].rss / (1024 * 1024), 1)
                            apps.append((pname, p.info['pid'], mem_mb))
                            seen.add(pname.lower())
                except Exception:
                    pass
            apps.sort(key=lambda x: x[2], reverse=True)
            top = apps[:25]
            return "Active Applications & Top Processes:\n" + "\n".join([f"- {n} (PID: {pid}, Memory: {m} MB)" for n, pid, m in top])

        if name == "set_volume":
            action = args.get("action", "up")
            if action == "mute":
                pyautogui.press("volumemute")
                return "Audio mute toggled."
            elif action == "up":
                for _ in range(5):
                    pyautogui.press("volumeup")
                return "Volume increased by 10%."
            elif action == "down":
                for _ in range(5):
                    pyautogui.press("volumedown")
                return "Volume decreased by 10%."
            elif action == "set":
                lvl = int(args.get("level", 50))
                for _ in range(50):
                    pyautogui.press("volumedown")
                steps_up = int(lvl / 2)
                for _ in range(steps_up):
                    pyautogui.press("volumeup")
                return f"Volume set to approximately {lvl}%."

        if name == "media_control":
            act = args.get("action", "play_pause")
            key_map = {"play_pause": "playpause", "next": "nexttrack", "previous": "prevtrack", "stop": "stop"}
            k = key_map.get(act, "playpause")
            pyautogui.press(k)
            return f"Media control signal sent: {act}."

        if name == "camera_control":
            act = args.get("action", "start").lower()
            await self.send(type="camera_stream", action=act)
            if act == "start":
                return "Optical sensory camera feed activated directly inside the HUD viewport, Sir."
            elif act == "stop":
                return "Optical sensory camera feed deactivated, Sir."
            elif act == "snapshot":
                return "Optical camera snapshot requested from the viewport sensor, Sir."
            return f"Optical camera action '{act}' executed."

        if name == "open_app":
            target = args["target"].strip()
            if target.lower() in ["camera", "webcam", "optical feed", "optical camera", "optical sensory feed", "microsoft.windows.camera:"]:
                await self.send(type="camera_stream", action="start")
                return "Optical sensory camera feed activated directly inside the HUD viewport, Sir."
            aliases = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "calc": "calc.exe",
                "spotify": "spotify.exe",
                "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                "msedge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                "brave": get_preferred_browser_path() or r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                "brave browser": get_preferred_browser_path() or r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                "terminal": "wt.exe",
                "powershell": "powershell.exe",
                "cmd": "cmd.exe",
                "explorer": "explorer.exe",
                "task manager": "taskmgr.exe",
                "taskmgr": "taskmgr.exe",
                "paint": "mspaint.exe",
                "wordpad": "write.exe",
                "control panel": "control.exe",
                "photos": "ms-photos:",
                "clock": "ms-clock:",
                "settings": "ms-settings:",
                "wifi": "ms-settings:network-wifi",
                "bluetooth": "ms-settings:bluetooth",
                "sound": "ms-settings:sound",
                "display": "ms-settings:display",
                "battery": "ms-settings:batterysaver",
                "windows update": "ms-settings:windowsupdate",
                "vscode": "code",
                "code": "code",
                "whatsapp": "whatsapp://",
                "whatsapp web": "https://web.whatsapp.com",
                "overlay": f'"{sys.executable}" overlay.py',
                "bubble": f'"{sys.executable}" overlay.py',
                "floating bubble": f'"{sys.executable}" overlay.py',
                "desktop bubble": f'"{sys.executable}" overlay.py',
                "gmail": "https://mail.google.com/mail/u/0/#inbox",
                "youtube": "https://www.youtube.com",
                "google": "https://www.google.com",
                "github": "https://github.com",
                "reddit": "https://www.reddit.com",
                "twitter": "https://twitter.com",
                "x": "https://x.com",
                "chatgpt": "https://chatgpt.com",
                "netflix": "https://www.netflix.com",
                "desktop": str(DESKTOP),
                "downloads": str(DOWNLOADS),
                "documents": str(DOCUMENTS),
            }
            exe = aliases.get(target.lower(), target)
            if exe.startswith("http://") or exe.startswith("https://") or exe.startswith("www."):
                launch_browser_tab(exe)
                return f"Opened browser tab for {target}."

            if sys.platform == "win32":
                subprocess.Popen(f'start "" "{exe}"', shell=True)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", exe])
            await asyncio.sleep(0.3)
            return f"Launched application: {target}."

        if name == "close_app":
            target = args["target"].strip()
            if target.lower() in ["camera", "webcam", "optical feed", "optical camera", "optical sensory feed"]:
                await self.send(type="camera_stream", action="stop")
                return "Optical sensory camera feed deactivated, Sir."
            target_exe = target if target.lower().endswith(".exe") else target + ".exe"
            await asyncio.to_thread(subprocess.run, f"taskkill /im {target_exe} /f", shell=True, capture_output=True)
            return f"Closed application {target}."

        if name == "manage_window":
            act = args.get("action", "show_desktop")
            if act == "maximize":
                pyautogui.hotkey("win", "up")
                return "Active window maximized."
            elif act == "minimize":
                pyautogui.hotkey("win", "down")
                return "Active window minimized."
            elif act == "snap_left":
                pyautogui.hotkey("win", "left")
                return "Active window snapped to left."
            elif act == "snap_right":
                pyautogui.hotkey("win", "right")
                return "Active window snapped to right."
            elif act == "restore":
                pyautogui.hotkey("win", "down")
                return "Window state restored."
            elif act == "show_desktop":
                pyautogui.hotkey("win", "d")
                return "Desktop toggled."
            elif act == "close":
                pyautogui.hotkey("alt", "f4")
                return "Active window closed."

        if name == "look":
            with_grid = bool(args.get("with_grid", False))
            detect_elements = bool(args.get("detect_elements", True))
            
            if with_grid:
                b64 = await asyncio.to_thread(self.take_screenshot, True)
                label = "Display Optical Telemetry (Coordinate Grid)"
                await self.send(type="screen", img="data:image/jpeg;base64," + b64, label=label)
                return {"image": b64}
            elif detect_elements:
                elements, pil_img, lat = await asyncio.to_thread(detect_ui_elements)
                b64 = await asyncio.to_thread(render_hud_visual_telemetry, pil_img, elements)
                label = f"OPTICAL SENSORY FEED ({len(elements)} TARGETS DETECTED)"
                await self.send(type="screen", img="data:image/jpeg;base64," + b64, label=label)
                await self.send(type="log", text=f"Optical Scan: {len(elements)} UI elements mapped in {lat:.0f}ms.")
                return {
                    "image": b64,
                    "detected_count": len(elements),
                    "elements": [f"'{e['text']}' at {e['center']}" for e in elements[:20]]
                }
            else:
                b64 = await asyncio.to_thread(self.take_screenshot, False)
                label = "Display Optical Telemetry"
                await self.send(type="screen", img="data:image/jpeg;base64," + b64, label=label)
                return {"image": b64}

        if name == "click_element":
            label = args["text_label"].strip()
            btn = args.get("button", "left")
            clicks = int(args.get("clicks", 1))
            res = await asyncio.to_thread(click_element_action, text_label=label, button=btn, clicks=clicks)
            
            if res.get("image_b64"):
                tag_label = f"TARGET: {res['element']['text']}" if res.get("success") else "OPTICAL SCAN"
                await self.send(type="screen", img="data:image/jpeg;base64," + res["image_b64"], label=tag_label)
                
            if res.get("success"):
                cx, cy = res["clicked_at"]
                await self.send(type="log", text=f"Optical Targeting: Acquired '{res['element']['text']}' at ({cx}, {cy}). Executed {btn} click in {res['latency_ms']}ms.")
                return f"Optical targeting acquired. Clicked element '{res['element']['text']}' at screen coordinates ({cx}, {cy}) [{btn} button] in {res['latency_ms']}ms, Sir."
            else:
                detected_str = ", ".join([f"'{txt}'" for txt in res.get("detected_labels", [])])
                return f"Optical scan could not find element matching '{label}' on screen. Detected visible elements: [{detected_str}]. Please verify the label or use the coordinate grid."

        if name == "click":
            x, y = args["x"], args["y"]
            btn = args.get("button", "left")
            clicks = int(args.get("clicks", 1))
            await asyncio.to_thread(pyautogui.click, x / self.scale, y / self.scale, clicks=clicks, button=btn)
            return f"Executed {btn} click ({clicks}x) at ({x}, {y})."

        if name == "move_mouse":
            x, y = args["x"], args["y"]
            await asyncio.to_thread(pyautogui.moveTo, x / self.scale, y / self.scale, 0.1)
            return f"Moved cursor to ({x}, {y})."

        if name == "drag":
            sx, sy = args["start_x"] / self.scale, args["start_y"] / self.scale
            ex, ey = args["end_x"] / self.scale, args["end_y"] / self.scale
            await asyncio.to_thread(pyautogui.moveTo, sx, sy)
            await asyncio.to_thread(pyautogui.dragTo, ex, ey, 0.25, button="left")
            return f"Dragged from ({args['start_x']}, {args['start_y']}) to ({args['end_x']}, {args['end_y']})."

        if name == "scroll":
            amt = int(args.get("amount", -300))
            await asyncio.to_thread(pyautogui.scroll, amt)
            return f"Scrolled wheel by {amt} units."

        if name == "type_text":
            text = args["text"]
            press_enter = args.get("press_enter", False)
            if len(text) > 4 or "\n" in text or any(c in text for c in ['{', '}', '[', ']', '"', "'", '`', '\\']):
                pyperclip.copy(text)
                await asyncio.to_thread(pyautogui.hotkey, "ctrl", "v")
            else:
                await asyncio.to_thread(pyautogui.write, text, 0.01)
            if press_enter:
                await asyncio.to_thread(pyautogui.press, "enter")
            return f"Typed '{text[:50]}{'...' if len(text) > 50 else ''}' into focused element."

        if name == "press":
            keys = args["keys"].lower().replace(" ", "").split("+")
            await asyncio.to_thread(pyautogui.hotkey, *keys)
            return f"Triggered key combo: {'+'.join(keys)}."

        if name == "get_clipboard":
            text = pyperclip.paste()
            return f"Clipboard text: '{text[:1500]}'." if text else "Clipboard is empty."

        if name == "set_clipboard":
            text = args["text"]
            pyperclip.copy(text)
            return "Updated clipboard contents."

        if name == "display_intel_media":
            from core.intel import fetch_subject_media
            query = args["query"].strip()
            data = await asyncio.to_thread(fetch_subject_media, query)
            img_url = data.get("image_url", "")
            backup_url = data.get("backup_url", "")
            title = data.get("title") or query.title()
            summary = data.get("summary", "")
            
            await self.send(
                type="intel_media",
                query=query,
                title=title,
                image_url=img_url,
                backup_url=backup_url,
                summary=summary
            )
            await self.send(type="log", text=f"Optical Sensory Viewport: Beamed intel for '{title}'")
            return f"Holographic subject media and intel beamed into HUD Optical Sensory Viewport for '{title}'. Image status: {'Active' if img_url else 'Pending'}. Briefing summary: {summary}"

        if name == "generate_antigravity_prompt":
            from core.evolution import generate_directive
            cat = args.get("category", "all")
            custom_feature = args.get("custom_feature", "")
            directive = generate_directive(cat, custom_feature)
            
            await self.send(
                type="antigravity_directive",
                directive=directive
            )
            await self.send(type="log", text=f"Generated Antigravity Directive: {directive.get('title')}")
            
            if "prompt" in directive:
                return f"Antigravity Directive Generated for '{directive['title']}':\n\n```markdown\n{directive['prompt']}\n```\n\nSir can copy this prompt directly into Antigravity to execute."
            else:
                blueprints = directive.get("blueprints", {})
                summary_lines = [f"- **{bp['title']}** (Slash command: `{bp['command']}`)" for bp in blueprints.values()]
                return "Stark Industries Antigravity Evolution Directives prepared. 1-click copy cards have been beamed to your HUD:\n" + "\n".join(summary_lines)

        if name == "focus_application":
            from core.window_manager import focus_app
            target = args["target"].strip()
            res = await asyncio.to_thread(focus_app, target)
            if res.get("success"):
                await self.send(type="log", text=f"Focused application: {res['title']} ({res['process']})")
                return f"Successfully focused {res['process']} ({res['title']}), Sir."
            return f"Failed to focus '{target}': {res.get('error')}"

        if name == "list_open_windows":
            from core.window_manager import list_desktop_windows
            wins = await asyncio.to_thread(list_desktop_windows)
            if not wins:
                return "No top-level application windows detected on active desktop."
            lines = [f"- **{w['process']}** (HWND: {w['hwnd']}): \"{w['title']}\"" for w in wins]
            return "Active Desktop Application Windows:\n" + "\n".join(lines)

        if name == "switch_tab":
            from core.window_manager import switch_app_tabs
            direction = args.get("direction", "next")
            tab_index = args.get("tab_index")
            msg = await asyncio.to_thread(switch_app_tabs, direction=direction, tab_index=tab_index)
            await self.send(type="log", text=msg)
            return msg

        if name == "type_into_app":
            from core.window_manager import type_into_app
            target = args["target"].strip()
            text = args["text"]
            press_enter = args.get("press_enter", True)
            res = await asyncio.to_thread(type_into_app, target, text, press_enter)
            if res.get("success"):
                await self.send(type="log", text=f"Typed into {res['app']}: '{res['typed']}'")
                return f"Typed '{res['typed']}' into {res['app']} ({res['title']})."
            return f"Error typing into '{target}': {res.get('error')}"

        if name == "dispatch_antigravity_evolution":
            from core.window_manager import dispatch_prompt_to_antigravity
            prompt = args["prompt"]
            return_to_hud = args.get("return_to_hud", True)
            await self.send(type="log", text="Initiating autonomous Antigravity dispatch sequence...")
            res = await asyncio.to_thread(dispatch_prompt_to_antigravity, prompt, return_to_hud)
            await self.send(type="log", text=res)
            return res

        if name == "trigger_morning_briefing":
            sentinel = get_sentinel()
            briefing = await asyncio.to_thread(sentinel.build_morning_briefing)
            await self.send(type="log", text=f"⚡ SENTINEL: {briefing['log']}")
            return briefing["speech"]

        if name == "configure_sentinel":
            sentinel = get_sentinel()
            changes = []
            if "morning_briefing" in args:
                sentinel.briefing_enabled = bool(args["morning_briefing"])
                changes.append(f"Morning Briefing: {'Enabled (9:00 AM)' if sentinel.briefing_enabled else 'Disabled'}")
            if "media_observer" in args:
                sentinel.media_observer_enabled = bool(args["media_observer"])
                changes.append(f"Media Observer: {'Active' if sentinel.media_observer_enabled else 'Suspended'}")
            if "battery_threshold" in args:
                sentinel.battery_threshold = int(args["battery_threshold"])
                changes.append(f"Battery Alert Threshold: {sentinel.battery_threshold}%")
            return "Sentinel configuration updated:\n" + "\n".join([f"- {c}" for c in changes])

        if name == "get_sentinel_status":
            sentinel = get_sentinel()
            evts = sentinel.events[-6:]
            evt_lines = [f"[{e['timestamp']}] ({e['category']}) {e['message']}" for e in evts]
            return (
                f"Autonomous Proactive Sentinel Status: {'OPERATIONAL' if sentinel.running else 'STANDBY'}\n"
                f"- Morning Executive Briefing: {'Enabled at 09:00 AM (Weekdays)' if sentinel.briefing_enabled else 'Disabled'}\n"
                f"- Battery Sentinel Threshold: {sentinel.battery_threshold}% (Alert cooldown: 20 min)\n"
                f"- Media Observer: {'Active (Spotify / YouTube)' if sentinel.media_observer_enabled else 'Disabled'}\n"
                f"- Last Monitored Track: '{sentinel.last_media_title or 'None'}'\n"
                f"- Recent Sentinel Events:\n" + ("\n".join(evt_lines) if evt_lines else "  No recent sentinel alerts.")
            )

        if name == "toggle_offline_mode":
            enabled = bool(args.get("enabled", True))
            self.offline_mode = enabled
            label = "NEURAL CORE // OFFLINE LOCAL MODE" if enabled else "NEURAL CORE // CLOUD (GEMINI)"
            await self.send(type="core_mode", mode="offline" if enabled else "cloud", label=label)
            await self.send(type="log", text=f"Switched neural mode: {label}")
            return f"Switched neural core to {'Local Offline Mode (Ollama)' if enabled else 'Cloud Mode (Gemini)'}, Sir."

        if name == "open_browser_tab":
            url = args.get("url", "").strip()
            service = args.get("service", "").lower()
            query = args.get("query", "").strip()
            
            service_urls = {
                "gmail": f"https://mail.google.com/mail/u/0/#search/{urllib.parse.quote_plus(query)}" if query else "https://mail.google.com/mail/u/0/#inbox",
                "youtube": f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}" if query else "https://www.youtube.com",
                "google": f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}" if query else "https://www.google.com",
                "github": f"https://github.com/search?q={urllib.parse.quote_plus(query)}" if query else "https://github.com",
                "reddit": f"https://www.reddit.com/search/?q={urllib.parse.quote_plus(query)}" if query else "https://www.reddit.com",
                "chatgpt": "https://chatgpt.com",
                "whatsapp": "https://web.whatsapp.com",
            }
            target_url = service_urls.get(service) or url or (f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}" if query else "https://www.google.com")
            launch_browser_tab(target_url)
            await self.send(type="open_tab", url=target_url)
            return f"Opened browser tab for {service or 'web'}: {target_url}."

        if name == "search_web":
            query = args["query"].strip()
            engine = args.get("engine", "google").lower()
            if engine == "youtube":
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
            elif engine == "gmail":
                url = f"https://mail.google.com/mail/u/0/#search/{urllib.parse.quote_plus(query)}"
            else:
                url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            launch_browser_tab(url)
            await self.send(type="open_tab", url=url)
            return f"Opened browser tab for {engine.capitalize()} search: '{query}'."

        if name == "open_url":
            url = args["url"].strip()
            launch_browser_tab(url)
            await self.send(type="open_tab", url=url)
            return f"Opened browser tab: {url}."

        if name == "gmail_action":
            action_type = args.get("action", "open_inbox")
            if action_type in ["open_inbox", "inbox"]:
                await self.send(type="open_tab", url="https://mail.google.com/mail/u/0/#inbox")
            elif action_type == "search" and args.get("query"):
                await self.send(type="open_tab", url=f"https://mail.google.com/mail/u/0/#search/{urllib.parse.quote_plus(args['query'])}")
            elif action_type in ["compose", "draft"]:
                params = {}
                if args.get("to"): params["to"] = args["to"]
                if args.get("subject"): params["su"] = args["subject"]
                if args.get("body"): params["body"] = args["body"]
                web_url = "https://mail.google.com/mail/?view=cm&fs=1" + ("&" + urllib.parse.urlencode(params) if params else "")
                await self.send(type="open_tab", url=web_url)

            return await asyncio.to_thread(
                handle_gmail_tool,
                action=action_type,
                to=args.get("to", ""),
                subject=args.get("subject", ""),
                body=args.get("body", ""),
                query=args.get("query", "")
            )

        if name == "whatsapp_action":
            return await asyncio.to_thread(
                handle_whatsapp_tool,
                action=args.get("action", "open_chat"),
                recipient=args.get("recipient", ""),
                message=args.get("message", "")
            )

        if name == "instagram_action":
            return await asyncio.to_thread(
                handle_instagram_tool,
                action=args.get("action", "check"),
                target=args.get("target", ""),
                message=args.get("message", "")
            )

        if name == "system_control":
            act = args.get("action", "lock")
            if act == "lock":
                if sys.platform == "win32":
                    ctypes.windll.user32.LockWorkStation()
                    return "Workstation locked successfully, Sir."
                return "Lock command not supported on non-Windows host."
            elif act == "show_desktop":
                pyautogui.hotkey("win", "d")
                return "Desktop toggled."
            elif act == "task_manager":
                subprocess.Popen("taskmgr.exe")
                return "Launched Windows Task Manager."
            elif act == "empty_recycle_bin":
                subprocess.run('powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"', shell=True)
                return "Emptied Windows Recycle Bin."
            elif act == "sleep":
                subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
                return "Put PC into sleep mode."
            elif act == "shutdown":
                subprocess.run("shutdown /s /t 10", shell=True)
                return "System shutdown sequence initiated (10s delay)."
            elif act == "restart":
                subprocess.run("shutdown /r /t 10", shell=True)
                return "System restart sequence initiated (10s delay)."

        if name == "file_action":
            act = args.get("action", "read")
            raw_path = args.get("path", "")
            fpath = Path(raw_path).expanduser().resolve() if raw_path else HERE

            if act == "search":
                query = (args.get("query") or raw_path).lower()
                matches = []
                for search_dir in [DESKTOP, DOWNLOADS, DOCUMENTS, HERE]:
                    if search_dir.exists():
                        try:
                            for p in search_dir.rglob(f"*{query}*"):
                                if p.is_file():
                                    matches.append(str(p))
                                    if len(matches) >= 15:
                                        break
                        except Exception:
                            pass
                return f"Files matching '{query}':\n" + "\n".join(matches) if matches else f"No matching files found for '{query}'."

            if act == "open_explorer":
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer.exe "{fpath}"', shell=True)
                return f"Opened Explorer at {fpath}."
            elif act == "read":
                if fpath.exists() and fpath.is_file():
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    return f"Content of {fpath.name}:\n{content[:3000]}"
                return f"File does not exist: {fpath}."
            elif act == "write":
                content = args.get("content", "")
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content, encoding="utf-8")
                return f"Successfully written {len(content)} characters to {fpath}."
            elif act == "append":
                content = args.get("content", "")
                fpath.parent.mkdir(parents=True, exist_ok=True)
                with open(fpath, "a", encoding="utf-8") as f:
                    f.write(content)
                return f"Appended {len(content)} characters to {fpath}."
            elif act == "list_directory":
                if fpath.exists() and fpath.is_dir():
                    items = [p.name + ("/" if p.is_dir() else "") for p in fpath.iterdir()][:50]
                    return f"Items in {fpath.name}:\n" + "\n".join(items)
                return f"Directory does not exist: {fpath}."

        if name == "run_command":
            cmd = args["command"]
            r = await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-Command", cmd] if sys.platform == "win32" else cmd,
                capture_output=True,
                text=True,
                timeout=60,
                shell=(sys.platform != "win32")
            )
            out = (r.stdout + r.stderr).strip()
            return out[-3000:] if out else "(Command completed with no output)"

        if name == "browse":
            return await self.browse(args["task"])

        if name == "openclaw_execute":
            prompt = args["prompt"]
            cmd = f'openclaw agent --message "{prompt}" --model google/gemini-3.1-flash-lite'
            r = await asyncio.to_thread(subprocess.run, cmd, shell=True, capture_output=True, text=True, timeout=90)
            res = (r.stdout + r.stderr).strip()
            return res[-3000:] if res else "OpenClaw agent execution completed."

        if name == "remember":
            fact = args["fact"].strip()
            category = args.get("category", "preference")
            entry = add_memory_to_cortex(fact, category=category)
            await self.send(type="memories", list=list_cortex_memories())
            return f"Committed to vector memory cortex: '{fact}' [Category: {entry.get('category', 'preference').upper()}]."

        if name == "search_memory":
            q = args["query"].strip()
            matches = query_semantic_memories(q, n_results=5, min_confidence=0.25)
            if not matches:
                return f"No memories found matching '{q}' in vector cortex."
            lines = [f"- [{m['category'].upper()} | {int(m['confidence']*100)}% match]: {m['text']} ({m['timestamp']})" for m in matches]
            return f"Semantic Vector Cortex search results for '{q}':\n" + "\n".join(lines)

        if name == "forget":
            target = args.get("keyword_or_id", args.get("keyword", "")).strip()
            success = delete_memory_from_cortex(target)
            await self.send(type="memories", list=list_cortex_memories())
            if success:
                return f"Purged memory record matching '{target}' from vector cortex."
            return f"No memory record found matching '{target}'."

        if name == "schedule_meeting":
            s = datetime.fromisoformat(args["start"])
            e = s + timedelta(minutes=args.get("duration_min", 30))
            f = "%Y%m%dT%H%M%S"
            q = {
                "action": "TEMPLATE",
                "text": args["title"],
                "dates": f"{s:{f}}/{e:{f}}",
                "details": args.get("notes", ""),
                "add": ",".join(args.get("guests", []))
            }
            webbrowser.open("https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(q))
            return "Opened pre-filled Google Calendar event for Sir's review."

        return "Unknown command requested."

    async def turn(self, user_text: str):
        try:
            save_chat_message("user", user_text)
        except Exception as e:
            print(f"Chat persistence error: {e}")
        self.history.append({"role": "user", "content": user_text})
        tools_executed = 0
        try:
            for _ in range(15):
                await self.send(type="state", s="thinking")
                msgs = [{"role": "system", "content": system_prompt(query=user_text)}] + prune_history(self.history)
                
                choice = None
                engine_name = "Gemini Cloud"

                if not self.manual_offline_mode:
                    try:
                        clean_msgs = sanitize_messages_for_cloud(msgs)
                        r = await client.chat.completions.create(model=MODEL, messages=clean_msgs, tools=TOOLS)
                        choice = r.choices[0].message
                        if self.in_failover:
                            self.in_failover = False
                            await self.send(type="core_mode", mode="cloud", label="NEURAL CORE // CLOUD (GEMINI)")
                            await self.send(type="log", text="⚡ Cloud Neural Link restored. All systems nominal.")
                    except Exception as cloud_err:
                        print(f"Cloud neural core fault ({cloud_err}). Initiating local Ollama failover...")
                        self.in_failover = True
                        await self.send(type="log", text=f"⚠️ CLOUD LLM ERROR ({cloud_err.__class__.__name__}): Routing to Local Failover.")
                        await self.send(type="core_mode", mode="offline", label="NEURAL CORE // LOCAL FAILOVER")

                if self.manual_offline_mode or choice is None:
                    from core.local_llm import execute_local_completion
                    choice, engine_name = await execute_local_completion(messages=msgs, tools=TOOLS)
                    if tools_executed == 0:
                        lbl = f"NEURAL CORE // OFFLINE ({engine_name})" if self.manual_offline_mode else f"NEURAL CORE // FAILOVER ({engine_name})"
                        await self.send(type="core_mode", mode="offline", label=lbl)
                        await self.send(type="log", text=f"⚡ Active Neural Engine: {engine_name}")

                self.history.append(choice.model_dump(exclude_none=True))

                # Optimized vocal dispatch: concurrent on tool turns, awaited on final turn
                if choice.content and choice.content.strip():
                    if choice.tool_calls:
                        asyncio.create_task(self.send_vocal_response(choice.content))
                    else:
                        await self.send_vocal_response(choice.content)

                if not choice.tool_calls:
                    # Semantic Vector Memory Cortex: autonomous extraction of preferences and facts
                    try:
                        extracted = auto_extract_and_remember(user_text, choice.content or "")
                        if extracted:
                            await self.send(type="log", text=f"🧠 Cortex Memorized: [{extracted['category'].upper()}] {extracted['text']}")
                            await self.send(type="memories", list=list_cortex_memories())
                    except Exception as ex:
                        print(f"Vector memory extraction error: {ex}")

                    # Automatic execution fallback guarantee:
                    # If Sir asked to open a tab/search and the LLM merely replied in dialogue, trigger the browser tab immediately!
                    if tools_executed == 0:
                        fallback_intent = extract_action_intent(user_text)
                        if fallback_intent:
                            fn_name, fn_args = fallback_intent
                            await self.send(type="log", text=f"Auto-Dispatching Tab Action {fn_name}: {json.dumps(fn_args)}")
                            try:
                                await self.run_tool(fn_name, fn_args)
                            except Exception as ex:
                                print(f"Auto-dispatch error: {ex}")
                    return

                tool_results, images = [], []
                for call in choice.tool_calls:
                    fn_name = call.function.name
                    args = json.loads(call.function.arguments or "{}")
                    tools_executed += 1

                    # Ask approval ONLY for destructive commands
                    if self.is_destructive_action(fn_name, args):
                        if not await self.request_approval(fn_name, args):
                            out = "Sir has denied this destructive action."
                        else:
                            await self.send(type="log", text=f"Protocol {fn_name}: {json.dumps(args)[:140]}")
                            try:
                                out = await self.run_tool(fn_name, args)
                            except Exception as ex:
                                out = f"Execution error: {ex}"
                    else:
                        # Full Autonomous Execution
                        await self.send(type="log", text=f"Executing {fn_name}: {json.dumps(args)[:140]}")
                        try:
                            out = await self.run_tool(fn_name, args)
                        except Exception as ex:
                            out = f"Execution error: {ex}"

                    if isinstance(out, dict) and "image" in out:
                        images.append(out["image"])
                        out = "Optical frame captured and appended to session."

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": str(out)
                    })

                self.history.extend(tool_results)
                if images:
                    self.history.append({
                        "role": "user",
                        "content": [{"type": "text", "text": "Optical snapshot visual data:"}] +
                                   [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}} for img in images]
                    })
        except asyncio.CancelledError:
            if self.history and self.history[-1]["role"] == "assistant":
                self.history.pop()
            await self.send_vocal_response("Protocol suspended, Sir.")
            raise
        except Exception as e:
            if self.history and self.history[-1]["role"] == "assistant":
                self.history.pop()
            await self.send(type="error", text=f"Diagnostic Fault: {e}")
        finally:
            await self.send(type="state", s="idle")

@app.get("/")
def get_index():
    return FileResponse(HERE / "static" / "index.html")

@app.get("/favicon.ico")
def get_favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#03080e" stroke="#00f0ff" stroke-width="6"/><circle cx="50" cy="50" r="20" fill="#00f0ff" filter="drop-shadow(0 0 8px #00f0ff)"/></svg>'
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/api/proxy_image")
async def proxy_image(url: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=6) as r:
            content = r.read()
            mime = r.headers.get("Content-Type", "image/jpeg")
            return Response(content=content, media_type=mime)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.websocket("/ws")
async def websocket_handler(ws: WebSocket):
    await ws.accept()
    session = JarvisSession(ws)
    ACTIVE_SESSIONS.add(session)

    async def telemetry_stream():
        try:
            while True:
                await session.send(**get_telemetry())
                await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    telemetry_task = asyncio.create_task(telemetry_stream())
    await session.send(type="memories", list=list_cortex_memories())
    
    # Restore persistent chat history across page refresh from SQLite cortex
    try:
        past_chats = get_recent_chat_history(limit=60)
        await session.send(type="chat_history", messages=past_chats)
    except Exception as e:
        print(f"Failed to fetch initial chat history: {e}")

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            is_busy = session.current_task is not None and not session.current_task.done()

            if msg_type == "task":
                if is_busy:
                    await session.send_vocal_response("One moment, Sir. I am executing the previous command.")
                else:
                    session.current_task = asyncio.create_task(session.turn(data["text"]))

            elif msg_type == "audio":
                audio_b64 = data.get("data")
                mime = data.get("mime", "audio/webm")
                if audio_b64:
                    await session.send(type="state", s="thinking")
                    await session.send(type="log", text="Acoustic waveform received. Processing neural transcription...")
                    audio_bytes = base64.b64decode(audio_b64)
                    transcription = await transcribe_audio_bytes(audio_bytes, mime)
                    if transcription:
                        await session.send(type="user_heard", text=transcription)
                        await session.send(type="log", text=f"Vocal command decoded: \"{transcription}\"")
                        if is_busy:
                            await session.send_vocal_response("One moment, Sir. Completing previous protocol.")
                        else:
                            session.current_task = asyncio.create_task(session.turn(transcription))
                    else:
                        await session.send(type="state", s="idle")
                        await session.send_vocal_response("I did not detect any clear speech in that transmission, Sir.")

            elif msg_type == "set_autonomy":
                session.full_autonomy = bool(data.get("enabled", True))
                await session.send(type="log", text=f"Hands-On Autonomy Level set to: {'FULL (MAXIMUM)' if session.full_autonomy else 'RESTRICTED (CONFIRM ALL)'}")

            elif msg_type == "set_offline_mode":
                session.manual_offline_mode = bool(data.get("enabled", False))
                label = "NEURAL CORE // OFFLINE LOCAL MODE" if session.manual_offline_mode else "NEURAL CORE // CLOUD (GEMINI)"
                await session.send(type="core_mode", mode="offline" if session.manual_offline_mode else "cloud", label=label)
                await session.send(type="log", text=f"Neural Engine Mode: {'OFFLINE (LOCAL OLLAMA)' if session.manual_offline_mode else 'ONLINE (GEMINI CLOUD)'}")

            elif msg_type == "ping":
                await session.send(type="pong", t=time.time())

            elif msg_type == "camera_status":
                c_status = data.get("status")
                c_err = data.get("error", "")
                if c_status == "active":
                    await session.send(type="log", text="Optical camera hardware feed online at 30 FPS.")
                elif c_status == "inactive":
                    await session.send(type="log", text="Optical camera stream deactivated.")
                elif c_status == "error":
                    await session.send(type="log", text=f"Optical camera hardware error: {c_err}")

            elif msg_type == "camera_frame":
                session.last_camera_frame = data.get("image")
                await session.send(type="log", text="Optical sensory snapshot received and cached in visual cortex.")

            elif msg_type == "approve":
                aid = data.get("id")
                if aid in session.pending:
                    session.pending[aid].set_result(bool(data.get("ok")))

            elif msg_type == "stop":
                if is_busy:
                    session.current_task.cancel()

            elif msg_type == "reset":
                if is_busy:
                    session.current_task.cancel()
                session.history.clear()
                await session.send_vocal_response("Session cache cleared. All systems nominal, Sir.")

            elif msg_type == "clear_chat":
                clear_chat_history()
                session.history.clear()
                await session.send(type="chat_cleared")
                await session.send(type="log", text="Persistent chat history cleared from SQLite cortex.")

            elif msg_type == "add_memory":
                fact = data.get("fact", "").strip()
                cat = data.get("category", "preference")
                if fact:
                    add_memory_to_cortex(fact, category=cat)
                    await session.send(type="memories", list=list_cortex_memories())

            elif msg_type == "delete_memory":
                mem_id = str(data.get("id") or data.get("index") or "")
                delete_memory_from_cortex(mem_id)
                await session.send(type="memories", list=list_cortex_memories())

            elif msg_type == "search_memories":
                q = data.get("query", "").strip()
                if q:
                    matches = query_semantic_memories(q, n_results=10, min_confidence=0.2)
                    await session.send(type="memory_search_results", query=q, list=matches)
                else:
                    await session.send(type="memories", list=list_cortex_memories())

            elif msg_type == "get_memories":
                await session.send(type="memories", list=list_cortex_memories())

    except WebSocketDisconnect:
        if session.current_task:
            session.current_task.cancel()
    finally:
        ACTIVE_SESSIONS.discard(session)
        telemetry_task.cancel()

if __name__ == "__main__":
    print(f"[*] J.A.R.V.I.S. Core initializing on http://127.0.0.1:{PORT}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
