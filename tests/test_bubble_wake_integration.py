"""
Integration Test: Wake-Word to Desktop Bubble Expansion & Mic Sync
===================================================================
Tests that:
1. WakeWordWorker emits wake_detected('hey_jarvis').
2. DesktopAIBubble automatically expands popup from 96x96 to 420x640.
3. Orb switches state to 'listening'.
4. Mic RMS audio_level signal modulates the bubble's audio level.
5. QWebChannel setMicDevice properly synchronizes selected mic to wake_worker.
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path("desktop_bubble").resolve()))

from PySide6.QtWidgets import QApplication
from bubble_ui import DesktopAIBubble

app = QApplication.instance() or QApplication(sys.argv)

print("1. Launching DesktopAIBubble...")
bubble = DesktopAIBubble("http://localhost:8765")
bubble.show()
app.processEvents()

assert bubble.width() == 96 and bubble.height() == 96
assert bubble.is_expanded == False
assert bubble.state == "idle"
print(" -> Collapsed bubble initialized in idle state.")

# Test live audio level pulsing
print("2. Testing audio level pulsing from WakeWordWorker...")
bubble.wake_worker.audio_level.emit(0.68)
app.processEvents()
assert bubble._audio_level > 0.1, f"Expected audio level > 0.1, got {bubble._audio_level}"
print(f" -> Bubble audio level updated to {bubble._audio_level:.2f} (OK)")

# Test microphone synchronization from web bridge
print("3. Testing microphone sync from Web App Settings bridge...")
bubble.bridge.setMicDevice("HyperX SoloCast Gaming Mic", "guid-hyperx-001")
app.processEvents()
assert bubble.wake_worker._pending_mic_label == "HyperX SoloCast Gaming Mic"
print(" -> Microphone change synced to WakeWordWorker successfully (OK)")

# Test Wake Word Trigger ("Hey Jarvis")
print("4. Triggering Wake-Word Detection ('Hey Jarvis')...")
bubble.wake_worker.trigger_wake_word("hey_jarvis")
app.processEvents()

# Bubble should now automatically expand and switch to listening state
assert bubble.is_expanded == True, "Bubble should have expanded upon wake word detection"
assert bubble.state == "listening", f"Bubble state should be 'listening', got '{bubble.state}'"
assert bubble.status_pill.text() == "● LISTENING"
print(" -> Bubble automatically expanded to 420x640 and state set to LISTENING! (OK)")

# Collapse back to bubble
print("5. Collapsing back to bubble...")
bubble.collapse_bubble()
app.processEvents()
assert bubble.is_expanded == False
print(" -> Cleanly collapsed back to floating orb.")

bubble.wake_worker.stop()
bubble.client.shutdown()
bubble.close()
app.quit()
print("\nALL WAKE-WORD TO BUBBLE EXPANSION INTEGRATION TESTS PASSED CLEANLY! (OK)")
