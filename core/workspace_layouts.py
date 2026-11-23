"""J.A.R.V.I.S. Workspace Layouts Engine
Stark Multi-App Grid Snap & Workspace Profiles for Windows 11.
Autonomously positions, resizes, and aligns applications (VS Code, Brave, Terminal, Spotify, YouTube).
"""
import ctypes
import os
import subprocess
import time
from pathlib import Path
import psutil

from core.window_manager import list_desktop_windows, activate_window_hwnd, focus_app
from core.browser import launch_browser_tab

user32 = ctypes.windll.user32
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004
SW_RESTORE = 9

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

def get_work_area():
    """Retrieve usable desktop work area excluding the Windows taskbar."""
    rect = RECT()
    SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
    return rect.left, rect.top, w, h

def move_window_exact(hwnd: int, x: int, y: int, width: int, height: int):
    """Restore and position an HWND to exact pixel coordinates."""
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.08)
        user32.SetWindowPos(hwnd, 0, int(x), int(y), int(width), int(height), SWP_SHOWWINDOW | SWP_NOZORDER)
        user32.BringWindowToTop(hwnd)
        return True
    except Exception as e:
        print(f"SetWindowPos error on HWND {hwnd}: {e}")
        return False

def find_hwnd_by_alias(alias: str) -> int | None:
    """Find the top-level HWND matching an app alias."""
    alias = alias.lower().strip()
    windows = list_desktop_windows()
    for w in windows:
        pname = w["process"].lower()
        title = w["title"].lower()
        if alias in pname or pname.replace(".exe", "") == alias:
            return w["hwnd"]
        if alias in title:
            return w["hwnd"]
    return None

def ensure_app_running(alias: str, launch_cmd: str = None) -> int | None:
    """Ensure an application is running; launch it if not present."""
    hwnd = find_hwnd_by_alias(alias)
    if hwnd:
        return hwnd
    
    # Launch application
    if launch_cmd:
        try:
            subprocess.Popen(launch_cmd, shell=True)
            time.sleep(1.2)
        except Exception as e:
            print(f"Launch error: {e}")
    
    return find_hwnd_by_alias(alias)

def apply_workspace_layout(layout_name: str = "coding") -> dict:
    """Apply a pre-configured Stark Multi-App Grid Layout.
    Layouts:
    - 'coding': VS Code (left 50%), Brave Browser (top-right 50%), Terminal (bottom-right 50%)
    - 'entertainment': Spotify (left 50%), YouTube / Media (right 50%)
    - 'focus_split': Primary App (left 65%), Reference (right 35%)
    - 'quad': 4 equal quadrant windows
    """
    layout = layout_name.lower().strip()
    left_offset, top_offset, work_w, work_h = get_work_area()
    half_w = work_w // 2
    half_h = work_h // 2
    
    # 1. CODING WORKSPACE LAYOUT
    if layout in ["coding", "code", "dev", "developer", "dev_sprint"]:
        # Launch/Ensure VS Code
        code_hwnd = ensure_app_running("code", "code")
        # Launch/Ensure Brave or Preferred Browser
        brave_hwnd = ensure_app_running("brave", None)
        if not brave_hwnd:
            brave_hwnd = ensure_app_running("chrome") or ensure_app_running("msedge")
        # Launch/Ensure Windows Terminal or PowerShell
        term_hwnd = ensure_app_running("windowsterminal", "wt") or ensure_app_running("powershell", "powershell") or ensure_app_running("cmd", "cmd")
        
        results = {}
        # Position VS Code: Left Half
        if code_hwnd:
            move_window_exact(code_hwnd, left_offset, top_offset, half_w, work_h)
            results["vscode"] = f"Snapped left (0, 0, {half_w}x{work_h})"
            
        # Position Browser: Top-Right (65% height)
        browser_h = int(work_h * 0.65)
        if brave_hwnd:
            move_window_exact(brave_hwnd, left_offset + half_w, top_offset, half_w, browser_h)
            results["browser"] = f"Snapped top-right ({half_w}, 0, {half_w}x{browser_h})"
            
        # Position Terminal: Bottom-Right (35% height)
        term_h = work_h - browser_h
        if term_hwnd:
            move_window_exact(term_hwnd, left_offset + half_w, top_offset + browser_h, half_w, term_h)
            results["terminal"] = f"Snapped bottom-right ({half_w}, {browser_h}, {half_w}x{term_h})"
            
        return {
            "success": True,
            "layout": "Coding Workspace",
            "windows_positioned": results,
            "message": "Coding workspace aligned: VS Code (Left Half), Browser (Top-Right), Terminal (Bottom-Right), Sir."
        }

    # 2. ENTERTAINMENT WORKSPACE LAYOUT
    elif layout in ["entertainment", "media", "music", "chill"]:
        spotify_hwnd = ensure_app_running("spotify", "spotify")
        browser_hwnd = find_hwnd_by_alias("brave") or find_hwnd_by_alias("chrome") or find_hwnd_by_alias("msedge")
        if not browser_hwnd:
            launch_browser_tab("https://www.youtube.com")
            time.sleep(1.2)
            browser_hwnd = find_hwnd_by_alias("brave") or find_hwnd_by_alias("chrome") or find_hwnd_by_alias("msedge")
            
        results = {}
        if spotify_hwnd:
            move_window_exact(spotify_hwnd, left_offset, top_offset, half_w, work_h)
            results["spotify"] = "Snapped left half"
        if browser_hwnd:
            move_window_exact(browser_hwnd, left_offset + half_w, top_offset, half_w, work_h)
            results["youtube_browser"] = "Snapped right half"
            
        return {
            "success": True,
            "layout": "Entertainment Workspace",
            "windows_positioned": results,
            "message": "Entertainment layout active: Spotify (Left Half), YouTube / Browser (Right Half)."
        }

    # 3. FOCUS SPLIT LAYOUT (65% Primary, 35% Secondary)
    elif layout in ["split", "focus_split", "reading", "research"]:
        windows = list_desktop_windows()
        if len(windows) >= 2:
            main_w = int(work_w * 0.65)
            side_w = work_w - main_w
            move_window_exact(windows[0]["hwnd"], left_offset, top_offset, main_w, work_h)
            move_window_exact(windows[1]["hwnd"], left_offset + main_w, top_offset, side_w, work_h)
            return {
                "success": True,
                "layout": "Focus Split",
                "message": f"Split screen engaged: '{windows[0]['title'][:25]}' (65%), '{windows[1]['title'][:25]}' (35%)."
            }
        return {"success": False, "error": "Need at least 2 open desktop windows to split."}

    # 4. QUADRANT LAYOUT (4 corners)
    elif layout in ["quad", "quadrant", "four"]:
        windows = list_desktop_windows()[:4]
        coords = [
            (left_offset, top_offset, half_w, half_h),
            (left_offset + half_w, top_offset, half_w, half_h),
            (left_offset, top_offset + half_h, half_w, half_h),
            (left_offset + half_w, top_offset + half_h, half_w, half_h),
        ]
        positioned = []
        for w, (x, y, width, height) in zip(windows, coords):
            move_window_exact(w["hwnd"], x, y, width, height)
            positioned.append(w["title"][:20])
        return {
            "success": True,
            "layout": "Quadrant Grid",
            "positioned": positioned,
            "message": f"Quadrant grid aligned across {len(positioned)} windows."
        }

    return {"success": False, "error": f"Unknown layout profile '{layout}'. Available: coding, entertainment, split, quad."}
