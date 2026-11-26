"""
J.A.R.V.I.S. Floating Desktop Sentinel Bubble
=============================================
A native Windows always-on-top, transparent, draggable circular AI companion orb.
Floats smoothly over all open applications, tabs, and desktop windows.

Features:
- Pure circular transparency with zero borders or window chrome
- Organic breathing glow physics (smooth 60 FPS sine-wave animation loop)
- Free draggable movement anywhere on the desktop
- Single Click: Toggle voice interaction / Speech Pill
- Double Click: Maximize & open full Stark HUD frontend in browser
- Right Click: Context menu with "👁️ See My Screen", "🚀 Maximize", "🎙️ Talk", "✕ Close"
- Companion Speech Pill: Non-activating translucent speech card beside the bubble
- Screen Vision: Captures screen and asks J.A.R.V.I.S. to analyze active windows
"""

import sys
import os
import json
import math
import time
import asyncio
import threading
import subprocess
import webbrowser
import ctypes
from pathlib import Path

# High-DPI awareness on Windows so coordinates and sizes are pixel-accurate
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32

# CRITICAL: Explicitly attach to the interactive user desktop 'Default' on WinSta0.
# When processes are spawned from background agents, Windows may place them on an isolated
# desktop (e.g. exebox-*). Switching to 'Default' guarantees the window is physically visible on screen!
try:
    h_desk = user32.OpenDesktopW("Default", 0, False, 0x10000000 | 0x01FF)
    if h_desk:
        user32.SetThreadDesktop(h_desk)
except Exception as e:
    print(f"Desktop attach notice: {e}")

import tkinter as tk

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "backend"))

WS_URL = "ws://127.0.0.1:8765/ws"
HUD_URL = "http://localhost:8765"
TRANS_KEY = "#000001"  # Cutout transparent color on Windows


class SpeechPill(tk.Toplevel):
    """Floating translucent speech card beside the bubble without stealing window focus."""
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.94)
        self.configure(bg="#030c1a")
        self.withdraw()

        self.frame = tk.Frame(self, bg="#030c1a", highlightbackground="#00f0ff", highlightthickness=1)
        self.frame.pack(fill="both", expand=True)

        self.title_lbl = tk.Label(
            self.frame, text="◈ J.A.R.V.I.S.", font=("Consolas", 8, "bold"),
            fg="#00f0ff", bg="#030c1a", anchor="w"
        )
        self.title_lbl.pack(fill="x", padx=10, pady=(6, 2))

        self.msg_lbl = tk.Label(
            self.frame, text="", font=("Segoe UI", 9),
            fg="#e2e8f0", bg="#030c1a", justify="left",
            wraplength=270, anchor="w"
        )
        self.msg_lbl.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self._hide_timer = None

    def show(self, title, text, duration_ms=7500):
        if self._hide_timer:
            self.after_cancel(self._hide_timer)

        self.title_lbl.config(text=title)
        self.msg_lbl.config(text=text)

        self.update_idletasks()
        bx = self.master.winfo_x()
        by = self.master.winfo_y()
        sw = self.winfo_screenwidth()

        pw = max(220, min(320, len(text) * 7 + 40))
        ph = max(65, min(180, (len(text) // 30 + 2) * 22 + 30))

        if bx + 140 + pw < sw:
            px = bx + 135
        else:
            px = bx - pw - 10
        py = max(20, by)

        self.geometry(f"{pw}x{ph}+{px}+{py}")
        self.deiconify()
        self.lift()

        self._hide_timer = self.after(duration_ms, self.withdraw)


class DesktopSentinelBubble(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("J.A.R.V.I.S. Desktop Bubble")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-toolwindow", True)
        self.attributes("-transparentcolor", TRANS_KEY)
        self.configure(bg=TRANS_KEY)

        # Bubble Dimensions: 130x130 px (clearly visible, easy to click and move)
        self.size = 130
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.x = screen_w - self.size - 50
        self.y = screen_h - self.size - 130
        self.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        # Canvas for the breathing circle
        self.canvas = tk.Canvas(
            self, width=self.size, height=self.size,
            bg=TRANS_KEY, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Dragging state
        self._drag_start = {"x": 0, "y": 0}
        self._is_dragging = False

        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._show_context_menu)

        # Context Menu
        self.menu = tk.Menu(
            self, tearoff=0, bg="#040e1c", fg="#e2e8f0",
            activebackground="#00f0ff", activeforeground="#01040a",
            font=("Segoe UI", 9)
        )
        self.menu.add_command(label="👁️  See My Screen (Vision)", command=self._analyze_screen)
        self.menu.add_command(label="🚀  Maximize / Open Full Frontend", command=self._open_full_hud)
        self.menu.add_command(label="🎙️  Toggle Voice Listening", command=self._toggle_voice)
        self.menu.add_separator()
        self.menu.add_command(label="🎭  Switch to Radon (@redonxd)", command=lambda: self._set_persona("radon"))
        self.menu.add_command(label="🤖  Switch to J.A.R.V.I.S.", command=lambda: self._set_persona("jarvis"))
        self.menu.add_separator()
        self.menu.add_command(label="✕   Close Bubble", command=self.destroy)

        # Speech pill companion
        self.pill = SpeechPill(self)

        # State & Animation Variables
        self.state = "idle"  # "idle", "listening", "thinking", "speaking"
        self.persona = "jarvis"
        self.breath_phase = 0.0
        self.ring_angle = 0.0

        self.colors = {
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

        # Lift & display
        self.lift()
        self.attributes("-topmost", True)
        self.update()

        self._frame_count = 0
        self._setup_topmost_handle()

        # Start Organic Breathing Animation Loop
        self._animate()

    def _setup_topmost_handle(self):
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_uint
            ]
            user32.SetWindowPos.restype = wintypes.BOOL
            w_id = self.winfo_id()
            self.top_hwnd = user32.GetParent(w_id) or w_id
            # HWND_TOPMOST (-1), SWP_NOSIZE (1) | SWP_NOMOVE (2) | SWP_NOACTIVATE (0x10) | SWP_SHOWWINDOW (0x40)
            user32.SetWindowPos(self.top_hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
        except Exception as e:
            print(f"Topmost setup notice: {e}")

    def _on_mouse_down(self, event):
        self._drag_start["x"] = event.x
        self._drag_start["y"] = event.y
        self._is_dragging = False

    def _on_mouse_drag(self, event):
        dx = event.x - self._drag_start["x"]
        dy = event.y - self._drag_start["y"]
        if abs(dx) > 2 or abs(dy) > 2:
            self._is_dragging = True
            new_x = self.winfo_x() + dx
            new_y = self.winfo_y() + dy
            self.geometry(f"+{new_x}+{new_y}")

    def _on_mouse_up(self, event):
        if not self._is_dragging:
            self._toggle_voice()

    def _on_double_click(self, event):
        self._open_full_hud()

    def _show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _open_full_hud(self):
        """Maximize and open the full frontend at http://localhost:8765, restoring browser if minimized."""
        self.pill.show("◈ STARK HUD", "Maximizing full neural workspace in browser...", 3500)
        try:
            import win32gui, win32process, win32con, psutil
            def restore_cb(hwnd, _):
                if win32gui.IsWindow(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        pname = psutil.Process(pid).name().lower()
                        title = win32gui.GetWindowText(hwnd).lower()
                        if any(b in pname for b in ["brave", "chrome", "msedge", "firefox", "opera"]):
                            if any(k in title for k in ["gemini", "jarvis", "localhost", "8765", "bubble", "stark"]):
                                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                return True
            win32gui.EnumWindows(restore_cb, None)
        except Exception:
            pass
        webbrowser.open(HUD_URL)

    def _analyze_screen(self):
        """Screen Vision: Captures screen and asks J.A.R.V.I.S. what is open."""
        self.state = "thinking"
        self.pill.show("◈ OPTICAL SCANNER", "Analyzing screen and active workspace...", 4000)
        self._send_ws({"type": "text", "text": "Look at my screen and tell me what is open and what you observe"})

    def _toggle_voice(self):
        if self.state == "listening":
            self.state = "thinking"
            self.pill.show("◈ AUDIO MATRIX", "Processing audio...", 2500)
        else:
            self.state = "listening"
            self.pill.show("◈ LISTENING", "Speak now, Sir. I am listening.", 4500)

    def _set_persona(self, p):
        self.persona = p
        self._send_ws({"type": "set_chat_persona", "persona": p})
        self.pill.show("◈ PERSONA", f"Switched to {p.upper()} persona", 3000)

    def _send_ws(self, payload):
        if self.ws_loop and self.ws:
            asyncio.run_coroutine_threadsafe(self._async_send(payload), self.ws_loop)

    async def _async_send(self, payload):
        try:
            if self.ws:
                await self.ws.send(json.dumps(payload))
        except Exception as e:
            print(f"WS error: {e}")

    def _start_ws_client(self):
        def loop_runner():
            self.ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.ws_loop)
            self.ws_loop.run_until_complete(self._ws_handler())

        threading.Thread(target=loop_runner, daemon=True).start()

    async def _ws_handler(self):
        import websockets
        while True:
            try:
                async with websockets.connect(WS_URL) as websocket:
                    self.ws = websocket
                    self.after(0, lambda: self.pill.show("◈ J.A.R.V.I.S.", "Sentinel Bubble Active on Desktop", 3000))
                    while True:
                        raw = await websocket.recv()
                        msg = json.loads(raw)
                        self.after(0, self._process_msg, msg)
            except Exception:
                self.ws = None
                await asyncio.sleep(2)

    def _process_msg(self, msg):
        mtype = msg.get("type")
        if mtype in ("say", "say_text"):
            text = msg.get("text", "")
            self.state = "speaking"
            self.pill.show("◈ J.A.R.V.I.S.", text, 8000)
            self.after(6000, lambda: setattr(self, "state", "idle"))
        elif mtype == "user_heard":
            text = msg.get("text", "")
            self.pill.show("◈ HEARD", f'"{text}"', 4000)
        elif mtype == "state":
            self.state = msg.get("s", "idle")
        elif mtype == "chat_persona_update":
            self.persona = msg.get("persona", "jarvis")

    def _animate(self):
        """Smooth 60 FPS Organic Breathing Physics Loop."""
        self.canvas.delete("all")

        cx = self.size / 2
        cy = self.size / 2

        # Sine wave breathing calculation
        self.breath_phase = (self.breath_phase + 0.052) % (math.pi * 2)
        breath = math.sin(self.breath_phase)  # -1.0 to +1.0

        # Cybernetic arc rotation
        speed = 4.0 if self.state == "thinking" else 1.2
        self.ring_angle = (self.ring_angle + speed) % 360

        pal = self.colors.get("radon" if self.persona == "radon" else self.state, self.colors["idle"])
        glow_col = pal["glow"]
        core_col = pal["core"]
        ring_col = pal["ring"]

        # 1. Base Solid Cyberpunk Disc (fills entire circle so clicks & drags register 100%)
        r_base = 50 + breath * 3.5
        self.canvas.create_oval(
            cx - r_base, cy - r_base,
            cx + r_base, cy + r_base,
            fill="#030d1e", outline=glow_col, width=2.5
        )

        # 2. Secondary Glowing Halo Ring
        r_halo = 44 + breath * 2.5
        self.canvas.create_oval(
            cx - r_halo, cy - r_halo,
            cx + r_halo, cy + r_halo,
            fill="", outline=ring_col, width=1.5
        )

        # 3. Rotating Cybernetic Segmented Arc Ring (Stark Mark VII Gyro)
        r_arc = 37 + breath * 1.5
        for offset in (0, 120, 240):
            start = (self.ring_angle + offset) % 360
            self.canvas.create_arc(
                cx - r_arc, cy - r_arc,
                cx + r_arc, cy + r_arc,
                start=start, extent=55,
                style="arc", outline=glow_col, width=3.0
            )

        # 4. Inner Breathing Arc Reactor Core
        r_core = 24 + breath * 2.2
        self.canvas.create_oval(
            cx - r_core, cy - r_core,
            cx + r_core, cy + r_core,
            fill=core_col, outline="#ffffff", width=1.5
        )

        # 5. Brilliant Center White Core Spark
        r_spark = 9 + breath * 1.0
        self.canvas.create_oval(
            cx - r_spark, cy - r_spark,
            cx + r_spark, cy + r_spark,
            fill="#ffffff", outline=""
        )

        # Periodically ensure topmost without stealing focus
        self._frame_count += 1
        if self._frame_count % 60 == 0:
            try:
                from ctypes import wintypes
                ctypes.windll.user32.SetWindowPos(self.top_hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            except Exception:
                pass

        # 16 ms = ~60 FPS
        self.after(16, self._animate)


def main():
    app = DesktopSentinelBubble()
    app.mainloop()


if __name__ == "__main__":
    main()
