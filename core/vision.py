"""J.A.R.V.I.S. High-Speed Visual Intelligence & Autonomous OCR Navigation Engine.
Powered by RapidOCR (ONNX Runtime) and OpenCV with sub-second execution on Windows 11.
Provides real-time UI element detection, label-based clicking, and Stark HUD telemetry overlays.
"""

import asyncio
import base64
import ctypes
import difflib
import io
import re
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageGrab
import pyautogui

# Module-level cached OCR engine for zero reload overhead
_OCR_ENGINE = None

def ensure_desktop_attached() -> bool:
    """Attach current thread to the interactive Windows user desktop station."""
    if sys.platform == "win32":
        try:
            hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                ctypes.windll.user32.SetThreadDesktop(hdesk)
                return True
        except Exception:
            pass
    return False

def get_ocr_engine():
    """Lazily initialize and return the singleton RapidOCR ONNX engine without cls overhead."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        # Initialize RapidOCR with use_cls=False to avoid unnecessary angle classification
        _OCR_ENGINE = RapidOCR(use_cls=False)
    return _OCR_ENGINE

def prewarm_vision() -> float:
    """Pre-warm ONNX runtime weights with a blank frame to achieve zero latency on first turn."""
    t0 = time.perf_counter()
    engine = get_ocr_engine()
    dummy = np.zeros((100, 100, 3), dtype=np.uint8)
    engine(dummy, use_cls=False)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000

def capture_desktop() -> Image.Image:
    """Capture a high-fidelity screenshot of the primary Windows display."""
    ensure_desktop_attached()
    try:
        return ImageGrab.grab()
    except Exception:
        # Fallback to PyAutoGUI screenshot
        return pyautogui.screenshot()

def detect_ui_elements(
    pil_img: Optional[Image.Image] = None,
    downscale: float = 0.55
) -> Tuple[List[Dict[str, Any]], Image.Image, float]:
    """Capture screen and detect all UI buttons, links, labels, and text with their screen coordinates.
    
    Returns:
        elements: List of dicts with 'text', 'center': (x, y), 'box': [(x1,y1), ...], 'score': float
        pil_img: The captured source PIL Image
        latency_ms: Processing duration in milliseconds
    """
    t0 = time.perf_counter()
    if pil_img is None:
        pil_img = capture_desktop()
        
    np_img = np.array(pil_img)
    # Convert RGB to BGR for OpenCV
    if len(np_img.shape) == 3 and np_img.shape[2] == 3:
        bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
    else:
        bgr = np_img

    scale = max(0.2, min(1.0, downscale))
    if scale < 1.0:
        small = cv2.resize(bgr, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = bgr

    engine = get_ocr_engine()
    ocr_results, _ = engine(small, use_cls=False)
    
    elements = []
    if ocr_results:
        for box, text, score in ocr_results:
            cleaned_text = str(text).strip()
            if not cleaned_text:
                continue
                
            # Map box coordinates back to full desktop resolution
            full_box = [[round(pt[0] / scale), round(pt[1] / scale)] for pt in box]
            cx = round((box[0][0] + box[2][0]) / (2.0 * scale))
            cy = round((box[0][1] + box[2][1]) / (2.0 * scale))
            
            elements.append({
                "text": cleaned_text,
                "center": (cx, cy),
                "box": full_box,
                "score": float(score)
            })

    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000
    return elements, pil_img, latency_ms

def _normalize_label(label: str) -> str:
    """Normalize label for robust fuzzy matching."""
    s = label.lower().strip()
    s = re.sub(r'^(click|press|tap|select|open|hit|button|the|link)\s+', '', s)
    s = re.sub(r'\s+(button|link|tab|icon)$', '', s)
    s = re.sub(r'[^\w\s]', '', s)
    return s.strip()

def find_element_by_label(
    query: str,
    elements: Optional[List[Dict[str, Any]]] = None,
    pil_img: Optional[Image.Image] = None,
    downscale: float = 0.55
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Image.Image, float]:
    """Search detected UI elements by text label using exact, word boundary, and fuzzy matching."""
    latency_ms = 0.0
    if elements is None:
        elements, pil_img, latency_ms = detect_ui_elements(pil_img, downscale=downscale)
    elif pil_img is None:
        pil_img = capture_desktop()

    q_norm = _normalize_label(query)
    q_words = set(q_norm.split())

    best_match = None
    best_score = 0.0

    for el in elements:
        text = el["text"]
        t_norm = _normalize_label(text)
        t_words = set(t_norm.split())
        
        score = 0.0
        # 1. Exact match
        if q_norm == t_norm:
            score = 100.0 + el["score"]
        # 2. Query is full substring of element text (e.g. "compose" in "compose email")
        elif q_norm and q_norm in t_norm:
            coverage = len(q_norm) / max(1, len(t_norm))
            score = 80.0 + (coverage * 15.0) + el["score"]
        # 3. Element text is whole word inside query (e.g. "submit" in "please click submit now")
        elif t_norm and t_norm in q_words:
            coverage = len(t_norm) / max(1, len(q_norm))
            score = 75.0 + (coverage * 15.0) + el["score"]
        # 4. Multi-word overlap (e.g. "new tab" matching "new tab button")
        elif q_words and t_words:
            overlap = q_words.intersection(t_words)
            if overlap:
                overlap_ratio = len(overlap) / max(len(q_words), len(t_words))
                if overlap_ratio >= 0.5:
                    score = 60.0 + (overlap_ratio * 30.0) + el["score"]
        # 5. Fuzzy sequence similarity (only if reasonable length ratio and similarity)
        if score == 0.0:
            len_ratio = min(len(q_norm), len(t_norm)) / max(1, max(len(q_norm), len(t_norm)))
            if len_ratio >= 0.5:
                sim = difflib.SequenceMatcher(None, q_norm, t_norm).ratio()
                if sim >= 0.65:
                    score = (sim * 50.0) + el["score"]

        if score > best_score:
            best_score = score
            best_match = el

    # Threshold for a confident match
    if best_score < 45.0:
        best_match = None

    return best_match, elements, pil_img, latency_ms

def render_hud_visual_telemetry(
    pil_img: Image.Image,
    elements: List[Dict[str, Any]],
    highlight_target: Optional[Dict[str, Any]] = None,
    max_preview_width: int = 1280
) -> str:
    """Render Stark-tech cyan HUD bounding boxes and targeted crosshairs, returning base64 JPEG."""
    canvas = pil_img.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()

    # Colors
    cyan_stroke = (0, 240, 255, 190)
    cyan_fill = (0, 240, 255, 20)
    green_stroke = (0, 255, 128, 255)
    green_fill = (0, 255, 128, 70)

    # 1. Draw all detected elements
    for el in elements:
        box = el["box"]
        poly = [(p[0], p[1]) for p in box]
        draw.polygon(poly, fill=cyan_fill, outline=cyan_stroke, width=1)
        
        # High-tech corner ticks
        x1, y1 = box[0]
        x2, y2 = box[1]
        x3, y3 = box[2]
        tick_len = min(6, max(2, int((x2 - x1) * 0.2)))
        draw.line([(x1, y1), (x1 + tick_len, y1)], fill=cyan_stroke, width=2)
        draw.line([(x1, y1), (x1, y1 + tick_len)], fill=cyan_stroke, width=2)
        draw.line([(x3, y3), (x3 - tick_len, y3)], fill=cyan_stroke, width=2)
        draw.line([(x3, y3), (x3, y3 - tick_len)], fill=cyan_stroke, width=2)

    # 2. Draw highlighted target with neon reticle
    if highlight_target:
        box = highlight_target["box"]
        cx, cy = highlight_target["center"]
        poly = [(p[0], p[1]) for p in box]
        # Thicker glowing polygon
        draw.polygon(poly, fill=green_fill, outline=green_stroke, width=3)

        # Crosshair reticle
        r = 14
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=green_stroke, width=2)
        draw.line([(cx - r - 8, cy), (cx + r + 8, cy)], fill=green_stroke, width=2)
        draw.line([(cx, cy - r - 8), (cx, cy + r + 8)], fill=green_stroke, width=2)

        # High-tech target banner
        lbl = f"TARGET: {highlight_target['text'][:25]} [{cx}, {cy}]"
        bbox = draw.textbbox((box[0][0], max(0, box[0][1] - 18)), lbl, font=font)
        draw.rectangle(bbox, fill=(0, 20, 25, 230), outline=green_stroke, width=1)
        draw.text((box[0][0] + 2, max(0, box[0][1] - 18)), lbl, fill=(0, 255, 128, 255), font=font)

    # Downscale for crisp, low-latency HUD streaming
    w, h = canvas.size
    if w > max_preview_width:
        ratio = max_preview_width / float(w)
        canvas = canvas.resize((max_preview_width, int(h * ratio)), Image.Resampling.BILINEAR)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=75, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def click_element_action(
    text_label: str,
    button: str = "left",
    clicks: int = 1,
    downscale: float = 0.55
) -> Dict[str, Any]:
    """Locate on-screen element by label, execute click, and produce telemetry image."""
    t0 = time.perf_counter()
    best_el, elements, pil_img, ocr_lat = find_element_by_label(text_label, downscale=downscale)
    
    if not best_el:
        # Generate HUD telemetry showing all currently detected items for diagnosis
        hud_b64 = render_hud_visual_telemetry(pil_img, elements, highlight_target=None)
        labels_preview = [e["text"] for e in elements[:12]]
        return {
            "success": False,
            "error": f"Element '{text_label}' could not be identified on the active display.",
            "detected_labels": labels_preview,
            "total_detected": len(elements),
            "image_b64": hud_b64,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
        }

    # Execute physical click
    cx, cy = best_el["center"]
    pyautogui.click(cx, cy, clicks=clicks, button=button)
    
    # Render Stark HUD overlay with target acquired reticle
    hud_b64 = render_hud_visual_telemetry(pil_img, elements, highlight_target=best_el)
    total_lat = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "success": True,
        "element": best_el,
        "clicked_at": (cx, cy),
        "button": button,
        "clicks": clicks,
        "image_b64": hud_b64,
        "latency_ms": total_lat
    }
