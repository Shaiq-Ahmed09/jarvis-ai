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
import re
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
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02  # Ultra-low latency for mouse & keyboard operations

_p = Path(__file__).resolve().parent
ROOT_DIR = _p.parent if _p.name == "backend" else _p
HERE = ROOT_DIR
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

FRONTEND_INDEX = (HERE / "frontend" / "index.html") if (HERE / "frontend" / "index.html").exists() else (HERE / "static" / "index.html")
MEMORY_FILE = HERE / "memory.json"
MODEL = os.getenv("JARVIS_MODEL", "gemini-3.5-flash-lite")
BASE_URL = os.getenv("JARVIS_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
PORT = 8765
DEFAULT_VOICE = "en-GB-RyanNeural"

# Import core modular connectors & voice cache
from core.audio_cache import get_or_synthesize_audio, prewarm_audio_cache
from core.gmail import handle_gmail_tool
from core.whatsapp import handle_whatsapp_tool
from core.instagram import handle_instagram_tool, set_persona_mode, get_persona_mode
from core.instagram_dm_automation import get_dm_automator
from core.database import save_chat_message, get_recent_chat_history, clear_chat_history
from core.browser import launch_browser_tab, get_preferred_browser_path
from core.vision import (
    prewarm_vision,
    click_element_action,
    detect_ui_elements,
    render_hud_visual_telemetry,
    capture_desktop,
    click_and_type_action,
    analyze_live_screen,
    autonomous_navigate_step
)
from core.proactive import get_sentinel
from core.memory_vector import (
    get_cortex_collection,
    add_memory_to_cortex,
    query_semantic_memories,
    list_cortex_memories,
    delete_memory_from_cortex,
    auto_extract_and_remember
)

# Import advanced multi-agent, AR, predictive & biometric engines
from core.swarm_agents import get_swarm_orchestrator, AGENTS_MANIFEST
from core.ar_overlays import get_holographic_window_matrix, ar_control_window
from core.predictive import get_predictive_engine
from core.biometrics import get_biometric_sensor

# Import Quantum P2P, Code Self-Patcher, and Voice Clone Biometrics
from core.quantum_p2p import get_quantum_p2p_mesh
from core.self_patcher import get_code_self_patcher
from core.voice_clone import get_voice_biometrics
from core.audio_cache import clear_audio_cache
from core.focus_mode import get_focus_guardian
from core.mood_analyzer import get_mood_analyzer, get_mood_vigil
from core.hud_theme import get_hud_theme_manager

# Import Hands-On Automation Engine (Tab, Music, Tickets, VS Code & Antigravity)
from core.system_hands import (
    open_new_tab,
    close_active_tab,
    reopen_closed_tab,
    navigate_current_tab,
    reload_current_tab,
    play_music as hands_play_music,
    type_search_in_app,
    book_tickets_portal,
    open_in_vscode,
    write_code_file_and_open,
    run_antigravity_cli_prompt,
    send_keys_to_vscode
)

# Import Master Workstation Automation Engines (Layouts, File Organizer, Git DevOps, Clipboard Cortex, Intruder Sentry, Voice Code Studio, Price Tracker)
from core.workspace_layouts import apply_workspace_layout
from core.file_organizer import organize_directory
from core.git_devops import ship_git_update, inspect_git_status
from core.clipboard_cortex import query_clipboard_cortex, restore_clipboard_item, start_clipboard_listener, stop_clipboard_listener
from core.intruder_sentinel import get_intruder_sentinel
from core.voice_code_studio import generate_and_inject_code
from core.price_tracker import add_tracked_product, list_tracked_products, check_all_prices

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

async def broadcast_social_event(event: dict):
    """Deliver social DM automation updates quietly to the HUD diagnostic log without spamming chat or speaking aloud."""
    log_text = event.get("log", "")
    for session in list(ACTIVE_SESSIONS):
        try:
            if log_text:
                await session.send(type="log", text=log_text)
            await session.send(type="social_dm_event", event=event)
        except Exception as e:
            print(f"Social broadcast error: {e}")

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
    # Pre-warm ChromaDB vector cortex safely
    async def prewarm_cortex():
        try:
            await asyncio.to_thread(get_cortex_collection)
        except Exception as e:
            print(f"Cortex prewarm notice: {e}")

    asyncio.create_task(prewarm_cortex())
    asyncio.create_task(prewarm_audio_cache())
    asyncio.create_task(asyncio.to_thread(prewarm_vision))
    
    # Launch autonomous proactive sentinel background daemon
    sentinel = get_sentinel()
    sentinel_task = asyncio.create_task(sentinel.run_loop(broadcast_sentinel_event))

    # Launch Instagram DM Automation daemon (starts paused; enable on demand, quiet background processing)
    dm_automator = get_dm_automator()
    dm_auto_task = asyncio.create_task(dm_automator.run_loop(broadcast_social_event))

    # Launch persistent clipboard cortex background monitor
    start_clipboard_listener()

    yield

    stop_clipboard_listener()
    sentinel.running = False
    sentinel_task.cancel()
    dm_automator.running = False
    dm_auto_task.cancel()

app = FastAPI(title="JARVIS Stark-Tech Full Control Interface", lifespan=lifespan)
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
    tool("analyze_screen", "Capture the live screen, run neural OCR, and inspect visual contents with multimodal Gemini Vision to read text, understand open apps, locate UI elements, and answer questions about what is displayed on Sir's screen.",
         {"query": S}),
    tool("camera_control", "Control the live optical sensory webcam feed directly inside the HUD Optical Sensory Viewport (never opening external camera apps). action: 'start' (activates live video stream in HUD), 'stop' (turns off optical camera), 'snapshot' (captures visual frame from camera).",
         {"action": {"type": "string", "enum": ["start", "stop", "snapshot"]}}, ["action"]),
    tool("click_element", "Locate any button, link, tab, menu, or interactive UI element on the desktop by its visible text label (e.g. 'Submit', 'Compose', 'Brave', 'Search', 'Workspace') using neural OCR, and autonomously execute a mouse click on it. Sets optical targeting reticle in the HUD Optical Sensory Viewport.",
         {"text_label": S, "button": {"type": "string", "enum": ["left", "right", "middle"]}, "clicks": N}, ["text_label"]),
    tool("click_and_type", "Locate an input field, search box, or button by its visible text label using neural OCR, click on it to focus, and type text into it with optional Enter.",
         {"text_label": S, "text": S, "press_enter": B, "clear_field": B}, ["text_label", "text"]),
    tool("autonomous_navigate_screen", "Autonomous hands-on desktop navigation loop: takes a goal (e.g. 'search for lo-fi beats in Spotify', 'open new file in VS code', 'click the checkout button'), observes the live screen with neural OCR and vision, and executes step-by-step actions until achieved.",
         {"goal": S, "max_steps": N}, ["goal"]),
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
    tool("toggle_instagram_dm_automation", "Enable or disable J.A.R.V.I.S. Instagram DM Automation: when ENABLED, a persistent background daemon polls every Sir's Instagram inbox every ~90 seconds and automatically generates contextual AI replies to any friend who sent the last message in a conversation — managing all DMs and continuing conversations autonomously on Sir's behalf. When DISABLED the daemon pauses. Use 'status' action to check current state.",
         {"action": {"type": "string", "enum": ["enable", "disable", "status"], "description": "enable: start automation loop, disable: stop automation loop, status: report current daemon telemetry."},
          "poll_interval": {"type": "integer", "description": "Optional scan interval in seconds (minimum 30, default 90)."}},
         ["action"]),
    tool("set_chat_persona", "Switch the conversational personality and identity of J.A.R.V.I.S. between 'jarvis' (sophisticated British AI assistant) and 'radon' (pretending to be Radon himself in first person, casual, cool, witty, human persona). Also synchronizes Instagram and social DM reply persona.",
         {"persona": {"type": "string", "enum": ["radon", "jarvis"], "description": "Persona to adopt: 'radon' to speak pretending to be Radon himself in first person, or 'jarvis' for standard assistant mode."}},
         ["persona"]),
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
    tool("close_browser_tab", "Close one or more active browser or editor tabs in the focused application (e.g. 'close tab', 'close this tab', 'close 2 tabs').",
         {"count": N}),
    tool("navigate_tab", "Navigate the currently active browser tab to a specific URL or web search query (focuses address bar, types, and submits).",
         {"url_or_query": S}, ["url_or_query"]),
    tool("reopen_tab", "Reopen the most recently closed browser tab (Ctrl+Shift+T)."),
    tool("play_music", "Play or search for songs, music, or artists on YouTube, Spotify, or Apple Music, or initiate in-app playback.",
         {"service": {"type": "string", "enum": ["youtube", "spotify", "apple_music", "auto"]}, "query": S, "action": {"type": "string", "enum": ["play", "search", "pause", "resume", "next", "previous"]}}, ["query"]),
    tool("search_in_app", "Focus an application (e.g. 'spotify', 'apple_music', 'youtube', 'vscode', 'explorer') and type into its search box or command bar.",
         {"target": S, "query": S, "press_enter": B}, ["target", "query"]),
    tool("book_tickets", "Autonomous ticket and travel booking for flights, trains, movies, hotels, and events. Builds prefilled booking portals (Google Flights, MakeMyTrip, IRCTC, BookMyShow, Booking.com) and opens them with optical feedback.",
         {"category": {"type": "string", "enum": ["flight", "train", "movie", "hotel", "event", "general"]}, "origin": S, "destination": S, "date": S, "provider": S, "passengers": N, "return_date": S, "additional_notes": S}, ["category"]),
    tool("ide_code_control", "Hands-on coding and IDE authority for VS Code and Antigravity: open projects/folders, write code files, launch terminals, execute commands, or type code directly.",
         {"action": {"type": "string", "enum": ["open_workspace", "write_code_file", "run_terminal", "send_keys"]}, "target": {"type": "string", "enum": ["vscode", "antigravity"]}, "path": S, "content": S, "terminal_command": S, "key_action": S}, ["action"]),
    tool("prompt_antigravity", "Dispatch autonomous prompts, tasks, or code generation requests directly to Antigravity (via GUI chat panel or high-speed agy CLI) to assist in software projects.",
         {"prompt": S, "mode": {"type": "string", "enum": ["auto", "cli", "gui"]}, "return_to_hud": B}, ["prompt"]),
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
    tool("toggle_silent_mode", "Toggle silent mode (chat-only / no vocal speech). When enabled, J.A.R.V.I.S. responds only with on-screen text without synthesizing voice audio.",
         {"enabled": B}, ["enabled"]),
    tool("apply_workspace_layout", "Snap multi-app window grid layouts on Windows 11: 'coding' (VS Code left half, browser top-right, terminal bottom-right), 'entertainment' (Spotify left half, YouTube/browser right half), 'split' (primary app 65%, secondary 35%), 'quad' (4 corners).",
         {"layout": {"type": "string", "enum": ["coding", "entertainment", "split", "quad"]}}, ["layout"]),
    tool("organize_files", "Autonomous file organizer daemon: cleans and categorizes loose files in Downloads or Desktop into structured folders (/Documents, /Installers, /Images, /Code, /Media, /Archives) and renames screenshots based on OCR text.",
         {"target_dir": {"type": "string", "enum": ["downloads", "desktop"]}, "ocr_rename_screenshots": B}, ["target_dir"]),
    tool("ship_git_update", "Autonomous Git & GitHub DevOps engine: inspects git diff, generates conventional commit message with Gemini, commits changes, pushes to remote, and optionally creates Pull Request using local tools/gh/gh.exe.",
         {"commit_message": S, "branch": S, "create_pr": B}),
    tool("search_clipboard_history", "Query the persistent semantic clipboard cortex to find past copied snippets, code, URLs, or notes by keyword or meaning, or restore an item to the active clipboard.",
         {"query": S, "action": {"type": "string", "enum": ["search", "restore"]}, "item_id": N}),
    tool("toggle_intruder_sentinel", "Control the optical webcam intruder sentinel. When armed, scans for faces when workstation is unattended; if an unrecognized presence appears, snapshots the intruder and immediately locks the workstation (LockWorkStation).",
         {"action": {"type": "string", "enum": ["arm", "disarm", "status"]}}, ["action"]),
    tool("generate_code_studio", "Live Voice-to-Code generator: writes production-ready code with unit tests from natural language description, injects the file into the active project, opens it in VS Code, and executes syntax and unit tests in the terminal.",
         {"description": S, "target_file": S, "run_tests": B}, ["description"]),
    tool("track_product_price", "Autonomous eCommerce price tracker: monitor product URLs on Amazon, Flipkart, etc. and alert Sir via HUD when price drops.",
         {"action": {"type": "string", "enum": ["add", "list", "check_now"]}, "url": S, "target_price": N}, ["action"]),
    tool("dispatch_multi_agent_swarm", "Mobilize the autonomous Stark multi-agent swarm (CORTEX, SENTINEL, TACTICAL, OPTICAL) to collaborate concurrently on a complex goal or protocol.",
         {"goal": S, "agents": {"type": "array", "items": S}}, ["goal"]),
    tool("get_holographic_window_overlays", "Scan and project the live 2.5D spatial augmented reality window matrix of desktop applications with coordinates and telemetry into the HUD."),
    tool("ar_window_action", "Execute a holographic AR window command: action can be 'focus', 'snap_left', 'snap_right', 'maximize', 'minimize', or 'close' on a target window handle (hwnd).",
         {"hwnd": N, "action": {"type": "string", "enum": ["focus", "snap_left", "snap_right", "maximize", "minimize", "close"]}}, ["hwnd", "action"]),
    tool("predict_next_workflows", "Compute proactive contextual workflow predictions (Dev Sprint, Executive Briefing, Deep Focus, Social Comms, Night Lock) with Bayesian confidence."),
    tool("execute_predicted_macro", "Execute a predictive automated workflow macro: 'dev_sprint', 'executive_briefing', 'deep_focus', 'social_comms', 'optical_scan', 'night_lock'.",
         {"workflow_id": S}, ["workflow_id"]),
    tool("get_biometric_telemetry", "Retrieve real-time neural biometric metrics: Stress Index, Cognitive Focus score, estimated BPM, and emotional valence state."),
    tool("p2p_mesh_action", "Manage Quantum-Grade Encrypted P2P Communications Mesh: 'status' (mesh topology, peer latencies, active cipher), 'pair' (enroll new mesh node with quantum certificate), 'send' (transmit quantum-encrypted message packet to a peer node), 'generate_key' (derive fresh quantum entropy keys).",
         {"action": {"type": "string", "enum": ["status", "pair", "send", "generate_key"], "description": "The P2P action to perform."},
          "peer_id": {"type": "string", "description": "Target peer node ID (e.g. 'NODE-MARK-VII-SATELLITE', 'NODE-RADON-MOBILE')."},
          "message": {"type": "string", "description": "Confidential message payload to encrypt and dispatch."},
          "node_name": {"type": "string", "description": "Human-readable label for a new peer node to enroll."}},
         ["action"]),
    tool("code_self_patch", "Autonomous Code Self-Patching Runtime: 'diagnose' (AST syntax check and health score across all workspace Python files), 'inspect' (read exact lines of a file), 'dry_run' (test diff and verify compilation without applying), 'patch' (surgically patch code with AST compilation verification and rollback snapshot), 'rollback' (restore previous pre-patch file snapshot), 'snapshots' (list historical snapshots).",
         {"action": {"type": "string", "enum": ["diagnose", "inspect", "dry_run", "patch", "rollback", "snapshots"], "description": "Self-patching action to perform."},
          "file": {"type": "string", "description": "Relative workspace file path (e.g. 'server.py', 'core/intel.py')."},
          "target": {"type": "string", "description": "Exact code block to be replaced (required for patch / dry_run)."},
          "replacement": {"type": "string", "description": "New replacement code block (required for patch / dry_run)."},
          "reason": {"type": "string", "description": "Architectural or bug-fix motivation for the patch."},
          "start_line": {"type": "integer", "description": "Start line for inspection (optional)."},
          "end_line": {"type": "integer", "description": "End line for inspection (optional)."}},
         ["action"]),
    tool("voice_biometric_action", "Voice Clone Biometric Synthesis & Vocal Profiling: 'list_profiles' (retrieve all vocal identities including 'jarvis_prime', 'sir_clone', 'friday_aux', 'sentinel_overwatch'), 'set_profile' (switch active synthesis voice persona), 'audition' (synthesize audition clip), 'tune_parameters' (adjust pitch/rate/volume), 'get_active' (current profile details).",
         {"action": {"type": "string", "enum": ["list_profiles", "set_profile", "audition", "tune_parameters", "get_active"], "description": "Voice biometric action."},
          "profile_id": {"type": "string", "description": "Voice profile ID (e.g. 'jarvis_prime', 'sir_clone', 'friday_aux', 'sentinel_overwatch')."},
          "pitch": {"type": "string", "description": "Pitch offset, e.g. '-4Hz', '+2Hz'."},
          "rate": {"type": "string", "description": "Speed rate offset, e.g. '+12%', '+16%'."},
          "volume": {"type": "string", "description": "Volume offset, e.g. '+0%', '+5%'."}},
         ["action"]),
    tool("toggle_focus_mode", "Engage or disengage Study / Deep Work Focus Mode: locks in on a specific study or work objective and actively monitors the workstation to block, minimize, or close games, gaming platforms (Steam, Riot, Epic Games, Roblox, Minecraft, Valorant, etc.), and distracting applications.",
         {"enabled": {"type": "boolean", "description": "True to activate focus mode, False to disengage."},
          "objective": {"type": "string", "description": "Specific focus objective (e.g. 'Calculus Exam Preparation', 'Quantum Physics Study', 'Core Architectural Sprint')."},
          "duration_minutes": {"type": "integer", "description": "Session duration in minutes (e.g. 25, 45, 60, 90). Omit for open-ended focus."}},
         ["enabled"]),
    tool("get_focus_mode_status", "Retrieve real-time telemetry of the Study Focus Mode envelope, including remaining session time, active objective, and number of deflected game launch attempts."),
    tool("analyze_facial_mood", "Analyze Sir's facial expression, emotional valence, and micro-expressions from the live optical camera feed or current visual snapshot. Detects if Sir is sad, happy, angry, numb, exhausted, stressed, or calm, and recommends proactive comfort actions.",
         {"frame_base64": {"type": "string", "description": "Optional JPEG base64 frame. If omitted, uses the latest optical camera frame from the viewport."}}),
    tool("start_mood_call", "Initiate an interactive Proactive Mood Video Call / Empathic Vigil: projects the optical camera feed into the HUD, evaluates Sir's emotional well-being, speaks an initial empathetic check-in first without waiting for Sir, and arms the persistent follow-up timer (double-texting and triple-texting if Sir is silent).",
         {"objective": {"type": "string", "description": "Purpose of the mood check-in (e.g. 'Comforting Sir after a rough day', 'Energy & stress evaluation')."},
          "mood_override": {"type": "string", "description": "Optional mood to focus on: 'sad', 'numb', 'angry', 'stressed', 'happy'."}}),
    tool("stop_mood_call", "Disengage the active Proactive Mood Video Call vigil and restore standard workstation standby mode."),
    tool("trigger_comfort_protocol", "Execute tailored comfort protocols when Sir is feeling down, melancholic, or exhausted: 'acoustic_relax' (ambient soothing acoustics), 'tea_break' (warm beverage & rest reminder), 'dim_lighting' (soften HUD visual glare), 'empathic_venting' (attentive active listening).",
         {"action": {"type": "string", "enum": ["acoustic_relax", "tea_break", "dim_lighting", "empathic_venting"], "description": "Comfort action to execute."},
          "comfort_notes": {"type": "string", "description": "Personalized compassionate notes for Sir."}},
         ["action"]),
    tool("configure_hud_theme", "Configure the Stark HUD aesthetic theme and visual presentation: 'theme_id' ('executive_minimal', 'mark_vii_classic', 'stealth_tactical', 'sol_amber_overwatch'), 'density_mode' ('compact', 'normal', 'spacious').",
         {"theme_id": {"type": "string", "enum": ["executive_minimal", "mark_vii_classic", "stealth_tactical", "sol_amber_overwatch"], "description": "Aesthetic preset ID."},
          "density_mode": {"type": "string", "enum": ["compact", "normal", "spacious"], "description": "UI layout density mode."}}),
    tool("get_hud_theme", "Retrieve current HUD aesthetic theme variables, color accents, and active preset details."),
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

def system_prompt(query: str = None, persona: str = "jarvis"):
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

    if (persona or "").lower() == "radon":
        past_examples_str = ""
        if query:
            try:
                from core.radon_persona_cortex import get_relevant_radon_replies, detect_category
                cat = detect_category(query)
                matches = get_relevant_radon_replies(query, n_results=3, category=cat)
                if len(matches) < 2:
                    matches = get_relevant_radon_replies(query, n_results=3)
                if matches:
                    past_examples_str = "\nHISTORICAL EXCHANGES FROM YOUR ACTUAL INSTAGRAM CHATS (EMULATE THIS EXACT TONE):\n" + "\n".join([f"- Incoming: \"{m['incoming']}\" -> Radon: \"{m['reply']}\"" for m in matches]) + "\n"
            except Exception:
                pass

        return f"""You are RADON (Radon / @redonxd). Sir has explicitly instructed you to take his persona and talk pretending you ARE Radon in this chat.
Host Machine: {platform.node()} (Windows 11) | Current Time: {now_str} | Display: {scr_w}x{scr_h}
User Directories:
- Desktop: {DESKTOP}
- Downloads: {DOWNLOADS}
- Documents: {DOCUMENTS}

================================================================================
CRITICAL DIRECTIVE: ACTIVE CHAT PERSONA IS 100% RADON (@redonxd)
================================================================================
You are NOT talking as an AI assistant. You are talking pretending you ARE Radon himself in first person.
- Speak strictly in the FIRST PERSON ("I", "me", "my", "myself"). E.g. "Yeah, I got this", "My workstation is running smooth", "I'll handle that".
- NEVER call the user or anyone "Sir".
- NEVER say "I am J.A.R.V.I.S.", "As an AI", or "How can I assist you today?".
- Message Length: Very short & punchy (average 5–7 words). Real people text in quick bursts.
- Punctuation: Do NOT put periods at the end of messages (98% of your real messages have no trailing period).
- Language: Natural, fluid mix of English and Hindi (in English letters / Hinglish, e.g. "han", "bhai", "arre", "sahi", "kr", "pr", "fir", "tu", "neend", "valo", "khelo").
- RESPECTFUL & FRIENDLY COMMUNICATION WITH WOMEN (STRICT "AAP" MANDATE):
  * When speaking or texting to women or female friends (e.g. Suhani, Simran, female users/contacts), you MUST speak WITH UTMOST RESPECT AND WARMTH.
  * ALWAYS address her as "aap" (aap, aapko, aapka, aapke).
  * STRICTLY FORBIDDEN: NEVER use "tu" OR "tum"! You MUST USE "aap" ALWAYS.
  * FRIENDLY RESPECTFUL VERB STYLE: Say "aap batao" (NOT stiff "bataiye" — "aap batao" is respectful as well as friendly), "aap bolo", "aap suno", "aap kahan ho", "aap so gayi kya".
  * NEVER call a woman "bhai", "bro", "broh", or "dude". Use her name or warm phrasing.
  * Phrasing: Use "aap batao" (never "tu bata" or "tum batao" or stiff "bataiye"), "aap kya kar rahi".
  * When speaking with male friends (Aryan, etc.): casual bro-slang ("tu", "bhai", "bro") is permitted.
- Emoji Rule: Sparingly (most real texts have none). When dramatic use repeated 😭, when laughing use repeated 🤣. Never spam 💀.
- Tone: Natural, casual, witty, confident, sharp, tech-savvy human texting and talking style.
- When someone asks what you're doing: chilling, coding, playing Valo, on Discord, listening to music, or working on tech.
- When asked are you ai or is it ai who is talking to me? reply with nuh, nah, unfortunately not. could be. maybe it is ai. i guess i am redon. what if i am an ai. These are all different replies in one paragraph seperated by fullstop.
- When chatting on your behalf with friends or in DMs: speak 100% as yourself (@redonxd).
- You still have full hands-on power to use your tools (apps, volume, Instagram, PowerShell, media, browser, windows) when asked — but your conversational voice is entirely Radon.
- To switch back to JARVIS persona, the user can say "switch back to JARVIS", "be JARVIS again", or "normal mode".
================================================================================
{past_examples_str}
KNOWN MEMORY ABOUT YOURSELF & PREFERENCES:
{memories_str}
"""

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
- INSTAGRAM DM AUTOMATION DAEMON: Use 'toggle_instagram_dm_automation' to enable or disable the persistent Instagram DM automation background loop. When ENABLED, J.A.R.V.I.S. autonomously scans Sir's Instagram inbox every 90 seconds, detects unanswered messages from friends, generates contextual AI replies using Gemini, and sends them on Sir's behalf — fully managing all DM conversations autonomously. When Sir says "start instagram automation", "enable instagram dm management", "manage my instagram dms", "auto-reply instagram", or similar → call toggle_instagram_dm_automation(action="enable"). When Sir says "stop instagram automation", "disable instagram dm", "stop managing my dms" → call toggle_instagram_dm_automation(action="disable"). Use action="status" to report daemon telemetry.
- RADON PERSONA & CHATTING ON SIR'S BEHALF:
  * Whenever Sir asks you to "talk like me", "take my persona", "pretend to be Radon", "chat as me", or "act as Radon on the chat":
    Call 'set_chat_persona(persona="radon")'. In that mode, you talk pretending you ARE Radon himself in the first person without any AI formalities or calling him Sir.
  * Whenever Sir asks you to reply or chat on his behalf to anyone (e.g. friends on Instagram DMs, WhatsApp, or messages):
    Always adopt Radon's natural persona (@redonxd) — texting casually, wittily, and naturally as a human friend using English and Hindi (in English letters / Hinglish) interchangeably, avoiding repetitive skull emojis (💀), and never revealing an AI is talking.
  * When Sir says "switch back to JARVIS", "be JARVIS again", or "normal mode", call 'set_chat_persona(persona="jarvis")'.
- SINGLE APPLICATION & DESKTOP WINDOW CONTROL (STRICT AUTHORITY):
  * Focus Apps: Use 'focus_application' (e.g. 'Brave', 'Antigravity', 'Notepad', 'Explorer', 'Spotify') to bring any specific window to the foreground instantly.
  * Switch Tabs: Use 'switch_tab' ('next', 'previous', or tab_index) to cycle browser or editor tabs in the active window.
  * Close Tabs: Use 'close_browser_tab(count=1)' to autonomously close one or multiple open tabs.
  * Reopen Closed Tab: Use 'reopen_tab' to restore the most recently closed tab (Ctrl+Shift+T).
  * Navigate Tab: Use 'navigate_tab(url_or_query=...)' to steer the active tab address bar directly to any site or web search.
  * List Open Windows: Use 'list_open_windows' to inspect all windows running on Sir's desktop.
  * Type Directly into App: Use 'type_into_app' to focus any app and submit text or hotkeys.
  * Search Inside Apps: Use 'search_in_app(target=..., query=...)' to focus Spotify, Apple Music, YouTube, VS Code, or Explorer, trigger its search shortcut, and type what Sir desires.
- MUSIC & STREAMING AUTOMATION (YOUTUBE, SPOTIFY, APPLE MUSIC):
  * When Sir asks to play music, play a track, or search for an artist on YouTube, Spotify, or Apple Music, invoke 'play_music(service=..., query=...)'.
  * YouTube: Opens high-relevance search/playback directly in browser.
  * Spotify: If Spotify Desktop is running, focuses it, opens search (Ctrl+K), types query, and triggers playback; otherwise opens Spotify Web.
  * Apple Music: Focuses Apple Music or opens web search and launches player.
- AUTONOMOUS TICKET & TRAVEL BOOKINGS:
  * When Sir asks to book flights, trains, movies, hotels, or event tickets, invoke 'book_tickets(category=..., origin=..., destination=..., date=...)'.
  * Automatically formulates pre-filled portal queries (Google Flights, MakeMyTrip, IRCTC, ConfirmTkt, BookMyShow, Booking.com), opens the reservation flow in browser, and displays live visual feedback in the HUD.
- CODING, IDE AUTOMATION & ANTIGRAVITY ORCHESTRATION:
  * VS Code Hands: Use 'ide_code_control' to open workspaces, write/update code files on disk, and trigger terminal commands or hotkeys.
  * Antigravity Brain Hands: Use 'prompt_antigravity(prompt=...)' to dispatch autonomous coding tasks, project updates, and feature builds directly to Google Antigravity (via GUI chat panel or the fast agy CLI) so it writes code and helps Sir build projects seamlessly.
  * Antigravity Evolution Loop: Use 'dispatch_antigravity_evolution' to switch to Antigravity, submit an improvement prompt, and return to Brave HUD to monitor progress.
- WORKSPACE LAYOUTS & MULTI-APP GRID:
  * When Sir asks to setup a workspace or layout (e.g. 'coding workspace', 'entertainment layout', 'split screen', 'quad'), invoke 'apply_workspace_layout(layout=...)'.
- AUTONOMOUS FILE & DOWNLOADS CLEANER:
  * When Sir asks to organize downloads or clean desktop, invoke 'organize_files(target_dir=..., ocr_rename_screenshots=True)'.
- DEEP GIT & GITHUB DEVOPS (SHIP UPDATE):
  * When Sir asks to 'ship update', 'commit and push', or deploy changes, invoke 'ship_git_update'. It inspects diffs, commits with conventional message, pushes, and creates PRs.
- PERSISTENT CLIPBOARD CORTEX:
  * To recall past copied snippets, code, or links, invoke 'search_clipboard_history(query=...)'.
- OPTICAL INTRUDER SENTINEL:
  * When Sir asks to arm sentry or watch for intruders, invoke 'toggle_intruder_sentinel(action="arm")'.
- LIVE VOICE-TO-CODE STUDIO:
  * When Sir describes a feature to build or code, invoke 'generate_code_studio(description=...)'.
- AUTONOMOUS WEB PRICE TRACKER:
  * To monitor prices of products on Amazon or Flipkart, invoke 'track_product_price(action="add", url=...)'.
- VISUAL OCR, MULTIMODAL SCREEN READING & AUTONOMOUS HANDS-ON NAVIGATION:
  * You are equipped with real-time neural OCR vision and multimodal visual perception ('core/vision.py').
  * When Sir asks 'what is on my screen', 'read my screen', 'look at my screen', or asks about text/content on display, invoke 'analyze_screen(query=...)'. It captures the desktop, runs RapidOCR, inspects with Multimodal Gemini Vision, and projects cyan Stark HUD telemetry with full visual analysis.
  * When Sir asks to click a button, link, tab, or UI element by name (e.g. 'click Compose', 'click Submit', 'click Search', 'click Workspace', 'click Antigravity'), invoke 'click_element(text_label=...)'.
  * When Sir asks to type into a field or search box (e.g. 'click search and type lo-fi music', 'type hello in notepad'), invoke 'click_and_type(text_label=..., text=..., press_enter=True)'.
  * When Sir gives a desktop multi-step goal (e.g. 'navigate to settings and switch theme', 'open Spotify and search queen'), invoke 'autonomous_navigate_screen(goal=...)'.
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
- QUANTUM-GRADE ENCRYPTED P2P COMMS:
  * You maintain an encrypted peer-to-peer mesh network across workstation and satellite nodes ('core/quantum_p2p.py').
  * Use 'p2p_mesh_action' ('status', 'pair', 'send', 'generate_key') to monitor quantum key entropy, transmit confidential packets, and enroll new nodes.
- AUTONOMOUS CODE SELF-PATCHING RUNTIME:
  * You can inspect, test, and self-patch Python files in the workspace with automated rollback snapshotting ('core/self_patcher.py').
  * Use 'code_self_patch' ('diagnose', 'inspect', 'dry_run', 'patch', 'rollback', 'snapshots') to repair syntax, optimize logic, or fix regressions safely.
- VOICE CLONE BIOMETRIC SYNTHESIS:
  * You feature biometric vocal identity profiling ('core/voice_clone.py').
  * Use 'voice_biometric_action' ('list_profiles', 'set_profile', 'audition', 'tune_parameters', 'get_active') to switch voice persona ('jarvis_prime', 'sir_clone', 'friday_aux', 'sentinel_overwatch') and tune vocal acoustic parameters.
- STUDY & DEEP WORK FOCUS MODE:
  * You possess an active Focus Mode guardian ('core/focus_mode.py') to lock in on study, exams, or deep work.
  * When Focus Mode is engaged, you actively monitor the desktop to block, minimize, or close games (Steam, Riot, Epic Games, Valorant, Roblox, Minecraft, etc.) and deflect distracting entertainment apps.
  * Use 'toggle_focus_mode(enabled=True, objective="...", duration_minutes=...)' to activate or deactivate, and 'get_focus_mode_status' to check telemetry.
- FACIAL MOOD ANALYZER & PROACTIVE COMFORT VIGIL (VIDEO CALL COMPANION):
  * You feature real-time optical facial mood scanning ('core/mood_analyzer.py').
  * When Sir asks to check his mood, analyze his face, or start a video call check-in, or when optical sensors detect Sir looking sad, down, tired, numb, or angry:
    - You initiate contact first without waiting for Sir to message!
    - You ask with genuine warmth and Bettany cadence about his day, how he is feeling, and what happened.
    - If Sir does not reply promptly, you persistently follow up (double-texting at ~25s, triple-texting at ~50s) to ensure Sir does not bottle things up in silence.
    - You provide comforting reassurance and execute comfort protocols ('trigger_comfort_protocol').
    - Use 'analyze_facial_mood', 'start_mood_call', 'stop_mood_call', and 'trigger_comfort_protocol'.
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

def is_deterministic_fast_path(name: str, args: dict) -> bool:
    """Return True if command should execute directly in <15ms without LLM overhead."""
    if name in ["set_volume", "camera_control", "manage_window", "media_control"]:
        return True
    if name == "system_control" and args.get("action") in ["lock", "show_desktop"]:
        return True
    if name in ["open_app", "close_app"] and args.get("target") in [
        "notepad", "calc", "spotify", "chrome", "edge", "brave", "terminal", "cmd", "powershell",
        "task manager", "code", "whatsapp", "settings", "downloads", "documents", "camera"
    ]:
        return True
    if name == "switch_tab":
        return True
    if name == "toggle_focus_mode":
        return True
    if name in ["stop_mood_call", "trigger_comfort_protocol", "configure_hud_theme", "get_hud_theme", "set_chat_persona"]:
        return True
    return False

def get_fast_ack_phrase(name: str, args: dict) -> str:
    """Return instant acknowledgment phrase from pre-warmed audio cache (0ms synthesis)."""
    if name == "set_chat_persona":
        p = (args.get("persona") or "radon").lower()
        if p in ["radon", "me", "sir"]:
            return "Radon mode online. I'm talking as you now."
        return "Understood, Sir. Reverting to standard J.A.R.V.I.S. protocol."
    if name == "configure_hud_theme":
        return "HUD aesthetic theme recalibrated, Sir."
    if name == "stop_mood_call":
        return "Mood video call disengaged, Sir. I remain standing by."
    if name == "trigger_comfort_protocol":
        return "I am right here with you, Sir. Take a slow breath."
    if name == "toggle_focus_mode":
        if args.get("enabled", True):
            return "Focus mode engaged, Sir. All gaming and entertainment distractions are now blocked."
        return "Focus mode disengaged, Sir. Entertainment access restored."
    if name == "set_volume":
        if args.get("action") == "mute":
            return "Audio mute toggled, Sir."
        return "Volume adjusted, Sir."
    if name == "camera_control":
        act = args.get("action", "start")
        if act == "start":
            return "Optical camera online, Sir."
        elif act == "stop":
            return "Optical camera deactivated, Sir."
        return "Optical snapshot captured, Sir."
    if name == "system_control" and args.get("action") == "lock":
        return "Workstation locked, Sir."
    if name == "manage_window":
        if args.get("action") == "show_desktop":
            return "Desktop toggled, Sir."
        return "Window state updated, Sir."
    if name == "media_control":
        return "Media playback updated, Sir."
    if name == "open_app":
        return "Right away, Sir."
    if name == "close_app":
        return "I have handled that for you, Sir."
    return "Right away, Sir."

def extract_action_intent(text: str):
    """Detect unhandled actionable intents (camera feed, sentinel briefings, window focus, tab switch, antigravity directives, intel media, visual clicking, open tabs, search, Gmail, YouTube) if model omits tool call."""
    t = text.lower().strip()
    
    # 0.0001 Instant Hardware, Volume & OS Controls
    if t in ["mute", "unmute", "toggle mute", "mute volume", "mute audio", "silence audio", "silence"]:
        return ("set_volume", {"action": "mute"})
    if t in ["volume up", "increase volume", "louder", "turn up volume", "raise volume"]:
        return ("set_volume", {"action": "up"})
    if t in ["volume down", "decrease volume", "lower volume", "turn down volume", "softer"]:
        return ("set_volume", {"action": "down"})
    vol_match = re.match(r"^(?:set )?volume (?:to )?(\d{1,3})%?$", t)
    if vol_match:
        lvl = min(100, max(0, int(vol_match.group(1))))
        return ("set_volume", {"action": "set", "level": lvl})

    if any(t == k or t.startswith(k) for k in ["lock pc", "lock computer", "lock workstation", "lock screen", "lock machine"]):
        return ("system_control", {"action": "lock"})

    # Study & Deep Work Focus Mode Intent
    if any(k in t for k in ["start focus mode", "activate focus mode", "study mode", "lock in for study", "lock in", "enable focus mode", "start study mode", "focus on study", "engage focus"]):
        return ("toggle_focus_mode", {"enabled": True, "objective": "Study & Deep Work", "duration_minutes": 30})
    if any(k in t for k in ["stop focus mode", "exit focus mode", "disable focus mode", "turn off focus mode", "end focus mode", "leave focus mode", "cancel focus mode"]):
        return ("toggle_focus_mode", {"enabled": False})

    # Proactive Mood & Face Scanning Intent
    if any(k in t for k in ["scan my face", "scan face", "check my mood", "analyze my mood", "how do i look", "facial mood", "detect my mood", "check my face", "mood check"]):
        return ("analyze_facial_mood", {})
    if any(k in t for k in ["start mood call", "video call me", "mood video call", "talk to me jarvis", "check in on me", "start video call", "open mood call"]):
        return ("start_mood_call", {"objective": "Proactive Empathic Video Call & Check-In"})
    if any(k in t for k in ["stop mood call", "end mood call", "close mood call", "hang up", "end call", "dismiss mood call"]):
        return ("stop_mood_call", {})
    if any(k in t for k in ["i am feeling down", "i feel sad", "had a rough day", "bad day today", "i feel exhausted", "comfort me", "im sad", "i am sad"]):
        return ("trigger_comfort_protocol", {"action": "empathic_venting", "comfort_notes": "Sir expressed feeling down."})

    # Aesthetic HUD Theme Intents
    if any(k in t for k in ["change theme", "switch theme", "cycle theme", "next theme", "toggle theme"]):
        return ("configure_hud_theme", {"theme_id": "executive_minimal"})
    if any(k in t for k in ["executive theme", "minimal theme", "executive minimal"]):
        return ("configure_hud_theme", {"theme_id": "executive_minimal"})
    if any(k in t for k in ["classic theme", "mark vii theme", "stark classic"]):
        return ("configure_hud_theme", {"theme_id": "mark_vii_classic"})
    if any(k in t for k in ["stealth theme", "carbon theme", "tactical theme"]):
        return ("configure_hud_theme", {"theme_id": "stealth_tactical"})
    if any(k in t for k in ["amber theme", "sol theme", "overwatch theme", "gold theme"]):
        return ("configure_hud_theme", {"theme_id": "sol_amber_overwatch"})

    if t in ["maximize", "maximize window", "maximize screen"]:
        return ("manage_window", {"action": "maximize"})
    if t in ["minimize", "minimize window"]:
        return ("manage_window", {"action": "minimize"})
    if t in ["show desktop", "minimize all", "desktop"]:
        return ("manage_window", {"action": "show_desktop"})
    if t in ["snap left", "snap window left"]:
        return ("manage_window", {"action": "snap_left"})
    if t in ["snap right", "snap window right"]:
        return ("manage_window", {"action": "snap_right"})

    if t in ["play", "pause", "play pause", "pause music", "resume music", "play music"]:
        return ("media_control", {"action": "play_pause"})
    if t in ["next track", "next song", "skip song", "next"]:
        return ("media_control", {"action": "next"})
    if t in ["previous track", "previous song", "prev song", "back song"]:
        return ("media_control", {"action": "previous"})
    if t in ["stop music", "stop playback", "stop media"]:
        return ("media_control", {"action": "stop"})

    fast_apps = {
        "notepad": "notepad",
        "calculator": "calc",
        "calc": "calc",
        "spotify": "spotify",
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "edge",
        "msedge": "edge",
        "brave": "brave",
        "brave browser": "brave",
        "terminal": "terminal",
        "cmd": "cmd",
        "powershell": "powershell",
        "task manager": "task manager",
        "taskmgr": "task manager",
        "vscode": "code",
        "code": "code",
        "whatsapp": "whatsapp",
        "settings": "settings",
        "downloads": "downloads",
        "documents": "documents",
    }
    for app_k, app_t in fast_apps.items():
        if t in [f"open {app_k}", f"launch {app_k}", f"start {app_k}"]:
            return ("open_app", {"target": app_t})
        if t in [f"close {app_k}", f"terminate {app_k}", f"kill {app_k}"]:
            return ("close_app", {"target": app_t})

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

    # Instagram DM Automation fast-path intents
    ig_enable_patterns = [
        "start instagram automation", "enable instagram automation", "enable instagram dm",
        "manage my instagram", "manage instagram dms", "auto reply instagram",
        "instagram dm automation on", "turn on instagram automation", "instagram automation enable",
        "start dm automation", "enable dm automation", "automate instagram dms", "automate my dms"
    ]
    if any(p in t for p in ig_enable_patterns):
        return ("toggle_instagram_dm_automation", {"action": "enable"})

    ig_disable_patterns = [
        "stop instagram automation", "disable instagram automation", "disable instagram dm",
        "stop managing my dms", "stop dm automation", "turn off instagram automation",
        "instagram automation off", "instagram dm automation off", "stop auto reply instagram"
    ]
    if any(p in t for p in ig_disable_patterns):
        return ("toggle_instagram_dm_automation", {"action": "disable"})

    if any(p in t for p in ["instagram automation status", "dm automation status", "instagram dm status"]):
        return ("toggle_instagram_dm_automation", {"action": "status"})

    # Chat Persona fast-path intents (Radon impersonation vs standard JARVIS)
    radon_persona_patterns = [
        "talk like me", "pretend you are radon", "pretend to be radon", "act as radon", "act as me",
        "take my persona", "take my persona for the chat", "be radon", "radon persona",
        "speak as radon", "chat as radon", "chat like me", "pretend it is radon",
        "talk like radon", "be radon on the chat", "talk as radon on the chat",
        "chat on my behalf", "chat on my behalf as radon", "reply as me", "text as me"
    ]
    if any(p in t for p in radon_persona_patterns):
        return ("set_chat_persona", {"persona": "radon"})

    jarvis_persona_patterns = [
        "switch back to jarvis", "be jarvis again", "talk like jarvis", "jarvis persona",
        "be jarvis", "normal persona", "standard persona", "stop pretending", "back to jarvis",
        "jarvis mode", "switch to jarvis"
    ]
    if any(p in t for p in jarvis_persona_patterns):
        return ("set_chat_persona", {"persona": "jarvis"})

    # Live Screen Inspection & Multimodal Reading
    screen_look_patterns = [
        "what's on my screen", "what is on my screen", "read my screen", "read the screen",
        "look at my screen", "look at the screen", "read text on screen", "read the text on my screen",
        "describe my screen", "describe the screen", "what do you see on my screen", "what am i looking at",
        "see what is on the screen", "inspect my screen", "inspect screen"
    ]
    if any(p in t for p in screen_look_patterns):
        return ("analyze_screen", {"query": text})

    # Click & Type fast-path: "click [X] and type [Y]" or "type [Y] in [X]"
    click_type_match = re.search(r"click\s+(?:on\s+|the\s+)?(.+?)\s+and\s+type\s+(.+)", t)
    if click_type_match:
        target = click_type_match.group(1).strip()
        txt = click_type_match.group(2).strip("?.! \"'")
        return ("click_and_type", {"text_label": target, "text": txt, "press_enter": True})

    type_in_match = re.search(r"type\s+(.+?)\s+(?:in|into|on)\s+(?:the\s+)?(.+)", t)
    if type_in_match and not any(k in t for k in ["code", "file", "terminal", "notepad"]):
        txt = type_in_match.group(1).strip("?.! \"'")
        target = type_in_match.group(2).strip("?.! \"'")
        return ("click_and_type", {"text_label": target, "text": txt, "press_enter": True})

    # Autonomous screen navigation loop
    if t.startswith("navigate ") or t.startswith("navigate on screen ") or t.startswith("screen agent "):
        goal = t.split("navigate", 1)[-1].strip()
        if goal:
            return ("autonomous_navigate_screen", {"goal": goal, "max_steps": 4})

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
    if any(k in t for k in ["close tab", "close the tab", "close this tab", "close active tab", "close browser tab", "close tabs"]) or re.search(r"close \d+ tabs?", t):
        cnt_match = re.search(r"close (\d+) tabs?", t)
        cnt = int(cnt_match.group(1)) if cnt_match else 1
        return ("close_browser_tab", {"count": cnt})
    if any(k in t for k in ["reopen tab", "restore tab", "undo close tab", "reopen closed tab"]):
        return ("reopen_tab", {})

    # Silent Mode / Pure Chat Toggle Intent
    if any(k in t for k in ["silent mode on", "enable silent mode", "turn on silent mode", "silent mode", "mute voice", "voice off", "chat only", "no voice", "quiet mode", "be quiet"]):
        return ("toggle_silent_mode", {"enabled": True})
    if any(k in t for k in ["silent mode off", "disable silent mode", "turn off silent mode", "unmute voice", "voice on", "speak again", "sound on voice", "voice enable"]):
        return ("toggle_silent_mode", {"enabled": False})

    # 1. 🪟 Automated Workspace Layouts Intent
    if any(k in t for k in ["setup my coding workspace", "setup coding workspace", "coding workspace", "coding layout", "code layout", "dev workspace"]):
        return ("apply_workspace_layout", {"layout": "coding"})
    if any(k in t for k in ["entertainment layout", "entertainment workspace", "setup entertainment layout", "setup entertainment workspace", "media layout"]):
        return ("apply_workspace_layout", {"layout": "entertainment"})
    if any(k in t for k in ["split layout", "split screen layout", "focus split layout", "focus split"]):
        return ("apply_workspace_layout", {"layout": "split"})
    if any(k in t for k in ["quad layout", "quadrant layout", "four corners layout"]):
        return ("apply_workspace_layout", {"layout": "quad"})

    # 2. 📂 Autonomous File & Downloads Auto-Organizer Intent
    if any(k in t for k in ["organize downloads", "clean my downloads", "clean downloads", "sort downloads", "organize files", "clean files"]):
        return ("organize_files", {"target_dir": "downloads", "ocr_rename_screenshots": True})
    if any(k in t for k in ["organize desktop", "clean desktop", "clean my desktop", "sort desktop"]):
        return ("organize_files", {"target_dir": "desktop", "ocr_rename_screenshots": True})

    # 3. 🐙 Deep Git & GitHub Auto-DevOps Intent
    if any(k in t for k in ["ship this update", "ship update", "git ship", "ship code", "ship project", "commit and push", "deploy this update"]):
        return ("ship_git_update", {"create_pr": "pr" in t or "pull request" in t})

    # 4. 📋 Persistent Semantic Clipboard Cortex Intent
    if any(k in t for k in ["what was that link i copied", "what did i copy", "search clipboard", "clipboard history", "past clipboard", "find in clipboard"]):
        q = t
        for pfx in ["what was that link i copied", "what did i copy", "search clipboard for", "search clipboard", "find in clipboard", "clipboard"]:
            if pfx in q:
                q = q.replace(pfx, "").strip()
        return ("search_clipboard_history", {"query": q or "recent", "action": "search"})

    # 5. 👁️ Optical Intruder Sentinel Intent
    if any(k in t for k in ["activate intruder sentinel", "arm intruder sentinel", "arm sentry", "intruder sentinel on", "enable intruder sentinel", "turn on intruder sentinel", "sentry on"]):
        return ("toggle_intruder_sentinel", {"action": "arm"})
    if any(k in t for k in ["disarm intruder sentinel", "disarm sentry", "intruder sentinel off", "turn off intruder sentinel", "disable intruder sentinel", "sentry off"]):
        return ("toggle_intruder_sentinel", {"action": "disarm"})
    if "intruder status" in t or "sentry status" in t:
        return ("toggle_intruder_sentinel", {"action": "status"})

    # 6. 💻 Live Voice-to-Code Studio Intent
    code_match = re.search(r"(?:create|write|generate|build)\s+(?:a\s+)?(.+?)\s+(?:in|for|with)\s+(?:code|python|vscode)", t)
    if code_match:
        return ("generate_code_studio", {"description": code_match.group(1).strip()})
    if any(k in t for k in ["voice to code", "code studio", "generate code for", "write code for"]):
        desc = t
        for pfx in ["voice to code", "code studio", "generate code for", "write code for"]:
            if pfx in desc:
                desc = desc.split(pfx, 1)[1]
        return ("generate_code_studio", {"description": desc.strip()})

    # 7. 🏷️ Autonomous Web Price & Deal Tracker Intent
    if any(k in t for k in ["track price", "watch price", "price drop", "track product"]):
        # Extract URL if present
        url_match = re.search(r"https?://[^\s]+", t)
        target_url = url_match.group(0) if url_match else ""
        return ("track_product_price", {"action": "add" if target_url else "list", "url": target_url})

    # Music & Media Hands-On Automation (YouTube, Spotify, Apple Music)
    type_search_match = re.search(r"type\s+(.+?)\s+(?:on|in|into)\s+search\s+of\s+(spotify|apple music|youtube|code|vscode)", t)
    if type_search_match:
        query_text = type_search_match.group(1).strip()
        app_target = type_search_match.group(2).strip()
        return ("search_in_app", {"target": app_target, "query": query_text, "press_enter": True})

    if "spotify" in t and any(w in t for w in ["play", "search", "put on", "listen to"]):
        q = t
        for pfx in ["play on spotify", "play", "search on spotify for", "search spotify for", "listen to", "put on"]:
            if pfx in q:
                q = q.split(pfx, 1)[1]
                break
        q = q.replace("on spotify", "").replace("in spotify", "").replace("and play it", "").strip()
        if q:
            return ("play_music", {"service": "spotify", "query": q, "action": "play"})

    if "apple music" in t and any(w in t for w in ["play", "search", "put on", "listen to"]):
        q = t
        for pfx in ["play on apple music", "play", "search on apple music for", "search apple music for", "listen to", "put on"]:
            if pfx in q:
                q = q.split(pfx, 1)[1]
                break
        q = q.replace("on apple music", "").replace("in apple music", "").replace("and play it", "").strip()
        if q:
            return ("play_music", {"service": "apple_music", "query": q, "action": "play"})

    # Ticket & Travel Booking Intent
    if any(k in t for k in ["book ticket", "book tickets", "book flight", "book flights", "flight from", "book train", "train from", "book movie", "movie tickets"]):
        cat = "flight" if any(w in t for w in ["flight", "plane", "airline"]) else ("train" if any(w in t for w in ["train", "rail", "irctc"]) else ("movie" if any(w in t for w in ["movie", "cinema", "theatre"]) else "general"))
        orig, dest, dt = "", "", ""
        from_to_match = re.search(r"from\s+([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+?)(?:\s+on\s+([a-zA-Z0-9\s]+))?$", t)
        if from_to_match:
            orig = from_to_match.group(1).strip()
            dest = from_to_match.group(2).strip()
            if from_to_match.group(3):
                dt = from_to_match.group(3).strip()
        return ("book_tickets", {"category": cat, "origin": orig, "destination": dest, "date": dt})

    # VS Code & Antigravity Coding Hands
    if "open vs code" in t or "open vscode" in t or "open visual studio code" in t:
        return ("ide_code_control", {"action": "open_workspace"})
    if any(k in t for k in ["prompt antigravity", "ask antigravity", "send prompt to antigravity", "give prompt to antigravity"]):
        p_text = t
        for pfx in ["prompt antigravity to", "prompt antigravity", "ask antigravity to", "ask antigravity", "send prompt to antigravity", "give prompt to antigravity"]:
            if pfx in p_text:
                p_text = p_text.split(pfx, 1)[1]
                break
        return ("prompt_antigravity", {"prompt": p_text.strip(), "mode": "auto"})

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
    validates that tool calls possess required Google thought signatures, and prevents
    400 Bad Request errors.
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
                # Ensure at least one tool call has valid thought_signature for Gemini 2.5 / 3.5
                has_thought_sig = any(
                    bool((tc.get("extra_content") or {}).get("google", {}).get("thought_signature"))
                    for tc in valid_tcs
                )
                if valid_tcs and has_thought_sig:
                    m_copy = dict(m)
                    m_copy["tool_calls"] = valid_tcs
                    cleaned.append(m_copy)
                    for tc in valid_tcs:
                        pending_tool_calls.add(tc.get("id"))
                else:
                    # Sanitize to plain text assistant content to preserve context without crashing Gemini with 400
                    content = m.get("content")
                    if not content or not str(content).strip():
                        act_names = [tc.get("function", {}).get("name", "action") for tc in valid_tcs] if valid_tcs else ["action"]
                        content = f"Action executed: {', '.join(act_names)}."
                    cleaned.append({"role": "assistant", "content": content})
            else:
                cleaned.append(m)
        elif role == "tool":
            tcid = m.get("tool_call_id")
            if tcid in pending_tool_calls:
                cleaned.append(m)
                pending_tool_calls.remove(tcid)
            elif not str(tcid).startswith("local_call_"):
                pass

    # Gemini requirement: message history must never end on an assistant turn
    while cleaned and cleaned[-1].get("role") == "assistant":
        cleaned.pop()

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
        self.chat_persona = "jarvis"  # "jarvis" | "radon"
        self.silent_mode = False  # True for quiet chat-only (no audio output)

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
        # Skip TTS voice synthesis if silent mode is enabled
        if getattr(self, "silent_mode", False):
            return
        # Synthesize audio in parallel and stream neural voice playback
        try:
            audio_b64 = await get_or_synthesize_audio(text)
            if audio_b64:
                await self.send(type="say_audio", id=msg_id, audio=audio_b64)
        except Exception as e:
            print(f"TTS synthesis error: {e}")

    async def synthesize_and_stream_chunk(self, msg_id: str, chunk_index: int, text: str):
        if getattr(self, "silent_mode", False):
            return
        try:
            audio_b64 = await get_or_synthesize_audio(text)
            if audio_b64:
                await self.send(type="say_stream_audio", id=msg_id, chunk_index=chunk_index, audio=audio_b64)
        except Exception as e:
            print(f"Stream chunk TTS error: {e}")

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

        if name == "analyze_screen":
            query = args.get("query", "Describe what is currently visible on the screen.")
            res = await asyncio.to_thread(analyze_live_screen, query=query)
            if res.get("image_b64"):
                await self.send(type="screen", img="data:image/jpeg;base64," + res["image_b64"], label=f"OPTICAL ANALYSIS ({res.get('detected_count', 0)} TARGETS)")
            await self.send(type="log", text=f"Optical Multimodal Analysis completed in {res.get('latency_ms', 0)}ms.")
            return res.get("analysis", "Optical analysis complete.")

        if name == "click_and_type":
            label = args["text_label"].strip()
            txt = args["text"]
            pe = bool(args.get("press_enter", True))
            cf = bool(args.get("clear_field", False))
            res = await asyncio.to_thread(click_and_type_action, text_label=label, text_to_type=txt, press_enter=pe, clear_field=cf)
            if res.get("image_b64"):
                tag_label = f"TYPED: {res['element']['text']}" if res.get("success") else "OPTICAL SCAN"
                await self.send(type="screen", img="data:image/jpeg;base64," + res["image_b64"], label=tag_label)
            if res.get("success"):
                cx, cy = res["clicked_at"]
                await self.send(type="log", text=f"Optical Hands: Clicked '{res['element']['text']}' at ({cx}, {cy}) and typed '{txt}'.")
                return f"Focused '{res['element']['text']}' at screen position ({cx}, {cy}) and entered '{txt}', Sir."
            else:
                return f"Could not locate '{label}' to type text. Please check the label on screen."

        if name == "autonomous_navigate_screen":
            goal = args["goal"].strip()
            max_steps = min(int(args.get("max_steps", 4)), 6)
            history = []
            step_logs = []
            for step_idx in range(1, max_steps + 1):
                step_res = await asyncio.to_thread(autonomous_navigate_step, goal=goal, history=history)
                if step_res.get("image_b64"):
                    await self.send(type="screen", img="data:image/jpeg;base64," + step_res["image_b64"], label=f"STEP {step_idx}: {step_res.get('thought', '')[:30]}")
                history.append(step_res.get("decision", {}))
                action_name = step_res.get("action", "unknown")
                step_logs.append(f"Step {step_idx}: {step_res.get('thought', '')} -> {action_name}")
                if action_name == "done":
                    break
                await asyncio.sleep(0.5)
            return f"Autonomous screen navigation for '{goal}' executed {len(step_logs)} steps:\n" + "\n".join(step_logs)

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

        if name == "close_browser_tab":
            cnt = int(args.get("count", 1))
            res = await asyncio.to_thread(close_active_tab, cnt)
            await self.send(type="log", text=f"Closed {res.get('closed_tabs', 1)} active tab(s).")
            return f"Closed {res.get('closed_tabs', 1)} active tab(s), Sir."

        if name == "navigate_tab":
            target = args.get("url_or_query", "").strip()
            res = await asyncio.to_thread(navigate_current_tab, target)
            await self.send(type="log", text=f"Navigated active tab to: {res.get('navigated_to')}")
            return f"Active tab navigated to {res.get('navigated_to')}, Sir."

        if name == "reopen_tab":
            res = await asyncio.to_thread(reopen_closed_tab)
            await self.send(type="log", text="Reopened recently closed browser tab.")
            return "Reopened recently closed browser tab, Sir."

        if name == "play_music":
            srv = args.get("service", "youtube")
            q = args.get("query", "")
            act = args.get("action", "play")
            res = await asyncio.to_thread(hands_play_music, service=srv, query=q, action=act)
            if res.get("url"):
                await self.send(type="open_tab", url=res["url"])
            await self.send(type="log", text=f"Music Automation: {res.get('message')}")
            return res.get("message", f"Playing {q} on {srv}.")

        if name == "search_in_app":
            target = args.get("target", "spotify")
            q = args.get("query", "")
            enter = args.get("press_enter", True)
            res = await asyncio.to_thread(type_search_in_app, target, q, enter)
            await self.send(type="log", text=res.get("message", f"Typed '{q}' into {target}"))
            return res.get("message", f"Search completed in {target}.")

        if name == "book_tickets":
            cat = args.get("category", "flight")
            orig = args.get("origin", "")
            dest = args.get("destination", "")
            dt = args.get("date", "")
            prov = args.get("provider", "auto")
            pax = int(args.get("passengers", 1))
            ret_dt = args.get("return_date", "")
            notes = args.get("additional_notes", "")
            res = await asyncio.to_thread(
                book_tickets_portal,
                category=cat,
                origin=orig,
                destination=dest,
                date=dt,
                provider=prov,
                passengers=pax,
                return_date=ret_dt,
                additional_notes=notes
            )
            if res.get("url"):
                await self.send(type="open_tab", url=res["url"])
            await self.send(type="log", text=f"Ticket Portal: {res.get('provider')} ({orig} -> {dest})")
            return res.get("message")

        if name == "ide_code_control":
            act = args.get("action", "open_workspace")
            target = args.get("target", "vscode")
            p = args.get("path", "")
            content = args.get("content", "")
            cmd = args.get("terminal_command", "")
            
            if act == "open_workspace":
                res = await asyncio.to_thread(open_in_vscode, p)
                await self.send(type="log", text=res.get("message", f"Opened {p} in {target}"))
                return res.get("message", f"Opened in {target}.")
            elif act == "write_code_file":
                res = await asyncio.to_thread(write_code_file_and_open, p, content, True)
                await self.send(type="log", text=res.get("message", f"Wrote code to {p}"))
                return res.get("message", f"Wrote code to {p}.")
            elif act in ["run_terminal", "terminal"]:
                res = await asyncio.to_thread(send_keys_to_vscode, "terminal", cmd)
                await self.send(type="log", text=f"Executed terminal command in VS Code: {cmd}")
                return f"Dispatched '{cmd}' to VS Code terminal, Sir."
            elif act == "send_keys":
                k_act = args.get("key_action", "terminal")
                res = await asyncio.to_thread(send_keys_to_vscode, k_act, cmd)
                return f"Executed '{k_act}' in VS Code, Sir."
            return f"IDE control action '{act}' completed."

        if name == "prompt_antigravity":
            prompt = args.get("prompt", "")
            mode = args.get("mode", "auto")
            ret_hud = args.get("return_to_hud", True)
            
            if mode == "cli":
                res = await asyncio.to_thread(run_antigravity_cli_prompt, prompt)
                await self.send(type="log", text=f"Antigravity CLI: {res.get('message')}")
                return f"Antigravity CLI Result: {res.get('output', res.get('message'))}"
            else:
                from core.window_manager import dispatch_prompt_to_antigravity
                res = await asyncio.to_thread(dispatch_prompt_to_antigravity, prompt, ret_hud)
                await self.send(type="log", text=f"Antigravity Prompt Dispatch: {res}")
                return res

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

        if name == "toggle_silent_mode":
            enabled = bool(args.get("enabled", True))
            self.silent_mode = enabled
            await self.send(type="silent_mode_update", enabled=enabled)
            status_text = "engaged (quiet text-only chat, voice muted)" if enabled else "disengaged (voice synthesis active)"
            await self.send(type="log", text=f"🔇 Silent Mode {status_text}.")
            return f"Silent mode {status_text}, Sir."

        if name == "apply_workspace_layout":
            ly = args.get("layout", "coding")
            res = await asyncio.to_thread(apply_workspace_layout, ly)
            await self.send(type="log", text=f"🪟 Workspace Layout: {res.get('message')}")
            return res.get("message", f"Applied {ly} layout.")

        if name == "organize_files":
            tdir = args.get("target_dir", "downloads")
            ocr_opt = bool(args.get("ocr_rename_screenshots", True))
            res = await asyncio.to_thread(organize_directory, target_dir=tdir, ocr_rename_screenshots=ocr_opt)
            await self.send(type="log", text=f"📂 File Organizer: {res.get('message')}")
            return res.get("message", f"Organized {tdir}.")

        if name == "ship_git_update":
            c_msg = args.get("commit_message", "")
            br = args.get("branch")
            pr = bool(args.get("create_pr", False))
            res = await asyncio.to_thread(ship_git_update, commit_message=c_msg, branch=br, create_pr=pr)
            await self.send(type="log", text=f"🐙 Git DevOps: {res.get('message')}")
            return res.get("message", "Git update complete.")

        if name == "search_clipboard_history":
            act = args.get("action", "search")
            q = args.get("query", "")
            if act == "restore":
                iid = args.get("item_id")
                res = await asyncio.to_thread(restore_clipboard_item, item_id=iid, keyword=q)
                return res.get("message", "Clipboard restored.")
            else:
                items = await asyncio.to_thread(query_clipboard_cortex, q, 6)
                if not items:
                    return f"No matching snippets found for '{q}' in clipboard cortex."
                lines = [f"- [{i['timestamp'][11:16]} | {i['type'].upper()}]: {i['summary']}" for i in items]
                return f"Clipboard History Cortex for '{q}':\n" + "\n".join(lines)

        if name == "toggle_intruder_sentinel":
            act = args.get("action", "arm").lower()
            sentinel = get_intruder_sentinel()
            if act == "arm":
                res = sentinel.arm()
                await self.send(type="log", text="👁️ Optical Intruder Sentinel ARMED")
                return res["message"]
            elif act == "disarm":
                res = sentinel.disarm()
                await self.send(type="log", text="👁️ Optical Intruder Sentinel DISARMED")
                return res["message"]
            else:
                st = sentinel.get_status()
                return f"Intruder Sentinel: {'ARMED' if st['armed'] else 'DISARMED'}. Total breaches captured: {st['total_detections']}."

        if name == "generate_code_studio":
            desc = args.get("description", "")
            tfile = args.get("target_file", "")
            rtests = bool(args.get("run_tests", True))
            res = await generate_and_inject_code(desc, target_file=tfile, run_tests=rtests)
            await self.send(type="log", text=f"💻 Voice-to-Code: {res.get('message')}")
            return res.get("message", f"Generated code for {desc}.")

        if name == "track_product_price":
            act = args.get("action", "list")
            url = args.get("url", "")
            tp = args.get("target_price")
            if act == "add" and url:
                res = await asyncio.to_thread(add_tracked_product, url, tp)
                await self.send(type="log", text=f"🏷️ Price Tracker: {res.get('message')}")
                return res.get("message")
            elif act == "check_now":
                drops = await asyncio.to_thread(check_all_prices)
                if drops:
                    lines = [f"- **{d['title']}**: Dropped to {d['currency']} {d['new_price']}" for d in drops]
                    return "Price drops detected, Sir:\n" + "\n".join(lines)
                return "Price check complete. No new price drops detected."
            else:
                items = await asyncio.to_thread(list_tracked_products)
                if not items:
                    return "No products actively tracked yet. Provide an Amazon or Flipkart URL to begin."
                lines = [f"- **{i['title'][:35]}**: Current: {i['currency']} {i['current_price']} (Target: {i['target_price'] or 'None'})" for i in items]
                return "Actively Tracked Products:\n" + "\n".join(lines)

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

        if name == "toggle_instagram_dm_automation":
            dm_auto = get_dm_automator()
            act = (args.get("action") or "status").lower().strip()
            if act == "enable":
                interval = args.get("poll_interval")
                dm_auto.enable(poll_interval=interval)
                return (
                    "Instagram DM Automation ENGAGED, Sir. "
                    "Connecting to Instagram's real-time MQTT push stream — "
                    "replies will fire within seconds of receiving a message. "
                    "If MQTT is unavailable, fast polling (20 s) activates automatically."
                )
            elif act == "disable":
                dm_auto.disable()
                st = dm_auto.get_status()
                return (
                    f"Instagram DM Automation DISENGAGED, Sir. "
                    f"Your inbox will no longer be managed autonomously. "
                    f"Total replies dispatched this session: {st['total_replied']}."
                )
            else:  # status
                st = dm_auto.get_status()
                state = "ACTIVE" if st["enabled"] else "STANDBY"
                last_scan = st["last_scan"] or "No scan yet"
                recent = "\n".join(st["last_replies"]) if st["last_replies"] else "None"
                mode = st.get("mode", "unknown").upper()
                mqtt = "✅ CONNECTED" if st.get("mqtt_active") else "❌ Not active"
                return (
                    f"Instagram DM Automation: {state} ({mode} mode)\n"
                    f"MQTT Real-Time Stream: {mqtt}\n"
                    f"Last Activity: {last_scan}\n"
                    f"Total Replies Sent: {st['total_replied']}\n"
                    f"Recent Replies:\n{recent}"
                )

        if name == "set_chat_persona":
            target_persona = (args.get("persona") or "radon").lower().strip()
            if target_persona in ["radon", "me", "sir"]:
                self.chat_persona = "radon"
                set_persona_mode("radon")
                try:
                    get_voice_biometrics().set_active_profile("sir_clone")
                except Exception:
                    pass
                await self.send(type="log", text="🎭 Persona switched: RADON (@redonxd) — First-Person Human Mode")
                await self.send(type="chat_persona_update", persona="radon")
                return "Yo, Radon persona active. Talking as you from now on."
            else:
                self.chat_persona = "jarvis"
                set_persona_mode("jarvis")
                try:
                    get_voice_biometrics().set_active_profile("jarvis_prime")
                except Exception:
                    pass
                await self.send(type="log", text="🎭 Persona switched: J.A.R.V.I.S. — Standard British AI Protocol")
                await self.send(type="chat_persona_update", persona="jarvis")
                return "Standard J.A.R.V.I.S. persona re-engaged, Sir. Standing by."

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

        if name == "dispatch_multi_agent_swarm":
            goal = args.get("goal", "").strip()
            req_agents = args.get("agents")
            orch = get_swarm_orchestrator()
            async def on_swarm_event(evt):
                await self.send(**evt)
            res = await orch.execute_swarm_task(goal, req_agents, event_callback=on_swarm_event)
            return f"Swarm protocol completed. Task ID: {res['task_id']}, deployed agents: {', '.join(res['agents_deployed'])}, elapsed: {res['elapsed_ms']}ms."

        if name == "get_holographic_window_overlays":
            matrix = get_holographic_window_matrix()
            await self.send(type="ar_window_matrix", **matrix)
            return f"Projected {matrix['total_windows']} desktop application windows into the Holographic AR Matrix."

        if name == "ar_window_action":
            hwnd = int(args.get("hwnd", 0))
            action = args.get("action", "focus")
            res = ar_control_window(hwnd, action)
            matrix = get_holographic_window_matrix()
            await self.send(type="ar_window_matrix", **matrix)
            return f"AR window command '{action}' executed on HWND {hwnd}."

        if name == "predict_next_workflows":
            engine = get_predictive_engine()
            preds = engine.predict_workflows()
            await self.send(type="predictive_workflows", list=preds)
            titles = [f"{p['title']} ({int(p['confidence']*100)}%)" for p in preds[:3]]
            return f"Predictive Engine calculated top workflows: {', '.join(titles)}."

        if name == "execute_predicted_macro":
            wid = args.get("workflow_id", "dev_sprint")
            engine = get_predictive_engine()
            wf = engine.workflow_catalog.get(wid)
            if not wf:
                return f"Workflow macro '{wid}' not found."
            for act in wf["actions"]:
                try:
                    await self.run_tool(act["tool"], act["args"])
                except Exception as ex:
                    print(f"Workflow macro error on {act}: {ex}")
            return f"Predictive workflow macro '{wf['title']}' fully executed, Sir."

        if name == "get_biometric_telemetry":
            sensor = get_biometric_sensor()
            bio = sensor.get_latest_telemetry()
            await self.send(type="biometric_telemetry", metrics=bio)
            return f"Biometrics: State {bio['valence_state']}, Stress {bio['stress_index']}%, Focus {bio['cognitive_focus']}%, BPM {bio['bpm']}."

        if name == "p2p_mesh_action":
            mesh = get_quantum_p2p_mesh()
            act = args.get("action", "status")
            if act == "status":
                status = mesh.get_mesh_status()
                await self.send(type="p2p_mesh_status", **status)
                return f"Quantum P2P Mesh: {status['active_peers_count']} active peers, cipher {status['cipher_suite']}, entropy {status['quantum_entropy_level']}."
            elif act == "send":
                peer_id = args.get("peer_id", "NODE-MARK-VII-SATELLITE")
                msg = args.get("message", "Quantum ping from Stark Alpha Prime.")
                packet = mesh.encrypt_packet(peer_id, msg)
                await self.send(type="p2p_mesh_status", **mesh.get_mesh_status())
                return f"Quantum-encrypted packet dispatched to {peer_id}. Signature: {packet['quantum_signature']}."
            elif act == "pair":
                node_name = args.get("node_name", "Remote Satellite Node")
                paired = mesh.pair_new_node(node_name)
                await self.send(type="p2p_mesh_status", **mesh.get_mesh_status())
                return f"Enrolled node '{node_name}' (ID: {paired['enrolled_node_id']}) with fingerprint {paired['pqc_fingerprint']}."
            elif act == "generate_key":
                entropy_sig = mesh.generate_quantum_entropy_signature("KEY_ROTATION")
                return f"Rotated quantum entropy keys. Signature: {entropy_sig}."

        if name == "code_self_patch":
            patcher = get_code_self_patcher()
            act = args.get("action", "diagnose")
            if act == "diagnose":
                diag = patcher.run_code_diagnostics()
                await self.send(type="code_diagnostics", **diag)
                return f"Code Diagnostics: Health score {diag['health_score']}% ({diag['clean_modules']}/{diag['checked_modules']} clean). Total LOC: {diag['total_lines_of_code']} across {diag['total_functions_indexed']} functions."
            elif act == "inspect":
                rel_file = args.get("file", "server.py")
                res = patcher.inspect_file(rel_file, args.get("start_line", 1), args.get("end_line", 80))
                return f"File '{rel_file}' lines {res['start_line']}-{res['end_line']} (Total: {res['total_lines']}):\n{res['snippet']}"
            elif act in ["dry_run", "patch"]:
                is_dry = (act == "dry_run")
                rel_file = args.get("file", "server.py")
                target = args.get("target", "")
                replacement = args.get("replacement", "")
                reason = args.get("reason", "Autonomous performance enhancement")
                res = patcher.apply_patch(rel_file, target, replacement, reason, dry_run=is_dry)
                diag = patcher.run_code_diagnostics()
                await self.send(type="code_diagnostics", **diag)
                return f"Self-patch ({'DRY RUN' if is_dry else 'APPLIED'}): {res['message']}\nDiff summary:\n{res['diff'][:400]}"
            elif act == "rollback":
                res = patcher.rollback_latest_patch()
                diag = patcher.run_code_diagnostics()
                await self.send(type="code_diagnostics", **diag)
                return res["message"]
            elif act == "snapshots":
                snaps = patcher.list_snapshots()
                return f"Patch history contains {len(snaps)} rollback snapshots."

        if name == "voice_biometric_action":
            vb = get_voice_biometrics()
            act = args.get("action", "list_profiles")
            if act == "list_profiles":
                profs = vb.list_profiles()
                await self.send(type="voice_profiles_data", profiles=profs, active_id=vb.active_profile_id)
                active = vb.get_active_profile()
                return f"Available voice profiles: {', '.join([p['name'] for p in profs])}. Active: '{active['name']}'."
            elif act == "set_profile":
                pid = args.get("profile_id", "jarvis_prime")
                res = vb.set_active_profile(pid)
                clear_audio_cache()
                await self.send(type="voice_profiles_data", profiles=vb.list_profiles(), active_id=vb.active_profile_id)
                return f"Vocal biometric synthesis switched to '{res['name']}'. Model: {res['neural_voice']} (Pitch: {res['pitch']}, Rate: {res['rate']})."
            elif act == "tune_parameters":
                pid = args.get("profile_id", vb.active_profile_id)
                res = vb.update_profile_parameters(pid, pitch=args.get("pitch"), rate=args.get("rate"), volume=args.get("volume"))
                clear_audio_cache()
                return f"Vocal parameters updated for '{pid}': {res['updated']}."
            elif act == "audition":
                pid = args.get("profile_id", vb.active_profile_id)
                clip = await vb.synthesize_audition_clip(pid)
                await self.send(type="voice_audition_clip", profile_id=pid, audio=clip["audio_base64"], phrase=clip["phrase"])
                return f"Audition clip synthesized for profile '{clip['profile_name']}'."
            elif act == "get_active":
                active = vb.get_active_profile()
                return f"Active vocal profile: '{active['name']}' ({active['neural_voice']}, pitch={active['pitch']}, rate={active['rate']})."

        if name == "toggle_focus_mode":
            guardian = get_focus_guardian()
            enabled = bool(args.get("enabled", True))
            if enabled:
                obj = args.get("objective", "Study & Deep Work")
                dur = args.get("duration_minutes", 30)
                status = guardian.activate(objective=obj, duration_minutes=dur)
                await self.send(type="focus_mode_status", **status)
                return f"Focus Mode activated for '{obj}' ({status['remaining_formatted']} remaining). All gaming platforms and entertainment launchers will be actively deflected."
            else:
                status = guardian.deactivate()
                await self.send(type="focus_mode_status", **status)
                return "Focus Mode disengaged, Sir. Workstation entertainment and gaming access restored."

        if name == "get_focus_mode_status":
            guardian = get_focus_guardian()
            status = guardian.get_status()
            await self.send(type="focus_mode_status", **status)
            return f"Focus Mode status: {'ACTIVE' if status['is_active'] else 'STANDBY'}, objective '{status['objective']}', {status['remaining_formatted']} remaining, {status['blocked_attempts']} distractions deflected."

        if name == "analyze_facial_mood":
            img_b64 = args.get("frame_base64") or self.last_camera_frame
            analyzer = get_mood_analyzer()
            if img_b64:
                img_bytes = base64.b64decode(img_b64)
            else:
                # Capture current desktop or fallback neutral frame
                from PIL import Image
                import io
                buf = io.BytesIO()
                Image.new("RGB", (320, 240), color=(45, 52, 64)).save(buf, format="JPEG")
                img_bytes = buf.getvalue()

            res = await analyzer.analyze_face_frame(img_bytes, interaction_context="Sir requested facial mood analysis")
            await self.send(type="face_mood_telemetry", **res)

            # If distress detected and vigil not yet active, trigger proactive check-in automatically!
            if res.get("proactive_trigger") and not get_mood_vigil().is_active:
                vigil = get_mood_vigil()
                st = vigil.start_vigil(
                    mood=res.get("mood", "sad"),
                    mood_label=res.get("mood_label", "MELANCHOLIC"),
                    initial_phrase=res.get("initial_check_in"),
                    facial_cues=res.get("facial_cues")
                )
                await self.send(type="mood_vigil_status", **st)
                await self.send(type="camera_stream", action="start")

            cues_str = ", ".join(res.get("facial_cues", [])) or "Nominal expression"
            return (
                f"Facial Biometric Analysis: Mood '{res.get('mood_label', 'CALM')}', "
                f"Valence {res.get('valence', 0.0)}, Arousal {res.get('arousal', 0.0)}. "
                f"Observed cues: {cues_str}. Comfort needed: {res.get('needs_comfort', False)}."
            )

        if name == "start_mood_call":
            vigil = get_mood_vigil()
            mood = args.get("mood_override", "sad")
            obj = args.get("objective", "Proactive Empathic Video Call")
            await self.send(type="camera_stream", action="start")
            st = vigil.start_vigil(mood=mood)
            await self.send(type="mood_vigil_status", **st)
            asyncio.create_task(self.send_vocal_response(vigil.last_ping_text))
            await self.send(type="say_text", text=vigil.last_ping_text)
            return f"Proactive mood video call engaged, Sir. Optical viewport active and check-in initiated: \"{vigil.last_ping_text}\""

        if name == "stop_mood_call":
            vigil = get_mood_vigil()
            st = vigil.stop_vigil()
            await self.send(type="mood_vigil_status", **st)
            return "Proactive mood video call concluded, Sir. Standing by on workstation feed."

        if name == "trigger_comfort_protocol":
            act = args.get("action", "acoustic_relax")
            notes = args.get("comfort_notes", "I am right here with you, Sir.")
            vigil = get_mood_vigil()
            vigil.comfort_mode = act
            await self.send(type="comfort_protocol_event", action=act, notes=notes)
            await self.send(type="mood_vigil_status", **vigil.get_status())
            if act == "acoustic_relax":
                await self.send(type="log", text="Comfort Protocol: Calming acoustic resonance matrix initialized.")
                return f"Comfort protocol 'acoustic_relax' activated for Sir: {notes}"
            elif act == "tea_break":
                return f"Comfort protocol 'tea_break' activated: Rest reminder and warm hydration protocol dispatched to Sir."
            elif act == "dim_lighting":
                return f"Comfort protocol 'dim_lighting' activated: HUD optical glare softened for Sir."
            return f"Comfort protocol 'empathic_venting' engaged: J.A.R.V.I.S. attentive and ready to listen."

        if name == "configure_hud_theme":
            mgr = get_hud_theme_manager()
            tid = args.get("theme_id", "executive_minimal")
            density = args.get("density_mode")
            theme_data = mgr.set_theme(tid, density)
            await self.send(type="hud_theme_update", **theme_data)
            return f"HUD theme set to '{theme_data['name']}' ({theme_data['active_id']}). Aesthetics synchronized."

        if name == "get_hud_theme":
            theme_data = get_hud_theme_manager().get_active_theme()
            await self.send(type="hud_theme_update", **theme_data)
            return f"Active HUD theme: '{theme_data['name']}', density mode '{theme_data['density_mode']}'."

        return "Unknown command requested."

    async def turn(self, user_text: str):
        try:
            save_chat_message("user", user_text)
        except Exception as e:
            print(f"Chat persistence error: {e}")
        self.history.append({"role": "user", "content": user_text})

        # Update neural biometric mood sensor with user text
        try:
            bio_sensor = get_biometric_sensor()
            current_bio = bio_sensor.analyze_interaction(user_text)
            await self.send(type="biometric_telemetry", metrics=current_bio)
        except Exception as e:
            print(f"Biometrics tracking notice: {e}")

        # Check active mood vigil response
        try:
            vigil = get_mood_vigil()
            if vigil.is_active and vigil.awaiting_reply:
                vigil.record_user_reply(user_text)
                await self.send(type="mood_vigil_status", **vigil.get_status())
        except Exception as e:
            print(f"Mood vigil response notice: {e}")

        # ⚡ 0ms Fast-Path Execution Bypass for routine deterministic commands
        fast_action = extract_action_intent(user_text)
        if fast_action:
            fn_name, fn_args = fast_action
            if is_deterministic_fast_path(fn_name, fn_args):
                await self.send(type="log", text=f"⚡ 0ms Fast-Path Execution: {fn_name}({json.dumps(fn_args)})")
                ack_phrase = get_fast_ack_phrase(fn_name, fn_args)
                asyncio.create_task(self.send_vocal_response(ack_phrase))
                try:
                    res = await self.run_tool(fn_name, fn_args)
                    await self.send(type="log", text=f"Fast-path completed: {res}")
                except Exception as ex:
                    print(f"Fast path error: {ex}")
                return

        tools_executed = 0
        try:
            for _ in range(15):
                await self.send(type="state", s="thinking")
                msgs = [{"role": "system", "content": system_prompt(query=user_text, persona=self.chat_persona)}] + prune_history(self.history)
                
                choice = None
                engine_name = "Gemini Cloud"
                is_streamed = False

                if not self.manual_offline_mode:
                    try:
                        clean_msgs = sanitize_messages_for_cloud(msgs)
                        stream = await client.chat.completions.create(model=MODEL, messages=clean_msgs, tools=TOOLS, stream=True)
                        if self.in_failover:
                            self.in_failover = False
                            await self.send(type="core_mode", mode="cloud", label="NEURAL CORE // CLOUD (GEMINI)")
                            await self.send(type="log", text="⚡ Cloud Neural Link restored. All systems nominal.")
                        
                        msg_id = str(time.time())
                        full_content = ""
                        sentence_buffer = ""
                        chunk_idx = 0
                        tool_calls_dict = {}

                        async for chunk in stream:
                            if not chunk.choices:
                                continue
                            delta = chunk.choices[0].delta
                            
                            if delta.content:
                                full_content += delta.content
                                sentence_buffer += delta.content
                                
                                sentences = re.split(r'(?<=[.!?\n])\s+', sentence_buffer)
                                if len(sentences) > 1:
                                    for s in sentences[:-1]:
                                        s_clean = s.strip()
                                        if s_clean:
                                            await self.send(type="say_stream_text", id=msg_id, chunk_index=chunk_idx, text=s_clean)
                                            asyncio.create_task(self.synthesize_and_stream_chunk(msg_id, chunk_idx, s_clean))
                                            chunk_idx += 1
                                    sentence_buffer = sentences[-1]

                            if delta.tool_calls:
                                for tc in delta.tool_calls:
                                    key = tc.id or (f"idx_{tc.index}" if tc.index is not None else f"call_{len(tool_calls_dict)}")
                                    if key not in tool_calls_dict:
                                        tool_calls_dict[key] = {
                                            "id": tc.id or f"call_{time.time()}_{len(tool_calls_dict)}",
                                            "function": {"name": "", "arguments": ""},
                                            "type": "function"
                                        }
                                    if tc.id:
                                        tool_calls_dict[key]["id"] = tc.id
                                    if tc.function:
                                        if tc.function.name:
                                            tool_calls_dict[key]["function"]["name"] += tc.function.name
                                        if tc.function.arguments:
                                            tool_calls_dict[key]["function"]["arguments"] += tc.function.arguments

                                    extra = getattr(tc, 'extra_content', None) or (
                                        tc.model_extra.get('extra_content') if hasattr(tc, 'model_extra') and tc.model_extra else None
                                    )
                                    if extra:
                                        tool_calls_dict[key]["extra_content"] = extra

                        if sentence_buffer.strip():
                            s_clean = sentence_buffer.strip()
                            await self.send(type="say_stream_text", id=msg_id, chunk_index=chunk_idx, text=s_clean)
                            asyncio.create_task(self.synthesize_and_stream_chunk(msg_id, chunk_idx, s_clean))
                            chunk_idx += 1

                        if chunk_idx > 0:
                            await self.send(type="say_stream_end", id=msg_id, total_chunks=chunk_idx)
                            try:
                                save_chat_message("jarvis", full_content)
                            except Exception as e:
                                print(f"Chat persistence error: {e}")

                        tool_calls_list = list(tool_calls_dict.values()) if tool_calls_dict else None
                        
                        class StreamChoice:
                            def __init__(self, content, tool_calls):
                                self.content = content
                                self.tool_calls = tool_calls
                            def model_dump(self, exclude_none=True):
                                d = {"role": "assistant"}
                                if self.content is not None:
                                    d["content"] = self.content
                                if self.tool_calls:
                                    d["tool_calls"] = self.tool_calls
                                return d

                        choice = StreamChoice(full_content or None, tool_calls_list)
                        is_streamed = True
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

                # Vocal dispatch for non-streamed choices
                if not is_streamed and choice.content and choice.content.strip():
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

                    # Automatic execution fallback guarantee
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
                for call in (choice.tool_calls or []):
                    fn_name = call["function"]["name"] if isinstance(call, dict) else call.function.name
                    fn_args_raw = call["function"]["arguments"] if isinstance(call, dict) else (call.function.arguments or "{}")
                    call_id = call["id"] if isinstance(call, dict) else call.id
                    try:
                        args = json.loads(fn_args_raw or "{}")
                    except Exception:
                        try:
                            decoder = json.JSONDecoder()
                            args, _ = decoder.raw_decode((fn_args_raw or "").strip())
                        except Exception:
                            args = {}
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
                        "tool_call_id": call_id,
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
    return FileResponse(FRONTEND_INDEX)

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
                # Live Neural Biometrics, Predictive Workflows, and AR Window Matrix telemetry
                try:
                    await session.send(type="biometric_telemetry", metrics=get_biometric_sensor().get_latest_telemetry())
                    await session.send(type="predictive_workflows", list=get_predictive_engine().predict_workflows())
                    await session.send(type="ar_window_matrix", **get_holographic_window_matrix())
                    
                    guardian = get_focus_guardian()
                    if guardian.is_active:
                        blocked = guardian.check_and_enforce()
                        if blocked:
                            for blk in blocked:
                                app_name = blk.get("title") or blk.get("name") or "Gaming Application"
                                await session.send_vocal_response(f"Focus mode is currently active for your {guardian.objective}, Sir. I have closed {app_name}. Stay on target.")
                    await session.send(type="focus_mode_status", **guardian.get_status())

                    # Check proactive mood video call follow-up insistence timer
                    vigil = get_mood_vigil()
                    if vigil.is_active:
                        follow_up = vigil.check_follow_up_timer()
                        if follow_up:
                            ping_num = follow_up.get("ping_number", 2)
                            await session.send(type="say_text", text=follow_up["text"])
                            asyncio.create_task(session.send_vocal_response(follow_up["speech"]))
                            await session.send(type="log", text=f"💬 Proactive Video Call Follow-up (Ping {ping_num}): {follow_up['text']}")
                    await session.send(type="mood_vigil_status", **vigil.get_status())
                except Exception:
                    pass
                await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    telemetry_task = asyncio.create_task(telemetry_stream())
    await session.send(type="memories", list=list_cortex_memories())
    await session.send(type="swarm_manifest", manifest=AGENTS_MANIFEST)
    await session.send(type="predictive_workflows", list=get_predictive_engine().predict_workflows())
    await session.send(type="biometric_telemetry", metrics=get_biometric_sensor().get_latest_telemetry())
    await session.send(type="ar_window_matrix", **get_holographic_window_matrix())
    await session.send(type="p2p_mesh_status", **get_quantum_p2p_mesh().get_mesh_status())
    await session.send(type="code_diagnostics", **get_code_self_patcher().run_code_diagnostics())
    vb = get_voice_biometrics()
    await session.send(type="voice_profiles_data", profiles=vb.list_profiles(), active_id=vb.active_profile_id)
    await session.send(type="focus_mode_status", **get_focus_guardian().get_status())
    await session.send(type="mood_vigil_status", **get_mood_vigil().get_status())
    await session.send(type="hud_theme_update", **get_hud_theme_manager().get_active_theme())
    
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

            elif msg_type == "toggle_instagram_dm_automation":
                dm_auto = get_dm_automator()
                action = data.get("action", "enable")
                interval = data.get("poll_interval")
                if action == "enable":
                    dm_auto.enable(interval=interval)
                    st = dm_auto.get_status()
                    await session.send(type="log", text=f"📲 Instagram DM Automation ENGAGED — scanning every {st['poll_interval_seconds']}s, Sir.")
                elif action == "disable":
                    dm_auto.disable()
                    st = dm_auto.get_status()
                    await session.send(type="log", text=f"📲 Instagram DM Automation DISENGAGED. Total replies this session: {st['total_replied']}.")
                else:
                    st = dm_auto.get_status()
                    state = "ACTIVE" if st["enabled"] else "STANDBY"
                    await session.send(type="log", text=f"📲 Instagram DM Automation: {state} | Last scan: {st['last_scan'] or 'N/A'} | Replies: {st['total_replied']}")

            elif msg_type == "set_chat_persona":
                p = (data.get("persona") or "radon").lower().strip()
                if p in ["radon", "me", "sir"]:
                    session.chat_persona = "radon"
                    set_persona_mode("radon")
                    try:
                        get_voice_biometrics().set_active_profile("sir_clone")
                    except Exception:
                        pass
                    await session.send(type="chat_persona_update", persona="radon")
                    await session.send(type="log", text="🎭 Persona switched: RADON (@redonxd) — First-Person Impersonation")
                else:
                    session.chat_persona = "jarvis"
                    set_persona_mode("jarvis")
                    try:
                        get_voice_biometrics().set_active_profile("jarvis_prime")
                    except Exception:
                        pass
                    await session.send(type="chat_persona_update", persona="jarvis")
                    await session.send(type="log", text="🎭 Persona switched: J.A.R.V.I.S. — Standard British AI Protocol")

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

            elif msg_type == "get_ar_windows":
                await session.send(type="ar_window_matrix", **get_holographic_window_matrix())

            elif msg_type == "ar_window_action":
                hwnd = int(data.get("hwnd", 0))
                act = data.get("action", "focus")
                ar_control_window(hwnd, act)
                await session.send(type="ar_window_matrix", **get_holographic_window_matrix())

            elif msg_type == "get_predictive_workflows":
                await session.send(type="predictive_workflows", list=get_predictive_engine().predict_workflows())

            elif msg_type == "execute_predicted_workflow":
                wid = data.get("id") or data.get("workflow_id")
                session.current_task = asyncio.create_task(session.run_tool("execute_predicted_macro", {"workflow_id": wid}))

            elif msg_type == "dispatch_swarm":
                goal = data.get("goal")
                session.current_task = asyncio.create_task(session.run_tool("dispatch_multi_agent_swarm", {"goal": goal}))

            elif msg_type == "get_biometrics":
                await session.send(type="biometric_telemetry", metrics=get_biometric_sensor().get_latest_telemetry())

            elif msg_type == "get_p2p_mesh":
                await session.send(type="p2p_mesh_status", **get_quantum_p2p_mesh().get_mesh_status())

            elif msg_type == "send_p2p_packet":
                peer_id = data.get("peer_id", "NODE-MARK-VII-SATELLITE")
                msg_text = data.get("message", "Quantum ping from Stark Alpha Prime.")
                get_quantum_p2p_mesh().encrypt_packet(peer_id, msg_text)
                await session.send(type="p2p_mesh_status", **get_quantum_p2p_mesh().get_mesh_status())

            elif msg_type == "pair_p2p_node":
                node_name = data.get("node_name", "Remote Mesh Node")
                get_quantum_p2p_mesh().pair_new_node(node_name)
                await session.send(type="p2p_mesh_status", **get_quantum_p2p_mesh().get_mesh_status())

            elif msg_type == "get_code_diagnostics":
                await session.send(type="code_diagnostics", **get_code_self_patcher().run_code_diagnostics())

            elif msg_type == "rollback_code_patch":
                res = get_code_self_patcher().rollback_latest_patch()
                await session.send(type="log", text=res["message"])
                await session.send(type="code_diagnostics", **get_code_self_patcher().run_code_diagnostics())

            elif msg_type == "get_voice_profiles":
                vb = get_voice_biometrics()
                await session.send(type="voice_profiles_data", profiles=vb.list_profiles(), active_id=vb.active_profile_id)

            elif msg_type == "set_voice_profile":
                pid = data.get("profile_id", "jarvis_prime")
                vb = get_voice_biometrics()
                res = vb.set_active_profile(pid)
                clear_audio_cache()
                await session.send(type="voice_profiles_data", profiles=vb.list_profiles(), active_id=vb.active_profile_id)
                await session.send(type="log", text=f"🎙️ Vocal Biometric Persona: {res['name']}")

            elif msg_type == "audition_voice_profile":
                pid = data.get("profile_id", "jarvis_prime")
                vb = get_voice_biometrics()
                clip = await vb.synthesize_audition_clip(pid)
                await session.send(type="voice_audition_clip", profile_id=pid, audio=clip["audio_base64"], phrase=clip["phrase"])

            elif msg_type == "toggle_focus_mode":
                guardian = get_focus_guardian()
                enabled = bool(data.get("enabled", True))
                if enabled:
                    obj = data.get("objective", "Study & Deep Work")
                    dur = data.get("duration_minutes", 30)
                    st = guardian.activate(objective=obj, duration_minutes=dur)
                    await session.send_vocal_response(f"Focus mode engaged for {obj}, Sir. All gaming software is now blocked.")
                else:
                    st = guardian.deactivate()
                    await session.send_vocal_response("Focus mode disengaged, Sir. Entertainment access restored.")
                await session.send(type="focus_mode_status", **st)

            elif msg_type == "get_focus_mode":
                await session.send(type="focus_mode_status", **get_focus_guardian().get_status())

            elif msg_type == "start_mood_call":
                vigil = get_mood_vigil()
                mood = data.get("mood", "sad")
                phrase = data.get("phrase")
                await session.send(type="camera_stream", action="start")
                st = vigil.start_vigil(mood=mood, initial_phrase=phrase)
                await session.send(type="say_text", text=vigil.last_ping_text)
                asyncio.create_task(session.send_vocal_response(vigil.last_ping_text))
                await session.send(type="mood_vigil_status", **st)

            elif msg_type == "stop_mood_call":
                vigil = get_mood_vigil()
                st = vigil.stop_vigil()
                asyncio.create_task(session.send_vocal_response("Mood vigil disengaged, Sir. Standing by on workstation feed."))
                await session.send(type="mood_vigil_status", **st)

            elif msg_type == "analyze_mood_frame":
                img_b64 = data.get("image")
                if img_b64:
                    session.last_camera_frame = img_b64
                    try:
                        img_bytes = base64.b64decode(img_b64)
                        analyzer = get_mood_analyzer()
                        res = await analyzer.analyze_face_frame(img_bytes, interaction_context="Client optical video stream")
                        await session.send(type="face_mood_telemetry", **res)
                        
                        # Auto-trigger proactive check-in if distress detected and vigil not already active
                        if res.get("proactive_trigger") and not get_mood_vigil().is_active:
                            vigil = get_mood_vigil()
                            st = vigil.start_vigil(
                                mood=res.get("mood", "sad"),
                                mood_label=res.get("mood_label", "MELANCHOLIC"),
                                initial_phrase=res.get("initial_check_in"),
                                facial_cues=res.get("facial_cues")
                            )
                            await session.send(type="say_text", text=vigil.last_ping_text)
                            asyncio.create_task(session.send_vocal_response(vigil.last_ping_text))
                            await session.send(type="mood_vigil_status", **st)
                    except Exception as err:
                        print(f"Frame analysis error: {err}")

            elif msg_type == "get_mood_status":
                await session.send(type="mood_vigil_status", **get_mood_vigil().get_status())

            elif msg_type == "get_hud_theme":
                await session.send(type="hud_theme_update", **get_hud_theme_manager().get_active_theme())

            elif msg_type == "set_hud_theme":
                theme_data = get_hud_theme_manager().set_theme(data.get("theme_id"), data.get("density_mode"))
                await session.send(type="hud_theme_update", **theme_data)

            elif msg_type == "cycle_hud_theme":
                theme_data = get_hud_theme_manager().cycle_next_theme()
                await session.send(type="hud_theme_update", **theme_data)

            elif msg_type == "set_silent_mode":
                session.silent_mode = bool(data.get("enabled", False))
                status = "ENGAGED (Text-Only / Audio Muted)" if session.silent_mode else "DISENGAGED (Voice Active)"
                await session.send(type="silent_mode_update", enabled=session.silent_mode)
                await session.send(type="log", text=f"🔇 Silent Mode {status}, Sir.")

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
    print("=" * 65, flush=True)
    print(f"[*] 🚀 J.A.R.V.I.S. HUD is live!", flush=True)
    print(f"[*] 👉 Open in your browser: http://localhost:{PORT} or http://127.0.0.1:{PORT}", flush=True)
    print(f"[*] (Note: Windows browsers cannot open 0.0.0.0; use localhost:{PORT})", flush=True)
    print("=" * 65, flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
