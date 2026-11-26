"""
J.A.R.V.I.S. Floating Desktop Sentinel Bubble
=============================================
A pure, borderless, transparent floating circular AI companion that hovers on top
of all Windows applications and desktop tabs.

Features:
- Breathing organic glowing animation (idle, listening, thinking, speaking)
- Free draggable movement across the desktop
- Single click: Toggle voice listening & speech interaction
- Double click: Maximize & open the full Stark HUD frontend in browser
- Right click: Quick menu (Vision screen analysis, persona switch, HUD launch)
- Floating Speech Bubble: Displays transcriptions and responses right next to the orb
- Vision ("See my screen"): Takes a screen snapshot and analyzes what you're working on
"""

import sys
import os
import json
import math
import time
import asyncio
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# Add project root to sys.path
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "backend"))

WS_URL = "ws://127.0.0.1:8765/ws"
HUD_URL = "http://localhost:8765"
TRANSPARENT_KEY = "#010203"  # Color key made 100% transparent on Windows


class SpeechPill(tk.Toplevel):
    """Floating companion pill that appears beside the bubble displaying transcripts."""
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.92)
        self.configure(bg="#040d1a")
        self.withdraw()

        self.frame = tk.Frame(self, bg="#040d1a", highlightbackground="#00f0ff", highlightthickness=1)
        self.frame.pack(fill="both", expand=True)

        self.title_lbl = tk.Label(
            self.frame, text="◈ J.A.R.V.I.S.", font=("Consolas", 8, "bold"),
            fg="#00f0ff", bg="#040d1a", anchor="w"
        )
        self.title_lbl.pack(fill="x", padx=10, pady=(6, 2))

        self.msg_lbl = tk.Label(
            self.frame, text="", font=("Segoe UI", 9),
            fg="#e2e8f0", bg="#040d1a", justify="left",
            wraplength=260, anchor="w"
        )
        self.msg_lbl.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self._hide_timer = None

    def show_message(self, title, text, duration=7000):
        if self._hide_timer:
            self.after_cancel(self._hide_timer)

        self.title_lbl.config(text=title)
        self.msg_lbl.config(text=text)

        # Position to the left or right of master bubble
        self.update_idletasks()
        bubble_x = self.master.winfo_x()
        bubble_y = self.master.winfo_y()
        screen_w = self.winfo_screenwidth()

        pill_w = max(200, min(300, len(text) * 7 + 30))
        pill_h = max(60, min(180, (len(text) // 30 + 2) * 22 + 30))

        if bubble_x + 130 + pill_w < screen_w:
            px = bubble_x + 120
        else:
            px = bubble_x - pill_w - 10
        py = max(20, bubble_y)

        self.geometry(f"{pill_w}x{pill_h}+{px}+{py}")
        self.deiconify()

        self._hide_timer = self.after(duration, self.withdraw)


class DesktopSentinelBubble(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("J.A.R.V.I.S. Bubble")
        self.overrideredirect(True)          # Borderless & frameless
        self.wm_attributes("-topmost", True)      # Always on top of all windows
        self.wm_attributes("-transparentcolor", TRANSPARENT_KEY)  # Cutout transparent bg
        self.configure(bg=TRANSPARENT_KEY)

        # Bubble Dimensions
        self.size = 110
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        start_x = screen_w - self.size - 30
        start_y = screen_h - self.size - 100
        self.geometry(f"{self.size}x{self.size}+{start_x}+{start_y}")

        # Canvas for the breathing circle
        self.canvas = tk.Canvas(
            self, width=self.size, height=self.size,
            bg=TRANSPARENT_KEY, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Dragging state
        self._drag_start = {"x": 0, "y": 0, "root_x": 0, "root_y": 0}
        self._moved = False

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._show_context_menu)

        # Context Menu
        self.menu = tk.Menu(self, tearoff=0, bg="#040e1c", fg="#e2e8f0", activebackground="#00f0ff", activeforeground="#01040a")
        self.menu.add_command(label="👁️  See Screen & Analyze", command=self._analyze_screen)
        self.menu.add_command(label="🚀  Open Full Frontend (Stark HUD)", command=self._open_full_hud)
        self.menu.add_command(label="🎙️  Toggle Voice Listening", command=self._toggle_voice)
        self.menu.add_separator()
        self.menu.add_command(label="🎭  Switch to Radon Persona", command=lambda: self._set_persona("radon"))
        self.menu.add_command(label="🤖  Switch to J.A.R.V.I.S. Persona", command=lambda: self._set_persona("jarvis"))
        self.menu.add_separator()
        self.menu.add_command(label="✕   Close Bubble", command=self.destroy)

        # Companion Speech Pill
        self.pill = SpeechPill(self)

        # State & Animation Variables
        self.state = "idle"  # "idle", "listening", "thinking", "speaking"
        self.persona = "jarvis"
        self.breath_phase = 0.0
        self.ring_angle = 0.0

        # Colors
        self.palette = {
            "idle": {"glow": "#00f0ff", "core": "#38bdf8", "ring": "#0284c7"},
            "listening": {"glow": "#00ff88", "core": "#4ade80", "ring": "#16a34a"},
            "thinking": {"glow": "#c084fc", "core": "#a855f7", "ring": "#7e22ce"},
            "speaking": {"glow": "#38bdf8", "core": "#00f0ff", "ring": "#0369a1"},
            "radon": {"glow": "#ffaa00", "core": "#fbbf24", "ring": "#d97706"},
        }

        # WebSocket Connection
        self.ws = None
        self.ws_loop = None
        self._start_ws_client()

        # Start 60 FPS Animation Loop
        self._animate()

    def _on_mouse_down(self, event):
        self._drag_start["x"] = event.x
        self._drag_start["y"] = event.y
        self._drag_start["root_x"] = self.winfo_x()
        self._drag_start["root_y"] = self.winfo_y()
        self._moved = False

    def _on_mouse_drag(self, event):
        dx = event.x - self._drag_start["x"]
        dy = event.y - self._drag_start["y"]
        if abs(dx) > 3 or abs(dy) > 3:
            self._moved = True
        new_x = self.winfo_x() + dx
        new_y = self.winfo_y() + dy
        self.geometry(f"+{new_x}+{new_y}")

    def _on_mouse_up(self, event):
        # If user simply clicked without dragging, toggle voice interaction
        if not self._moved:
            self._toggle_voice()

    def _on_double_click(self, event):
        self._open_full_hud()

    def _show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _open_full_hud(self):
        """Maximize and open the full frontend in default web browser."""
        self.pill.show_message("◈ STARK HUD", "Expanding full neural workspace in browser...", duration=3000)
        webbrowser.open(HUD_URL)

    def _analyze_screen(self):
        """Screen Vision: Captures screen and asks Jarvis to analyze active window."""
        self.pill.show_message("◈ OPTICAL SENSORS", "Scanning desktop and active window...", duration=4000)
        self.state = "thinking"
        # Dispatch query to websocket
        self._send_ws({"type": "text", "text": "Look at my screen and tell me what is open and what you observe"})

    def _toggle_voice(self):
        """Toggle speech listening state."""
        if self.state == "listening":
            self.state = "thinking"
            self.pill.show_message("◈ AUDIO MATRIX", "Processing verbal input...", duration=2500)
        else:
            self.state = "listening"
            self.pill.show_message("◈ AUDIO MATRIX", "Listening... Speak your command, Sir.", duration=5000)

    def _set_persona(self, mode):
        self.persona = mode
        self._send_ws({"type": "set_chat_persona", "persona": mode})
        self.pill.show_message("◈ PERSONA MATRIX", f"Active Persona set to: {mode.upper()}", duration=3000)

    def _send_ws(self, payload):
        if self.ws_loop and self.ws:
            asyncio.run_coroutine_threadsafe(self._async_send(payload), self.ws_loop)

    async def _async_send(self, payload):
        try:
            if self.ws:
                await self.ws.send(json.dumps(payload))
        except Exception as e:
            print(f"WS send error: {e}")

    def _start_ws_client(self):
        def run_loop():
            self.ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.ws_loop)
            self.ws_loop.run_until_complete(self._ws_handler())

        threading.Thread(target=run_loop, daemon=True).start()

    async def _ws_handler(self):
        import websockets
        while True:
            try:
                async with websockets.connect(WS_URL) as websocket:
                    self.ws = websocket
                    self.after(0, lambda: self.pill.show_message("◈ J.A.R.V.I.S.", "Sentinel Bubble Connected // Online", 3000))
                    while True:
                        raw = await websocket.recv()
                        msg = json.loads(raw)
                        self.after(0, self._process_ws_msg, msg)
            except Exception as e:
                self.ws = None
                await asyncio.sleep(3)

    def _process_ws_msg(self, msg):
        mtype = msg.get("type")
        if mtype in ("say", "say_text"):
            text = msg.get("text", "")
            self.state = "speaking"
            self.pill.show_message("◈ J.A.R.V.I.S.", text, duration=8000)
            self.after(5000, lambda: setattr(self, "state", "idle"))
        elif mtype == "user_heard":
            text = msg.get("text", "")
            self.pill.show_message("◈ HEARD", f'"{text}"', duration=4000)
        elif mtype == "state":
            self.state = msg.get("s", "idle")
        elif mtype == "chat_persona_update":
            self.persona = msg.get("persona", "jarvis")

    def _animate(self):
        """60 FPS Organic Breathing Animation."""
        self.canvas.delete("all")

        cx = self.size / 2
        cy = self.size / 2

        # Breathing Physics: Sine wave calculation
        self.breath_phase = (self.breath_phase + 0.055) % (math.pi * 2)
        breath = math.sin(self.breath_phase)  # -1.0 to +1.0

        self.ring_angle = (self.ring_angle + (3.5 if self.state == "thinking" else 1.2)) % 360

        # Select color palette based on persona and state
        current_palette = self.palette.get("radon" if self.persona == "radon" else self.state, self.palette["idle"])
        glow_color = current_palette["glow"]
        core_color = current_palette["core"]
        ring_color = current_palette["ring"]

        # 1. Outer Soft Breathing Aura Halo
        halo_radius = 42 + breath * 4.5
        self.canvas.create_oval(
            cx - halo_radius, cy - halo_radius,
            cx + halo_radius, cy + halo_radius,
            fill="", outline=glow_color, width=1.5
        )

        # 2. Secondary Pulsing Glow Disc
        disc_radius = 35 + breath * 3.0
        self.canvas.create_oval(
            cx - disc_radius, cy - disc_radius,
            cx + disc_radius, cy + disc_radius,
            fill="#031024", outline=ring_color, width=2.0
        )

        # 3. Rotating Cybernetic Segmented Arc Ring
        arc_radius = 31 + breath * 1.5
        for offset in (0, 120, 240):
            start = (self.ring_angle + offset) % 360
            self.canvas.create_arc(
                cx - arc_radius, cy - arc_radius,
                cx + arc_radius, cy + arc_radius,
                start=start, extent=55,
                style="arc", outline=glow_color, width=2.5
            )

        # 4. Inner Breathing Arc Reactor Core
        core_radius = 21 + breath * 2.2
        self.canvas.create_oval(
            cx - core_radius, cy - core_radius,
            cx + core_radius, cy + core_radius,
            fill=core_color, outline="#ffffff", width=1.5
        )

        # 5. Center Brilliant White Spark
        center_r = 7 + breath * 1.0
        self.canvas.create_oval(
            cx - center_r, cy - center_r,
            cx + center_r, cy + center_r,
            fill="#ffffff", outline=""
        )

        # Next frame in ~16ms (~60 FPS)
        self.after(16, self._animate)


def main():
    app = DesktopSentinelBubble()
    app.mainloop()


if __name__ == "__main__":
    main()
