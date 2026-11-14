"""High-Performance In-Memory Audio Cache & Voice Pre-Warmer for J.A.R.V.I.S.
Eliminates network TTS latency for frequent acknowledgments and common phrases.
"""
import asyncio
import base64
import edge_tts

DEFAULT_VOICE = "en-GB-RyanNeural"
VOICE_PITCH = "-1Hz"
VOICE_RATE = "+3%"

# In-memory LRU-like audio cache: text -> base64 MP3
_AUDIO_CACHE = {}

COMMON_PHRASES = [
    "Right away, Sir.",
    "At your service, Sir.",
    "I have handled that for you, Sir.",
    "All systems nominal, Sir.",
    "Workstation locked, Sir.",
    "Session cache cleared, Sir.",
    "Protocol suspended, Sir.",
    "One moment, Sir.",
    "Executing that for you now, Sir.",
    "Volume adjusted, Sir.",
    "Audio mute toggled, Sir.",
    "Optical camera online, Sir.",
    "Optical camera deactivated, Sir.",
    "Optical snapshot captured, Sir.",
    "Desktop toggled, Sir.",
    "Window state updated, Sir.",
    "Media playback updated, Sir.",
    "Application launched, Sir."
]

async def synthesize_raw(text: str, voice: str = DEFAULT_VOICE) -> str:
    """Direct Edge-TTS synthesis returning base64 MP3."""
    try:
        communicate = edge_tts.Communicate(text, voice, pitch=VOICE_PITCH, rate=VOICE_RATE)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode()
        return ""
    except Exception as e:
        print(f"Edge-TTS synthesis error: {e}")
        return ""

async def get_or_synthesize_audio(text: str, voice: str = DEFAULT_VOICE) -> str:
    """Return cached base64 audio if available (0ms), otherwise synthesize and cache."""
    clean_key = text.strip()
    if clean_key in _AUDIO_CACHE:
        return _AUDIO_CACHE[clean_key]
        
    b64 = await synthesize_raw(clean_key, voice)
    if b64 and len(clean_key) < 120:
        _AUDIO_CACHE[clean_key] = b64
    return b64

async def prewarm_audio_cache():
    """Background task to pre-synthesize common phrases on server startup."""
    print("[*] Pre-warming J.A.R.V.I.S. neural voice cache...")
    for phrase in COMMON_PHRASES:
        if phrase not in _AUDIO_CACHE:
            try:
                b64 = await synthesize_raw(phrase)
                if b64:
                    _AUDIO_CACHE[phrase] = b64
            except Exception:
                pass
    print(f"[*] Voice cache ready: {len(_AUDIO_CACHE)} common phrases loaded (0ms latency).")
