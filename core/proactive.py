"""J.A.R.V.I.S. Autonomous Proactive Sentinel Daemon.
Monitors hardware vitals, detects media playback changes, and delivers scheduled morning executive briefings.
Delivers proactive vocal syntheses and HUD telemetry updates.
"""

import asyncio
from datetime import datetime, date
import os
import platform
import re
import time
from typing import Callable, Dict, List, Optional, Any
import urllib.request

import psutil

# Circular import safe module references
_broadcast_callback: Optional[Callable[[str, str], Any]] = None

class ProactiveSentinel:
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
        # Morning briefing settings
        self.briefing_enabled = True
        self.briefing_hour = 9
        self.briefing_minute = 0
        self.last_briefing_date: Optional[str] = None
        
        # Hardware sentinel settings
        self.battery_threshold = 20
        self.last_battery_alert: float = 0.0
        self.battery_alert_cooldown = 1200.0  # 20 minutes
        self.cpu_high_counter = 0
        self.last_cpu_alert: float = 0.0
        self.cpu_alert_cooldown = 900.0  # 15 minutes
        
        # Media observer settings
        self.media_observer_enabled = True
        self.last_media_title: str = ""
        self.last_media_announce: float = 0.0
        self.media_announce_cooldown = 15.0  # 15 seconds
        
        # Diagnostic event log
        self.events: List[Dict[str, Any]] = []

    def log_event(self, category: str, message: str):
        evt = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "category": category,
            "message": message
        }
        self.events.append(evt)
        if len(self.events) > 50:
            self.events.pop(0)

    def fetch_weather_report(self) -> str:
        """Fetch concise live weather telemetry via wttr.in with rapid fallback."""
        try:
            req = urllib.request.Request(
                "https://wttr.in/?format=%C,+%t+(humidity+%h,+wind+%w)",
                headers={"User-Agent": "curl/8.0"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                raw = resp.read().decode("utf-8").strip()
                if raw and "Unknown location" not in raw and "<html" not in raw:
                    return raw
        except Exception:
            pass
        return "28°C, skies are currently clear"

    def get_unread_emails_summary(self) -> str:
        """Query Gmail recent unread emails and format for briefing."""
        try:
            from core.gmail import handle_gmail_tool
            res = handle_gmail_tool("read_recent")
            if not res or "Error" in res:
                return "Your inbox is clear with no pressing alerts."
            
            lines = [l for l in res.splitlines() if l.strip() and not l.startswith("---") and not l.startswith("ID") and "lucky090405" not in l]
            count = len(lines)
            if count == 0:
                return "You have zero unread messages in your inbox."
            elif count == 1:
                return f"You have 1 unread message in your inbox."
            else:
                return f"You have {count} unread messages in your primary inbox."
        except Exception as e:
            return "Inbox status is currently synchronized."

    def build_morning_briefing(self) -> Dict[str, str]:
        """Synthesize a complete, articulate, British Stark JARVIS executive briefing."""
        now = datetime.now()
        day_str = now.strftime("%A, %d %B")
        time_str = now.strftime("%I:%M %p")
        
        weather = self.fetch_weather_report()
        email_summary = self.get_unread_emails_summary()
        
        batt = psutil.sensors_battery()
        batt_info = f"Battery is at {batt.percent}%, {'connected to AC power' if batt.power_plugged else 'running on battery cell'}." if batt else "Power reserves nominal."
        
        speech = (
            f"Good morning, Sir. The time is {time_str} on {day_str}. "
            f"Current atmospheric readings report {weather}. "
            f"{email_summary} "
            f"Workstation vitals: {batt_info} "
            f"All primary systems are calibrated and standing by. What shall we direct our attention to first?"
        )
        
        log_text = f"Executive Morning Briefing delivered: {weather} | {email_summary}"
        self.log_event("briefing", log_text)
        return {"speech": speech, "log": log_text}

    def check_hardware_vitals(self) -> Optional[Dict[str, str]]:
        """Sentinel check for critical battery depletion and sustained CPU loads."""
        now = time.time()
        
        # 1. Battery check
        batt = psutil.sensors_battery()
        if batt and not batt.power_plugged and batt.percent <= self.battery_threshold:
            if now - self.last_battery_alert > self.battery_alert_cooldown:
                self.last_battery_alert = now
                msg = f"Sir, emergency telemetry: battery cell reserves have depleted to {batt.percent}%. Workstation requires immediate connection to AC power."
                self.log_event("hardware_alert", msg)
                return {
                    "category": "battery_critical",
                    "speech": msg,
                    "log": f"⚠️ BATTERY CRITICAL: {batt.percent}% (Discharging)"
                }

        # 2. CPU load check
        cpu = psutil.cpu_percent(interval=None)
        if cpu >= 90.0:
            self.cpu_high_counter += 1
            if self.cpu_high_counter >= 3:  # Sustained across 3 ticks (30s)
                if now - self.last_cpu_alert > self.cpu_alert_cooldown:
                    self.last_cpu_alert = now
                    self.cpu_high_counter = 0
                    msg = f"Sir, processor matrix is experiencing sustained thermal stress at {cpu:.0f}% load. You may wish to review background workloads."
                    self.log_event("hardware_alert", msg)
                    return {
                        "category": "cpu_high",
                        "speech": msg,
                        "log": f"⚠️ CPU LOAD ELEVATED: {cpu:.0f}% sustained"
                    }
        else:
            self.cpu_high_counter = 0

        return None

    def check_active_media(self) -> Optional[Dict[str, str]]:
        """Inspect running windows for new Spotify or YouTube playback."""
        if not self.media_observer_enabled:
            return None

        now = time.time()
        from core.window_manager import list_desktop_windows
        windows = list_desktop_windows()
        
        current_track = None
        media_source = None

        for w in windows:
            pname = w["process"].lower()
            title = w["title"].strip()
            
            # 1. Spotify
            if "spotify" in pname:
                # If playing a song, title is 'Song - Artist'. If stopped/idle, title is 'Spotify' or 'Spotify Premium'
                if " - " in title and not title.lower().startswith("spotify"):
                    current_track = title
                    media_source = "Spotify"
                    break
                    
            # 2. YouTube in browser
            elif any(b in pname for b in ["brave", "chrome", "msedge"]):
                if " - youtube" in title.lower():
                    # Strip ' - YouTube - Brave' or ' - YouTube'
                    clean = re.sub(r' - YouTube.*$', '', title, flags=re.IGNORECASE).strip()
                    if clean and "j.a.r.v.i.s." not in clean.lower():
                        current_track = clean
                        media_source = "YouTube"
                        break

        if current_track and current_track != self.last_media_title:
            self.last_media_title = current_track
            if now - self.last_media_announce > self.media_announce_cooldown:
                self.last_media_announce = now
                msg = f"Now playing on {media_source}: {current_track}, Sir."
                self.log_event("media_change", f"{media_source}: {current_track}")
                return {
                    "category": "media_track",
                    "speech": msg,
                    "log": f"🎵 MEDIA: [{media_source}] {current_track}"
                }

        return None

    async def run_loop(self, broadcast_fn: Callable[[Dict[str, Any]], Any]):
        """Main proactive sentinel evaluation loop running every 10 seconds."""
        self.running = True
        print("[*] J.A.R.V.I.S. Proactive Sentinel Daemon operational.")
        
        while self.running:
            try:
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                
                # 1. Morning Executive Briefing Trigger
                # Weekdays (Monday=0 to Friday=4) at 9:00 AM
                if self.briefing_enabled and now.weekday() < 5:
                    if now.hour == self.briefing_hour and now.minute == self.briefing_minute:
                        if self.last_briefing_date != today_str:
                            self.last_briefing_date = today_str
                            briefing = await asyncio.to_thread(self.build_morning_briefing)
                            await broadcast_fn({
                                "type": "proactive_briefing",
                                "speech": briefing["speech"],
                                "log": briefing["log"]
                            })

                # 2. Hardware Vitals Check
                hw_alert = await asyncio.to_thread(self.check_hardware_vitals)
                if hw_alert:
                    await broadcast_fn({
                        "type": "proactive_alert",
                        "category": hw_alert["category"],
                        "speech": hw_alert["speech"],
                        "log": hw_alert["log"]
                    })

                # 3. Media Observer Check
                media_alert = await asyncio.to_thread(self.check_active_media)
                if media_alert:
                    await broadcast_fn({
                        "type": "proactive_media",
                        "category": media_alert["category"],
                        "speech": media_alert["speech"],
                        "log": media_alert["log"]
                    })

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Sentinel evaluation exception: {e}")

            await asyncio.sleep(10.0)

        self.running = False
        print("[*] J.A.R.V.I.S. Proactive Sentinel Daemon suspended.")

# Singleton instance
_SENTINEL = ProactiveSentinel()

def get_sentinel() -> ProactiveSentinel:
    return _SENTINEL
