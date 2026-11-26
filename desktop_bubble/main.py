"""
J.A.R.V.I.S. Floating Desktop Sentinel Bubble - Application Entry Point
=======================================================================
Pure Python Windows 11 floating AI companion overlay built with PySide6.
Features:
- Frameless transparent 80x80 floating AI bubble expanding to 380x480 neural chat.
- Global 'Alt + Space' hotkey bringing overlay to front & auto-focusing input.
- Native Windows System Tray icon with context menu (Show/Hide, Reset Position, Quit).
- Non-blocking FastAPI client (httpx + QThread) connected to http://localhost:8000/chat.
"""

import sys
import os
import argparse
from pathlib import Path

# Add current directory to sys.path so modules resolve cleanly
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QRadialGradient, QColor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from bubble_ui import DesktopAIBubble
from hotkey_manager import HotkeyManager


def create_tray_icon() -> QIcon:
    """Generates a high-res glowing cyan cyber-orb QIcon for Windows System Tray."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Ambient radial gradient
    grad = QRadialGradient(32, 32, 28)
    grad.setColorAt(0.0, QColor("#00f0ff"))
    grad.setColorAt(0.5, QColor("#0284c7"))
    grad.setColorAt(0.85, QColor("#1e1b4b"))
    grad.setColorAt(1.0, QColor(0, 0, 0, 0))

    painter.setPen(Qt.NoPen)
    painter.setBrush(grad)
    painter.drawEllipse(4, 4, 56, 56)

    # Core spark
    painter.setBrush(QColor("#ffffff"))
    painter.drawEllipse(26, 26, 12, 12)
    painter.end()

    return QIcon(pixmap)


def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Floating Desktop AI Bubble")
    parser.add_argument("--url", default=os.getenv("JARVIS_WEB_URL", "http://localhost:8765"), help="FastAPI backend URL (default: http://localhost:8765 or JARVIS_WEB_URL)")
    args = parser.parse_args()

    # Enable high-DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS Desktop Bubble")
    app.setQuitOnLastWindowClosed(False)

    # 1. Instantiate the Desktop Sentinel Bubble Window
    bubble = DesktopAIBubble(backend_url=args.url)
    bubble.show()

    # 2. System Tray Integration
    tray_icon = QSystemTrayIcon(create_tray_icon(), app)
    tray_icon.setToolTip("J.A.R.V.I.S. Desktop AI Bubble (Alt + Space)")

    tray_menu = QMenu()
    tray_menu.setStyleSheet("""
        QMenu {
            background-color: #0b132b;
            color: #e2e8f0;
            border: 1px solid #00f0ff;
            border-radius: 8px;
            padding: 6px;
            font-family: 'Segoe UI', sans-serif;
            font-size: 12px;
        }
        QMenu::item {
            padding: 6px 20px 6px 12px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: rgba(0, 240, 255, 0.2);
            color: #00f0ff;
        }
        QMenu::separator {
            height: 1px;
            background: rgba(0, 240, 255, 0.2);
            margin: 4px 8px;
        }
    """)

    act_toggle = tray_menu.addAction("🔮  Show / Hide Bubble")
    def toggle_visibility():
        if bubble.isVisible():
            if bubble.is_expanded:
                bubble.collapse_bubble()
            else:
                bubble.hide()
        else:
            bubble.show()
    act_toggle.triggered.connect(toggle_visibility)

    act_reset = tray_menu.addAction("📍  Reset Position")
    act_reset.triggered.connect(bubble.reset_to_default_position)

    tray_menu.addSeparator()

    act_open_app = tray_menu.addAction("🌐  Open Full Jarvis Web App")
    def open_full_web_app():
        import webbrowser
        url = bubble.backend_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"
        session = getattr(bubble, "session_id", "")
        full_url = f"{url}?session_id={session}" if session else url
        webbrowser.open(full_url)
    act_open_app.triggered.connect(open_full_web_app)

    act_quit = tray_menu.addAction("✕   Quit J.A.R.V.I.S.")
    act_quit.triggered.connect(app.quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # 3. Global Hotkeys: Alt + Space (Toggle) & Ctrl + Shift + Space (Clipboard Hook)
    hotkey_mgr = HotkeyManager("Alt + Space / Ctrl + Shift + Space")

    def on_global_hotkey():
        """Brings overlay to front & expands popup, or collapses if already active."""
        if not bubble.isVisible():
            bubble.show()
            bubble.expand_popup()
        elif bubble.is_expanded and bubble.isActiveWindow():
            bubble.collapse_bubble()
        else:
            bubble.show()
            bubble.raise_()
            bubble.activateWindow()
            bubble.expand_popup()

    hotkey_mgr.hotkey_triggered.connect(on_global_hotkey)

    def on_clipboard_hotkey():
        """Reads current Windows clipboard, expands bubble, and pre-loads into Jarvis."""
        text = QApplication.clipboard().text()
        print(f"[HotkeyManager] Ctrl + Shift + Space hook triggered! Clipboard: {len(text)} chars.")
        bubble.handle_clipboard_action(text)

    hotkey_mgr.clipboard_triggered.connect(on_clipboard_hotkey)

    # 4. Clean Shutdown Handling
    def on_shutdown():
        hotkey_mgr.stop()
        bubble.client.shutdown()

    app.aboutToQuit.connect(on_shutdown)

    print(f"==================================================")
    print(f" J.A.R.V.I.S. PySide6 Desktop AI Bubble Active")
    print(f" Backend Endpoint: {args.url}")
    print(f" Global Hotkey   : Alt + Space (Toggle & Focus)")
    print(f" System Tray     : Active in Taskbar Notification Area")
    print(f"==================================================")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
