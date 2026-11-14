"""J.A.R.V.I.S. Evolution Engine: Generates specialized prompts and commands for Google Antigravity.
Enables J.A.R.V.I.S. to autonomously formulate architectural upgrade directives for the Antigravity agent.
"""

ANTIGRAVITY_BLUEPRINTS = {
    "wake_word": {
        "title": "Hands-Free Voice Wake-Word Engine ('Hey Jarvis')",
        "command": "/boost",
        "prompt": (
            "/boost Implement continuous, zero-click voice wake-word detection for J.A.R.V.I.S. "
            "so Sir can speak 'Hey Jarvis' or 'Jarvis' hands-free without clicking or holding the Spacebar.\n\n"
            "Requirements:\n"
            "1. In static/index.html, implement Web Speech API continuous recognition or integrate openWakeWord / Picovoice Porcupine in Python.\n"
            "2. When the wake phrase 'Hey Jarvis' or 'Jarvis' is acoustic-detected, automatically activate recording state with audio chime.\n"
            "3. Stream audio command directly to server.py WebSocket without requiring keyboard hold.\n"
            "4. Provide a toggle in the UI: 'Continuous Wake-Word Listener [ON/OFF]'.\n"
            "5. Verify latency is under 300ms on Windows host Radon."
        )
    },
    "vision_ai": {
        "title": "Computer Vision & Autonomous GUI Interaction Engine",
        "command": "/plan",
        "prompt": (
            "/plan Enhance J.A.R.V.I.S.'s visual automation capabilities in server.py.\n\n"
            "Objectives:\n"
            "1. Implement core/vision.py with high-speed local OCR (e.g. RapidOCR or EasyOCR) to read all text, buttons, and UI element coordinates from the live screenshot.\n"
            "2. Add tool 'click_element(text_label, button='left')' that automatically finds the bounding box of any on-screen button or link by label (e.g. 'click Submit', 'click Compose') and executes the click.\n"
            "3. Update 'look' tool to display detected interactive bounding boxes directly in the HUD Optical Sensory Viewport.\n"
            "4. Ensure sub-second execution on Windows 11."
        )
    },
    "holographic_3d": {
        "title": "Three.js 3D Holographic Arc Reactor & Audio Reactive HUD",
        "command": "/boost",
        "prompt": (
            "/boost Upgrade the Stark HUD Neural Core in static/index.html to an interactive 3D WebGL / Three.js holographic Arc Reactor Mark VII.\n\n"
            "Objectives:\n"
            "1. Embed Three.js inside #arc to render a full 3D Arc Reactor with rotating metallic rings, central glowing core, and floating cyan particle fields.\n"
            "2. Connect live Web Audio API AnalyserNode to deform the 3D particles and pulsate the core synchronously with J.A.R.V.I.S.'s neural voice.\n"
            "3. Add mouse-parallax holographic tilt so moving the cursor rotates the 3D reactor dynamically.\n"
            "4. Keep bundle lightweight and zero-dependency via CDN."
        )
    },
    "proactive": {
        "title": "Proactive Autonomous Sentinel & Scheduled Briefings",
        "command": "/schedule",
        "prompt": (
            "/schedule Add an autonomous proactive sentinel daemon to J.A.R.V.I.S. (server.py & core/proactive.py).\n\n"
            "Capabilities:\n"
            "1. Morning Executive Briefing: Every weekday at 9:00 AM, synthesize a vocal briefing with weather, unread VIP emails from Gmail, and schedule highlights.\n"
            "2. Hardware Sentinel: Continuously monitor battery level (alert when unplugged < 20%) and CPU temperature.\n"
            "3. Media Observer: Announce newly playing Spotify/YouTube tracks when media changes.\n"
            "4. Deliver proactive alerts both audibly through edge-tts and visibly in the HUD log."
        )
    },
    "local_llm": {
        "title": "Local Offline LLM Failover (Ollama / Llama-3)",
        "command": "/boost",
        "prompt": (
            "/boost Implement zero-downtime local LLM failover for J.A.R.V.I.S. in server.py.\n\n"
            "Architecture:\n"
            "1. In core/local_llm.py, connect to local Ollama instance (http://localhost:11434) with model 'llama3.2:latest' or 'phi3'.\n"
            "2. In server.py, wrap Gemini API calls with automatic failover: if internet is down, Gemini quota is exceeded (429/503), or offline mode is toggled, route seamlessly to Ollama.\n"
            "3. Support the same tool schema (open_app, set_volume, media_control, look, etc.) via Ollama tool-calling.\n"
            "4. Display 'NEURAL CORE // OFFLINE LOCAL MODE' on the HUD status badge."
        )
    },
    "memory_vector": {
        "title": "Semantic Vector Memory Cortex (ChromaDB / SQLite-VSS)",
        "command": "/boost",
        "prompt": (
            "/boost Upgrade J.A.R.V.I.S.'s memory architecture from memory.json to an embedding-powered vector memory cortex.\n\n"
            "Objectives:\n"
            "1. Create core/memory_vector.py using chromadb or sqlite-vss with lightweight local embeddings (all-MiniLM-L6-v2).\n"
            "2. Automatically vectorize conversational context, Sir's declared preferences, project notes, and frequently executed workflows.\n"
            "3. Perform semantic similarity search on every turn to inject relevant past memories into the system prompt.\n"
            "4. Add UI visualization in the slide-out Memory Drawer with confidence scores and timestamps."
        )
    }
}

def generate_directive(category: str = "all", custom_feature: str = "") -> dict:
    """Generate Antigravity prompt directives."""
    cat = category.lower().strip()
    cust = custom_feature.strip()
    
    # If explicitly custom or requesting a specific custom feature
    if cat == "custom" or (cust and cat not in ["all", ""]):
        prompt = (
            f"/boost Implement '{cust}' for the J.A.R.V.I.S. workstation assistant.\n\n"
            f"Codebase Context:\n"
            f"- Backend: server.py (FastAPI, WebSockets, Windows API, pywin32, pyautogui, Gemini 3.5 Flash-Lite)\n"
            f"- Integrations: core/intel.py (Bing/Wikipedia Optical Viewport), core/gmail.py (Gmail CLI), core/whatsapp.py\n"
            f"- Frontend HUD: static/index.html (Vanilla JS, Cyberpunk Mark VII Stark HUD)\n\n"
            f"Step-by-step Implementation Plan:\n"
            f"1. Design and author required modules in core/.\n"
            f"2. Expose the functionality as an autonomous tool in server.py TOOLS array and run_tool handler.\n"
            f"3. Update static/index.html with real-time HUD telemetry, widgets, and audio feedback.\n"
            f"4. Verify the feature live and test edge cases."
        )
        return {
            "title": f"Custom Feature Directive: {cust}",
            "command": "/boost",
            "prompt": prompt,
            "category": "custom"
        }
        
    if cat in ANTIGRAVITY_BLUEPRINTS and cat != "all":
        bp = ANTIGRAVITY_BLUEPRINTS[cat]
        return {
            "title": bp["title"],
            "command": bp["command"],
            "prompt": bp["prompt"],
            "category": cat
        }
        
    # Default: Return all 6 comprehensive architectural blueprints
    return {
        "title": "Stark Industries Comprehensive Evolution Directives",
        "blueprints": ANTIGRAVITY_BLUEPRINTS,
        "category": "all"
    }
