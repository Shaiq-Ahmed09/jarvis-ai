"""
J.A.R.V.I.S. Desktop Screen Capture & Multimodal Vision Bridge
==============================================================
Captures Windows primary display or active window using mss or PIL.ImageGrab.
Attaches automatically to interactive Windows desktop station.
Resizes image to max 1280px width for low-latency neural inference.
Encodes as optimized base64 JPEG and provides FastAPI multimodal submission.
"""

import sys
import io
import time
import base64
import ctypes
from typing import Optional, Dict, Any
from PIL import Image


def ensure_desktop_attached() -> bool:
    """Attaches the calling thread to the interactive Windows user desktop."""
    if sys.platform == "win32":
        try:
            hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                ctypes.windll.user32.SetThreadDesktop(hdesk)
                return True
        except Exception:
            pass
    return False


def capture_screen_pil() -> Image.Image:
    """
    Captures high-fidelity snapshot of primary monitor.
    Uses mss as primary high-speed grabber, falling back to PIL.ImageGrab.
    """
    ensure_desktop_attached()

    # 1. High-speed mss grab
    try:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(mon)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        pass

    # 2. PIL ImageGrab fallback
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        if img:
            return img.convert("RGB") if img.mode != "RGB" else img
    except Exception:
        pass

    # 3. PySide6 screen grab fallback
    try:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            pix = screen.grabWindow(0)
            from PIL import ImageQt
            return ImageQt.fromqpixmap(pix).convert("RGB")
    except Exception:
        pass

    raise RuntimeError("Failed to capture Windows desktop display.")


def capture_screen_base64(max_width: int = 1280, quality: int = 80) -> str:
    """
    Captures primary screen, resizes to max_width (default: 1280px maintaining aspect ratio),
    and encodes as optimized base64 JPEG string.
    """
    img = capture_screen_pil()
    w, h = img.size

    # Resize to max 1280px width for fast neural vision inference
    if w > max_width:
        ratio = max_width / float(w)
        new_h = int(h * ratio)
        img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def send_to_vision_api(
    backend_url: str,
    image_b64: str,
    query: str = "Describe what is on screen and what you observe."
) -> Dict[str, Any]:
    """Sends captured screen image to FastAPI multimodal vision endpoint."""
    import httpx
    target_url = backend_url.rstrip("/")
    if not target_url.startswith("http"):
        target_url = f"http://{target_url}"
    vision_endpoint = f"{target_url}/api/vision"

    payload = {
        "query": query,
        "image": image_b64
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(vision_endpoint, json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Vision API returned status {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"error": f"Failed to connect to Vision API: {e}"}
