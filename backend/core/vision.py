"""J.A.R.V.I.S. High-Speed Visual Intelligence & Autonomous OCR Navigation Engine.
Powered by RapidOCR (ONNX Runtime) and OpenCV with sub-second execution on Windows 11.
Provides real-time UI element detection, label-based clicking, and Stark HUD telemetry overlays.
"""

import asyncio
import base64
import ctypes
import difflib
import io
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageGrab
import pyautogui
import pyperclip
from dotenv import load_dotenv

load_dotenv()

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

def click_and_type_action(
    text_label: str,
    text_to_type: str,
    press_enter: bool = True,
    clear_field: bool = False,
    downscale: float = 0.55
) -> Dict[str, Any]:
    """Locate on-screen input field or element by text label, click to focus, and type text."""
    t0 = time.perf_counter()
    best_el, elements, pil_img, _ = find_element_by_label(text_label, downscale=downscale)
    
    if not best_el:
        hud_b64 = render_hud_visual_telemetry(pil_img, elements, highlight_target=None)
        labels_preview = [e["text"] for e in elements[:12]]
        return {
            "success": False,
            "error": f"Target element '{text_label}' not found on display.",
            "detected_labels": labels_preview,
            "image_b64": hud_b64,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
        }

    cx, cy = best_el["center"]
    pyautogui.click(cx, cy)
    time.sleep(0.15)

    if clear_field:
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        time.sleep(0.05)

    # Use clipboard paste for instant, Unicode-safe typing
    try:
        pyperclip.copy(text_to_type)
        pyautogui.hotkey("ctrl", "v")
    except Exception:
        pyautogui.typewrite(text_to_type, interval=0.02)

    if press_enter:
        time.sleep(0.1)
        pyautogui.press("enter")

    hud_b64 = render_hud_visual_telemetry(pil_img, elements, highlight_target=best_el)
    lat = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "success": True,
        "element": best_el,
        "clicked_at": (cx, cy),
        "typed": text_to_type,
        "enter_pressed": press_enter,
        "image_b64": hud_b64,
        "latency_ms": lat
    }

def analyze_live_screen(
    query: str = "Describe what is currently visible on the active display, active applications, text, buttons, and context.",
    pil_img: Optional[Image.Image] = None,
    downscale: float = 0.55
) -> Dict[str, Any]:
    """Capture screen, run RapidOCR to identify all UI coordinates, and use Multimodal Gemini Vision to describe/read the screen."""
    t0 = time.perf_counter()
    if pil_img is None:
        pil_img = capture_desktop()

    elements, _, ocr_lat = detect_ui_elements(pil_img, downscale=downscale)
    hud_b64 = render_hud_visual_telemetry(pil_img, elements)

    # Compile OCR elements summary for precision
    labels_summary = "\n".join([f"- '{e['text']}' at screen position {e['center']}" for e in elements[:50]])

    # Initialize Gemini multimodal client
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    analysis_text = ""

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are J.A.R.V.I.S., the advanced AI assistant looking directly at Sir's live desktop screen.\n"
                f"User request: '{query}'\n\n"
                f"Instructions:\n"
                f"1. Explain what is visible on the screen clearly and concisely in Stark Industries J.A.R.V.I.S. persona.\n"
                f"2. Read any relevant text, code, titles, messages, or numbers Sir asked for.\n"
                f"3. Highlight key interactive elements, buttons, or open tabs Sir can click or interact with.\n\n"
                f"Prominent on-screen UI text elements detected by high-speed neural OCR:\n{labels_summary}"
            )
            # Resize image to reasonable size for vision API (max 1920 width)
            w, h = pil_img.size
            if w > 1920:
                scale_ratio = 1920.0 / w
                send_img = pil_img.resize((1920, int(h * scale_ratio)), Image.Resampling.BILINEAR)
            else:
                send_img = pil_img

            # Try models in order of capability
            models_to_try = [
                os.getenv("JARVIS_VISION_MODEL", "gemini-3.5-flash-lite"),
                "gemini-2.5-flash",
                "gemini-flash-latest"
            ]
            for m in models_to_try:
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents=[send_img, prompt]
                    )
                    if resp and resp.text:
                        analysis_text = resp.text.strip()
                        break
                except Exception:
                    continue
        except Exception as e:
            analysis_text = f"Visual multimodal pipeline encountered: {e}. Falling back to neural OCR mapping."

    if not analysis_text:
        # Fallback to local OCR synthesis if offline
        sample_texts = [e["text"] for e in elements[:20]]
        analysis_text = (
            f"Optical scan mapped {len(elements)} interactive UI elements across your display.\n"
            f"Prominent visible text:\n" + "\n".join([f"• {t}" for t in sample_texts])
        )

    lat = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "success": True,
        "query": query,
        "analysis": analysis_text,
        "detected_count": len(elements),
        "elements": [f"'{e['text']}' at {e['center']}" for e in elements[:30]],
        "image_b64": hud_b64,
        "latency_ms": lat
    }

def autonomous_navigate_step(
    goal: str,
    history: Optional[List[Dict[str, Any]]] = None,
    downscale: float = 0.55
) -> Dict[str, Any]:
    """Execute one autonomous perception-action step towards achieving a desktop goal.
    
    Captures live screen, detects UI elements, prompts Gemini to decide the next action,
    executes it (click, type, scroll, hotkey), and returns telemetry.
    """
    t0 = time.perf_counter()
    pil_img = capture_desktop()
    elements, _, _ = detect_ui_elements(pil_img, downscale=downscale)

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "error": "No API key configured for autonomous visual reasoning."}

    from google import genai
    client = genai.Client(api_key=api_key)

    elements_list = [{"text": e["text"], "center": e["center"]} for e in elements[:60]]
    history_str = json.dumps(history[-3:] if history else [], indent=2)

    prompt = (
        f"You are the visual navigation brain of J.A.R.V.I.S. controlling a Windows desktop.\n"
        f"Goal: {goal}\n"
        f"Previous steps taken: {history_str}\n\n"
        f"Detected visible UI elements on screen (with coordinates):\n{json.dumps(elements_list, indent=2)}\n\n"
        f"Choose the single next logical action to take to achieve the goal. Respond ONLY in valid JSON with this format:\n"
        f"{{\n"
        f'  "action": "click" | "type" | "hotkey" | "scroll" | "done",\n'
        f'  "target_label": "exact text label to click or focus",\n'
        f'  "text_to_type": "string to type if action is type",\n'
        f'  "keys": "e.g. enter, ctrl+t, esc if action is hotkey",\n'
        f'  "direction": "up" | "down" if action is scroll,\n'
        f'  "thought": "brief 1-sentence reasoning for this step"\n'
        f"}}"
    )

    try:
        resp = client.models.generate_content(
            model=os.getenv("JARVIS_VISION_MODEL", "gemini-3.5-flash-lite"),
            contents=[pil_img, prompt]
        )
        text = resp.text.strip()
        # Clean markdown codeblocks
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        decision = json.loads(text.strip())
    except Exception as e:
        decision = {"action": "done", "thought": f"Could not determine next visual step: {e}"}

    action = decision.get("action", "done")
    step_result = {"decision": decision, "action": action, "thought": decision.get("thought", "")}

    if action == "click":
        target = decision.get("target_label", "")
        res = click_element_action(target)
        step_result["execution"] = res
    elif action == "type":
        target = decision.get("target_label", "")
        txt = decision.get("text_to_type", "")
        res = click_and_type_action(target, txt, press_enter=True)
        step_result["execution"] = res
    elif action == "hotkey":
        keys = decision.get("keys", "enter").split("+")
        pyautogui.hotkey(*[k.strip().lower() for k in keys])
        step_result["execution"] = f"Pressed hotkey {keys}"
    elif action == "scroll":
        direction = decision.get("direction", "down")
        amt = -400 if direction == "down" else 400
        pyautogui.scroll(amt)
        step_result["execution"] = f"Scrolled {direction}"
    elif action == "done":
        step_result["execution"] = "Goal completed or terminal state reached."

    # Capture after-action screenshot
    after_img = capture_desktop()
    hud_b64 = render_hud_visual_telemetry(after_img, elements)
    step_result["image_b64"] = hud_b64
    step_result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    step_result["success"] = True

    return step_result
