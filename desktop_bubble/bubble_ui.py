"""
J.A.R.V.I.S. Floating Desktop Sentinel Bubble UI (PySide6 + QWebEngineView)
===========================================================================
High-End Sci-Fi HUD AI Orb with Smooth 60 FPS Physics, Windows 11 Translucency,
and Embedded Web App Bridge via QWebEngineView & QWebChannel.

Features:
- Collapsed (96x96 Frameless Orb):
  * Pure circular mask with zero square container (QRegion.Ellipse)
  * 60 FPS Multi-layer QPainter Sci-Fi HUD orb (ambient glow, counter-rotating HUD arcs,
    orbital focal point gradient, 3D glass specular crescent highlight, spark)
  * State reactive: idle, listening, thinking, speaking
  * Mic RMS audio level modulation
  * Magnetic screen-edge snapping on drag release (24px padding)
- Expanded (420x640 Glassmorphic Container):
  * Sleek rounded dark container (rgba(10, 16, 28, 235)) with Windows 11 Acrylic blur
  * Top drag-bar for effortless window movement, with live mini-orb, reload, external HUD, and minimize buttons
  * Embedded QWebEngineView rendering the full Jarvis Web Interface with transparent background
  * Auto-approved WebEngine audio/mic permissions (MediaAudioCapture) for zero-prompt Windows 11 operation
  * Two-way QWebChannel bridge (window.jarvisDesktop) updating orb state and live mic RMS audio level
  * Global Alt + Space dispatching 'jarvis-hotkey-activate' custom event to auto-focus web input
"""

import sys
import os
import math
import ctypes
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

from PySide6.QtCore import (
    Qt, QRect, QRectF, QPoint, QTimer, QPropertyAnimation,
    QEasingCurve, Signal, Property, Slot, QUrl, QObject
)
from PySide6.QtGui import (
    QPainter, QRadialGradient, QLinearGradient, QColor, QPen, QBrush,
    QFont, QCursor, QRegion, QKeyEvent
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QApplication, QSizePolicy
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebChannel import QWebChannel

from jarvis_client import JarvisClient
from wake_word import WakeWordWorker

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
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
        backdrop = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))

        dark = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception:
        pass

    # 2. Universal Windows 10/11 Acrylic / BlurBehind fallback
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
        policy.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        policy.AccentFlags = 2
        policy.GradientColor = 0xDC1A100C  # rgba(12, 16, 26, 220)
        policy.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.byref(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)

        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        pass


def disable_windows_translucency(hwnd: int):
    """Disables Windows 11 DWM Acrylic / BlurBehind so no square container or blur remains when collapsed."""
    if sys.platform != "win32":
        return

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
        policy.AccentState = 0  # ACCENT_DISABLED
        policy.AccentFlags = 0
        policy.GradientColor = 0
        policy.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(ctypes.byref(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)

        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        pass

    try:
        dwmapi = ctypes.windll.dwmapi
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMSBT_NONE = 1
        backdrop = ctypes.c_int(DWMSBT_NONE)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    except Exception:
        pass


class JarvisBridge(QObject):
    """
    Two-way communication bridge exposed to JavaScript via QWebChannel as `window.jarvisDesktop`.
    Allows the web app to control the floating orb's visual state and audio reactivity,
    sync the selected microphone hardware, handle wake-word activation, and request collapsing/minimizing.
    """
    orbStateChanged = Signal(str)
    audioLevelChanged = Signal(float)
    minimizeRequested = Signal()
    micDeviceChanged = Signal(str, str)
    wakeTriggered = Signal(str)

    @Slot(str)
    def setOrbState(self, state: str):
        """Allows JavaScript to set orb state: 'idle' | 'listening' | 'thinking' | 'speaking'."""
        self.orbStateChanged.emit(str(state))

    @Slot(float)
    def setAudioLevel(self, level: float):
        """Allows JavaScript to stream microphone RMS audio level (0.0 to 1.0)."""
        self.audioLevelChanged.emit(float(level))

    @Slot()
    def minimizeToBubble(self):
        """Allows JavaScript to request collapsing back to the 96x96 floating orb."""
        self.minimizeRequested.emit()

    @Slot(str, str)
    def setMicDevice(self, label: str, device_id: str):
        """Allows JavaScript to notify Python of the user's selected microphone hardware."""
        self.micDeviceChanged.emit(str(label), str(device_id))


class JarvisWebEnginePage(QWebEnginePage):
    """
    Custom QWebEnginePage with automatic feature permission approval.
    Specifically grants MediaAudioCapture (microphone access) so voice interaction
    in Windows 11 never triggers blocking dialogs or permission denials.
    """
    def __init__(self, profile=None, parent=None):
        super().__init__(profile, parent) if profile else super().__init__(parent)
        self.featurePermissionRequested.connect(self._on_feature_permission_requested)

    def _on_feature_permission_requested(self, security_origin, feature):
        # Automatically grant microphone, camera, and notification permissions
        auto_grant_features = [
            QWebEnginePage.Feature.MediaAudioCapture,
            QWebEnginePage.Feature.MediaVideoCapture,
            QWebEnginePage.Feature.MediaAudioVideoCapture,
            QWebEnginePage.Feature.Notifications,
        ]
        if feature in auto_grant_features:
            self.setFeaturePermission(
                security_origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            )
        else:
            self.setFeaturePermission(
                security_origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
            )


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
        if self.bubble.state == "thinking":
            arc_color = QColor("#c084fc")
        elif self.bubble.state == "listening":
            arc_color = QColor("#10b981")
        elif self.bubble.state == "speaking":
            arc_color = QColor("#38bdf8")
        else:
            arc_color = QColor("#00f0ff")

        arc_pen = QPen(arc_color, 1.4)
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
        elif self.bubble.state == "speaking":
            grad.setColorAt(0.0, QColor("#38bdf8"))
            grad.setColorAt(1.0, QColor("#0c4a6e"))
        else:
            grad.setColorAt(0.0, QColor("#00f0ff"))
            grad.setColorAt(1.0, QColor("#0f172a"))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPoint(int(cx), int(cy)), 6, 6)

        # Center spark
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPoint(int(cx), int(cy)), 2, 2)


class TopDragBar(QFrame):
    """
    Sleek top drag bar for the expanded 420x640 container.
    Allows moving the window by dragging anywhere on the header bar.
    """
    def __init__(self, parent_bubble):
        super().__init__()
        self.bubble = parent_bubble
        self._drag_start = QPoint()
        self._start_pos = QPoint()
        self._is_dragging = False
        self.setObjectName("topDragBar")
        self.setFixedHeight(38)
        self.setStyleSheet("""
            #topDragBar {
                background: rgba(10, 16, 28, 0.95);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
                border-bottom: 1px solid rgba(0, 240, 255, 0.2);
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_start = event.globalPosition().toPoint()
            self._start_pos = self.bubble.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and (event.buttons() & Qt.LeftButton):
            cur = event.globalPosition().toPoint()
            self.bubble.move(self._start_pos + (cur - self._drag_start))
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        event.accept()


class DesktopAIBubble(QWidget):
    """
    Main PySide6 Desktop Sentinel Window:
    - Collapsed: 96x96 frameless sci-fi HUD AI orb (60x60 core, 60 FPS multi-layer physics, pure circular mask).
    - Expanded: 420x640 Windows 11 DWM glassmorphic card embedding the full Jarvis Web App inside QWebEngineView.
    """
    def __init__(self, backend_url: str = "http://localhost:8765"):
        super().__init__()

        # Determine target web URL: prioritize argument, then environment, default to 8765
        self.backend_url = backend_url or os.getenv("JARVIS_WEB_URL", "http://localhost:8765")
        self.is_expanded = False
        self.state = "idle"  # "idle", "listening", "thinking", "speaking"
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

        # Backend Health Client for connection status pill
        self.client = JarvisClient(self.backend_url)
        self.client.status_changed.connect(self._on_status_changed)

        # Window Flags & Attributes
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)

        # Low-CPU Background Wake-Word Engine (sounddevice + openwakeword)
        self.wake_worker = WakeWordWorker()
        self.wake_worker.audio_level.connect(self._on_wake_audio_level)
        self.wake_worker.wake_detected.connect(self._on_wake_word_triggered)
        self.wake_worker.start()

        # Build UI layout (Glassmorphic card container with embedded QWebEngineView)
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
        """Modulates listening/speaking state aura and ring radius dynamically (0.0 to 1.0)."""
        self._audio_level = max(0.0, min(1.0, float(level)))

    def set_state(self, state: str):
        """Updates orb animation state from bridge or client ('idle' | 'listening' | 'thinking' | 'speaking')."""
        s = str(state).lower().strip()
        if s in ("idle", "listening", "thinking", "speaking"):
            self.state = s
            if s == "idle":
                self.status_pill.setText("● ONLINE")
                self.status_pill.setStyleSheet("""
                    QLabel {
                        color: #10b981;
                        background: rgba(16, 185, 129, 0.12);
                        border: 1px solid rgba(16, 185, 129, 0.3);
                        border-radius: 10px;
                        padding: 2px 8px;
                    }
                """)
            elif s == "listening":
                self.status_pill.setText("● LISTENING")
                self.status_pill.setStyleSheet("""
                    QLabel {
                        color: #10b981;
                        background: rgba(16, 185, 129, 0.22);
                        border: 1px solid #10b981;
                        border-radius: 10px;
                        padding: 2px 8px;
                    }
                """)
            elif s == "thinking":
                self.status_pill.setText("● THINKING")
                self.status_pill.setStyleSheet("""
                    QLabel {
                        color: #c084fc;
                        background: rgba(192, 132, 252, 0.18);
                        border: 1px solid rgba(192, 132, 252, 0.4);
                        border-radius: 10px;
                        padding: 2px 8px;
                    }
                """)
            elif s == "speaking":
                self.status_pill.setText("● SPEAKING")
                self.status_pill.setStyleSheet("""
                    QLabel {
                        color: #00f0ff;
                        background: rgba(0, 240, 255, 0.18);
                        border: 1px solid #00f0ff;
                        border-radius: 10px;
                        padding: 2px 8px;
                    }
                """)
            if not self.is_expanded:
                self.update()
            elif hasattr(self, "mini_orb"):
                self.mini_orb.update()

    # -------------------------------------------------------------------------
    # UI Construction (Embedded QWebEngineView + Top Drag Bar)
    # -------------------------------------------------------------------------
    def _build_ui(self):
        """Constructs the dark glassmorphic popup container with QWebEngineView & QWebChannel."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Outer Glassmorphic Card Container (420x640px)
        self.card = QFrame(self)
        self.card.setObjectName("webCard")
        self.card.setStyleSheet("""
            #webCard {
                background: rgba(10, 16, 28, 238);
                border: 1px solid rgba(0, 240, 255, 0.45);
                border-radius: 16px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 1. Top Drag Bar
        self.top_drag_bar = TopDragBar(self)
        top_layout = QHBoxLayout(self.top_drag_bar)
        top_layout.setContentsMargins(10, 4, 10, 4)
        top_layout.setSpacing(8)

        # Live Mini-Orb
        self.mini_orb = MiniOrbWidget(self)
        top_layout.addWidget(self.mini_orb)

        # Title Label
        title_lbl = QLabel("J.A.R.V.I.S.")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #00f0ff; letter-spacing: 1.2px; margin-left: 2px;")
        top_layout.addWidget(title_lbl)

        # Connection Status Pill
        self.status_pill = QLabel("● ONLINE")
        self.status_pill.setFont(QFont("Consolas", 8, QFont.Bold))
        self.status_pill.setStyleSheet("""
            QLabel {
                color: #10b981;
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 10px;
                padding: 2px 8px;
            }
        """)
        top_layout.addWidget(self.status_pill)
        top_layout.addStretch()

        # Action Buttons: Reload, Open in Browser, Minimize
        self.btn_reload = QPushButton("🔄")
        self.btn_reload.setObjectName("btnHeaderAction")
        self.btn_reload.setToolTip("Reload Web Interface")
        self.btn_reload.setFixedSize(26, 26)
        self.btn_reload.setCursor(Qt.PointingHandCursor)
        self.btn_reload.clicked.connect(self._reload_web_view)

        self.btn_hud = QPushButton("🌐")
        self.btn_hud.setObjectName("btnHeaderAction")
        self.btn_hud.setToolTip("Open in External Browser")
        self.btn_hud.setFixedSize(26, 26)
        self.btn_hud.setCursor(Qt.PointingHandCursor)
        self.btn_hud.clicked.connect(self._open_web_hud)

        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("btnHeaderAction")
        self.btn_min.setToolTip("Minimize to Desktop Bubble (Esc)")
        self.btn_min.setFixedSize(26, 26)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.collapse_bubble)

        self.top_drag_bar.setStyleSheet(self.top_drag_bar.styleSheet() + """
            QPushButton#btnHeaderAction {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 13px;
                color: #00f0ff;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btnHeaderAction:hover {
                background: rgba(0, 240, 255, 0.25);
                border-color: #00f0ff;
            }
        """)

        top_layout.addWidget(self.btn_reload)
        top_layout.addWidget(self.btn_hud)
        top_layout.addWidget(self.btn_min)
        card_layout.addWidget(self.top_drag_bar)

        # 2. Embedded QWebEngineView with QWebChannel Bridge
        self.web_view = QWebEngineView(self.card)
        self.web_page = JarvisWebEnginePage(self.web_view)
        self.web_page.setBackgroundColor(Qt.transparent)
        self.web_view.setPage(self.web_page)
        self.web_view.setAttribute(Qt.WA_TranslucentBackground, True)
        self.web_view.setStyleSheet("background: transparent;")

        # Set up QWebChannel to expose Python JarvisBridge to JavaScript
        self.channel = QWebChannel(self.web_page)
        self.bridge = JarvisBridge(self)
        self.bridge.orbStateChanged.connect(self.set_state)
        self.bridge.audioLevelChanged.connect(self.set_audio_level)
        self.bridge.minimizeRequested.connect(self.collapse_bubble)
        if hasattr(self, "wake_worker"):
            self.bridge.micDeviceChanged.connect(self.wake_worker.set_microphone)
        self.channel.registerObject("jarvisDesktop", self.bridge)
        self.web_page.setWebChannel(self.channel)

        # Initial web page load
        target_url = self.backend_url
        if not target_url.startswith("http"):
            target_url = f"http://{target_url}"
        self.web_view.load(QUrl(target_url))

        card_layout.addWidget(self.web_view, 1)

        self.main_layout.addWidget(self.card)
        self.card.hide()  # Collapsed initially

    def _update_mask(self):
        """Enforces a pure circular window mask when collapsed, and clears it when expanded."""
        if not self.is_expanded:
            # Elliptical mask clips any opaque container or window background to a pure circle
            self.setMask(QRegion(0, 0, self.width(), self.height(), QRegion.Ellipse))
        else:
            self.clearMask()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_mask()

    def reset_to_default_position(self):
        """Anchors the 96x96 bubble 24px away from bottom-right of primary screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        bx = screen.right() - 96 - 24
        by = screen.bottom() - 96 - 48
        self.setGeometry(bx, by, 96, 96)
        self._dock_side = "right"
        self._update_mask()

    def _reload_web_view(self):
        """Reloads the embedded web view interface."""
        if hasattr(self, "web_view"):
            self.web_view.reload()

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
        elif self.state == "speaking":
            v_outer = 3.6   # Accelerated energetic speech rotation
            v_inner = -2.8
        else:
            v_outer = 1.6   # Smooth steady clockwise rotation
            v_inner = -1.2  # Smooth steady counter-clockwise rotation

        self._ring_angle_outer = (self._ring_angle_outer + v_outer) % 360
        self._ring_angle_inner = (self._ring_angle_inner + v_inner) % 360

        # 4. Audio level smooth decay back to baseline if not actively being fed
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

        # Clear backing store completely to transparent so zero opaque container appears
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

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
        ambient_r = 45.0 + breath * 1.5 + (self._audio_level * 2.0)
        ambient_glow = QRadialGradient(cx, cy, ambient_r)

        if self.state == "listening":
            base_a = int(min(255, (160 + self._audio_level * 95) * glow_boost))
            ambient_glow.setColorAt(0.0, QColor(16, 185, 129, base_a))
            ambient_glow.setColorAt(0.55, QColor(245, 158, 11, int(70 * glow_boost)))
            ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        elif self.state == "thinking":
            base_a = int(min(255, 190 * glow_boost))
            ambient_glow.setColorAt(0.0, QColor(192, 132, 252, base_a))
            ambient_glow.setColorAt(0.55, QColor(0, 240, 255, int(90 * glow_boost)))
            ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        elif self.state == "speaking":
            base_a = int(min(255, (180 + self._audio_level * 75) * glow_boost))
            ambient_glow.setColorAt(0.0, QColor(0, 240, 255, base_a))
            ambient_glow.setColorAt(0.50, QColor(56, 189, 248, int(110 * glow_boost)))
            ambient_glow.setColorAt(0.85, QColor(14, 165, 233, int(45 * glow_boost)))
            ambient_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:
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
        r_outer_arc = 39.0 + (self._audio_level * 3.0 if self.state in ("listening", "speaking") else 0.0)
        arc_pen_out = QPen()
        arc_pen_out.setWidthF(2.0)
        arc_pen_out.setCapStyle(Qt.RoundCap)

        if self.state == "listening":
            arc_pen_out.setColor(QColor(16, 185, 129, int(220 * glow_boost)))
        elif self.state == "thinking":
            arc_pen_out.setColor(QColor(192, 132, 252, int(240 * glow_boost)))
        elif self.state == "speaking":
            arc_pen_out.setColor(QColor(56, 189, 248, int(240 * glow_boost)))
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
        r_inner_arc = 34.0 + (self._audio_level * 4.0 if self.state in ("listening", "speaking") else 0.0)
        arc_pen_in = QPen()
        arc_pen_in.setWidthF(1.8)
        arc_pen_in.setCapStyle(Qt.RoundCap)

        if self.state == "listening":
            arc_pen_in.setColor(QColor(245, 158, 11, int(210 * glow_boost)))
        elif self.state == "thinking":
            arc_pen_in.setColor(QColor(0, 240, 255, int(230 * glow_boost)))
        elif self.state == "speaking":
            arc_pen_in.setColor(QColor(0, 240, 255, int(220 * glow_boost)))
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
        r_core = 30.0 + breath * 0.6 + (self._audio_level * 3.5 if self.state in ("listening", "speaking") else 0.0)
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
        elif self.state == "speaking":
            core_grad.setColorAt(0.0, QColor("#bae6fd"))
            core_grad.setColorAt(0.35, QColor("#0284c7"))
            core_grad.setColorAt(0.70, QColor("#0369a1"))
            core_grad.setColorAt(1.0, QColor("#082f49"))
            border_pen = QPen(QColor("#38bdf8"), 1.8)
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
                # Stationary click (< 4px cursor delta) toggles the expanded web app
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
        """Restores or opens the full Stark HUD web interface in external browser."""
        import webbrowser
        target = self.backend_url
        if not target.startswith("http"):
            target = f"http://{target}"
        webbrowser.open(target)

    def _perform_magnetic_snap(self):
        """Snaps 24px away from nearest left or right screen edge with OutCubic physics."""
        screen = QApplication.primaryScreen().availableGeometry()
        w = self.width()
        h = self.height()
        cur_center_x = self.x() + w / 2

        if cur_center_x < (screen.left() + screen.width() / 2):
            snap_x = screen.left() + 24
            self._dock_side = "left"
        else:
            snap_x = screen.right() - w - 24
            self._dock_side = "right"

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
        """Smoothly expands to 420x640px, anchored from bubble corner with Windows 11 DWM blur."""
        if self.is_expanded:
            self.activateWindow()
            self._dispatch_hotkey_activation()
            return

        self.is_expanded = True
        cur_x, cur_y = self.x(), self.y()
        cur_w, cur_h = self.width(), self.height()

        target_w, target_h = 420, 640
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

        # Clear mask for expanded card layout and engage Windows 11 DWM Blur & Acrylic
        self.clearMask()
        try:
            enable_windows_translucency(int(self.winId()))
        except Exception:
            pass

        self.card.show()
        self.activateWindow()
        self._dispatch_hotkey_activation()

    def collapse_bubble(self):
        """Smoothly collapses back to the 96x96 floating HUD orb."""
        if not self.is_expanded:
            return

        self.is_expanded = False
        self.card.hide()

        # Disable Acrylic/BlurBehind immediately so no square backdrop remains on screen
        try:
            disable_windows_translucency(int(self.winId()))
        except Exception:
            pass
        self._update_mask()

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
            self.clearMask()
            self.card.show()
            self._dispatch_hotkey_activation()
        else:
            self.card.hide()
            self._update_mask()
            self.update()

    def _dispatch_hotkey_activation(self):
        """Dispatches custom event 'jarvis-hotkey-activate' into the embedded web application."""
        if hasattr(self, "web_view") and self.web_view.page():
            self.web_view.page().runJavaScript(
                'window.dispatchEvent(new CustomEvent("jarvis-hotkey-activate"));'
            )

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.collapse_bubble()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_status_changed(self, online: bool):
        if online:
            self.status_pill.setText("● ONLINE")
            self.status_pill.setStyleSheet("""
                QLabel {
                    color: #10b981;
                    background: rgba(16, 185, 129, 0.12);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 10px;
                    padding: 2px 8px;
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
                    padding: 2px 8px;
                }
            """)

    def _on_wake_audio_level(self, level: float):
        """Streams live mic RMS level to orb so the floating bubble pulses with voice."""
        if not self.is_expanded or self.state in ("idle", "listening"):
            self.set_audio_level(level)

    def _on_wake_word_triggered(self, phrase: str):
        """Triggered when background wake-word engine detects 'Hey Jarvis'."""
        print(f"[DesktopAIBubble] Wake word '{phrase}' detected! Expanding popup & listening...")
        self.expand_popup()
        self.set_state("listening")
        if hasattr(self, "bridge"):
            self.bridge.wakeTriggered.emit(phrase)
        if hasattr(self, "web_view") and self.web_view.page():
            self.web_view.page().runJavaScript(
                f'window.dispatchEvent(new CustomEvent("jarvis-wake-activate", {{ detail: {{ phrase: "{phrase}" }} }}));'
            )

    def closeEvent(self, event):
        if hasattr(self, "wake_worker"):
            self.wake_worker.stop()
        self.client.shutdown()
        super().closeEvent(event)
