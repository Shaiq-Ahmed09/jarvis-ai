"""
J.A.R.V.I.S. Floating Desktop Sentinel Bubble UI (PySide6)
===========================================================
High-End Sci-Fi HUD AI Orb with Smooth 60 FPS Physics & Windows 11 Translucency.

Features:
- 60 FPS Multi-Layer QPainter Orb (96x96 canvas, 60x60 core):
  * Outer radial ambient glow fading to 0 before window boundaries
  * Two counter-rotating broken HUD arcs with dynamic angular velocity
  * Multi-stop QRadialGradient inner core with orbital focal point
  * Top-left glass specular crescent highlight for 3D depth
- State-Reactive Animations:
  * Idle: 3.5s sinusoidal breathing glow in cyan/electric blue (#00F0FF / #2563EB)
  * Hover: Smooth scale-up (1.0 to 1.12) via QEasingCurve.OutBack and increased arc brightness
  * Listening: Palette shift to emerald/amber with set_audio_level(float) dynamic radius modulation
  * Thinking: 4x accelerated HUD arc rotation with violet-cyan gradient sweep
- Magnetic Screen-Edge Snapping:
  * Snaps 24px from closest left/right screen edge after dragging, vertically clamped
- Windows 11 DWM Blur & Glassmorphism:
  * Native Acrylic / DWM BlurBehind integration (rgba(12, 16, 26, 220), 16px radius, glowing border)
  * 220ms QEasingCurve.OutExpo expansion/collapse anchored from bubble position
  * Synchronized live animated mini-orb in popup header
"""

import sys
import math
import ctypes
from ctypes import wintypes
from PySide6.QtCore import (
    Qt, QRect, QRectF, QPoint, QTimer, QPropertyAnimation,
    QEasingCurve, Signal, Property
)
from PySide6.QtGui import (
    QPainter, QRadialGradient, QLinearGradient, QColor, QPen, QBrush,
    QFont, QCursor, QKeyEvent
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QApplication, QSizePolicy
)

from jarvis_client import JarvisClient

# Windows Default Desktop Attach for reliable monitor mapping
try:
    user32 = ctypes.windll.user32
    h_desk = user32.OpenDesktopW("Default", 0, False, 0x10000000 | 0x01FF)
    if h_desk:
        user32.SetThreadDesktop(h_desk)
except Exception:
    pass


def enable_windows_translucency(hwnd: int):
    """Enables Windows 11 DWM Acrylic / BlurBehind on the top-level window."""
    if sys.platform != "win32":
        return

    # 1. Windows 11 DwmSetWindowAttribute (Build 22000+)
    try:
        dwmapi = ctypes.windll.dwmapi
        # DWMWA_SYSTEMBACKDROP_TYPE = 38, DWMSBT_TRANSIENTWINDOW = 3 (Acrylic)
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMSBT_TRANSIENTWINDOW = 3
        backdrop = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception:
        pass

    # 2. SetWindowCompositionAttribute (Universal Windows 10/11 Acrylic / BlurBehind fallback)
    try:
        user32 = ctypes.windll.user32

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int),
            ]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        policy = ACCENT_POLICY()
        policy.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND (or 3 for BLURBEHIND)
        policy.AccentFlags = 2
        # GradientColor in AABBGGRR: A=220 (0xDC), B=26 (0x1A), G=16 (0x10), R=12 (0x0C) -> rgba(12, 16, 26, 220)
        policy.GradientColor = 0xDC1A100C
        policy.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.byref(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)

        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        pass


class MiniOrbWidget(QWidget):
    """Synchronized live animated mini-orb widget in the popup header."""
    def __init__(self, parent_bubble):
        super().__init__()
        self.bubble = parent_bubble
        self.setFixedSize(26, 26)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = 13.0, 13.0
        r = 10.0

        # Mini rotating arc
        arc_pen = QPen(QColor("#00f0ff") if self.bubble.state != "thinking" else QColor("#c084fc"), 1.4)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), int(self.bubble._ring_angle_outer * 16), int(120 * 16))

        # Core orb
        grad = QRadialGradient(cx, cy, 7.0)
        if self.bubble.state == "listening":
            grad.setColorAt(0.0, QColor("#10b981"))
            grad.setColorAt(1.0, QColor("#022c22"))
        elif self.bubble.state == "thinking":
            grad.setColorAt(0.0, QColor("#c084fc"))
            grad.setColorAt(1.0, QColor("#3b0764"))
        else:
            grad.setColorAt(0.0, QColor("#00f0ff"))
            grad.setColorAt(1.0, QColor("#0f172a"))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPoint(int(cx), int(cy)), 6, 6)

        # Center spark
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPoint(int(cx), int(cy)), 2, 2)


class ChatMessageBubble(QFrame):
    """Custom styled chat message card for user and Jarvis replies."""
    def __init__(self, text: str, is_user: bool = False):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        sender_label = QLabel("YOU" if is_user else "◈ J.A.R.V.I.S.")
        sender_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        sender_label.setStyleSheet("color: #00f0ff;" if not is_user else "color: #94a3b8;")

        msg_label = QLabel(text)
        msg_label.setFont(QFont("Segoe UI", 9))
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        if is_user:
            self.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                    border: 1px solid rgba(0, 240, 255, 0.4);
                    border-radius: 12px;
                    border-bottom-right-radius: 2px;
                }
                QLabel { color: #f8fafc; }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: rgba(8, 14, 26, 0.85);
                    border: 1px solid rgba(59, 130, 246, 0.35);
                    border-radius: 12px;
                    border-top-left-radius: 2px;
                }
                QLabel { color: #e2e8f0; }
            """)

        layout.addWidget(sender_label)
        layout.addWidget(msg_label)


class ChatInput(QLineEdit):
    """Custom QLineEdit capturing Enter to send and Esc to collapse."""
    send_requested = Signal()
    collapse_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not event.modifiers() & Qt.ShiftModifier:
                self.send_requested.emit()
                return
        elif event.key() == Qt.Key_Escape:
            self.collapse_requested.emit()
            return
        super().keyPressEvent(event)


class DesktopAIBubble(QWidget):
    """
    Main PySide6 Window:
    - Collapsed: 96x96 frameless sci-fi HUD AI orb (60x60 core, 60 FPS multi-layer physics).
    - Expanded: 380x480 Windows 11 DWM glassmorphic neural assistant card.
    """
    def __init__(self, backend_url: str = "http://localhost:8000"):
        super().__init__()

        self.backend_url = backend_url
        self.is_expanded = False
        self.state = "idle"  # "idle", "listening", "thinking"
        self._is_dragging = False
        self._drag_start = QPoint()
        self._start_pos = QPoint()
        self._dock_side = "right"  # "left" or "right"

        # Animation state variables
        self._breath_phase = 0.0      # 3.5s sinusoidal breathing cycle
        self._orbit_phase = 0.0       # Gentle orbital focal point
        self._ring_angle_outer = 0.0  # Outer clockwise broken arc
        self._ring_angle_inner = 0.0  # Inner counter-clockwise broken arc
        self._hover_scale = 1.0       # Hover scale factor (1.0 to 1.12)
        self._audio_level = 0.0       # Mic RMS audio level (0.0 to 1.0)

        # Backend Client
        self.client = JarvisClient(self.backend_url)
        self.client.response_received.connect(self._on_ai_response)
        self.client.error_occurred.connect(self._on_ai_error)
        self.client.status_changed.connect(self._on_status_changed)
        self.client.thinking_started.connect(self._on_thinking_started)

        # Window Flags & Attributes
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setMouseTracking(True)

        # Build UI layout (Glassmorphic card container)
        self._build_ui()

        # Expansion/Collapse Geometry Animation (220ms, QEasingCurve.OutExpo)
        self.geom_anim = QPropertyAnimation(self, b"geometry")
        self.geom_anim.setDuration(220)
        self.geom_anim.setEasingCurve(QEasingCurve.OutExpo)
        self.geom_anim.finished.connect(self._on_anim_finished)

        # Magnetic Edge Snapping Animation (QEasingCurve.OutCubic, 280ms)
        self.snap_anim = QPropertyAnimation(self, b"pos")
        self.snap_anim.setDuration(280)
        self.snap_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Hover Scale Animation (QEasingCurve.OutBack, 180ms)
        self.hover_anim = QPropertyAnimation(self, b"hover_scale")
        self.hover_anim.setDuration(180)
        self.hover_anim.setEasingCurve(QEasingCurve.OutBack)

        # 60 FPS Render Timer for breathing, rotating, pulsing physics
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_render_tick)
        self.anim_timer.start(16)

        # Start anchored 24px from bottom-right of primary screen
        self.reset_to_default_position()

    # -------------------------------------------------------------------------
    # Properties for Animations
    # -------------------------------------------------------------------------
    def get_hover_scale(self) -> float:
        return self._hover_scale

    def set_hover_scale(self, val: float):
        self._hover_scale = val
        if not self.is_expanded:
            self.update()

    hover_scale = Property(float, get_hover_scale, set_hover_scale)

    def set_audio_level(self, level: float):
        """Modulates listening state aura and ring radius dynamically (0.0 to 1.0)."""
        self._audio_level = max(0.0, min(1.0, float(level)))

    # -------------------------------------------------------------------------
    # UI Construction (Glassmorphic Card)
    # -------------------------------------------------------------------------
    def _build_ui(self):
        """Constructs the dark glassmorphic popup card layout."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("chatCard")
        # Glassmorphic card styling matching Windows 11 Acrylic blur
        self.card.setStyleSheet("""
            #chatCard {
                background: rgba(12, 16, 26, 220);
                border: 1px solid rgba(0, 240, 255, 0.4);
                border-radius: 16px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        # 1. Top Bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        # Live Mini-Orb
        self.mini_orb = MiniOrbWidget(self)
        top_bar.addWidget(self.mini_orb)

        # Title
        title_lbl = QLabel("J.A.R.V.I.S.")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #00f0ff; letter-spacing: 1px; margin-left: 2px;")
        top_bar.addWidget(title_lbl)

        # Connection Status Pill
        self.status_pill = QLabel("● OFFLINE")
        self.status_pill.setFont(QFont("Consolas", 8, QFont.Bold))
        self.status_pill.setStyleSheet("""
            QLabel {
                color: #ef4444;
                background: rgba(239, 68, 68, 0.12);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 10px;
                padding: 3px 8px;
            }
        """)
        top_bar.addWidget(self.status_pill)
        top_bar.addStretch()

        # Open Full Web HUD Button
        self.btn_hud = QPushButton("🌐")
        self.btn_hud.setObjectName("btnHUD")
        self.btn_hud.setToolTip("Open Full Stark HUD & Telemetry (http://localhost:8765)")
        self.btn_hud.setFixedSize(28, 28)
        self.btn_hud.setCursor(Qt.PointingHandCursor)
        self.btn_hud.clicked.connect(self._open_web_hud)

        # Mic Toggle Button
        self.btn_mic = QPushButton("🎙️")
        self.btn_mic.setObjectName("btnMic")
        self.btn_mic.setToolTip("Toggle Voice Listening")
        self.btn_mic.setFixedSize(28, 28)
        self.btn_mic.setCursor(Qt.PointingHandCursor)
        self.btn_mic.clicked.connect(self._toggle_mic)

        # Minimize Button
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("btnMinimize")
        self.btn_min.setToolTip("Minimize to Desktop Bubble (Esc)")
        self.btn_min.setFixedSize(28, 28)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.collapse_bubble)

        self.card.setStyleSheet(self.card.styleSheet() + """
            QPushButton#btnMic, QPushButton#btnMinimize, QPushButton#btnHUD {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 14px;
                color: #00f0ff;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btnMic:hover, QPushButton#btnMinimize:hover, QPushButton#btnHUD:hover {
                background: rgba(0, 240, 255, 0.22);
                border-color: #00f0ff;
            }
        """)

        top_bar.addWidget(self.btn_hud)
        top_bar.addWidget(self.btn_mic)
        top_bar.addWidget(self.btn_min)
        card_layout.addLayout(top_bar)

        # 2. Scrollable Chat History
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 240, 255, 0.3);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00f0ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        card_layout.addWidget(self.scroll_area, 1)

        # Initial Welcome Message
        self._append_message("Greetings, Sir. Neural companion online. How may I assist you?", is_user=False)

        # 3. Input Bar
        self.input_field = ChatInput()
        self.input_field.setPlaceholderText("Ask J.A.R.V.I.S. (Return to send, Esc to minimize)...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(2, 6, 23, 0.85);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 12px;
                color: #e2e8f0;
                padding: 10px 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00f0ff;
                background: rgba(2, 6, 23, 0.98);
            }
        """)
        self.input_field.send_requested.connect(self._on_send_prompt)
        self.input_field.collapse_requested.connect(self.collapse_bubble)
        card_layout.addWidget(self.input_field)

        self.main_layout.addWidget(self.card)
        self.card.hide()  # Collapsed initially

    def reset_to_default_position(self):
        """Anchors the 96x96 bubble 24px away from bottom-right of primary screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        bx = screen.right() - 96 - 24
        by = screen.bottom() - 96 - 48
        self.setGeometry(bx, by, 96, 96)
        self._dock_side = "right"

    # -------------------------------------------------------------------------
    # 60 FPS Physics & Render Loop
    # -------------------------------------------------------------------------
    def _on_render_tick(self):
        # 1. 3.5s Sinusoidal Breathing Cycle (2*pi / (3.5 * 60) ~= 0.0299 rad/frame)
        self._breath_phase = (self._breath_phase + 0.0299) % (math.pi * 2)

        # 2. Orbital Core Focal Point Motion
        self._orbit_phase = (self._orbit_phase + 0.024) % (math.pi * 2)

        # 3. Dynamic Angular Velocities for Counter-Rotating HUD Arcs
        if self.state == "thinking":
            v_outer = 6.4   # 4x Accelerated clockwise rotation
            v_inner = -4.8  # 4x Accelerated counter-clockwise rotation
        else:
            v_outer = 1.6   # Smooth steady clockwise rotation
            v_inner = -1.2  # Smooth steady counter-clockwise rotation

        self._ring_angle_outer = (self._ring_angle_outer + v_outer) % 360
        self._ring_angle_inner = (self._ring_angle_inner + v_inner) % 360

        # 4. Audio level smooth decay back to baseline
        if self._audio_level > 0.005:
            self._audio_level *= 0.88
        else:
            self._audio_level = 0.0

        if not self.is_expanded:
            self.update()
        else:
            if hasattr(self, "mini_orb"):
                self.mini_orb.update()

    # -------------------------------------------------------------------------
    # Multi-Layer QPainter Sci-Fi HUD Orb (96x96 Canvas, 60x60 Core)
    # -------------------------------------------------------------------------
    def paintEvent(self, event):
        if self.is_expanded:
            return  # QSS + DWM Blur handles expanded card layout

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        cx, cy = 48.0, 48.0
        breath = math.sin(self._breath_phase)  # -1.0 to +1.0
        glow_boost = 1.25 if self._hover_scale > 1.01 else 1.0

        # Apply Hover Scale with OutBack Physics around Center
        painter.save()
        if abs(self._hover_scale - 1.0) > 0.001:
            painter.translate(cx, cy)
            painter.scale(self._hover_scale, self._hover_scale)
            painter.translate(-cx, -cy)

        # ---------------------------------------------------------------------
        # LAYER 1: Soft Outer Radial Ambient Glow (Fades to 0 before 96px bounds)
        # ---------------------------------------------------------------------
        ambient_r = 45.0 + breath * 1.5
        ambient_glow = QRadialGradient(cx, cy, ambient_r)

        if self.state == "listening":
            # Emerald / Amber Listening Shift
            base_a = int(min(255, (160 + self._audio_level * 95) * glow_boost))
            ambient_glow.setColorAt(0.0, QColor(16, 185, 129, base_a))
            ambient_glow.setColorAt(0.55, QColor(245, 158, 11, int(70 * glow_boost)))
            ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        elif self.state == "thinking":
            # Violet-Cyan Thinking Gradient Sweep
            base_a = int(min(255, 190 * glow_boost))
            ambient_glow.setColorAt(0.0, QColor(192, 132, 252, base_a))
            ambient_glow.setColorAt(0.55, QColor(0, 240, 255, int(90 * glow_boost)))
            ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:
            # Idle: Smooth 3.5s Sinusoidal Cyan / Electric Blue (#00F0FF / #2563EB)
            base_a = int((140 + breath * 45) * glow_boost)
            ambient_glow.setColorAt(0.0, QColor(0, 240, 255, base_a))
            ambient_glow.setColorAt(0.50, QColor(37, 99, 235, int((75 + breath * 20) * glow_boost)))
            ambient_glow.setColorAt(0.85, QColor(30, 27, 75, int(35 * glow_boost)))
            ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(ambient_glow))
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(ambient_r), int(ambient_r))

        # ---------------------------------------------------------------------
        # LAYER 2: Outer Clockwise Broken HUD Arc (Radius ~39px)
        # ---------------------------------------------------------------------
        r_outer_arc = 39.0 + (self._audio_level * 3.0 if self.state == "listening" else 0.0)
        arc_pen_out = QPen()
        arc_pen_out.setWidthF(2.0)
        arc_pen_out.setCapStyle(Qt.RoundCap)

        if self.state == "listening":
            arc_pen_out.setColor(QColor(16, 185, 129, int(220 * glow_boost)))
        elif self.state == "thinking":
            arc_pen_out.setColor(QColor(192, 132, 252, int(240 * glow_boost)))
        else:
            arc_pen_out.setColor(QColor(0, 240, 255, int((190 + breath * 35) * glow_boost)))

        painter.setPen(arc_pen_out)
        painter.setBrush(Qt.NoBrush)
        rect_out = QRectF(cx - r_outer_arc, cy - r_outer_arc, r_outer_arc * 2, r_outer_arc * 2)

        # 2 Broken Segments: 70 deg and 110 deg
        painter.drawArc(rect_out, int(self._ring_angle_outer * 16), int(70 * 16))
        painter.drawArc(rect_out, int((self._ring_angle_outer + 180) * 16), int(110 * 16))

        # ---------------------------------------------------------------------
        # LAYER 3: Inner Counter-Clockwise Broken HUD Arc (Radius ~34px)
        # ---------------------------------------------------------------------
        r_inner_arc = 34.0 + (self._audio_level * 4.0 if self.state == "listening" else 0.0)
        arc_pen_in = QPen()
        arc_pen_in.setWidthF(1.8)
        arc_pen_in.setCapStyle(Qt.RoundCap)

        if self.state == "listening":
            arc_pen_in.setColor(QColor(245, 158, 11, int(210 * glow_boost)))
        elif self.state == "thinking":
            arc_pen_in.setColor(QColor(0, 240, 255, int(230 * glow_boost)))
        else:
            arc_pen_in.setColor(QColor(56, 189, 248, int((170 + breath * 30) * glow_boost)))

        painter.setPen(arc_pen_in)
        rect_in = QRectF(cx - r_inner_arc, cy - r_inner_arc, r_inner_arc * 2, r_inner_arc * 2)

        # 3 Broken Segments: 45 deg, 35 deg, 55 deg
        painter.drawArc(rect_in, int(self._ring_angle_inner * 16), int(45 * 16))
        painter.drawArc(rect_in, int((self._ring_angle_inner + 120) * 16), int(35 * 16))
        painter.drawArc(rect_in, int((self._ring_angle_inner + 240) * 16), int(55 * 16))

        # ---------------------------------------------------------------------
        # LAYER 4: Multi-Stop QRadialGradient Inner Core (60x60 Core, Orbital Focal Point)
        # ---------------------------------------------------------------------
        r_core = 30.0 + breath * 0.6 + (self._audio_level * 3.5 if self.state == "listening" else 0.0)
        focal_x = cx + math.cos(self._orbit_phase) * 6.5
        focal_y = cy + math.sin(self._orbit_phase) * 6.5

        core_grad = QRadialGradient(QPoint(int(cx), int(cy)), int(r_core), QPoint(int(focal_x), int(focal_y)))

        if self.state == "listening":
            core_grad.setColorAt(0.0, QColor("#a7f3d0"))
            core_grad.setColorAt(0.35, QColor("#10b981"))
            core_grad.setColorAt(0.70, QColor("#d97706"))
            core_grad.setColorAt(1.0, QColor("#022c22"))
            border_pen = QPen(QColor("#10b981"), 1.8)
        elif self.state == "thinking":
            core_grad.setColorAt(0.0, QColor("#f5d0fe"))
            core_grad.setColorAt(0.35, QColor("#c084fc"))
            core_grad.setColorAt(0.70, QColor("#7c3aed"))
            core_grad.setColorAt(1.0, QColor("#1e1035"))
            border_pen = QPen(QColor("#c084fc"), 1.8)
        else:
            core_grad.setColorAt(0.0, QColor("#a5f3fc"))
            core_grad.setColorAt(0.35, QColor("#00f0ff"))
            core_grad.setColorAt(0.68, QColor("#2563eb"))
            core_grad.setColorAt(0.88, QColor("#1e1b4b"))
            core_grad.setColorAt(1.0, QColor("#030712"))
            border_pen = QPen(QColor(0, 240, 255, int(200 * glow_boost)), 1.8)

        painter.setPen(border_pen)
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(r_core), int(r_core))

        # ---------------------------------------------------------------------
        # LAYER 5: Top-Left Glass Specular Crescent Highlight (Authentic 3D Depth)
        # ---------------------------------------------------------------------
        specular_rect = QRectF(cx - 21.0, cy - 22.0, 28.0, 14.0)
        spec_grad = QLinearGradient(specular_rect.topLeft(), specular_rect.bottomRight())
        spec_grad.setColorAt(0.0, QColor(255, 255, 255, int(130 * glow_boost)))
        spec_grad.setColorAt(0.6, QColor(255, 255, 255, int(45 * glow_boost)))
        spec_grad.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(spec_grad))
        painter.drawEllipse(specular_rect)

        # ---------------------------------------------------------------------
        # LAYER 6: Brilliant Core Center Spark
        # ---------------------------------------------------------------------
        spark_r = 6.5 + breath * 0.4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(spark_r), int(spark_r))

        painter.restore()

    # -------------------------------------------------------------------------
    # Hover Detection (Smooth Scale-Up via QEasingCurve.OutBack)
    # -------------------------------------------------------------------------
    def enterEvent(self, event):
        if not self.is_expanded:
            self.hover_anim.stop()
            self.hover_anim.setDuration(180)
            self.hover_anim.setEasingCurve(QEasingCurve.OutBack)
            self.hover_anim.setStartValue(self._hover_scale)
            self.hover_anim.setEndValue(1.12)
            self.hover_anim.start()
            self.setCursor(Qt.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_expanded:
            self.hover_anim.stop()
            self.hover_anim.setDuration(160)
            self.hover_anim.setEasingCurve(QEasingCurve.OutCubic)
            self.hover_anim.setStartValue(self._hover_scale)
            self.hover_anim.setEndValue(1.0)
            self.hover_anim.start()
            self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

    # -------------------------------------------------------------------------
    # Mouse Dragging & Magnetic Screen-Edge Snapping
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._start_pos = self.pos()
            self._is_dragging = False
            self.snap_anim.stop()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            cur_point = event.globalPosition().toPoint()
            delta = (cur_point - self._drag_start).manhattanLength()
            if delta >= 4:
                self._is_dragging = True
                self.move(self._start_pos + (cur_point - self._drag_start))
                event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._is_dragging:
                # Magnetic Screen-Edge Snapping (24px padding from nearest edge)
                self._perform_magnetic_snap()
            else:
                # Stationary click (< 4px cursor delta)
                self.toggle_expand()
            self._is_dragging = False
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if not self.is_expanded:
            self._open_web_hud()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _open_web_hud(self):
        """Restores or opens the full Stark HUD web interface at http://localhost:8765."""
        import webbrowser
        try:
            import win32gui, win32process, win32con, psutil
            def restore_cb(hwnd, _):
                if win32gui.IsWindow(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        pname = psutil.Process(pid).name().lower()
                        title = win32gui.GetWindowText(hwnd).lower()
                        if any(b in pname for b in ["brave", "chrome", "msedge", "firefox", "opera"]):
                            if any(k in title for k in ["jarvis", "localhost", "8765"]):
                                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                return True
            win32gui.EnumWindows(restore_cb, None)
        except Exception:
            pass
        webbrowser.open("http://localhost:8765")

    def _perform_magnetic_snap(self):
        """Snaps 24px away from nearest left or right screen edge with OutCubic physics."""
        screen = QApplication.primaryScreen().availableGeometry()
        w = self.width()
        h = self.height()
        cur_center_x = self.x() + w / 2

        # Choose left vs right edge
        if cur_center_x < (screen.left() + screen.width() / 2):
            snap_x = screen.left() + 24
            self._dock_side = "left"
        else:
            snap_x = screen.right() - w - 24
            self._dock_side = "right"

        # Vertically clamp within work area
        snap_y = max(screen.top() + 24, min(self.y(), screen.bottom() - h - 24))

        self.snap_anim.stop()
        self.snap_anim.setStartValue(self.pos())
        self.snap_anim.setEndValue(QPoint(snap_x, snap_y))
        self.snap_anim.start()

    # -------------------------------------------------------------------------
    # Expand / Collapse Mechanics (220ms, QEasingCurve.OutExpo)
    # -------------------------------------------------------------------------
    def toggle_expand(self):
        if self.is_expanded:
            self.collapse_bubble()
        else:
            self.expand_popup()

    def expand_popup(self):
        """Smoothly expands to 380x480px, anchored from bubble corner with Windows 11 DWM blur."""
        if self.is_expanded:
            self.activateWindow()
            self.input_field.setFocus()
            return

        self.is_expanded = True
        cur_x, cur_y = self.x(), self.y()
        cur_w, cur_h = self.width(), self.height()

        target_w, target_h = 380, 480
        screen = QApplication.primaryScreen().availableGeometry()

        # Anchor corner based on screen dock side
        if self._dock_side == "left":
            target_x = cur_x
        else:
            target_x = cur_x + cur_w - target_w
        target_y = cur_y + cur_h - target_h

        # Boundary clamping
        target_x = max(screen.left() + 12, min(target_x, screen.right() - target_w - 12))
        target_y = max(screen.top() + 12, min(target_y, screen.bottom() - target_h - 12))

        self.geom_anim.stop()
        self.geom_anim.setDuration(220)
        self.geom_anim.setEasingCurve(QEasingCurve.OutExpo)
        self.geom_anim.setStartValue(self.geometry())
        self.geom_anim.setEndValue(QRect(target_x, target_y, target_w, target_h))
        self.geom_anim.start()

        # Engage Windows 11 DWM Blur & Acrylic Translucency
        try:
            enable_windows_translucency(int(self.winId()))
        except Exception:
            pass

        self.card.show()
        self.activateWindow()
        self.input_field.setFocus()

    def collapse_bubble(self):
        """Smoothly collapses back to the 96x96 floating HUD orb."""
        if not self.is_expanded:
            return

        self.is_expanded = False
        self.card.hide()

        cur_x, cur_y = self.x(), self.y()
        cur_w, cur_h = self.width(), self.height()

        target_w, target_h = 96, 96
        if self._dock_side == "left":
            target_x = cur_x
        else:
            target_x = cur_x + cur_w - target_w
        target_y = cur_y + cur_h - target_h

        self.geom_anim.stop()
        self.geom_anim.setDuration(220)
        self.geom_anim.setEasingCurve(QEasingCurve.OutExpo)
        self.geom_anim.setStartValue(self.geometry())
        self.geom_anim.setEndValue(QRect(target_x, target_y, target_w, target_h))
        self.geom_anim.start()

    def _on_anim_finished(self):
        if self.is_expanded:
            self.card.show()
            self.input_field.setFocus()
        else:
            self.card.hide()
            self.update()

    # -------------------------------------------------------------------------
    # Chat & Client Communication
    # -------------------------------------------------------------------------
    def _on_send_prompt(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self._append_message(text, is_user=True)
        self.input_field.clear()
        self.client.send_prompt(text)

    def _on_thinking_started(self):
        self.state = "thinking"
        self.status_pill.setText("● THINKING")
        self.status_pill.setStyleSheet("""
            QLabel {
                color: #c084fc;
                background: rgba(192, 132, 252, 0.15);
                border: 1px solid rgba(192, 132, 252, 0.35);
                border-radius: 10px;
                padding: 3px 8px;
            }
        """)

    def _on_ai_response(self, text: str):
        self.state = "idle"
        self._append_message(text, is_user=False)
        self._on_status_changed(True)

    def _on_ai_error(self, err: str):
        self.state = "idle"
        self._append_message(f"⚠️ {err}", is_user=False)
        self._on_status_changed(False)

    def _on_status_changed(self, online: bool):
        if online:
            self.status_pill.setText("● ONLINE")
            self.status_pill.setStyleSheet("""
                QLabel {
                    color: #10b981;
                    background: rgba(16, 185, 129, 0.12);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 10px;
                    padding: 3px 8px;
                }
            """)
        else:
            self.status_pill.setText("● OFFLINE")
            self.status_pill.setStyleSheet("""
                QLabel {
                    color: #ef4444;
                    background: rgba(239, 68, 68, 0.12);
                    border: 1px solid rgba(239, 68, 68, 0.3);
                    border-radius: 10px;
                    padding: 3px 8px;
                }
            """)

    def _append_message(self, text: str, is_user: bool = False):
        bubble = ChatMessageBubble(text, is_user=is_user)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vbar = self.scroll_area.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def _toggle_mic(self):
        if self.state == "listening":
            self.state = "idle"
            self.btn_mic.setStyleSheet("")
        else:
            self.state = "listening"
            self.set_audio_level(0.65)  # Initial audio pulse test
            self.btn_mic.setStyleSheet("background: rgba(16, 185, 129, 0.35); border-color: #10b981;")

    def closeEvent(self, event):
        self.client.shutdown()
        super().closeEvent(event)
