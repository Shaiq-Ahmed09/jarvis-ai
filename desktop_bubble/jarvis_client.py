"""
J.A.R.V.I.S. FastAPI Async Client (PySide6 QThread + httpx)
============================================================
Non-blocking worker thread communicating with local FastAPI Jarvis backend.
Sends POST requests to http://localhost:8000/chat without freezing the UI.
Includes continuous background health monitoring and graceful offline recovery.
"""

import json
import logging
import httpx
from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger("JarvisClient")

DEFAULT_BASE_URL = "http://localhost:8000"


class ChatWorker(QThread):
    """Worker thread that executes the HTTP POST request to FastAPI backend."""
    response_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, base_url: str, prompt: str):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.prompt = prompt

    def run(self):
        url = f"{self.base_url}/chat"
        payload = {"message": self.prompt}
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    # Support multiple common response schemas
                    if isinstance(data, dict):
                        reply = (
                            data.get("response")
                            or data.get("reply")
                            or data.get("text")
                            or data.get("message")
                            or json.dumps(data, indent=2)
                        )
                    else:
                        reply = str(data)
                    self.response_received.emit(reply)
                else:
                    self.error_occurred.emit(
                        f"Server returned HTTP {resp.status_code}: {resp.text[:120]}"
                    )
        except httpx.ConnectError:
            self.error_occurred.emit(
                f"Cannot connect to Jarvis backend at {self.base_url}. Ensure server is running."
            )
        except httpx.TimeoutException:
            self.error_occurred.emit("Jarvis response timed out (30s). Please try again.")
        except Exception as e:
            self.error_occurred.emit(f"Unexpected error: {str(e)}")


class HealthWorker(QThread):
    """Background polling thread that tracks FastAPI Jarvis connection state."""
    status_updated = Signal(bool)  # True = Online, False = Offline

    def __init__(self, base_url: str, interval_sec: float = 4.0):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.interval_sec = interval_sec
        self._running = True

    def run(self):
        while self._running:
            online = self._ping()
            self.status_updated.emit(online)
            # Sleep in small slices for fast responsiveness on shutdown
            slices = int(self.interval_sec * 10)
            for _ in range(slices):
                if not self._running:
                    break
                self.msleep(100)

    def _ping(self) -> bool:
        test_urls = [
            f"{self.base_url}/",
            f"{self.base_url}/health",
            f"{self.base_url}/docs",
        ]
        for url in test_urls:
            try:
                with httpx.Client(timeout=1.5) as client:
                    resp = client.get(url)
                    if resp.status_code in (200, 404):
                        return True
            except Exception:
                continue
        return False

    def stop(self):
        self._running = False
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait(500)

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass


class JarvisClient(QObject):
    """High-level client coordinating chat requests and health monitoring."""
    response_received = Signal(str)
    error_occurred = Signal(str)
    status_changed = Signal(bool)
    thinking_started = Signal()

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        super().__init__()
        self.base_url = base_url
        self._active_worker = None
        self._health_worker = HealthWorker(self.base_url)
        self._health_worker.status_updated.connect(self._on_health_update)
        self._health_worker.start()
        self.is_online = False

    def _on_health_update(self, online: bool):
        if online != self.is_online:
            self.is_online = online
            self.status_changed.emit(online)

    def send_prompt(self, text: str):
        """Dispatches prompt non-blockingly via background ChatWorker."""
        text = text.strip()
        if not text:
            return

        self.thinking_started.emit()

        # If previous worker is running, disconnect before spawning new
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.terminate()
            self._active_worker.wait(500)

        self._active_worker = ChatWorker(self.base_url, text)
        self._active_worker.response_received.connect(self._handle_response)
        self._active_worker.error_occurred.connect(self._handle_error)
        self._active_worker.start()

    def _handle_response(self, text: str):
        self.is_online = True
        self.status_changed.emit(True)
        self.response_received.emit(text)

    def _handle_error(self, err: str):
        self.error_occurred.emit(err)

    def shutdown(self):
        """Clean shutdown of background threads."""
        if self._health_worker:
            self._health_worker.stop()
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.terminate()
            self._active_worker.wait(500)

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass
