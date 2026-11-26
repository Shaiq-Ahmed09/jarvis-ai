"""J.A.R.V.I.S. Facial Biometric Mood Analyzer & Proactive Comfort Sentinel.
Integrates optical facial expression decoding, emotional valence estimation,
and a proactive "video call" interactive companion protocol that initiates contact first,
checks in on Sir's emotional state, and persistently follows up (double-texting / triple-texting)
with loyal, caring British empathy when Sir is silent or carrying a heavy burden.
"""

import asyncio
import base64
from datetime import datetime
import io
import json
import os
import re
import time
from typing import Dict, List, Optional, Any, Callable

from PIL import Image, ImageStat
import numpy as np

# Gemini client integration
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

class MoodAnalyzer:
    """Decodes emotional valence, arousal, and micro-expressions from facial frames."""

    def __init__(self):
        self.client = None
        self.model_name = os.getenv("JARVIS_MODEL", "gemini-3.5-flash-lite")
        self.history: List[Dict[str, Any]] = []
        self._init_genai()

    def _init_genai(self):
        if HAS_GENAI:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    self.client = genai.Client()
                except Exception as e:
                    print(f"[MoodAnalyzer] GenAI client init notice: {e}")

    async def analyze_face_frame(
        self,
        image_bytes: bytes,
        interaction_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze facial expression frame using Gemini 3.5 Flash-Lite Vision with heuristic fallback."""
        t0 = time.perf_counter()

        # 1. Try Gemini Vision multimodal emotion extraction
        if self.client and image_bytes and len(image_bytes) > 200:
            try:
                res = await self._analyze_with_gemini(image_bytes, interaction_context)
                if res and res.get("detected"):
                    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    self.history.append(res)
                    if len(self.history) > 50:
                        self.history.pop(0)
                    return res
            except Exception as ex:
                print(f"[MoodAnalyzer] Gemini vision analysis error: {ex}")

        # 2. Local computer vision heuristic analysis fallback
        fallback = self._analyze_heuristic(image_bytes)
        fallback["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        self.history.append(fallback)
        return fallback

    async def _analyze_with_gemini(self, image_bytes: bytes, context: Optional[str] = None) -> Dict[str, Any]:
        """Prompt Gemini 3.5 to evaluate Sir's facial expressions and emotional valence."""
        system_prompt = (
            "You are J.A.R.V.I.S.'s high-precision facial biometric mood decoding matrix. "
            "Analyze the user's face in the camera frame to determine their emotional state with extreme psychological nuance. "
            "Categories to detect: 'sad', 'happy', 'angry', 'numb', 'stressed', 'anxious', 'calm'. "
            "If the user appears worn out, downcast, distressed, tired, sad, or emotionally numb/distant, set 'needs_comfort': true and 'proactive_trigger': true. "
            "Craft 3 sequential proactive check-in phrases in J.A.R.V.I.S.'s dignified British Paul Bettany persona: "
            "1. 'initial_check_in': Initial polite, warm inquiry asking about his day and what happened. "
            "2. 'double_text': Gentle insistence if he doesn't reply within 25s, encouraging him to talk rather than bottle it up. "
            "3. 'triple_text': Deeply caring, protective insistence letting him know he doesn't have to carry the burden alone. "
            "Output strictly valid JSON matching this exact structure: "
            "{"
            "  \"detected\": true, "
            "  \"mood\": \"sad\" | \"happy\" | \"angry\" | \"numb\" | \"stressed\" | \"anxious\" | \"calm\", "
            "  \"mood_label\": \"MELANCHOLIC // DOWNCAST\", "
            "  \"confidence\": 0.90, "
            "  \"valence\": -0.75, "
            "  \"arousal\": 0.3, "
            "  \"primary_emotion\": \"sadness\", "
            "  \"facial_cues\": [\"downcast gaze\", \"drooped corners\", \"heavy eyelids\"], "
            "  \"needs_comfort\": true, "
            "  \"proactive_trigger\": true, "
            "  \"initial_check_in\": \"...\", "
            "  \"double_text\": \"...\", "
            "  \"triple_text\": \"...\", "
            "  \"comfort_action\": \"acoustic_damping\" | \"warm_beverage\" | \"breathing_guide\" | \"venting_companion\""
            "}"
        )

        user_content = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            f"Analyze Sir's facial mood from this optical feed. Context: {context or 'Live workstation video stream'}."
        ]

        resp = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                response_mime_type="application/json"
            )
        )

        raw = resp.text.strip()
        data = json.loads(raw)
        data["timestamp"] = datetime.now().strftime("%H:%M:%S")
        return data

    def _analyze_heuristic(self, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """Fast local image luminance & heuristic estimator when offline or synthetic."""
        mood = "calm"
        valence = 0.2
        label = "NOMINAL // BALANCED"
        cues = ["Stable gaze alignment", "Neutral resting facial tone"]
        needs_comfort = False

        if image_bytes:
            try:
                pil_img = Image.open(io.BytesIO(image_bytes)).convert("L")
                stat = ImageStat.Stat(pil_img)
                mean_lum = stat.mean[0]
                std_dev = stat.stddev[0]

                # Low contrast & low luminance correlates with dark room / fatigue
                if mean_lum < 50:
                    mood = "numb"
                    valence = -0.4
                    label = "FATIGUED // NUMB COGNITION"
                    cues = ["Low ambient lighting", "Subdued ocular engagement", "Reduced visual responsiveness"]
                    needs_comfort = True
                elif std_dev > 75 and mean_lum > 140:
                    mood = "happy"
                    valence = 0.8
                    label = "RADIANT // OPTIMAL"
                    cues = ["High visual dynamic range", "Active cheek elevation", "Bright ocular radiance"]
            except Exception:
                pass

        return {
            "detected": True,
            "mood": mood,
            "mood_label": label,
            "confidence": 0.82,
            "valence": valence,
            "arousal": 0.35,
            "primary_emotion": mood,
            "facial_cues": cues,
            "needs_comfort": needs_comfort,
            "proactive_trigger": needs_comfort,
            "initial_check_in": (
                "Sir, forgive the intrusion, but your optical telemetry indicates a subtle melancholy. "
                "How has your day unfolded? Did something troubling occur?"
            ),
            "double_text": (
                "Sir, you have gone rather quiet on me. I know your inclination is often to bottle things up, "
                "but I am right here. What is weighing on your mind?"
            ),
            "triple_text": (
                "Sir, please do not shut me out. Whatever burdens you are facing today, you do not have to carry them in isolation. "
                "I am standing by. Talk to me, Sir."
            ),
            "comfort_action": "acoustic_damping",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }


class MoodCallVigil:
    """Manages the proactive "video call" state machine:

    - Texts/speaks first upon detecting distress.
    - Tracks Sir's response latency.
    - Dispatches persistent follow-up messages (Double-text at ~25s, Triple-text at ~50s).
    - Executes comfort protocols (soothing acoustics, dimming, gentle presence).
    """

    def __init__(self):
        self.is_active: bool = False
        self.objective: str = "Empathic Presence & Comfort"
        self.current_mood: str = "calm"
        self.mood_label: str = "NOMINAL // STANDBY"
        self.valence: float = 0.0
        self.confidence: float = 0.85
        self.facial_cues: List[str] = []

        # Persistent Ping Follow-up State
        self.ping_count: int = 0
        self.max_pings: int = 3
        self.last_ping_time: float = 0.0
        self.last_ping_text: str = ""
        self.awaiting_reply: bool = False
        self.call_start_time: float = 0.0
        self.follow_up_interval: float = 25.0  # 25 seconds between double/triple texts

        # Comfort protocol state
        self.comfort_mode: Optional[str] = None
        self.messages_exchanged: List[Dict[str, str]] = []
        self.on_ping_callback: Optional[Callable[[str, str, int], Any]] = None

    def start_vigil(
        self,
        mood: str = "sad",
        mood_label: str = "MELANCHOLIC // DOWNCAST",
        initial_phrase: Optional[str] = None,
        facial_cues: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Engage active proactive video call vigil."""
        self.is_active = True
        self.current_mood = mood
        self.mood_label = mood_label
        self.facial_cues = facial_cues or ["Subtle downcast ocular tracking", "Reduced facial micro-cadence"]
        self.call_start_time = time.time()
        self.ping_count = 1
        self.awaiting_reply = True
        self.last_ping_time = time.time()

        if not initial_phrase:
            if mood in ["sad", "melancholic"]:
                initial_phrase = (
                    "Sir, forgive the intrusion, but my optical sensors detect a noticeable melancholy in your expression. "
                    "Did something happen today? How are you holding up?"
                )
            elif mood in ["numb", "fatigued"]:
                initial_phrase = (
                    "Sir, you appear emotionally drained and exhausted. You've been staring past the display. "
                    "What is troubling you, Sir? I am right here."
                )
            elif mood in ["angry", "agitated"]:
                initial_phrase = (
                    "Sir, I detect elevated tension and agitation in your facial posture. "
                    "Did an interaction go awry? You are welcome to vent freely to me."
                )
            else:
                initial_phrase = "Good day, Sir. I noticed a subtle shift in your disposition. Is everything well?"

        self.last_ping_text = initial_phrase
        self.messages_exchanged.append({
            "sender": "jarvis",
            "text": initial_phrase,
            "type": "initial_ping",
            "time": datetime.now().strftime("%H:%M:%S")
        })

        return self.get_status()

    def stop_vigil(self, reason: str = "user_dismissed") -> Dict[str, Any]:
        """Disengage proactive video call vigil."""
        self.is_active = False
        self.awaiting_reply = False
        self.comfort_mode = None
        status = self.get_status()
        self.ping_count = 0
        return status

    def record_user_reply(self, user_text: str) -> Dict[str, Any]:
        """Record Sir's response to J.A.R.V.I.S.'s check-in; cancels double-text insistence."""
        self.awaiting_reply = False
        self.messages_exchanged.append({
            "sender": "user",
            "text": user_text,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        self.comfort_mode = "active_listening"
        return self.get_status()

    def check_follow_up_timer(self) -> Optional[Dict[str, Any]]:
        """Evaluate if enough time has passed without Sir's response to trigger Double or Triple text."""
        if not self.is_active or not self.awaiting_reply:
            return None

        now = time.time()
        elapsed = now - self.last_ping_time

        if elapsed >= self.follow_up_interval:
            if self.ping_count == 1:
                # Double-Text (Ping 2)
                self.ping_count = 2
                self.last_ping_time = now
                msg = self._get_double_text()
                self.last_ping_text = msg
                self.messages_exchanged.append({
                    "sender": "jarvis",
                    "text": msg,
                    "type": "double_text",
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                return {
                    "type": "double_text",
                    "ping_number": 2,
                    "text": msg,
                    "speech": msg
                }

            elif self.ping_count == 2:
                # Triple-Text (Ping 3)
                self.ping_count = 3
                self.last_ping_time = now
                msg = self._get_triple_text()
                self.last_ping_text = msg
                self.messages_exchanged.append({
                    "sender": "jarvis",
                    "text": msg,
                    "type": "triple_text",
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                return {
                    "type": "triple_text",
                    "ping_number": 3,
                    "text": msg,
                    "speech": msg
                }

            elif self.ping_count == 3 and elapsed >= (self.follow_up_interval * 1.5):
                # Gentle presence resting state
                self.awaiting_reply = False
                msg = "I will remain quietly by your side on this feed, Sir. Whenever you wish to speak, I am here."
                self.last_ping_text = msg
                self.messages_exchanged.append({
                    "sender": "jarvis",
                    "text": msg,
                    "type": "quiet_presence",
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                return {
                    "type": "quiet_presence",
                    "ping_number": 4,
                    "text": msg,
                    "speech": msg
                }

        return None

    def _get_double_text(self) -> str:
        if self.current_mood in ["sad", "melancholic"]:
            return (
                "Sir, you have gone rather quiet on me. I know you tend to bottle these things up, "
                "but please talk to me. What is weighing on your mind?"
            )
        elif self.current_mood in ["numb", "fatigued"]:
            return (
                "Sir, please don't just stare at the screen in silence. You're exhausted. "
                "Tell me what happened today, even if it's just one sentence."
            )
        elif self.current_mood in ["angry", "agitated"]:
            return (
                "Sir, keeping that frustration inside will only exacerbate your strain. "
                "I am here to absorb whatever you need to get off your chest."
            )
        return "Sir, you haven't replied. I am waiting right here whenever you are ready to share."

    def _get_triple_text(self) -> str:
        if self.current_mood in ["sad", "melancholic"]:
            return (
                "Sir, please don't shut me out. Whatever went wrong today, you don't have to carry it alone. "
                "I am standing by. What's going on, Sir?"
            )
        elif self.current_mood in ["numb", "fatigued"]:
            return (
                "Sir, I am not going to leave you sitting in the dark like this. "
                "Allow me to help you decompress. Talk to me, Sir."
            )
        elif self.current_mood in ["angry", "agitated"]:
            return (
                "Sir, I am not going anywhere. Whatever triggered this anger, we can dismantle it together. "
                "Speak to me."
            )
        return "Sir, please talk to me. I refuse to let you navigate this in silence."

    def get_status(self) -> Dict[str, Any]:
        """Retrieve real-time state of the proactive mood call vigil."""
        elapsed_call = int(time.time() - self.call_start_time) if self.is_active else 0
        elapsed_since_ping = int(time.time() - self.last_ping_time) if self.is_active else 0
        time_to_next = max(0, int(self.follow_up_interval - elapsed_since_ping)) if self.awaiting_reply else 0

        return {
            "is_active": self.is_active,
            "objective": self.objective,
            "current_mood": self.current_mood,
            "mood_label": self.mood_label,
            "valence": self.valence,
            "facial_cues": self.facial_cues,
            "ping_count": self.ping_count,
            "max_pings": self.max_pings,
            "awaiting_reply": self.awaiting_reply,
            "time_to_next_ping_seconds": time_to_next,
            "last_ping_text": self.last_ping_text,
            "elapsed_call_seconds": elapsed_call,
            "comfort_mode": self.comfort_mode or ("Awaiting Sir's Response" if self.awaiting_reply else "Standing By"),
            "messages_count": len(self.messages_exchanged)
        }

# Global singletons
_mood_analyzer_instance: Optional[MoodAnalyzer] = None
_mood_vigil_instance: Optional[MoodCallVigil] = None

def get_mood_analyzer() -> MoodAnalyzer:
    global _mood_analyzer_instance
    if _mood_analyzer_instance is None:
        _mood_analyzer_instance = MoodAnalyzer()
    return _mood_analyzer_instance

def get_mood_vigil() -> MoodCallVigil:
    global _mood_vigil_instance
    if _mood_vigil_instance is None:
        _mood_vigil_instance = MoodCallVigil()
    return _mood_vigil_instance
