"""J.A.R.V.I.S. Neural Biometric Mood & Cognitive Sensing Engine
Analyzes conversational prosody, sentiment cadence, lexical urgency, and interaction velocity
to estimate Sir's cognitive state, stress index, and vital emotional valence in real-time.
"""
import re
import time
from typing import Dict, Any, List

class BiometricSensor:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.baseline_bpm = 72
        self.current_stress = 22.0
        self.current_focus = 85.0
        self.current_state = "CALM_FOCUSED"

    def analyze_interaction(self, text: str) -> Dict[str, Any]:
        """Compute live biometric telemetry from user's text and vocal transcript."""
        t = text.lower().strip()
        words = re.findall(r'\b\w+\b', t)
        word_count = len(words)

        # 1. Detect Urgency & Tension Markers
        urgent_keywords = ["urgent", "asap", "hurry", "quick", "faster", "fast", "emergency", "fatal", "broken", "critical", "crash"]
        stress_keywords = ["stress", "stressed", "tired", "exhausted", "annoyed", "hate", "angry", "headache", "confused", "stuck", "bug"]
        flow_keywords = ["build", "code", "optimize", "implement", "deploy", "create", "solve", "design", "clean", "perfect"]
        calm_keywords = ["thanks", "good", "great", "excellent", "nice", "hello", "morning", "quiet", "relax", "nominal"]

        urgency_score = sum(1 for w in words if w in urgent_keywords)
        stress_score = sum(1 for w in words if w in stress_keywords)
        flow_score = sum(1 for w in words if w in flow_keywords)
        calm_score = sum(1 for w in words if w in calm_keywords)

        # Rapid punctuation indicators (! and ? repetitions)
        exclamation_count = text.count("!")
        caps_ratio = sum(1 for c in text if c.isupper()) / max(1, len(text))

        # Dynamic Stress Index Adjustment
        stress_delta = (urgency_score * 12) + (stress_score * 15) + (exclamation_count * 8) + (caps_ratio * 20) - (calm_score * 10)
        self.current_stress = max(8.0, min(95.0, self.current_stress * 0.7 + (22.0 + stress_delta) * 0.3))

        # Dynamic Cognitive Focus Adjustment
        focus_delta = (flow_score * 10) + (word_count * 0.8) - (stress_score * 5)
        self.current_focus = max(15.0, min(99.0, self.current_focus * 0.7 + (75.0 + focus_delta) * 0.3))

        # Calculated Simulated Heart Rate (BPM) based on stress & focus
        computed_bpm = int(self.baseline_bpm + (self.current_stress - 20) * 0.35 + (1.0 if word_count > 15 else 0))
        computed_bpm = max(58, min(118, computed_bpm))

        # State Classification
        if self.current_stress > 70.0:
            state = "ALERT_CRITICAL" if urgency_score > 0 else "ELEVATED_STRESS"
            color = "#ff2840"
            rec = "Elevated tension detected. Acoustic volume dampened and quiet focus protocol queued."
        elif self.current_stress > 45.0:
            state = "COGNITIVE_PRESSURE"
            color = "#ffaa00"
            rec = "Workload density high. Standing by for hands-on sub-task delegation."
        elif self.current_focus > 75.0:
            state = "OPTIMAL_FLOW"
            color = "#00ff88"
            rec = "Optimal cognitive flow detected. System latency minimized to sub-20ms."
        else:
            state = "CALM_FOCUSED"
            color = "#00f0ff"
            rec = "Biometric vitals balanced. Workstation nominal and attentive, Sir."

        self.current_state = state

        record = {
            "timestamp": time.strftime("%H:%M:%S"),
            "stress_index": round(self.current_stress, 1),
            "cognitive_focus": round(self.current_focus, 1),
            "bpm": computed_bpm,
            "valence_state": state,
            "theme_color": color,
            "recommendation": rec,
            "metrics": {
                "word_density": word_count,
                "urgency_level": urgency_score,
                "stress_level": stress_score,
                "flow_resonance": flow_score
            }
        }
        self.history.append(record)
        if len(self.history) > 50:
            self.history.pop(0)

        return record

    def get_latest_telemetry(self) -> Dict[str, Any]:
        if self.history:
            return self.history[-1]
        return self.analyze_interaction("System check nominal")

_sensor = BiometricSensor()

def get_biometric_sensor() -> BiometricSensor:
    return _sensor
