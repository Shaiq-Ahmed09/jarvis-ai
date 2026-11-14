"""J.A.R.V.I.S. Native Windows Floating Corner Sentinel Overlay
Always-on-top, draggable cybernetic Stark Arc Reactor bubble.
Connects directly to the J.A.R.V.I.S. Core WebSocket server (ws://127.0.0.1:8765/ws).
"""
import sys
import os
import json
import math
import time
import asyncio
import threading
import tkinter as tk
from tkinter import ttk

WS_URL = "ws://127.0.0.1:8765/ws"

class JarvisOverlay(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("J.A.R.V.I.S. Sentinel")
        self.overrideredirect(True)      # Borderless frameless window
        self.wm_attributes("-topmost", True)  # Always on top of all Windows apps
        self.wm_attributes("-alpha", 0.94)    # Sleek cybernetic translucency

        # Geometry: 280px wide x 340px tall, positioned at bottom right corner
        self.width = 280
        self.height = 340
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        start_x = screen_w - self.width - 24
        start_y = screen_h - self.height - 60
        self.geometry(f"{self.width}x{self.height}+{start_x}+{start_y}")
        self.configure(bg="#020813")

        # Draggable state
        self._drag_data = {"x": 0, "y": 0}
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)

        # Communication & state
        self.ws = None
        self.loop = None
        self.state = "idle" # idle, listening, thinking, speaking
        self.anim_angle = 0
        self.pulse_phase = 0
        self.is_compact = False

        self._build_ui()
        self._start_ws_thread()
        self._animate()

    def _build_ui(self):
        # Outer Glowing Frame
        self.outer_frame = tk.Frame(self, bg="#020813", highlightbackground="#00f0ff", highlightthickness=1)
        self.outer_frame.pack(fill="both", expand=True)

        # Header Bar
        self.header = tk.Frame(self.outer_frame, bg="#041224", height=28)
        self.header.pack(fill="x", side="top", padx=1, pady=1)

        self.title_lbl = tk.Label(
            self.header, text="◈ J.A.R.V.I.S. // SENTINEL",
            fg="#00f0ff", bg="#041224", font=("Consolas", 9, "bold")
        )
        self.title_lbl.pack(side="left", padx=8, pady=4)
        self.title_lbl.bind("<Button-1>", self._start_drag)
        self.title_lbl.bind("<B1-Motion>", self._on_drag)

        # Window Controls
        self.btn_close = tk.Label(self.header, text="✕", fg="#ff4455", bg="#041224", font=("Consolas", 10, "bold"), cursor="hand2")
        self.btn_close.pack(side="right", padx=6)
        self.btn_close.bind("<Button-1>", lambda e: self.destroy())

        self.btn_min = tk.Label(self.header, text="−", fg="#00f0ff", bg="#041224", font=("Consolas", 12, "bold"), cursor="hand2")
        self.btn_min.pack(side="right", padx=4)
        self.btn_min.bind("<Button-1>", self._toggle_compact)

        # Content Body
        self.body = tk.Frame(self.outer_frame, bg="#020813")
        self.body.pack(fill="both", expand=True, padx=8, pady=6)

        # Arc Reactor Canvas
        self.canvas = tk.Canvas(self.body, width=90, height=90, bg="#020813", highlightthickness=0)
        self.canvas.pack(pady=4)

        # Speech HUD Status Pill
        self.hud_lbl = tk.Label(
            self.body, text="🟢 ATTENTIVE // SAY 'JARVIS'",
            fg="#00ff88", bg="#04181a", font=("Consolas", 8, "bold"),
            padx=6, pady=3, relief="groove", borderwidth=1
        )
        self.hud_lbl.pack(fill="x", pady=4)

        # Transcript / Response Bubble Box
        self.msg_box = tk.Label(
            self.body, text="J.A.R.V.I.S. is vigilant.\nAttentive across all apps, Sir.",
            fg="#cfd8dc", bg="#031020", font=("Segoe UI", 9),
            wraplength=250, justify="left", padx=8, pady=6,
            relief="sunken", borderwidth=1, anchor="nw", height=4
        )
        self.msg_box.pack(fill="both", expand=True, pady=4)

        # Input & Transmit Bar
        self.input_frame = tk.Frame(self.body, bg="#020813")
        self.input_frame.pack(fill="x", pady=2)

        self.cmd_entry = tk.Entry(
            self.input_frame, bg="#041224", fg="#ffffff", insertbackground="#00f0ff",
            font=("Segoe UI", 9), relief="flat", highlightbackground="#00f0ff", highlightthickness=1
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=3)
        self.cmd_entry.bind("<Return>", self._send_text_command)

        self.btn_send = tk.Button(
            self.input_frame, text="SEND", bg="#00f0ff", fg="#020813",
            font=("Consolas", 8, "bold"), relief="flat", cursor="hand2",
            command=self._send_text_command
        )
        self.btn_send.pack(side="right")

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")

    def _toggle_compact(self, event=None):
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.body.pack_forget()
            self.geometry(f"{self.width}x32")
            self.btn_min.config(text="+")
        else:
            self.geometry(f"{self.width}x{self.height}")
            self.body.pack(fill="both", expand=True, padx=8, pady=6)
            self.btn_min.config(text="−")

    def _animate(self):
        """Draw animated rotating Arc Reactor rings & pulsing core."""
        self.anim_angle = (self.anim_angle + 3) % 360
        self.pulse_phase = (self.pulse_phase + 0.1) % (math.pi * 2)

        self.canvas.delete("all")
        cx, cy = 45, 45

        # Colors based on state
        if self.state == "listening":
            ring_color = "#ffaa00"
            core_color = "#ffe082"
        elif self.state == "thinking":
            ring_color = "#00f0ff"
            core_color = "#80deea"
        elif self.state == "speaking":
            ring_color = "#ffb300"
            core_color = "#ffffff"
        else:
            ring_color = "#00f0ff"
            core_color = "#00f0ff"

        # Outer dashed arc ring
        r_outer = 38
        self.canvas.create_arc(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            start=self.anim_angle, extent=120, outline=ring_color, width=2, style="arc"
        )
        self.canvas.create_arc(
            cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,
            start=(self.anim_angle + 180) % 360, extent=120, outline=ring_color, width=2, style="arc"
        )

        # Counter-rotating inner ring
        r_inner = 26
        inner_angle = (360 - self.anim_angle * 1.5) % 360
        self.canvas.create_arc(
            cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
            start=inner_angle, extent=90, outline=ring_color, width=1.5, style="arc"
        )
        self.canvas.create_arc(
            cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
            start=(inner_angle + 180) % 360, extent=90, outline=ring_color, width=1.5, style="arc"
        )

        # Pulsing Core
        pulse_val = 14 + math.sin(self.pulse_phase) * 3
        self.canvas.create_oval(
            cx - pulse_val, cy - pulse_val, cx + pulse_val, cy + pulse_val,
            fill=core_color, outline="#ffffff", width=1
        )

        self.after(45, self._animate)

    def _start_ws_thread(self):
        t = threading.Thread(target=self._ws_worker, daemon=True)
        t.start()

    def _ws_worker(self):
        import websockets
        async def run():
            while True:
                try:
                    async with websockets.connect(WS_URL) as ws:
                        self.ws = ws
                        self.after(0, lambda: self.hud_lbl.config(
                            text="🟢 ATTENTIVE // SAY 'JARVIS'", fg="#00ff88", bg="#04181a"
                        ))
                        async for msg in ws:
                            data = json.loads(msg)
                            self._handle_ws_msg(data)
                except Exception as e:
                    self.ws = None
                    self.after(0, lambda: self.hud_lbl.config(
                        text="⚠️ LINK RECONNECTING...", fg="#ffaa00", bg="#1a1402"
                    ))
                    await asyncio.sleep(2)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(run())

    def _handle_ws_msg(self, data):
        mtype = data.get("type")
        if mtype == "say_text":
            text = data.get("text", "")
            self.after(0, lambda: self._update_response(text))
        elif mtype == "user_heard":
            text = data.get("text", "")
            self.after(0, lambda: self._update_user_text(text))
        elif mtype == "state":
            s = data.get("s", "idle")
            self.after(0, lambda: self._set_state(s))

    def _update_response(self, text):
        self.state = "speaking"
        self.msg_box.config(text=text)
        self.hud_lbl.config(text="⚡ J.A.R.V.I.S. ONLINE", fg="#00f0ff")

    def _update_user_text(self, text):
        self.state = "thinking"
        self.msg_box.config(text=f"Sir: {text}")
        self.hud_lbl.config(text=f"⚡ COMMAND: \"{text[:20]}...\"", fg="#ffaa00")

    def _set_state(self, s):
        self.state = s
        if s == "thinking":
            self.hud_lbl.config(text="⚡ PROCESSING PROTOCOL...", fg="#00f0ff")
        elif s == "idle":
            self.hud_lbl.config(text="🟢 ATTENTIVE // SAY 'JARVIS'", fg="#00ff88", bg="#04181a")

    def _send_text_command(self, event=None):
        txt = self.cmd_entry.get().strip()
        if not txt:
            return
        self.cmd_entry.delete(0, "end")
        self.msg_box.config(text=f"Sir: {txt}")
        self.hud_lbl.config(text="⚡ DISPATCHING...", fg="#00f0ff")

        if self.ws and self.loop:
            payload = json.dumps({"type": "task", "text": txt})
            asyncio.run_coroutine_threadsafe(self.ws.send(payload), self.loop)

if __name__ == "__main__":
    app = JarvisOverlay()
    app.mainloop()
