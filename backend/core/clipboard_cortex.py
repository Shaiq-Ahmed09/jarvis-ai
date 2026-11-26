"""J.A.R.V.I.S. Persistent Semantic Clipboard Cortex
Monitors Windows clipboard changes, records text snippets, code, and links to SQLite,
and indexes entries into the vector memory cortex for natural language retrieval.
"""
import asyncio
import hashlib
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
import pyperclip

from core.database import get_connection
from core.memory_vector import add_memory_to_cortex

_listener_thread = None
_listening = False
_last_clip_hash = None

def init_clipboard_table():
    """Ensure clipboard_history table exists in SQLite database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clipboard_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash TEXT UNIQUE,
        content TEXT NOT NULL,
        content_type TEXT NOT NULL,
        char_count INTEGER,
        summary TEXT,
        timestamp TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def detect_content_type(text: str) -> str:
    """Classify clipboard content into URL, code, email, or general text."""
    t = text.strip()
    if t.startswith("http://") or t.startswith("https://") or t.startswith("www."):
        return "url"
    if "@" in t and " " not in t and "." in t.split("@")[-1]:
        return "email"
    if any(k in t for k in ["def ", "class ", "import ", "const ", "function", "var ", "let ", "SELECT ", "CREATE TABLE", "=>", "{}", "()"]):
        return "code"
    if len(t) < 80 and ("\\" in t or "/" in t) and ("." in t or ":" in t):
        return "file_path"
    return "text"

def record_clipboard_item(text: str) -> dict | None:
    """Record a unique clipboard string to SQLite and long-term vector cortex."""
    global _last_clip_hash
    t = (text or "").strip()
    if not t or len(t) < 3:
        return None

    clip_hash = hashlib.sha256(t.encode("utf-8")).hexdigest()
    if clip_hash == _last_clip_hash:
        return None
    _last_clip_hash = clip_hash

    init_clipboard_table()
    conn = get_connection()
    cursor = conn.cursor()

    c_type = detect_content_type(t)
    summary = t[:120].replace("\n", " ").strip()
    now_iso = datetime.now().isoformat()

    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO clipboard_history (hash, content, content_type, char_count, summary, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (clip_hash, t, c_type, len(t), summary, now_iso)
        )
        conn.commit()
    except Exception as e:
        print(f"Clipboard cortex error: {e}")
    finally:
        conn.close()

    # Index into vector cortex if meaningful snippet or code/url
    if len(t) > 15:
        try:
            add_memory_to_cortex(
                f"[CLIPBOARD {c_type.upper()}]: {summary}",
                category="workflow"
            )
        except Exception:
            pass

    return {
        "hash": clip_hash,
        "type": c_type,
        "summary": summary,
        "timestamp": now_iso
    }

def query_clipboard_cortex(query: str, limit: int = 5) -> list[dict]:
    """Retrieve past clipboard snippets matching keyword or natural language query."""
    init_clipboard_table()
    conn = get_connection()
    cursor = conn.cursor()

    q = f"%{query.strip()}%"
    cursor.execute(
        """
        SELECT id, content, content_type, char_count, summary, timestamp
        FROM clipboard_history
        WHERE content LIKE ? OR summary LIKE ?
        ORDER BY id DESC LIMIT ?
        """,
        (q, q, limit)
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "type": r["content_type"],
            "content": r["content"],
            "summary": r["summary"],
            "timestamp": r["timestamp"]
        })
    return results

def restore_clipboard_item(item_id: int = None, keyword: str = "") -> dict:
    """Restore a historical clipboard item back into the active Windows clipboard."""
    init_clipboard_table()
    conn = get_connection()
    cursor = conn.cursor()

    if item_id:
        cursor.execute("SELECT content, summary FROM clipboard_history WHERE id = ?", (item_id,))
    elif keyword:
        q = f"%{keyword.strip()}%"
        cursor.execute("SELECT content, summary FROM clipboard_history WHERE content LIKE ? ORDER BY id DESC LIMIT 1", (q,))
    else:
        cursor.execute("SELECT content, summary FROM clipboard_history ORDER BY id DESC LIMIT 1")

    row = cursor.fetchone()
    conn.close()

    if row:
        pyperclip.copy(row["content"])
        return {
            "success": True,
            "summary": row["summary"],
            "message": f"Restored to active clipboard: '{row['summary'][:60]}...'"
        }
    return {"success": False, "error": "No matching clipboard entry found."}

def _clipboard_poll_loop():
    """Background polling daemon checking Windows clipboard every 1.2 seconds."""
    global _listening
    while _listening:
        try:
            val = pyperclip.paste()
            if val:
                record_clipboard_item(val)
        except Exception:
            pass
        time.sleep(1.2)

def start_clipboard_listener():
    """Start the persistent clipboard monitoring thread."""
    global _listener_thread, _listening
    if _listening:
        return
    _listening = True
    _listener_thread = threading.Thread(target=_clipboard_poll_loop, daemon=True)
    _listener_thread.start()

def stop_clipboard_listener():
    """Stop the background clipboard monitoring thread."""
    global _listening
    _listening = False
