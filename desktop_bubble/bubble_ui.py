"""
J.A.R.V.I.S. Floating Desktop Sentinel Bubble UI (PySide6)
===========================================================
A native Windows 11 frameless, translucent, always-on-top AI companion window.

Modes:
- Collapsed (80x80 px): Sleek 64x64 circular AI orb with radial gradient,
  idle breathing animation, thinking rotating arcs, and listening pulsing ring.
  Smooth drag vs. stationary click (<4px delta) separation.
- Expanded (380x480 px): Glassmorphic popup card anchored at bottom-right,
  containing connection telemetry, scrollable chat area, mic toggle, and auto-focused input.
"""

import math
import ctypes
from PySide6.QtCore import (
    Qt, QRect, QRectF, QPoint, QTimer, QPropertyAnimation,
    QEasingCurve, Signal, Slot
)
from PySide6.QtGui import (
    QPainter, QRadialGradient, QColor, QPen, QBrush,
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
                    background: rgba(4, 13, 30, 0.95);
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
    - Collapsed: 80x80 frameless translucent floating AI bubble orb.
    - Expanded: 380x480 glassmorphic neural assistant popup.
    """
    def __init__(self, backend_url: str = "http://localhost:8000"):
        super().__init__()

        self.backend_url = backend_url
        self.is_expanded = False
        self.state = "idle"  # "idle", "listening", "thinking"
        self._is_dragging = False
        self._drag_start = QPoint()
        self._start_pos = QPoint()

        # Animation state variables
        self._anim_phase = 0.0
        self._ring_angle = 0.0
        self._pulse_scale = 1.0

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

        # Build UI layout (Card container)
        self._build_ui()

        # Geometry animation controller
        self.geom_anim = QPropertyAnimation(self, b"geometry")
        self.geom_anim.setDuration(240)
        self.geom_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.geom_anim.finished.connect(self._on_anim_finished)

        # 60 FPS Render Timer for breathing, rotating, pulsing physics
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_render_tick)
        self.anim_timer.start(16)

        # Start anchored at bottom-right of primary screen
        self.reset_to_default_position()

    def _build_ui(self):
        """Constructs the dark glassmorphic popup card layout."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("chatCard")
        self.card.setStyleSheet("""
            #chatCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(8, 14, 28, 0.96), stop:1 rgba(4, 8, 18, 0.98));
                border: 1.5px solid rgba(0, 240, 255, 0.4);
                border-radius: 18px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        # 1. Top Bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        # Title & Online Status
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

        title_lbl = QLabel("J.A.R.V.I.S.")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #00f0ff; letter-spacing: 1px;")

        top_bar.addWidget(title_lbl)
        top_bar.addWidget(self.status_pill)
        top_bar.addStretch()

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
            QPushButton#btnMic, QPushButton#btnMinimize {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 14px;
                color: #00f0ff;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btnMic:hover, QPushButton#btnMinimize:hover {
                background: rgba(0, 240, 255, 0.22);
                border-color: #00f0ff;
            }
        """)

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
        """Anchors the 80x80 bubble to the bottom-right of primary screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        bx = screen.right() - 80 - 24
        by = screen.bottom() - 80 - 48
        self.setGeometry(bx, by, 80, 80)

    # -------------------------------------------------------------------------
    # Render & Animation Loop (Collapsed AI Orb)
    # -------------------------------------------------------------------------
    def _on_render_tick(self):
        self._anim_phase = (self._anim_phase + 0.052) % (math.pi * 2)
        speed = 4.5 if self.state == "thinking" else 1.2
        self._ring_angle = (self._ring_angle + speed) % 360

        if self.state == "listening":
            self._pulse_scale = 1.0 + math.sin(self._anim_phase * 2) * 0.15
        else:
            self._pulse_scale = 1.0

        if not self.is_expanded:
            self.update()

    def paintEvent(self, event):
        """Paints the 64x64 sleek circular AI orb inside the 80x80 canvas."""
        if self.is_expanded:
            return  # QSS handles the expanded card layout

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = 40.0, 40.0
        breath = math.sin(self._anim_phase)  # -1.0 to 1.0

        # 1. Listening Pulsing Outer Aura
        if self.state == "listening":
            aura_radius = 34.0 * self._pulse_scale
            aura_pen = QPen(QColor(16, 185, 129, int(120 + breath * 40)), 2.0)
            painter.setPen(aura_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(int(cx), int(cy)), int(aura_radius), int(aura_radius))

        # 2. Outer Ambient Radial Glow
        glow_radius = 31.0 + breath * 1.5
        glow = QRadialGradient(cx, cy, glow_radius)
        if self.state == "listening":
            glow.setColorAt(0.0, QColor(0, 255, 136, 180))
            glow.setColorAt(0.7, QColor(16, 185, 129, 60))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        elif self.state == "thinking":
            glow.setColorAt(0.0, QColor(192, 132, 252, 200))
            glow.setColorAt(0.7, QColor(147, 51, 234, 70))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:  # Idle
            glow.setColorAt(0.0, QColor(0, 240, 255, 190))
            glow.setColorAt(0.5, QColor(59, 130, 246, 90))
            glow.setColorAt(0.85, QColor(79, 70, 229, 40))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(glow_radius), int(glow_radius))

        # 3. Main Circular AI Orb Base (64x64 centered)
        orb_radius = 28.0 + breath * 0.8
        orb_grad = QRadialGradient(cx - 6, cy - 6, orb_radius)
        if self.state == "listening":
            orb_grad.setColorAt(0.0, QColor("#34d399"))
            orb_grad.setColorAt(0.5, QColor("#059669"))
            orb_grad.setColorAt(1.0, QColor("#022c22"))
            border_col = QColor("#10b981")
        elif self.state == "thinking":
            orb_grad.setColorAt(0.0, QColor("#e879f9"))
            orb_grad.setColorAt(0.5, QColor("#9333ea"))
            orb_grad.setColorAt(1.0, QColor("#2e1065"))
            border_col = QColor("#c084fc")
        else:
            orb_grad.setColorAt(0.0, QColor("#38bdf8"))
            orb_grad.setColorAt(0.4, QColor("#0284c7"))
            orb_grad.setColorAt(0.8, QColor("#1e1b4b"))
            orb_grad.setColorAt(1.0, QColor("#030712"))
            border_col = QColor("#00f0ff")

        painter.setPen(QPen(border_col, 1.8))
        painter.setBrush(QBrush(orb_grad))
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(orb_radius), int(orb_radius))

        # 4. Thinking Rotating Arc Ring
        arc_radius = 23.0
        arc_pen = QPen(border_col, 2.2)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        painter.setBrush(Qt.NoBrush)

        rect_arc = QRectF(cx - arc_radius, cy - arc_radius, arc_radius * 2, arc_radius * 2)
        for offset in (0, 120, 240):
            start_ang = int((self._ring_angle + offset) % 360 * 16)
            span_ang = int(55 * 16)
            painter.drawArc(rect_arc, start_ang, span_ang)

        # 5. Core Spark
        spark_radius = 7.0 + breath * 0.5
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(spark_radius), int(spark_radius))

    # -------------------------------------------------------------------------
    # Mouse Events: Drag vs. Click Separation (< 4px delta)
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._start_pos = self.pos()
            self._is_dragging = False
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
            if not self._is_dragging:
                # Stationary click (< 4px cursor delta)
                self.toggle_expand()
            self._is_dragging = False
            event.accept()

    # -------------------------------------------------------------------------
    # Expand / Collapse Mechanics (Bottom-Right Anchored)
    # -------------------------------------------------------------------------
    def toggle_expand(self):
        if self.is_expanded:
            self.collapse_bubble()
        else:
            self.expand_popup()

    def expand_popup(self):
        """Smoothly expands window to 380x480px, keeping bottom-right corner anchored."""
        if self.is_expanded:
            self.activateWindow()
            self.input_field.setFocus()
            return

        self.is_expanded = True
        cur_x, cur_y = self.x(), self.y()
        cur_w, cur_h = self.width(), self.height()

        target_w, target_h = 380, 480
        # Anchor bottom-right corner
        target_x = cur_x + cur_w - target_w
        target_y = cur_y + cur_h - target_h

        # Keep safely within screen working area
        screen = QApplication.primaryScreen().availableGeometry()
        target_x = max(screen.left() + 10, min(target_x, screen.right() - target_w - 10))
        target_y = max(screen.top() + 10, min(target_y, screen.bottom() - target_h - 10))

        self.geom_anim.stop()
        self.geom_anim.setStartValue(self.geometry())
        self.geom_anim.setEndValue(QRect(target_x, target_y, target_w, target_h))
        self.geom_anim.start()

        self.card.show()
        self.activateWindow()
        self.input_field.setFocus()

    def collapse_bubble(self):
        """Smoothly collapses back to the 80x80 floating orb."""
        if not self.is_expanded:
            return

        self.is_expanded = False
        self.card.hide()

        cur_x, cur_y = self.x(), self.y()
        cur_w, cur_h = self.width(), self.height()

        target_w, target_h = 80, 80
        target_x = cur_x + cur_w - target_w
        target_y = cur_y + cur_h - target_h

        self.geom_anim.stop()
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
        # Insert before the trailing stretch
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
            self.btn_mic.setStyleSheet("background: rgba(16, 185, 129, 0.35); border-color: #10b981;")

    def closeEvent(self, event):
        self.client.shutdown()
        super().closeEvent(event)
