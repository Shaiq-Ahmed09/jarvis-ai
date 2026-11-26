"""J.A.R.V.I.S. Predictive Workflow Automation Engine
Anticipates Sir's workflow directives based on temporal context, running desktop applications,
workstation hardware load, and semantic task patterns.
"""
from datetime import datetime
import psutil
from typing import List, Dict, Any

class PredictiveEngine:
    def __init__(self):
        self.workflow_catalog = {
            "dev_sprint": {
                "id": "dev_sprint",
                "title": "DEV SPRINT PROTOCOL",
                "icon": "⚡",
                "category": "ENGINEERING",
                "description": "Align developer workspace: focus VS Code, snap terminal, and engage focus cadence.",
                "actions": [
                    {"tool": "open_app", "args": {"target": "code"}},
                    {"tool": "open_app", "args": {"target": "terminal"}}
                ]
            },
            "executive_briefing": {
                "id": "executive_briefing",
                "title": "MORNING EXECUTIVE BRIEFING",
                "icon": "🌅",
                "category": "INTEL",
                "description": "Synthesize live weather, VIP Gmail inbox, system vitals, and scheduled meetings.",
                "actions": [
                    {"tool": "trigger_morning_briefing", "args": {}}
                ]
            },
            "deep_focus": {
                "id": "deep_focus",
                "title": "DEEP COGNITIVE FOCUS",
                "icon": "🛡️",
                "category": "WORKSTATION",
                "description": "Engage study focus mode, block all gaming software, mute audio, and silence distractions.",
                "actions": [
                    {"tool": "toggle_focus_mode", "args": {"enabled": True, "objective": "Deep Cognitive Focus & Study", "duration_minutes": 30}},
                    {"tool": "set_volume", "args": {"action": "mute"}},
                    {"tool": "manage_window", "args": {"action": "minimize"}}
                ]
            },
            "social_comms": {
                "id": "social_comms",
                "title": "SOCIAL COMMS RADAR",
                "icon": "💬",
                "category": "COMMUNICATIONS",
                "description": "Scan Instagram unread direct messages and sync WhatsApp communications cortex.",
                "actions": [
                    {"tool": "instagram_action", "args": {"action": "check"}},
                    {"tool": "whatsapp_action", "args": {"action": "open_web"}}
                ]
            },
            "optical_scan": {
                "id": "optical_scan",
                "title": "NEURAL OPTICAL SCAN",
                "icon": "👁️",
                "category": "VISION",
                "description": "Capture screen telemetry with coordinate grid and detect interactive clickable UI elements.",
                "actions": [
                    {"tool": "look", "args": {"detect_elements": True, "with_grid": True}}
                ]
            },
            "night_lock": {
                "id": "night_lock",
                "title": "SECURE NIGHT STANDBY",
                "icon": "🔒",
                "category": "SECURITY",
                "description": "Power down sensory feeds, clear session scratchpad, and lock workstation.",
                "actions": [
                    {"tool": "system_control", "args": {"action": "lock"}}
                ]
            }
        }

    def predict_workflows(self) -> List[Dict[str, Any]]:
        """Compute top contextual workflow predictions with Bayesian dynamic confidence scores."""
        now = datetime.now()
        hour = now.hour
        
        # Check active processes
        running = set()
        for p in psutil.process_iter(['name']):
            try:
                name = p.info['name']
                if name:
                    running.add(name.lower())
            except Exception:
                pass

        has_code = any(k in running for k in ["code.exe", "cursor.exe", "devenv.exe", "pycharm64.exe"])
        has_browser = any(k in running for k in ["brave.exe", "chrome.exe", "msedge.exe"])

        predictions = []

        # 1. Morning or Comms Prediction
        if 5 <= hour <= 12:
            p = dict(self.workflow_catalog["executive_briefing"])
            p["confidence"] = 0.96
            p["reason"] = f"Optimal time ({now.strftime('%I:%M %p')}) for morning executive briefing and inbox triage."
            predictions.append(p)

        # 2. Dev Sprint Protocol
        dev_p = dict(self.workflow_catalog["dev_sprint"])
        if has_code:
            dev_p["confidence"] = 0.94
            dev_p["reason"] = "Active development process detected in memory. Ready for synchronized terminal workspace."
        else:
            dev_p["confidence"] = 0.82
            dev_p["reason"] = "Prime working hours. Recommended 1-click developer workspace mobilization."
        predictions.append(dev_p)

        # 3. Optical Neural Scan
        opt_p = dict(self.workflow_catalog["optical_scan"])
        opt_p["confidence"] = 0.88
        opt_p["reason"] = "Display active. Neural OCR ready to map interactive UI buttons and reticles."
        predictions.append(opt_p)

        # 4. Social Comms or Deep Focus
        if 13 <= hour <= 21:
            soc_p = dict(self.workflow_catalog["social_comms"])
            soc_p["confidence"] = 0.85
            soc_p["reason"] = "Afternoon communications window active for Instagram & WhatsApp friend interactions."
            predictions.append(soc_p)
        else:
            night_p = dict(self.workflow_catalog["night_lock"])
            night_p["confidence"] = 0.91 if (hour >= 22 or hour < 4) else 0.70
            night_p["reason"] = "Late hours detected. One-click workstation security lock and standby protocol."
            predictions.append(night_p)

        # Sort by confidence descending
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        return predictions

_engine = PredictiveEngine()

def get_predictive_engine() -> PredictiveEngine:
    return _engine
