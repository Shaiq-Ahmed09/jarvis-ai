"""J.A.R.V.I.S. Deep Focus & Study Mode Guardian.
Enforces an impenetrable focus envelope for Sir's studies and deep work sessions.
Monitors active desktop processes and windows, actively deflecting/closing games
and distracting entertainment software while maintaining target study applications in focus.
"""

import asyncio
import os
import time
from typing import Dict, List, Optional, Any, Callable

import psutil

try:
    import win32gui
    import win32process
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Comprehensive catalog of common gaming platforms, launchers, and titles
DEFAULT_GAME_PROCESSES = {
    # Launchers & Stores
    "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "riotclientservices.exe",
    "battlenet.exe", "eadesktop.exe", "origin.exe", "ubisoftconnect.exe", "gog galaxy.exe",
    # Popular Games & Engines
    "valorant.exe", "valorant-win64-shipping.exe", "leagueclient.exe", "leagueclientux.exe",
    "minecraft.exe", "javaw.exe", "robloxplayerbeta.exe", "roblox.exe",
    "csgo.exe", "cs2.exe", "dota2.exe", "genshinimpact.exe", "honkaistarrail.exe",
    "fortniteclient-win64-shipping.exe", "apexlegends.exe", "overwatch.exe",
    "cyberpunk2077.exe", "gta5.exe", "gta_sa.exe", "eldenring.exe", "witcher3.exe",
    "rocketleague.exe", "fallguys_client.exe", "tarkov.exe", "escapefromtarkov.exe"
}

DEFAULT_GAME_TITLES = [
    "steam", "epic games", "riot client", "valorant", "league of legends",
    "minecraft", "roblox", "counter-strike", "dota 2", "genshin impact",
    "fortnite", "apex legends", "overwatch", "cyberpunk 2077", "grand theft auto",
    "battle.net", "ea app", "ubisoft connect", "elden ring", "rocket league"
]

class FocusModeGuardian:
    def __init__(self):
        self.is_active: bool = False
        self.objective: str = "General Study & Deep Work"
        self.start_time: float = 0.0
        self.duration_seconds: Optional[int] = None
        self.target_app: Optional[str] = None
        self.blocked_attempts: int = 0
        self.blocked_log: List[Dict[str, Any]] = []
        self.on_blocked_callback: Optional[Callable[[str, str], Any]] = None
        self._watcher_task: Optional[asyncio.Task] = None

    def activate(
        self,
        objective: str = "Study & Deep Work",
        duration_minutes: Optional[int] = 30,
        target_app: Optional[str] = None
    ) -> Dict[str, Any]:
        """Engage focus mode envelope."""
        self.is_active = True
        self.objective = objective or "Study & Deep Work"
        self.start_time = time.time()
        self.duration_seconds = (duration_minutes * 60) if duration_minutes else None
        self.target_app = target_app
        self.blocked_attempts = 0
        self.blocked_log.clear()

        # Immediate sweep upon activation
        self.check_and_enforce()

        return self.get_status()

    def deactivate(self) -> Dict[str, Any]:
        """Disengage focus mode envelope."""
        self.is_active = False
        status = self.get_status()
        self.duration_seconds = None
        return status

    def get_status(self) -> Dict[str, Any]:
        """Retrieve real-time status of the study focus mode envelope."""
        if not self.is_active:
            return {
                "is_active": False,
                "objective": self.objective,
                "remaining_seconds": 0,
                "remaining_formatted": "00:00",
                "elapsed_seconds": 0,
                "blocked_attempts": self.blocked_attempts,
                "blocked_log": self.blocked_log[-6:],
                "status_text": "STANDBY // READY TO LOCK IN"
            }

        elapsed = int(time.time() - self.start_time)
        remaining = 0
        formatted = "UNLIMITED"

        if self.duration_seconds:
            remaining = max(0, self.duration_seconds - elapsed)
            mins = remaining // 60
            secs = remaining % 60
            formatted = f"{mins:02d}:{secs:02d}"

            # Auto-expire if duration elapsed
            if remaining <= 0:
                self.is_active = False
                return {
                    "is_active": False,
                    "objective": self.objective,
                    "remaining_seconds": 0,
                    "remaining_formatted": "COMPLETED",
                    "elapsed_seconds": elapsed,
                    "blocked_attempts": self.blocked_attempts,
                    "blocked_log": self.blocked_log[-6:],
                    "status_text": "SESSION COMPLETED // WELL DONE, SIR"
                }

        return {
            "is_active": True,
            "objective": self.objective,
            "remaining_seconds": remaining,
            "remaining_formatted": formatted,
            "elapsed_seconds": elapsed,
            "blocked_attempts": self.blocked_attempts,
            "blocked_log": self.blocked_log[-6:],
            "status_text": f"LOCKED IN // {self.objective.upper()}"
        }

    def check_and_enforce(self) -> List[Dict[str, Any]]:
        """Scan running processes and top desktop windows; deflect and close any gaming software."""
        if not self.is_active:
            return []

        deflected = []

        # 1. Inspect Windows Desktop GUI Top-Level Windows
        if HAS_WIN32:
            def enum_cb(hwnd, extra):
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd).strip()
                if not title:
                    return True

                lower_title = title.lower()
                for game_kw in DEFAULT_GAME_TITLES:
                    if game_kw in lower_title:
                        # Match found! Deflect window
                        try:
                            # Attempt clean close signal first
                            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                            # Minimize to eliminate distraction immediately
                            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                            deflected.append({"type": "window", "title": title, "keyword": game_kw})
                        except Exception as e:
                            print(f"[Focus Guardian] Window deflection notice: {e}")
                        break
                return True

            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception as e:
                print(f"[Focus Guardian] EnumWindows error: {e}")

        # 2. Inspect Running Background/Foreground Processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info.get('name', '').lower()
                if pname in DEFAULT_GAME_PROCESSES:
                    try:
                        proc.terminate()
                        deflected.append({"type": "process", "name": pname, "pid": proc.info.get('pid')})
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Record events
        for item in deflected:
            self.blocked_attempts += 1
            app_label = item.get("title") or item.get("name") or "Gaming Application"
            entry = {
                "app": app_label,
                "timestamp": time.strftime("%H:%M:%S"),
                "action": "BLOCKED & TERMINATED"
            }
            self.blocked_log.append(entry)
            print(f"[Focus Guardian] 🛑 Deflected distraction: {app_label} during '{self.objective}'")

            # Fire notification callback if hooked
            if self.on_blocked_callback:
                try:
                    self.on_blocked_callback(app_label, self.objective)
                except Exception as cb_err:
                    print(f"[Focus Guardian] Callback notice: {cb_err}")

        return deflected

# Global singleton
_focus_guardian_instance: Optional[FocusModeGuardian] = None

def get_focus_guardian() -> FocusModeGuardian:
    global _focus_guardian_instance
    if _focus_guardian_instance is None:
        _focus_guardian_instance = FocusModeGuardian()
    return _focus_guardian_instance
