"""J.A.R.V.I.S. Single-App Window & Tab Controller
Full hands-on control over individual desktop application windows, switching tabs,
foreground window activation, and autonomous app-to-app workflow loops.
"""
import ctypes
import time
import psutil
import pyautogui
import pyperclip

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
user32.EnumDesktopWindows.argtypes = [ctypes.c_void_p, WNDENUMPROC, ctypes.c_void_p]
user32.EnumDesktopWindows.restype = ctypes.c_bool

def _ensure_desktop():
    """Ensure current thread is attached to the active interactive input desktop."""
    try:
        hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return hdesk
    except Exception:
        pass
    return None

def list_desktop_windows() -> list[dict]:
    """Enumerate all open, visible top-level application windows on the desktop."""
    hdesk = _ensure_desktop()
    windows = []
    
    def callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
                
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
                
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
            
            # Filter zero-sized and system shell overlays
            rect = (ctypes.c_long * 4)()
            user32.GetWindowRect(hwnd, rect)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w < 100 or h < 100:
                return True
                
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            try:
                p = psutil.Process(pid.value)
                pname = p.name()
            except Exception:
                pname = "unknown"
                
            # Filter explorer shell overlays
            if pname.lower() == "explorer.exe" and title in ["Program Manager", "Start"]:
                return True
                
            windows.append({
                "hwnd": hwnd,
                "title": title,
                "process": pname,
                "pid": pid.value,
                "rect": (rect[0], rect[1], rect[2], rect[3]),
                "width": w,
                "height": h
            })
        except Exception:
            pass
        return True

    cb = WNDENUMPROC(callback)
    user32.EnumDesktopWindows(hdesk, cb, 0)
    return windows

def activate_window_hwnd(hwnd: int) -> bool:
    """Bypass Windows 11 foreground restrictions and bring window to the front."""
    try:
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        
        fg_hwnd = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
        cur_thread = kernel32.GetCurrentThreadId()
        
        if fg_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, fg_thread, True)
            
        # Simulate Alt key release to unlock foreground rights in Win32
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        
        if fg_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
            
        time.sleep(0.1)
        return True
    except Exception as e:
        print(f"Window activation error: {e}")
        return False

def focus_app(target: str) -> dict:
    """Find and focus an individual application by process name or window title."""
    t = target.lower().strip()
    windows = list_desktop_windows()
    
    # 1. Exact or partial process name match (e.g. 'brave', 'antigravity', 'code', 'notepad', 'spotify')
    for w in windows:
        pname = w["process"].lower()
        if t in pname or pname.replace(".exe", "") == t:
            activate_window_hwnd(w["hwnd"])
            return {"success": True, "title": w["title"], "process": w["process"], "hwnd": w["hwnd"]}
            
    # 2. Window title match
    for w in windows:
        if t in w["title"].lower():
            activate_window_hwnd(w["hwnd"])
            return {"success": True, "title": w["title"], "process": w["process"], "hwnd": w["hwnd"]}
            
    # 3. Known aliases
    alias_map = {
        "browser": "brave",
        "chat": "brave",
        "ide": "antigravity",
        "editor": "antigravity",
        "vs code": "code",
        "vscode": "code",
        "terminal": "wt",
        "explorer": "explorer",
        "files": "explorer",
    }
    alias = alias_map.get(t)
    if alias:
        for w in windows:
            if alias in w["process"].lower():
                activate_window_hwnd(w["hwnd"])
                return {"success": True, "title": w["title"], "process": w["process"], "hwnd": w["hwnd"]}

    return {"success": False, "error": f"No active window found matching '{target}'. Available: {[w['process'] + ': ' + w['title'][:30] for w in windows]}"}

def switch_app_tabs(direction: str = "next", tab_index: int = None) -> str:
    """Switch browser or editor tabs in the currently focused application."""
    if tab_index is not None and 1 <= tab_index <= 9:
        pyautogui.hotkey("ctrl", str(tab_index))
        return f"Switched to tab {tab_index}."
    elif direction.lower() in ["prev", "previous", "left", "back"]:
        pyautogui.hotkey("ctrl", "shift", "tab")
        return "Switched to previous tab."
    else:
        pyautogui.hotkey("ctrl", "tab")
        return "Switched to next tab."

def type_into_app(target: str, text: str, press_enter: bool = True) -> dict:
    """Focus a specific application and type/paste text directly into it."""
    res = focus_app(target)
    if not res.get("success"):
        return res
        
    time.sleep(0.3)
    if text:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        if press_enter:
            time.sleep(0.1)
            pyautogui.press("enter")
            
    return {"success": True, "app": res["process"], "title": res["title"], "typed": text[:60]}

def dispatch_prompt_to_antigravity(prompt: str, return_to_brave: bool = True) -> str:
    """Dispatch an autonomous improvement prompt directly into Antigravity and optionally return to Brave."""
    # 1. Copy prompt to clipboard
    pyperclip.copy(prompt)
    
    # 2. Focus Antigravity IDE
    res = focus_app("Antigravity")
    if not res.get("success"):
        return f"Could not focus Antigravity: {res.get('error')}"
        
    time.sleep(0.5)
    
    # 3. Paste the prompt into Antigravity's active chat input and press Enter
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)
    pyautogui.press("enter")
    
    # 4. If requested, return focus back to Brave / J.A.R.V.I.S. HUD after short delay
    if return_to_brave:
        time.sleep(1.2)
        focus_app("Brave")
        return f"Prompt successfully submitted into Antigravity ('{prompt[:50]}...'). Re-focused Brave HUD to monitor progress."
        
    return f"Prompt submitted into Antigravity. Focused on Antigravity."
