"""J.A.R.V.I.S. System Hands Engine: Autonomous Desktop, Tab, Media & Coding Control.
Gives J.A.R.V.I.S. full hands-on operational authority across:
1. Browser Tab Management (open, close, navigate, switch, reload, reopen).
2. Music & Streaming Automation (YouTube, Spotify, Apple Music search, playback, in-app typing).
3. Travel & Ticket Booking (Flights, Trains, Movies, Hotels, Events on Google Flights, MakeMyTrip, IRCTC, BookMyShow).
4. Coding & IDE Control (VS Code, Antigravity GUI automation & agy CLI execution).
"""

import os
import sys
import time
import json
import urllib.parse
import subprocess
from pathlib import Path
import psutil
import pyautogui
import pyperclip

from core.browser import launch_browser_tab, get_preferred_browser_path
from core.window_manager import focus_app, list_desktop_windows, activate_window_hwnd

AGY_CLI_PATH = Path(r"C:\Users\lucky\.gemini\bin\agy.exe")
VSCODE_CMD_PATH = Path(r"C:\Users\lucky\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd")

# ==============================================================================
# 1. TAB & BROWSER MANAGEMENT
# ==============================================================================

def open_new_tab(url: str = "") -> dict:
    """Open a new tab in the active browser, optionally loading a URL."""
    if url:
        success = launch_browser_tab(url)
        return {"success": success, "url": url, "action": "opened_url_tab"}
    
    # Focus browser and press Ctrl+T
    res = focus_app("browser")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "t")
    return {"success": True, "action": "opened_blank_tab", "focused": res.get("process", "browser")}

def close_active_tab(count: int = 1) -> dict:
    """Close one or more active tabs in the currently focused browser or application."""
    windows = list_desktop_windows()
    browser_procs = ["brave.exe", "chrome.exe", "msedge.exe", "firefox.exe", "code.exe"]
    
    for w in windows:
        if w["process"].lower() in browser_procs:
            activate_window_hwnd(w["hwnd"])
            break
            
    time.sleep(0.15)
    closed = 0
    for _ in range(max(1, count)):
        pyautogui.hotkey("ctrl", "w")
        closed += 1
        time.sleep(0.08)
        
    return {"success": True, "closed_tabs": closed, "message": f"Closed {closed} tab(s)."}

def reopen_closed_tab() -> dict:
    """Reopen the most recently closed browser tab (Ctrl+Shift+T)."""
    focus_app("browser")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "shift", "t")
    return {"success": True, "action": "reopened_tab"}

def navigate_current_tab(url_or_query: str) -> dict:
    """Focus active browser tab address bar, type URL/query, and navigate."""
    focus_app("browser")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.1)
    
    target = url_or_query.strip()
    if not (target.startswith("http://") or target.startswith("https://") or "." in target.split("/")[0]):
        # Treat as search query
        target = f"https://www.google.com/search?q={urllib.parse.quote_plus(target)}"
    elif not (target.startswith("http://") or target.startswith("https://")):
        target = "https://" + target
        
    pyperclip.copy(target)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.05)
    pyautogui.press("enter")
    return {"success": True, "navigated_to": target}

def reload_current_tab() -> dict:
    """Reload the currently active browser tab."""
    focus_app("browser")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "r")
    return {"success": True, "action": "reloaded_tab"}

# ==============================================================================
# 2. MUSIC & MEDIA AUTOMATION (YouTube, Spotify, Apple Music)
# ==============================================================================

def play_music(service: str = "youtube", query: str = "", action: str = "play") -> dict:
    """Play music or search across YouTube, Spotify, or Apple Music."""
    srv = (service or "youtube").lower().strip()
    q = (query or "").strip()
    act = (action or "play").lower().strip()
    
    # 1. YOUTUBE AUTOMATION
    if srv in ["youtube", "yt"]:
        if q:
            yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}"
            launch_browser_tab(yt_url)
            return {
                "success": True,
                "service": "YouTube",
                "query": q,
                "url": yt_url,
                "message": f"Searching and queuing '{q}' on YouTube, Sir."
            }
        else:
            launch_browser_tab("https://www.youtube.com")
            return {"success": True, "service": "YouTube", "message": "Opened YouTube."}
            
    # 2. SPOTIFY AUTOMATION
    elif srv in ["spotify", "sp"]:
        spotify_running = any(
            p.info.get("name", "").lower() == "spotify.exe" 
            for p in psutil.process_iter(["name"]) 
            if p.info and p.info.get("name")
        )
        
        if spotify_running and q:
            focus_app("spotify")
            time.sleep(0.35)
            pyautogui.hotkey("ctrl", "k")
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "a")
            pyperclip.copy(q)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.15)
            pyautogui.press("enter")
            if act == "play":
                time.sleep(0.5)
                pyautogui.press("enter")
            return {
                "success": True,
                "service": "Spotify Desktop",
                "query": q,
                "message": f"Typed '{q}' into Spotify search and initiated playback."
            }
        elif q:
            sp_url = f"https://open.spotify.com/search/{urllib.parse.quote_plus(q)}"
            launch_browser_tab(sp_url)
            return {
                "success": True,
                "service": "Spotify Web",
                "query": q,
                "url": sp_url,
                "message": f"Opened Spotify Web search for '{q}', Sir."
            }
        else:
            if spotify_running:
                focus_app("spotify")
                pyautogui.press("playpause")
                return {"success": True, "service": "Spotify", "message": "Focused Spotify and toggled playback."}
            else:
                launch_browser_tab("https://open.spotify.com")
                return {"success": True, "service": "Spotify", "message": "Opened Spotify."}

    # 3. APPLE MUSIC AUTOMATION
    elif srv in ["apple_music", "applemusic", "apple music"]:
        apple_running = any(
            "apple" in p.info.get("name", "").lower() and "music" in p.info.get("name", "").lower()
            for p in psutil.process_iter(["name"]) 
            if p.info and p.info.get("name")
        )
        
        if apple_running and q:
            focus_app("Apple Music")
            time.sleep(0.3)
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "a")
            pyperclip.copy(q)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.15)
            pyautogui.press("enter")
            return {
                "success": True,
                "service": "Apple Music App",
                "query": q,
                "message": f"Typed '{q}' into Apple Music search."
            }
        elif q:
            am_url = f"https://music.apple.com/search?term={urllib.parse.quote_plus(q)}"
            launch_browser_tab(am_url)
            return {
                "success": True,
                "service": "Apple Music Web",
                "query": q,
                "url": am_url,
                "message": f"Opened Apple Music search for '{q}', Sir."
            }
        else:
            launch_browser_tab("https://music.apple.com")
            return {"success": True, "service": "Apple Music", "message": "Opened Apple Music."}
            
    # Default fallback to YouTube
    else:
        yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q or srv)}"
        launch_browser_tab(yt_url)
        return {"success": True, "service": "YouTube", "url": yt_url, "query": q or srv}

def type_search_in_app(target: str, query: str, press_enter: bool = True) -> dict:
    """Focus an application and type directly into its search bar or command palette."""
    t = target.lower().strip()
    res = focus_app(t)
    if not res.get("success"):
        return res
        
    time.sleep(0.3)
    
    if "spotify" in t:
        pyautogui.hotkey("ctrl", "k")
    elif "apple" in t:
        pyautogui.hotkey("ctrl", "f")
    elif "code" in t or "vscode" in t:
        pyautogui.hotkey("ctrl", "p")
    elif "antigravity" in t:
        pyautogui.hotkey("ctrl", "l")
    elif "explorer" in t:
        pyautogui.hotkey("ctrl", "e")
    else:
        pyautogui.hotkey("ctrl", "f")
        
    time.sleep(0.15)
    pyperclip.copy(query)
    pyautogui.hotkey("ctrl", "v")
    
    if press_enter:
        time.sleep(0.1)
        pyautogui.press("enter")
        
    return {
        "success": True,
        "app": res.get("process", target),
        "query": query,
        "message": f"Typed '{query}' into search bar of {res.get('process', target)}."
    }

# ==============================================================================
# 3. TICKET & TRAVEL BOOKINGS (Flights, Trains, Movies, Hotels, Events)
# ==============================================================================

def book_tickets_portal(
    category: str = "flight",
    origin: str = "",
    destination: str = "",
    date: str = "",
    provider: str = "auto",
    passengers: int = 1,
    return_date: str = "",
    additional_notes: str = ""
) -> dict:
    """Build prefilled booking portal URLs and launch them directly in browser."""
    cat = (category or "flight").lower().strip()
    prov = (provider or "auto").lower().strip()
    orig = (origin or "").strip()
    dest = (destination or "").strip()
    dt = (date or "").strip()
    
    portal_name = ""
    portal_url = ""
    
    # 1. FLIGHT BOOKINGS
    if cat in ["flight", "flights", "airline", "air"]:
        if prov in ["makemytrip", "mmt"]:
            portal_name = "MakeMyTrip Flights"
            portal_url = f"https://www.makemytrip.com/flight/search?itinerary={orig}-{dest}-{dt}" if orig and dest else "https://www.makemytrip.com/flights/"
        elif prov in ["skyscanner"]:
            portal_name = "Skyscanner Flights"
            portal_url = f"https://www.skyscanner.com/transport/flights/{orig}/{dest}/{dt}/" if orig and dest else "https://www.skyscanner.com/flights"
        else:
            portal_name = "Google Flights"
            q_parts = ["flights"]
            if orig: q_parts.append(f"from {orig}")
            if dest: q_parts.append(f"to {dest}")
            if dt: q_parts.append(f"on {dt}")
            if return_date: q_parts.append(f"return {return_date}")
            if passengers > 1: q_parts.append(f"for {passengers} people")
            flight_query = "+".join([urllib.parse.quote_plus(p) for p in q_parts])
            portal_url = f"https://www.google.com/travel/flights?q={flight_query}"

    # 2. TRAIN BOOKINGS
    elif cat in ["train", "rail", "railway", "irctc"]:
        if orig and dest:
            portal_name = "ConfirmTkt Railway Search"
            portal_url = f"https://www.confirmtkt.com/trains/search?from={urllib.parse.quote_plus(orig)}&to={urllib.parse.quote_plus(dest)}&date={urllib.parse.quote_plus(dt)}"
        else:
            portal_name = "IRCTC Official Portal"
            portal_url = "https://www.irctc.co.in/nget/train-search"

    # 3. MOVIE & CINEMA TICKETS
    elif cat in ["movie", "cinema", "theatre", "film"]:
        portal_name = "BookMyShow Movies"
        q_term = dest or orig or additional_notes or "movies"
        portal_url = f"https://in.bookmyshow.com/explore/movies?q={urllib.parse.quote_plus(q_term)}"

    # 4. HOTEL & STAY RESERVATIONS
    elif cat in ["hotel", "stay", "resort"]:
        portal_name = "Booking.com Hotels"
        dest_term = dest or orig or "hotels"
        dt_param = f"&checkin={urllib.parse.quote_plus(dt)}" if dt else ""
        portal_url = f"https://www.booking.com/searchresults.html?ss={urllib.parse.quote_plus(dest_term)}{dt_param}"

    # 5. CONCERTS & EVENTS
    elif cat in ["concert", "event", "show", "live"]:
        portal_name = "BookMyShow Events"
        q_term = dest or orig or additional_notes or "events"
        portal_url = f"https://in.bookmyshow.com/explore/events?q={urllib.parse.quote_plus(q_term)}"

    # Default fallback
    else:
        portal_name = "Google Travel"
        portal_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(f'book {cat} {orig} to {dest} {dt}')}"

    launch_browser_tab(portal_url)
    
    return {
        "success": True,
        "category": cat,
        "provider": portal_name,
        "url": portal_url,
        "origin": orig,
        "destination": dest,
        "date": dt,
        "message": f"Pre-filled booking portal opened on {portal_name} ({orig} -> {dest} on {dt or 'upcoming'}). Ready for Sir's review."
    }

# ==============================================================================
# 4. CODING & IDE AUTOMATION (VS Code & Antigravity)
# ==============================================================================

def open_in_vscode(path_or_file: str = "") -> dict:
    """Launch or focus VS Code with the specified file or workspace path."""
    target_path = Path(path_or_file).expanduser().resolve() if path_or_file else Path.cwd()
    cmd = str(VSCODE_CMD_PATH) if VSCODE_CMD_PATH.exists() else "code"
    
    try:
        subprocess.Popen([cmd, str(target_path)], shell=True)
        time.sleep(0.4)
        focus_app("code")
        return {"success": True, "target": str(target_path), "message": f"Opened '{target_path}' in VS Code."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def write_code_file_and_open(file_path: str, content: str, open_in_editor: bool = True) -> dict:
    """Write/create a code file on disk and optionally open it in VS Code or Antigravity."""
    fpath = Path(file_path).expanduser().resolve()
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content, encoding="utf-8")
    
    if open_in_editor:
        open_in_vscode(str(fpath))
        
    return {
        "success": True,
        "path": str(fpath),
        "size_bytes": len(content),
        "message": f"Wrote code to {fpath.name} ({len(content)} bytes) and launched editor."
    }

def run_antigravity_cli_prompt(prompt: str, effort: str = "high") -> dict:
    """Execute an autonomous task directly via Antigravity CLI (agy.exe)."""
    if not AGY_CLI_PATH.exists():
        return {"success": False, "error": f"Antigravity CLI not found at {AGY_CLI_PATH}"}
        
    cmd = [
        str(AGY_CLI_PATH),
        "-p", prompt,
        "--effort", effort,
        "--dangerously-skip-permissions"
    ]
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        try:
            out, err = proc.communicate(timeout=30)
            return {
                "success": proc.returncode == 0,
                "output": (out or err).strip()[:2000],
                "message": "Antigravity CLI completed turn successfully."
            }
        except subprocess.TimeoutExpired:
            return {
                "success": True,
                "pid": proc.pid,
                "message": "Antigravity CLI is executing task autonomously in background."
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_keys_to_vscode(action: str = "terminal", text: str = "") -> dict:
    """Send specialized developer shortcuts to the active VS Code window."""
    res = focus_app("code")
    if not res.get("success"):
        return res
        
    time.sleep(0.3)
    act = action.lower().strip()
    
    if act in ["terminal", "toggle_terminal", "open_terminal"]:
        pyautogui.hotkey("ctrl", "`")
        if text:
            time.sleep(0.3)
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
        return {"success": True, "action": "terminal", "typed": text}
        
    elif act in ["command_palette", "commands"]:
        pyautogui.hotkey("ctrl", "shift", "p")
        if text:
            time.sleep(0.15)
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
        return {"success": True, "action": "command_palette"}
        
    elif act in ["quick_open", "find_file"]:
        pyautogui.hotkey("ctrl", "p")
        if text:
            time.sleep(0.15)
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            pyautogui.press("enter")
        return {"success": True, "action": "quick_open"}
        
    elif act in ["save", "save_file"]:
        pyautogui.hotkey("ctrl", "s")
        return {"success": True, "action": "saved_file"}
        
    return {"success": False, "error": f"Unknown VS Code action '{action}'"}
