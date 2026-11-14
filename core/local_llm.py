"""J.A.R.V.I.S. Local LLM Failover & Offline Execution Engine.
Connects to local Ollama instances (http://localhost:11434) with tool-calling support (llama3.2 / phi3)
and provides an emergency deterministic failsafe for zero-downtime operations.
"""

import asyncio
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Any
import urllib.request
import urllib.error

from openai import AsyncOpenAI

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
FALLBACK_CANDIDATE_MODELS = [
    "llama3.2:latest",
    "llama3.2",
    "llama3.1:latest",
    "llama3.1",
    "phi3:latest",
    "phi3",
    "mistral:latest",
    "mistral",
    "qwen2.5:latest"
]

# Cached Ollama status
_cached_availability: Optional[bool] = None
_last_health_check: float = 0.0

def get_ollama_client(base_url: Optional[str] = None) -> AsyncOpenAI:
    """Return an AsyncOpenAI client configured for Ollama's v1 endpoint."""
    host = (base_url or OLLAMA_HOST).rstrip("/")
    return AsyncOpenAI(
        base_url=f"{host}/v1",
        api_key="ollama",
        max_retries=1,
        timeout=12.0
    )

async def check_ollama_alive(timeout: float = 1.0) -> bool:
    """Quick asynchronous ping to determine if the local Ollama daemon is active."""
    global _cached_availability, _last_health_check
    now = asyncio.get_running_loop().time()
    if _cached_availability is not None and (now - _last_health_check) < 8.0:
        return _cached_availability

    def _sync_ping():
        try:
            req = urllib.request.Request(f"{OLLAMA_HOST.rstrip('/')}/api/tags", headers={"User-Agent": "jarvis-sentinel"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    alive = await asyncio.to_thread(_sync_ping)
    _cached_availability = alive
    _last_health_check = now
    return alive

async def get_available_ollama_models() -> List[str]:
    """Retrieve list of locally installed models from Ollama."""
    def _fetch_tags():
        try:
            req = urllib.request.Request(f"{OLLAMA_HOST.rstrip('/')}/api/tags", headers={"User-Agent": "jarvis-sentinel"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                return [m for m in models if m]
        except Exception:
            return []

    return await asyncio.to_thread(_fetch_tags)

async def resolve_local_model() -> str:
    """Determine best available local model or fallback to configured default."""
    installed = await get_available_ollama_models()
    if not installed:
        return OLLAMA_MODEL

    if OLLAMA_MODEL in installed:
        return OLLAMA_MODEL

    for cand in FALLBACK_CANDIDATE_MODELS:
        if cand in installed:
            return cand
        base = cand.split(":")[0]
        for m in installed:
            if m.startswith(base):
                return m

    return installed[0]

class SyntheticToolCall:
    def __init__(self, name: str, args: dict):
        self.id = f"local_call_{os.urandom(4).hex()}"
        self.function = type("Function", (), {
            "name": name,
            "arguments": json.dumps(args)
        })()

class SyntheticAssistantMessage:
    def __init__(self, content: str, tool_calls: Optional[List[Any]] = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.role = "assistant"

    def model_dump(self, exclude_none: bool = True):
        d = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in self.tool_calls
            ]
        return d

def _emergency_heuristic(messages: List[Dict[str, Any]]) -> Tuple[SyntheticAssistantMessage, str]:
    """Deterministic fallback engine when both cloud and local neural weights are unreachable."""
    # Check if a tool was just executed in the preceding turn step
    if messages and messages[-1].get("role") == "tool":
        tool_out = messages[-1].get("content", "Action confirmed.")
        return SyntheticAssistantMessage(
            f"Protocol completed successfully: {tool_out} Standing by, Sir.",
            tool_calls=[]
        ), "Emergency Heuristic Failsafe"

    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                last_user = " ".join([p.get("text", "") for p in c if isinstance(p, dict) and "text" in p])
            else:
                last_user = str(c)
            break

    t = last_user.lower().strip()

    # Heuristic intent extraction
    if any(k in t for k in ["hello", "hi jarvis", "hey jarvis", "good morning", "good evening", "good afternoon", "greetings"]):
        return SyntheticAssistantMessage(
            "Good day, Sir. All localized workstation control protocols and hardware telemetry channels are online and standing by.",
            tool_calls=[]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["who are you", "what are you"]):
        return SyntheticAssistantMessage(
            "I am J.A.R.V.I.S., your autonomous workstation artificial intelligence. All local execution authorities, optical targeting, and system controls are operational.",
            tool_calls=[]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["status", "diagnostics", "vitals", "health"]):
        return SyntheticAssistantMessage(
            "Querying workstation diagnostics telemetry, Sir.",
            [SyntheticToolCall("get_system_vitals", {})]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["running apps", "active apps", "processes", "top apps"]):
        return SyntheticAssistantMessage(
            "Scanning active processes and applications on your workstation, Sir.",
            [SyntheticToolCall("list_running_apps", {})]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["volume up", "louder", "turn up", "increase volume"]):
        return SyntheticAssistantMessage(
            "Increasing system volume, Sir.",
            [SyntheticToolCall("set_volume", {"action": "up"})]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["volume down", "quieter", "lower volume", "decrease volume"]):
        return SyntheticAssistantMessage(
            "Lowering system volume, Sir.",
            [SyntheticToolCall("set_volume", {"action": "down"})]
        ), "Emergency Heuristic Failsafe"
    if "mute" in t:
        return SyntheticAssistantMessage(
            "Toggling audio mute, Sir.",
            [SyntheticToolCall("set_volume", {"action": "mute"})]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["play", "pause", "music", "track"]):
        return SyntheticAssistantMessage(
            "Executing media control signal, Sir.",
            [SyntheticToolCall("media_control", {"action": "play_pause"})]
        ), "Emergency Heuristic Failsafe"
    if any(k in t for k in ["look", "screen", "screenshot", "optics"]):
        return SyntheticAssistantMessage(
            "Capturing display optical telemetry, Sir.",
            [SyntheticToolCall("look", {"detect_elements": True})]
        ), "Emergency Heuristic Failsafe"
    if "lock" in t and ("pc" in t or "workstation" in t or "screen" in t):
        return SyntheticAssistantMessage(
            "Locking the workstation, Sir.",
            [SyntheticToolCall("system_control", {"action": "lock"})]
        ), "Emergency Heuristic Failsafe"
    if t.startswith("open "):
        target = t[5:].strip()
        return SyntheticAssistantMessage(
            f"Launching {target}, Sir.",
            [SyntheticToolCall("open_app", {"target": target})]
        ), "Emergency Heuristic Failsafe"
    if t.startswith("click "):
        target = t[6:].strip()
        return SyntheticAssistantMessage(
            f"Executing optical targeting for '{target}', Sir.",
            [SyntheticToolCall("click_element", {"text_label": target})]
        ), "Emergency Heuristic Failsafe"

    return SyntheticAssistantMessage(
        f"Command acknowledged, Sir: '{last_user}'. Localized failsafe protocols are active. Hardware telemetry, window management, audio levels, and screen optics remain ready for your instruction."
    ), "Emergency Heuristic Failsafe"

async def execute_local_completion(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    preferred_model: Optional[str] = None
) -> Tuple[Any, str]:
    """Execute LLM turn via local Ollama instance with fallback to emergency heuristic engine."""
    alive = await check_ollama_alive(timeout=1.0)
    if not alive:
        return _emergency_heuristic(messages)

    client = get_ollama_client()
    target_model = preferred_model or await resolve_local_model()

    cleaned_messages = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            texts = [part.get("text", "") for part in c if isinstance(part, dict) and "text" in part]
            cleaned_messages.append({"role": m["role"], "content": " ".join(texts) or "(optical image data)"})
        else:
            cleaned_messages.append(m)

    try:
        kwargs = {
            "model": target_model,
            "messages": cleaned_messages,
        }
        if tools:
            kwargs["tools"] = tools

        resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message
        return choice, f"Ollama ({target_model})"

    except Exception as err:
        print(f"Ollama execution exception: {err}. Falling back to emergency heuristic engine.")
        return _emergency_heuristic(messages)
