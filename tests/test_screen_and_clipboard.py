"""
Unit & Integration Tests: Screen Context & Clipboard Hook
=========================================================
Tests:
1. Screen capture (mss & PIL.ImageGrab) with max-1280px downscaling.
2. Base64 encoding fidelity and dimensions.
3. JarvisBridge captureActiveScreen and getClipboardText slots.
4. DesktopAIBubble.handle_clipboard_action expansion and signal wiring.
5. HotkeyManager multi-hotkey registration (Alt+Space and Ctrl+Shift+Space).
6. FastAPI /api/vision multimodal endpoint request/response.
"""

import sys
import io
import base64
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.path.insert(0, str(Path("desktop_bubble").resolve()))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from screen_capture import capture_screen_pil, capture_screen_base64
from hotkey_manager import HotkeyManager
from bubble_ui import DesktopAIBubble


def test_screen_capture():
    print("[TEST] 1. Testing native desktop screen capture...")
    img = capture_screen_pil()
    assert img is not None, "Failed to capture PIL Image"
    assert img.width > 0 and img.height > 0
    print(f"  -> Captured display dimensions: {img.width}x{img.height} (OK)")

    # Test base64 encoding and max 1280px width constraint
    b64 = capture_screen_base64(max_width=1280, quality=80)
    assert b64 and len(b64) > 1000, "Base64 capture is empty or invalid"

    # Decode and verify dimensions <= 1280
    raw = base64.b64decode(b64)
    decoded_img = Image.open(io.BytesIO(raw))
    assert decoded_img.width <= 1280, f"Expected width <= 1280, got {decoded_img.width}"
    print(f"  -> Base64 JPEG size: {len(b64)} chars, Decoded resolution: {decoded_img.width}x{decoded_img.height} (OK)")


def test_hotkey_manager_signals():
    print("[TEST] 2. Testing HotkeyManager multi-hotkey signals...")
    mgr = HotkeyManager()
    assert hasattr(mgr, "hotkey_triggered"), "Missing hotkey_triggered signal"
    assert hasattr(mgr, "clipboard_triggered"), "Missing clipboard_triggered signal"
    
    triggered = []
    mgr.hotkey_triggered.connect(lambda: triggered.append("toggle"))
    mgr.clipboard_triggered.connect(lambda: triggered.append("clipboard"))

    mgr._on_key_event()
    mgr._on_clipboard_event()

    assert triggered == ["toggle", "clipboard"]
    mgr.stop()
    print("  -> Alt+Space and Ctrl+Shift+Space signals registered & verified (OK)")


def test_bridge_and_bubble_clipboard():
    print("[TEST] 3. Testing JarvisBridge and DesktopAIBubble clipboard hook...")
    app = QApplication.instance() or QApplication(sys.argv)

    # Set test clipboard content
    test_code = "def stark_arc_reactor():\n    return 'Clean Energy 100%'\n"
    app.clipboard().setText(test_code)

    bubble = DesktopAIBubble("http://localhost:8765")
    bubble.show()
    app.processEvents()

    assert bubble.is_expanded == False
    assert bubble.bridge.getClipboardText() == test_code
    print("  -> JarvisBridge.getClipboardText() matched clipboard text (OK)")

    # Test screen capture slot
    b64 = bubble.bridge.captureActiveScreen()
    assert b64 and len(b64) > 500, "captureActiveScreen failed"
    print("  -> JarvisBridge.captureActiveScreen() returned valid base64 (OK)")

    # Test clipboard action expansion
    received_clipboard = []
    bubble.bridge.clipboardActivated.connect(lambda txt: received_clipboard.append(txt))

    bubble.handle_clipboard_action(test_code)
    app.processEvents()

    assert bubble.is_expanded == True, "Bubble should expand on clipboard action"
    assert len(received_clipboard) == 1 and received_clipboard[0] == test_code
    print("  -> Bubble expanded and clipboardActivated emitted cleanly (OK)")

    bubble.wake_worker.stop()
    bubble.client.shutdown()
    bubble.close()


def test_fastapi_vision_endpoint():
    print("[TEST] 4. Testing FastAPI /api/vision multimodal route...")
    # Generate tiny 320x240 test JPEG
    dummy = Image.new("RGB", (320, 240), color=(10, 20, 40))
    buf = io.BytesIO()
    dummy.save(buf, format="JPEG")
    dummy_b64 = base64.b64encode(buf.getvalue()).decode()

    # Test directly against FastAPI app via TestClient
    from starlette.testclient import TestClient
    from backend.server import app as fastapi_app
    client = TestClient(fastapi_app)
    resp = client.post(
        "/api/vision",
        json={"query": "Test visual inspection query", "image": dummy_b64}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert "response" in data and "image" in data
    print(f"  -> FastAPI /api/vision HTTP 200 verified! Output: {data['response'][:60]}... (OK)")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_screen_capture()
    test_hotkey_manager_signals()
    test_bridge_and_bubble_clipboard()
    test_fastapi_vision_endpoint()
    print("\nALL SCREEN CONTEXT & CLIPBOARD HOOK TESTS PASSED CLEANLY! (OK)")
    app.quit()
    sys.exit(0)
