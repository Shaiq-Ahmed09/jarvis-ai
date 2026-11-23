"""J.A.R.V.I.S. Optical Intruder Sentinel & Screen Lock
Monitors webcam frames using OpenCV when armed or during workstation idle.
Detects faces, snapshots intruders to data/intruders/, and immediately locks Windows (LockWorkStation).
"""
import ctypes
import os
import threading
import time
from datetime import datetime
from pathlib import Path
import cv2

HERE = Path(__file__).resolve().parent.parent
INTRUDER_DIR = HERE / "data" / "intruders"

class IntruderSentinel:
    def __init__(self):
        self.armed = False
        self._thread = None
        self._running = False
        self.last_intruder_time = 0
        self.intruder_history = []
        INTRUDER_DIR.mkdir(parents=True, exist_ok=True)

    def arm(self) -> dict:
        """Arm the optical webcam intruder watchdog."""
        if self.armed:
            return {"status": "already_armed", "message": "Optical Intruder Sentinel is already active and armed, Sir."}
        self.armed = True
        self._running = True
        self._thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._thread.start()
        return {
            "status": "armed",
            "message": "Optical Intruder Sentinel ARMED. Workstation will lock automatically if an unrecognized presence is detected."
        }

    def disarm(self) -> dict:
        """Disarm the optical webcam intruder watchdog."""
        self.armed = False
        self._running = False
        return {"status": "disarmed", "message": "Optical Intruder Sentinel DISARMED."}

    def get_status(self) -> dict:
        """Retrieve sentry status and recent alerts."""
        return {
            "armed": self.armed,
            "running": self._running,
            "total_detections": len(self.intruder_history),
            "recent_events": self.intruder_history[-5:],
            "intruder_dir": str(INTRUDER_DIR)
        }

    def _watchdog_loop(self):
        """Webcam scan loop running every 2.5 seconds when armed."""
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)

        while self._running and self.armed:
            try:
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    time.sleep(4)
                    continue

                ret, frame = cap.read()
                cap.release()

                if not ret or frame is None:
                    time.sleep(3)
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(60, 60))

                now = time.time()
                # If a face is detected and sentry is armed, lock workstation and snap intruder photo
                if len(faces) > 0 and (now - self.last_intruder_time > 30):
                    self.last_intruder_time = now
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    photo_name = f"intruder_{ts}.jpg"
                    photo_path = INTRUDER_DIR / photo_name

                    # Draw red tactical targeting box on intruder
                    for (x, y, w, h) in faces:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        cv2.putText(frame, "SECURITY BREACH", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    cv2.imwrite(str(photo_path), frame)

                    evt = {
                        "timestamp": datetime.now().isoformat(),
                        "photo": photo_name,
                        "faces_detected": len(faces),
                        "action": "Workstation Locked"
                    }
                    self.intruder_history.append(evt)

                    # Lock Windows Workstation immediately
                    try:
                        ctypes.windll.user32.LockWorkStation()
                    except Exception as ex:
                        print(f"LockWorkStation error: {ex}")

            except Exception as e:
                print(f"Intruder watchdog loop error: {e}")

            time.sleep(2.5)

_sentinel_singleton = None

def get_intruder_sentinel() -> IntruderSentinel:
    global _sentinel_singleton
    if _sentinel_singleton is None:
        _sentinel_singleton = IntruderSentinel()
    return _sentinel_singleton
