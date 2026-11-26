"""
Tests for Jarvis Desktop Compact Voice HUD Mode and Startup Flow.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "desktop_bubble"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from bubble_ui import CompactHudWidget, DesktopAIBubble, JarvisBridge
from backend.server import app
from starlette.testclient import TestClient


def get_qapp():
    app_instance = QApplication.instance()
    if app_instance is None:
        app_instance = QApplication(sys.argv)
    return app_instance


def test_health_endpoint():
    print("[TEST] 1. Testing FastAPI /health endpoint...")
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data.get("status") == "ok", f"Expected 'ok', got {data.get('status')}"
    assert data.get("online") is True
    print("  -> /health returned 200 OK with status='ok', online=True (PASS)")


def test_compact_hud_widget_structure():
    print("[TEST] 2. Testing CompactHudWidget components and transcript updates...")
    qapp = get_qapp()
    bubble = DesktopAIBubble()
    hud = CompactHudWidget(bubble)

    assert hud is not None
    assert hud.orb is not None
    assert hud.status_label is not None
    assert hud.transcript_label is not None
    assert hud.btn_expand_full is not None
    assert hud.btn_mute_stop is not None
    assert hud.btn_min is not None

    # Test transcript updates
    hud.set_transcript("Affirmative, Sir.", "jarvis")
    assert "Affirmative, Sir." in hud.transcript_label.text()
    assert "J.A.R.V.I.S." in hud.status_label.text()

    hud.set_transcript("What is the battery level?", "user")
    assert "What is the battery level?" in hud.transcript_label.text()
    assert "SIR" in hud.status_label.text()

    hud.set_transcript("Listening to your directive...", "system")
    assert "Listening to your directive..." in hud.transcript_label.text()
    assert "LISTENING" in hud.status_label.text()
    print("  -> Compact HUD components and speaker-reactive transcript working (PASS)")


def test_desktop_bubble_mode_toggle():
    print("[TEST] 3. Testing mode toggle between Full (420x640) and Compact HUD (320x110)...")
    qapp = get_qapp()
    bubble = DesktopAIBubble()
    assert bubble.popup_mode == "full"

    # Toggle to compact
    bubble.toggle_popup_mode()
    assert bubble.popup_mode == "compact"

    # Toggle back to full
    bubble.toggle_popup_mode()
    assert bubble.popup_mode == "full"

    # Direct set
    bubble.set_popup_mode("compact")
    assert bubble.popup_mode == "compact"
    bubble.set_popup_mode("invalid_mode")
    assert bubble.popup_mode == "compact"
    print("  -> Mode toggle full/compact logic working (PASS)")


def test_stop_directive_and_bridge_transcript():
    print("[TEST] 4. Testing stop directive and bridge transcript signal...")
    qapp = get_qapp()
    bubble = DesktopAIBubble()
    bubble.set_state("speaking")
    assert bubble.state == "speaking"

    bubble.stop_directive()
    assert bubble.state == "idle"
    assert "stopped" in bubble.compact_hud_widget.transcript_label.text().lower()

    # Test bridge transcript slot
    bubble.bridge.updateTranscriptSpeaker("Processing audio waveform...", "jarvis")
    assert "Processing audio waveform..." in bubble.compact_hud_widget.transcript_label.text()
    print("  -> Stop directive and bridge transcript signals working (PASS)")


def test_launcher_scripts_exist():
    print("[TEST] 5. Verifying launcher and startup scripts...")
    bat_launcher = os.path.join(ROOT_DIR, "start_jarvis_desktop.bat")
    ps1_launcher = os.path.join(ROOT_DIR, "start_jarvis_desktop.ps1")
    vbs_launcher = os.path.join(ROOT_DIR, "start_jarvis_desktop.vbs")
    install_ps1 = os.path.join(ROOT_DIR, "install_startup.ps1")
    install_bat = os.path.join(ROOT_DIR, "install_startup.bat")

    for path in [bat_launcher, ps1_launcher, vbs_launcher, install_ps1, install_bat]:
        assert os.path.isfile(path), f"File {path} must exist"
        assert os.path.getsize(path) > 10, f"File {path} must not be empty"
        print(f"  -> File verified: {os.path.basename(path)}")
    print("  -> All launcher and installer scripts exist (PASS)")


if __name__ == "__main__":
    test_health_endpoint()
    test_compact_hud_widget_structure()
    test_desktop_bubble_mode_toggle()
    test_stop_directive_and_bridge_transcript()
    test_launcher_scripts_exist()
    print("\n✅ ALL COMPACT HUD & STARTUP TESTS PASSED SUCCESSFULLY!")
    sys.exit(0)
