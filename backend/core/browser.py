"""High-Reliability Browser & Tab Launcher for J.A.R.V.I.S.
Detects active running browsers (Brave, Chrome, Edge) and dispatches URLs directly into new tabs.
"""
import os
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path
import psutil

def get_preferred_browser_path() -> str | None:
    """Detect the user's active/preferred browser executable."""
    try:
        running_names = {p.info['name'].lower() for p in psutil.process_iter(['name']) if p.info and p.info.get('name')}
    except Exception:
        running_names = set()
        
    known_browsers = [
        ("brave.exe", [
            Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / r"BraveSoftware\Brave-Browser\Application\brave.exe",
        ]),
        ("chrome.exe", [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe",
        ]),
        ("msedge.exe", [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        ])
    ]
    
    # Priority 1: A browser that is currently running (e.g. Brave!)
    for proc_name, paths in known_browsers:
        if proc_name in running_names:
            for p in paths:
                if p.exists():
                    return str(p)
                    
    # Priority 2: Any installed browser
    for proc_name, paths in known_browsers:
        for p in paths:
            if p.exists():
                return str(p)
                
    return None

def launch_browser_tab(url: str) -> bool:
    """Launch a URL as a visible tab in the user's active browser."""
    if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("whatsapp://"):
        url = "https://" + url
        
    # Method 1: Launch directly via the running browser binary (Brave/Chrome/Edge)
    b_path = get_preferred_browser_path()
    if b_path and not url.startswith("whatsapp://"):
        try:
            subprocess.Popen([b_path, url])
            return True
        except Exception as e:
            print(f"Direct browser execution failed: {e}")
            
    # Method 2: Native Windows ShellExecute
    if sys.platform == "win32":
        try:
            os.startfile(url)
            return True
        except Exception:
            pass
            
    # Method 3: Standard library webbrowser
    try:
        webbrowser.open_new_tab(url)
        return True
    except Exception:
        return False
