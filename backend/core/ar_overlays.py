"""J.A.R.V.I.S. Holographic Augmented Reality Window Overlays
Projects live 2.5D spatial holographic window matrices, tracking desktop window geometries,
process resource consumption, focus hierarchy, and instantaneous HUD snapping controls.
"""
import ctypes
import psutil
import pyautogui
from typing import List, Dict, Any
from core.window_manager import list_desktop_windows, activate_window_hwnd

user32 = ctypes.windll.user32

def get_holographic_window_matrix() -> Dict[str, Any]:
    """Scan and compute the 2.5D spatial AR matrix of all active desktop windows."""
    scr_w, scr_h = pyautogui.size()
    fg_hwnd = user32.GetForegroundWindow()
    raw_windows = list_desktop_windows()
    
    ar_windows: List[Dict[str, Any]] = []
    
    for idx, w in enumerate(raw_windows[:12]):
        hwnd = w["hwnd"]
        pid = w["pid"]
        rect = w["rect"] # (left, top, right, bottom)
        
        # Calculate screen geometry
        left, top, right, bottom = rect
        width = max(10, right - left)
        height = max(10, bottom - top)
        
        # Normalized coordinates (0.0 to 1.0)
        norm_x = round(max(0.0, min(1.0, left / scr_w)), 3)
        norm_y = round(max(0.0, min(1.0, top / scr_h)), 3)
        norm_w = round(max(0.05, min(1.0, width / scr_w)), 3)
        norm_h = round(max(0.05, min(1.0, height / scr_h)), 3)
        
        # Query process telemetry
        mem_mb = 0.0
        cpu_pct = 0.0
        try:
            p = psutil.Process(pid)
            mem_mb = round(p.memory_info().rss / (1024 * 1024), 1)
            cpu_pct = round(p.cpu_percent(interval=None), 1)
        except Exception:
            pass

        is_focused = (hwnd == fg_hwnd)
        
        ar_windows.append({
            "index": idx + 1,
            "hwnd": hwnd,
            "title": w["title"],
            "process": w["process"],
            "pid": pid,
            "is_focused": is_focused,
            "coords": {
                "x": left,
                "y": top,
                "width": width,
                "height": height
            },
            "normalized": {
                "x": norm_x,
                "y": norm_y,
                "w": norm_w,
                "h": norm_h
            },
            "telemetry": {
                "ram_mb": mem_mb,
                "cpu_pct": cpu_pct
            },
            "status": "FOCUSED_ACTIVE" if is_focused else "BACKGROUND_STANDBY"
        })

    return {
        "timestamp": pyautogui.time.time(),
        "display": {
            "width": scr_w,
            "height": scr_h,
            "aspect_ratio": round(scr_w / scr_h, 2)
        },
        "total_windows": len(ar_windows),
        "windows": ar_windows
    }

def ar_control_window(hwnd: int, action: str) -> Dict[str, Any]:
    """Execute holographic AR window command: 'focus', 'snap_left', 'snap_right', 'maximize', 'minimize', 'close'."""
    try:
        if action == "focus":
            activate_window_hwnd(hwnd)
            return {"success": True, "action": action, "hwnd": hwnd}
            
        activate_window_hwnd(hwnd)
        SW_MAXIMIZE = 3
        SW_MINIMIZE = 6
        SW_RESTORE = 9
        
        if action == "maximize":
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
        elif action == "minimize":
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        elif action == "snap_left":
            user32.ShowWindow(hwnd, SW_RESTORE)
            pyautogui.hotkey("win", "left")
        elif action == "snap_right":
            user32.ShowWindow(hwnd, SW_RESTORE)
            pyautogui.hotkey("win", "right")
        elif action == "close":
            WM_CLOSE = 0x0010
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            
        return {"success": True, "action": action, "hwnd": hwnd}
    except Exception as e:
        return {"success": False, "error": str(e), "hwnd": hwnd}
