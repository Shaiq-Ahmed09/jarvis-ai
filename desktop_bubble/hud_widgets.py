"""
J.A.R.V.I.S. Two-Bubble Side-Docking HUD Widgets (PySide6)
===========================================================
Ultra-minimalist floating HUD that docks beside the orb:

  ┌─────────────────────────────────────────┐  ← Response Bubble (auto-height)
  │  ✦  Jarvis replied text goes here...    │
  │     with clean word-wrap typography     │
  └─────────────────────────────────────────┘
  ┌─────────────────────────────────────────┐  ← Input Pill (46px tall)
  │  🎙  Ask Jarvis...              [Enter] │
  └─────────────────────────────────────────┘

Both appear in a single frameless transparent overlay window
to the left (or right) of the 96x96 orb window.
Clicking the orb again or pressing Esc collapses everything.
"""

import uuid
import math
import ctypes
from PySide6.QtCore import (
    Qt, QRect, QRectF, QPoint, QTimer, QPropertyAnimation,
    QEasingCurve, Signal, Slot, QThread, QObject
)
from PySide6.QtGui import (
    QPainter, QRadialGradient, QLinearGradient, QColor, QPen, QBrush,
    QFont, QFontMetrics, QCursor, QPainterPath, QTextOption
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QApplication, QSizePolicy, QGraphicsOpacityEffect
)

import httpx


# ---------------------------------------------------------------------------
# Non-blocking Chat Worker (session-aware)
# ---------------------------------------------------------------------------
class HudChatWorker(QThread):
    """Non-blocking QThread that POSTs to /chat with a persistent session_id."""
    response_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, base_url: str, prompt: str, session_id: str):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.prompt = prompt
        self.session_id = session_id

    def run(self):
        candidates = [self.base_url, "http://localhost:8765", "http://localhost:8000"]
        seen = []
        for u in candidates:
            u = u.rstrip("/")
            if u not in seen:
                seen.append(u)

        payload = {
            "message": self.prompt,
            "session_id": self.session_id,
        }

        last_err = None
        for base in seen:
            url = f"{base}/chat"
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict):
                            reply = (
                                data.get("response")
                                or data.get("reply")
                                or data.get("text")
                                or data.get("message")
                                or str(data)
                            )
                        else:
                            reply = str(data)
                        self.response_received.emit(str(reply))
                        return
                    else:
                        last_err = f"HTTP {resp.status_code}: {resp.text[:100]}"
            except httpx.ConnectError:
                last_err = f"Cannot reach {base}. Is server running?"
                continue
            except httpx.TimeoutException:
                self.error_occurred.emit("Response timed out (30s). Please try again, Sir.")
                return
            except Exception as e:
                self.error_occurred.emit(f"Unexpected error: {e}")
                return

        self.error_occurred.emit(last_err or "Cannot connect to J.A.R.V.I.S. backend.")


# ---------------------------------------------------------------------------
# Input Pill  (320 × 46 px glassmorphic rounded pill)
# ---------------------------------------------------------------------------
class InputPill(QWidget):
    """
    Sleek, dark translucent rounded pill with auto-focused QLineEdit,
    mic icon, and Enter/Esc key handling.
    """
    submit_requested = Signal(str)   # emitted when user presses Enter with text
    dismiss_requested = Signal()     # emitted when Esc pressed on empty field

    _PILL_H = 46
    _PILL_W = 320

    def __init__(self, parent=None, mic_placeholder: bool = True):
        super().__init__(parent)
        self.setFixedSize(self._PILL_W, self._PILL_H)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")

        # Main horizontal layout inside the pill
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(8)

        # Mic button (decorative / triggers voice if wired)
        if mic_placeholder:
            self.btn_mic = QPushButton("🎙")
            self.btn_mic.setFixedSize(24, 24)
            self.btn_mic.setCursor(Qt.PointingHandCursor)
            self.btn_mic.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #00f0ff;
                    font-size: 14px;
                }
                QPushButton:hover { color: #ffffff; }
            """)
            layout.addWidget(self.btn_mic, 0, Qt.AlignCenter)
        else:
            self.btn_mic = None

        # Text input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Jarvis…")
        self.input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                selection-background-color: rgba(0, 240, 255, 0.3);
            }
        """)
        self.input.returnPressed.connect(self._on_enter)
        self.input.installEventFilter(self)
        layout.addWidget(self.input, 1)

        # Send hint (small label)
        hint = QLabel("↵")
        hint.setStyleSheet("color: rgba(0,240,255,0.55); font-size: 14px; font-family: 'Segoe UI';")
        hint.setFixedWidth(16)
        layout.addWidget(hint, 0, Qt.AlignCenter)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.input and event.type() == QEvent.KeyPress:
            from PySide6.QtGui import QKeyEvent
            if event.key() == Qt.Key_Escape:
                self.dismiss_requested.emit()
                return True
        return super().eventFilter(obj, event)

    def _on_enter(self):
        text = self.input.text().strip()
        if text:
            self.submit_requested.emit(text)
        else:
            self.dismiss_requested.emit()

    def clear_and_focus(self):
        self.input.clear()
        self.input.setFocus()

    def set_enabled(self, enabled: bool):
        self.input.setEnabled(enabled)
        self.input.setPlaceholderText("Ask Jarvis…" if enabled else "Computing response…")

    def set_text(self, text: str):
        self.input.setText(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Glassmorphic dark pill body
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 23, 23)

        # Dark translucent fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(10, 16, 28, 230))
        painter.drawPath(path)

        # Cyan glow border
        border_pen = QPen(QColor(0, 240, 255, 160), 1.0)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Very subtle inner top highlight
        painter.setPen(Qt.NoPen)
        highlight = QLinearGradient(0, 0, 0, 10)
        highlight.setColorAt(0.0, QColor(255, 255, 255, 18))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight))
        small_path = QPainterPath()
        small_path.addRoundedRect(QRectF(2, 1, self.width() - 4, 12), 10, 10)
        painter.drawPath(small_path)


# ---------------------------------------------------------------------------
# Response Bubble  (auto-height glassmorphic bubble with tail toward orb)
# ---------------------------------------------------------------------------
class ResponseBubble(QWidget):
    """
    Compact floating dark glassmorphic response bubble.
    Auto-sizes vertically to reply text. Shows a small glowing tail
    pointing toward the orb. Has a tiny copy icon.
    """
    copy_requested = Signal()
    expand_requested = Signal(str)   # full text for clipboard / full view

    _MAX_W = 320
    _PADDING_H = 16
    _PADDING_V = 12
    _TAIL_SIZE = 8   # px triangle tail pointing right toward orb

    def __init__(self, parent=None, tail_side: str = "right"):
        super().__init__(parent)
        self.tail_side = tail_side   # "right" (orb is to the right) or "left"
        self._reply_text = ""
        self._hovered = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            14,
            self._PADDING_V,
            14 + (self._TAIL_SIZE if tail_side == "right" else 0),
            self._PADDING_V,
        )
        layout.setSpacing(8)

        # Reply text label
        self.reply_label = QLabel()
        self.reply_label.setWordWrap(True)
        self.reply_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.reply_label.setStyleSheet("""
            QLabel {
                color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.4;
                background: transparent;
            }
        """)
        self.reply_label.setMaximumWidth(self._MAX_W - 36)
        layout.addWidget(self.reply_label)

        # Action bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)
        action_bar.addStretch(1)

        self.btn_copy = QPushButton("⎘ Copy")
        self.btn_copy.setFixedHeight(20)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: rgba(0,240,255,0.6);
                font-size: 10px;
                font-family: 'Segoe UI';
                padding: 0 4px;
            }
            QPushButton:hover { color: #00f0ff; }
        """)
        self.btn_copy.clicked.connect(self._on_copy)
        action_bar.addWidget(self.btn_copy)

        layout.addLayout(action_bar)
        self.setFixedWidth(self._MAX_W + self._TAIL_SIZE)

    def set_reply(self, text: str):
        self._reply_text = text
        self.reply_label.setText(text)
        self.adjustSize()
        # Force repaint after geometry change
        self.update()

    def _on_copy(self):
        QApplication.clipboard().setText(self._reply_text)
        self.btn_copy.setText("✓ Copied")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("⎘ Copy"))

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        tail = self._TAIL_SIZE
        r = 14   # corner radius

        # Bubble body rect (leave room for tail on the right/left)
        if self.tail_side == "right":
            body_rect = QRectF(0, 0, w - tail, h)
        else:
            body_rect = QRectF(tail, 0, w - tail, h)

        path = QPainterPath()
        path.addRoundedRect(body_rect, r, r)

        # Tail triangle pointing toward orb
        mid_y = h / 2.0
        t_path = QPainterPath()
        if self.tail_side == "right":
            t_path.moveTo(w - tail, mid_y - tail * 0.65)
            t_path.lineTo(w, mid_y)
            t_path.lineTo(w - tail, mid_y + tail * 0.65)
            t_path.closeSubpath()
        else:
            t_path.moveTo(tail, mid_y - tail * 0.65)
            t_path.lineTo(0, mid_y)
            t_path.lineTo(tail, mid_y + tail * 0.65)
            t_path.closeSubpath()

        full_path = path.united(t_path)

        # Dark fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(10, 16, 28, 235))
        painter.drawPath(full_path)

        # Border glow
        glow_alpha = 200 if self._hovered else 140
        painter.setPen(QPen(QColor(0, 240, 255, glow_alpha), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(full_path)

        # Subtle top-gradient inner shine
        painter.setPen(Qt.NoPen)
        shine = QLinearGradient(body_rect.topLeft(), QRectF(body_rect.x(), body_rect.y() + 16, body_rect.width(), 1).topLeft())
        shine.setColorAt(0.0, QColor(255, 255, 255, 20))
        shine.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(shine))
        shine_path = QPainterPath()
        shine_path.addRoundedRect(QRectF(body_rect.x() + 2, body_rect.y() + 1, body_rect.width() - 4, 14), 7, 7)
        painter.drawPath(shine_path)


# ---------------------------------------------------------------------------
# HUD Overlay Window  (the transparent container that holds both pills)
# ---------------------------------------------------------------------------
class TwoBubbleHUD(QWidget):
    """
    Transparent frameless overlay window that positions itself beside the
    96x96 orb and shows at most two widgets stacked vertically:
      [0]  Response Bubble  (optional, hidden on first expansion)
      [1]  Input Pill       (always present while HUD is open)

    Interaction flow:
      1. HUD opens → Input Pill only visible (auto-focused).
      2. User types + Enter → orb goes Thinking, chat worker fires.
      3. Reply arrives → Response Bubble slides into [0], new Input Pill below.
      4. Esc or orb-click → HUD collapses (hidden).

    The HUD window is a sibling of the orb window, not a child.
    It tracks orb position changes via update_position().
    """

    # Signals
    dismissed = Signal()
    state_changed = Signal(str)   # "idle" | "thinking" | "speaking"
    audio_level_changed = Signal(float)

    _HUD_W = 340           # fixed width of the overlay column
    _GAP = 10              # horizontal gap between orb edge and HUD
    _PILL_SPACING = 8      # vertical gap between response bubble and input pill
    _SLIDE_MS = 180        # animation duration

    def __init__(self, orb_widget, backend_url: str, session_id: str):
        super().__init__()
        self.orb = orb_widget
        self.backend_url = backend_url
        self.session_id = session_id
        self._worker = None
        self._dock_side = "left"   # HUD appears to the left of orb by default

        # Window setup
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setStyleSheet("background: transparent;")

        # Main vertical layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self._PILL_SPACING)
        self._layout.setAlignment(Qt.AlignBottom)

        # Widgets (created but only response bubble hidden initially)
        self.response_bubble = ResponseBubble(tail_side="right")
        self.response_bubble.hide()
        self._layout.addWidget(self.response_bubble)

        self.input_pill = InputPill()
        self.input_pill.submit_requested.connect(self._on_submit)
        self.input_pill.dismiss_requested.connect(self.collapse)
        self._layout.addWidget(self.input_pill)

        # Slide-in animation on the whole HUD pos
        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(self._SLIDE_MS)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Fade effect for response bubble transitions
        self._fade_effect = QGraphicsOpacityEffect(self.response_bubble)
        self.response_bubble.setGraphicsEffect(self._fade_effect)
        self._fade_anim = QPropertyAnimation(self._fade_effect, b"opacity")
        self._fade_anim.setDuration(200)

        self.hide()

    # -----------------------------------------------------------------------
    # Positioning helpers
    # -----------------------------------------------------------------------
    def update_position(self):
        """Recalculates HUD position relative to current orb geometry."""
        orb_geo = self.orb.geometry()
        screen = QApplication.primaryScreen().availableGeometry()

        orb_cx = orb_geo.x() + orb_geo.width() / 2.0
        # Decide which side to dock: if orb is on right half → HUD left; else right
        if orb_cx > screen.left() + screen.width() / 2.0:
            self._dock_side = "left"
            self.response_bubble.tail_side = "right"
        else:
            self._dock_side = "right"
            self.response_bubble.tail_side = "left"

        self._snap_to_orb(animate=False)

    def _snap_to_orb(self, animate: bool = True):
        orb_geo = self.orb.geometry()
        screen = QApplication.primaryScreen().availableGeometry()

        # Height: input pill + optional response bubble
        hud_h = InputPill._PILL_H
        if self.response_bubble.isVisible():
            hud_h += self.response_bubble.height() + self._PILL_SPACING

        hud_w = self._HUD_W

        orb_bottom = orb_geo.bottom()
        orb_top = orb_geo.top()
        # Align HUD bottom edge with orb bottom edge
        target_y = orb_bottom - hud_h
        target_y = max(screen.top() + 8, min(target_y, screen.bottom() - hud_h - 8))

        if self._dock_side == "left":
            target_x = orb_geo.left() - hud_w - self._GAP
            target_x = max(screen.left() + 8, target_x)
        else:
            target_x = orb_geo.right() + self._GAP
            target_x = min(target_x, screen.right() - hud_w - 8)

        new_geo = QRect(target_x, target_y, hud_w, hud_h)
        self.setFixedSize(hud_w, hud_h)

        if animate and self.isVisible():
            self._slide_anim.stop()
            self._slide_anim.setStartValue(self.pos())
            self._slide_anim.setEndValue(QPoint(target_x, target_y))
            self._slide_anim.start()
        else:
            self.move(target_x, target_y)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    def expand(self):
        """Shows the HUD beside the orb with slide-in animation."""
        self.response_bubble.hide()
        self.input_pill.set_enabled(True)
        self.input_pill.clear_and_focus()
        self.update_position()
        self.show()
        self.raise_()
        self.activateWindow()

        # Slide in from off-screen
        orb_geo = self.orb.geometry()
        if self._dock_side == "left":
            start_x = orb_geo.left() - 20
        else:
            start_x = orb_geo.right() + 20

        self._slide_anim.stop()
        self._slide_anim.setStartValue(QPoint(start_x, self.y()))
        self._slide_anim.setEndValue(self.pos())
        self._slide_anim.start()

        try:
            enable_windows_translucency_hud(int(self.winId()))
        except Exception:
            pass

    def collapse(self):
        """Collapses HUD and emits dismissed."""
        if self._worker and self._worker.isRunning():
            self._worker.quit()
        self._slide_anim.stop()
        self.hide()
        self.response_bubble.hide()
        self.input_pill.set_enabled(True)
        self.input_pill.clear_and_focus()
        self.dismissed.emit()

    def pre_fill(self, text: str):
        """Pre-loads text into input pill (e.g. from clipboard hook)."""
        self.input_pill.set_text(text)
        self.input_pill.input.setFocus()

    # -----------------------------------------------------------------------
    # Chat interaction
    # -----------------------------------------------------------------------
    def _on_submit(self, text: str):
        self.input_pill.set_enabled(False)
        self.state_changed.emit("thinking")

        self._worker = HudChatWorker(self.backend_url, text, self.session_id)
        self._worker.response_received.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_response(self, reply: str):
        self.state_changed.emit("idle")
        self._show_response(reply)

    def _on_error(self, error_msg: str):
        self.state_changed.emit("idle")
        err_text = f"⚠ {error_msg}"
        self._show_response(err_text)

    def _show_response(self, text: str):
        """Fades in the response bubble and refreshes the input pill below."""
        self.response_bubble.set_reply(text)

        # Fade in if first time, or animate update
        self._fade_effect.setOpacity(0.0)
        self.response_bubble.show()
        self._snap_to_orb(animate=True)

        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

        # Re-enable input pill for follow-up
        self.input_pill.set_enabled(True)
        self.input_pill.clear_and_focus()

    # -----------------------------------------------------------------------
    # Key events (Esc to dismiss)
    # -----------------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.collapse()
            event.accept()
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Windows DWM Acrylic for HUD overlay (lighter blur for translucent pills)
# ---------------------------------------------------------------------------
def enable_windows_translucency_hud(hwnd: int):
    """Applies a subtle DWM blur to the HUD overlay window."""
    import sys, ctypes
    if sys.platform != "win32":
        return
    try:
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
        policy.AccentState = 4   # ACCENT_ENABLE_ACRYLICBLURBEHIND
        policy.AccentFlags = 2
        policy.GradientColor = 0xC0100A0C  # rgba(12, 10, 16, 192) — dark acrylic
        policy.AnimationId = 0

        data = WINCOMPATTRDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(ctypes.byref(policy), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(policy)

        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        pass
