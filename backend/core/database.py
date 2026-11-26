"""
J.A.R.V.I.S. Persistent Database Cortex (SQLite)
Stores conversation history, Social DMs (WhatsApp & Instagram), and long-term memory.
Survives browser refresh and system restarts.
"""
import sqlite3
import json
import os
import time
from datetime import datetime
from pathlib import Path

_p = Path(__file__).resolve().parent
HERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent
DATA_DIR = HERE / "data"
DB_PATH = DATA_DIR / "jarvis.db"

def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Main Chat History (HUD Interface messages)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        session_id TEXT DEFAULT 'default',
        metadata TEXT DEFAULT '{}'
    )
    """)

    # 2. Social DMs (Instagram & WhatsApp conversation logs)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS social_dms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        thread_id TEXT,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        message_text TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        is_incoming INTEGER DEFAULT 1,
        ai_response TEXT,
        status TEXT DEFAULT 'received',
        raw_payload TEXT DEFAULT '{}'
    )
    """)

    # 3. Cortex Long-Term Semantic Memories
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cortex_memories (
        id TEXT PRIMARY KEY,
        fact TEXT NOT NULL,
        category TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        timestamp TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

# ----------------- Chat History Methods -----------------

def save_chat_message(role: str, text: str, session_id: str = "default", metadata: dict = None) -> int:
    """Save a chat message (user or jarvis) to SQLite database."""
    if not text or not text.strip():
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    meta_json = json.dumps(metadata or {})
    cursor.execute(
        "INSERT INTO chat_history (role, text, timestamp, session_id, metadata) VALUES (?, ?, ?, ?, ?)",
        (role, text.strip(), now_iso, session_id, meta_json)
    )
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id

def get_recent_chat_history(limit: int = 50, session_id: str = None) -> list:
    """Retrieve recent chat history chronologically ordered."""
    conn = get_connection()
    cursor = conn.cursor()
    if session_id:
        cursor.execute(
            "SELECT id, role, text, timestamp, metadata FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
    else:
        cursor.execute(
            "SELECT id, role, text, timestamp, metadata FROM chat_history ORDER BY id DESC LIMIT ?",
            (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    # Reverse to return chronologically oldest -> newest
    messages = []
    for r in reversed(rows):
        messages.append({
            "id": r["id"],
            "role": r["role"],
            "text": r["text"],
            "timestamp": r["timestamp"]
        })
    return messages

def clear_chat_history(session_id: str = None):
    """Purge chat history from database."""
    conn = get_connection()
    cursor = conn.cursor()
    if session_id:
        cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    else:
        cursor.execute("DELETE FROM chat_history")
    conn.commit()
    conn.close()

# ----------------- Social DMs Methods (Instagram & WhatsApp) -----------------

def log_social_dm(platform: str, sender: str, recipient: str, message_text: str,
                  thread_id: str = "", is_incoming: bool = True, ai_response: str = None,
                  status: str = "received", raw_payload: dict = None) -> int:
    """Log an incoming or outgoing DM from WhatsApp or Instagram."""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    raw_json = json.dumps(raw_payload or {})
    cursor.execute("""
    INSERT INTO social_dms (platform, thread_id, sender, recipient, message_text, timestamp, is_incoming, ai_response, status, raw_payload)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (platform.lower(), str(thread_id), str(sender), str(recipient), str(message_text),
          now_iso, 1 if is_incoming else 0, ai_response, status, raw_json))
    conn.commit()
    dm_id = cursor.lastrowid
    conn.close()
    return dm_id

def get_recent_social_dms(platform: str = None, limit: int = 50) -> list:
    """Fetch logged DMs from Instagram or WhatsApp."""
    conn = get_connection()
    cursor = conn.cursor()
    if platform:
        cursor.execute(
            "SELECT * FROM social_dms WHERE platform = ? ORDER BY id DESC LIMIT ?",
            (platform.lower(), limit)
        )
    else:
        cursor.execute("SELECT * FROM social_dms ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_dm_ai_response(dm_id: int, ai_response: str, status: str = "replied"):
    """Update DM with AI-generated response."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE social_dms SET ai_response = ?, status = ? WHERE id = ?",
        (ai_response, status, dm_id)
    )
    conn.commit()
    conn.close()

# Initialize tables immediately on module load
init_db()
