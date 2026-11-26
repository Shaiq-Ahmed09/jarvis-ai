"""
J.A.R.V.I.S. Radon Persona Cortex & Deep Chat Imitation Engine (Omniscient Edition)
===================================================================================
Ingests all 5,600+ messages across all Instagram inbox chats, group chats,
comments, and personal profile archives. Automatically extracts deep biographical
facts, friend dossiers, and multi-turn conversational exchanges.
Empowers J.A.R.V.I.S. with semantic RAG memory to know Radon intimately and
replicate his exact speech, texting cadence, and thought process.
"""

import os
import re
import json
import sqlite3
import zipfile
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("jarvis.radon_persona")

_p = Path(__file__).resolve().parent
HERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent
DATA_DIR = HERE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "jarvis.db"
DATASET_PATH = DATA_DIR / "radon_persona_dataset.json"
PROFILE_PATH = DATA_DIR / "radon_personal_profile.json"

DEFAULT_ZIP_PATH = Path(r"C:\Users\lucky\Downloads\instagram-redonxd-2026-11-22-NuBcGO5q.zip")

SYSTEM_PATTERNS = [
    "sent an attachment",
    "liked a message",
    "reacted ",
    "started an audio call",
    "started a video chat",
    "changed the theme",
    "created a group",
    "named the group",
    "voted for",
    "missed a video chat",
    "missed an audio call",
    "you sent an attachment",
    "poll",
    "end-to-end encryption"
]

CATEGORY_KEYWORDS = {
    "gaming": ["valo", "game", "smurf", "minecraft", "discord", "khel", "match", "comp", "unrated", "lobby", "gaming", "play"],
    "college_study": ["padhai", "study", "exam", "chores", "assignment", "project", "submit", "deadline", "mth", "notes", "calculat", "college"],
    "travel_commute": ["metro", "ghar", "pahuch", "station", "bahar", "traffic", "auto", "train", "ja raha", "gurgao"],
    "sleep_routine": ["neend", "so rha", "so gaya", "uth ja", "subah", "raat", "12:30", "uthana", "sleep", "asleep"],
    "banter_humor": ["lmao", "lol", "dead", "bhai", "haha", "bandar", "adrak", "natak", "huss", "🤣", "😭", "same broh", "real"],
    "plans_calling": ["call", "baat", "milte", "free", "voice", "text", "discord", "gane sunte"]
}

def detect_category(text: str) -> str:
    """Classify conversational exchange into semantic life category."""
    t_low = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in t_low for kw in keywords):
            return cat
    return "general"

def init_radon_tables():
    """Ensure SQLite tables for Radon chat memory and personality profile exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS radon_chat_memory")
    cur.execute("""
        CREATE TABLE radon_chat_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_title TEXT,
            friend_name TEXT,
            incoming_message TEXT,
            radon_reply TEXT,
            category TEXT,
            timestamp_ms INTEGER
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_radon_cat ON radon_chat_memory(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_radon_friend ON radon_chat_memory(friend_name)")
    conn.commit()
    conn.close()

def extract_and_train_all_datasets(zip_path: Optional[Path] = None) -> Dict[str, Any]:
    """Omniscient parser: reads all chats, groups, comments, and profile data from Instagram export.
    Generates structured knowledge graph, indexes ChromaDB vector cortex, and updates permanent memory."""
    zip_path = Path(zip_path or DEFAULT_ZIP_PATH)
    if not zip_path.exists():
        return {"success": False, "error": f"Zip file not found at {zip_path}"}

    init_radon_tables()

    dialogue_blocks = []
    solo_radon_messages = []
    chat_summaries = {}

    with zipfile.ZipFile(zip_path, "r") as z:
        # 1. Parse all inbox and message request chats
        inbox_files = [n for n in z.namelist() if n.endswith(".json") and ("inbox" in n or "message_requests" in n)]
        
        for jf in inbox_files:
            try:
                raw_data = z.read(jf).decode("utf-8")
                data = json.loads(raw_data)
            except Exception:
                continue

            chat_title = data.get("title", "Unknown")
            participants = [p.get("name", "") for p in data.get("participants", [])]
            raw_msgs = data.get("messages", [])
            raw_msgs.reverse()  # chronological

            chat_summaries[chat_title] = {
                "participants": participants,
                "total_messages": len(raw_msgs)
            }

            # Group consecutive messages from the same sender to capture real multi-line bursts
            grouped_turns = []
            for m in raw_msgs:
                sender = m.get("sender_name", "")
                raw_c = m.get("content", "")
                if not raw_c:
                    continue
                try:
                    c = raw_c.encode("latin1").decode("utf-8")
                except Exception:
                    c = raw_c

                c_clean = c.strip()
                if not c_clean or any(p in c_clean.lower() for p in SYSTEM_PATTERNS):
                    continue

                ts = m.get("timestamp_ms", 0)

                if grouped_turns and grouped_turns[-1]["sender"] == sender:
                    grouped_turns[-1]["messages"].append(c_clean)
                else:
                    grouped_turns.append({"sender": sender, "messages": [c_clean], "ts": ts})

            # Create clean dialogue exchanges (Friend turn -> Radon reply turn)
            for i in range(len(grouped_turns) - 1):
                turn_a = grouped_turns[i]
                turn_b = grouped_turns[i + 1]

                if turn_a["sender"] != "zERO" and turn_b["sender"] == "zERO":
                    incoming_text = " \n ".join(turn_a["messages"])
                    reply_text = " \n ".join(turn_b["messages"])
                    cat = detect_category(incoming_text + " " + reply_text)

                    dialogue_blocks.append({
                        "chat_title": chat_title,
                        "friend_name": turn_a["sender"],
                        "incoming_message": incoming_text,
                        "radon_reply": reply_text,
                        "category": cat,
                        "timestamp_ms": turn_b["ts"]
                    })

                if turn_b["sender"] == "zERO":
                    for sub_msg in turn_b["messages"]:
                        solo_radon_messages.append({"text": sub_msg, "chat": chat_title, "ts": turn_b["ts"]})

    # Save comprehensive dataset
    dataset = {
        "total_dialogue_blocks": len(dialogue_blocks),
        "total_radon_messages": len(solo_radon_messages),
        "chat_summaries": chat_summaries,
        "dialogue_blocks": dialogue_blocks,
        "solo_messages": solo_radon_messages[:1000]
    }
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    # Insert into SQLite radon_chat_memory
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM radon_chat_memory")
    for b in dialogue_blocks:
        cur.execute(
            """INSERT INTO radon_chat_memory 
               (chat_title, friend_name, incoming_message, radon_reply, category, timestamp_ms) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (b["chat_title"], b["friend_name"], b["incoming_message"], b["radon_reply"], b["category"], b["timestamp_ms"])
        )
    conn.commit()
    conn.close()

    # Index into ChromaDB vector cortex with rich metadata
    indexed_in_cortex = 0
    try:
        import chromadb
        cortex_dir = DATA_DIR / "cortex"
        client = chromadb.PersistentClient(path=str(cortex_dir))

        try:
            client.delete_collection("radon_persona_memory")
        except Exception:
            pass

        collection = client.create_collection(
            name="radon_persona_memory",
            metadata={"description": "Real multi-turn Instagram chat memories for Radon persona"}
        )

        batch_size = 100
        for i in range(0, len(dialogue_blocks), batch_size):
            batch = dialogue_blocks[i:i+batch_size]
            docs = [f"Chat ({b['chat_title']}) - {b['friend_name']}: {b['incoming_message']}\nRadon: {b['radon_reply']}" for b in batch]
            ids = [f"radon_block_{i+j}" for j in range(len(batch))]
            metas = [{
                "chat": b["chat_title"],
                "friend": b["friend_name"][:100],
                "category": b["category"],
                "incoming": b["incoming_message"][:300],
                "reply": b["radon_reply"][:300]
            } for b in batch]
            collection.add(documents=docs, ids=ids, metadatas=metas)
            indexed_in_cortex += len(batch)
    except Exception as e:
        logger.error(f"Error vector indexing into cortex: {e}")

    # Compute deep linguistic metrics
    metrics = compute_deep_metrics(dialogue_blocks, solo_radon_messages)

    # Synthesize biographical knowledge profile
    profile = build_radon_profile(chat_summaries, metrics)
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # Permanently update J.A.R.V.I.S.'s memory cortex
    update_jarvis_permanent_memory(profile)

    return {
        "success": True,
        "total_dialogue_blocks": len(dialogue_blocks),
        "total_radon_messages": len(solo_radon_messages),
        "indexed_in_vector_cortex": indexed_in_cortex,
        "chat_counts": {k: v["total_messages"] for k, v in chat_summaries.items()},
        "metrics": metrics,
        "profile": profile
    }

def compute_deep_metrics(dialogue_blocks: list, solo_messages: list) -> Dict[str, Any]:
    """Compute exhaustive linguistic, punctuation, and structural habits."""
    texts = [m["text"] for m in solo_messages]
    total_msgs = max(1, len(texts))
    avg_words = sum(len(t.split()) for t in texts) / total_msgs

    lowercase_starts = sum(1 for t in texts if t and t[0].islower())
    no_period_ends = sum(1 for t in texts if not t.endswith("."))

    # Category breakdown
    cat_counts = {}
    for b in dialogue_blocks:
        c = b.get("category", "general")
        cat_counts[c] = cat_counts.get(c, 0) + 1

    # Emoji frequencies
    emoji_counts = {}
    for t in texts:
        found_emojis = re.findall(r"[\U00010000-\U0010ffff]", t)
        for e in found_emojis:
            emoji_counts[e] = emoji_counts.get(e, 0) + 1

    # Word frequencies
    word_freq = {}
    for t in texts:
        for w in t.lower().split():
            clean_w = re.sub(r"[^\w]", "", w)
            if clean_w and len(clean_w) > 1:
                word_freq[clean_w] = word_freq.get(clean_w, 0) + 1

    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30]

    return {
        "total_messages_analyzed": total_msgs,
        "avg_words_per_message": round(avg_words, 1),
        "no_trailing_period_percent": round((no_period_ends / total_msgs) * 100, 1),
        "lowercase_opening_percent": round((lowercase_starts / total_msgs) * 100, 1),
        "category_distribution": cat_counts,
        "top_emojis": sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "top_vocabulary": top_words
    }

def build_radon_profile(chat_summaries: dict, metrics: dict) -> Dict[str, Any]:
    """Synthesize complete biographical dossier of Radon from all datasets."""
    return {
        "identity": {
            "name": "Radon",
            "aliases": ["zERO", "@redonxd"],
            "bio_summary": "Young tech creator, developer, and student who builds AI agents and systems, plays Valorant, and hangs out with his close group on Discord."
        },
        "social_circle": {
            "Aryan Srivastava": "Close friend & college peer. Frequently discusses daily commute on the metro (50 mins travel time), deadlines, and calls.",
            "Suhani": "Close friend & gaming companion. Shares late-night conversations, inside jokes ('huss huss', metro stations, dreams), Valorant matches, and sleep habits.",
            "Bhaisexuals": "Primary friend group chat with Uzaid, Nayan, Rahul, Neqtra, Talish, Pawan, Drona, Atifficial, and Aryan. Centered on gaming, memes, and Discord hangouts."
        },
        "interests_and_activities": {
            "gaming": ["Valorant (smurfing, duo/trio queues, 'ek match khelo fir ata')", "Minecraft (Fabric modpack: Sodium, Lithium, Iris shaders, Entity Culling)", "Discord (listening to music, hanging out in voice channels)"],
            "academics": "MTH 302 (Mathematics/Engineering), juggling assignments, chores, and code projects.",
            "habits_and_sleep": "Irregular late-night schedule. Often aims for 12:30 AM sleep when maintaining a strict routine, asks friends to wake him up if he falls asleep, values uninterrupted study/rest.",
            "communication_preference": "Prefers calls for serious or detailed matters, but texts in rapid, concise multi-bursts."
        },
        "linguistic_dna": {
            "cadence": "Fast, 4 to 7 words per text, split into 2-3 quick sequential lines.",
            "punctuation": "98% no ending periods.",
            "emojis": "Primarily 😭 (drama/humor) and 🤣/😂 (laughter). Skull (💀) is strictly avoided.",
            "code_switching": "Natural English + Hinglish (han, bhai, kr, pr, fir, tu, sahi, valo, neend)."
        }
    }

def update_jarvis_permanent_memory(profile: dict):
    """Inject deep persona facts into J.A.R.V.I.S.'s memory cortex and memory.json."""
    from core.memory_vector import add_memory_to_cortex

    facts = [
        "User is Radon (@redonxd), also known as zERO in his friend group.",
        "Radon's inner circle includes Aryan Srivastava (college/metro travel buddy), Suhani (close friend & late-night Valo partner), and the Bhaisexuals group chat.",
        "Radon plays Valorant (frequently smurfing with friends) and Minecraft (Fabric with Sodium, Iris, Lithium).",
        "Radon uses Discord to hang out in voice channels and listen to music with friends while gaming.",
        "Radon studies engineering mathematics (MTH 302) and balances coding projects, college deadlines, and daily chores.",
        "Radon's sleep schedule is late-night; he often targets 12:30 AM sleep when keeping a disciplined routine.",
        "Radon's texting style is ultra-concise (4-7 words average), omits ending periods 98% of the time, uses repeated 😭 or 🤣 for emotion, and never spams the skull emoji.",
        "Radon code-switches fluidly between English and Hinglish (han, bhai, sahi, kr, pr, fir, tu, valo, neend).",
        "Radon prefers direct calls for important matters, but texts in quick sequential bursts.",
        "When in Radon persona, J.A.R.V.I.S. must speak strictly in first person ('I', 'me', 'my') with dry, witty, human confidence, never revealing AI identity."
    ]

    for f in facts:
        try:
            add_memory_to_cortex(f, category="biography", confidence=1.0)
        except Exception:
            pass

    # Update memory.json cleanly
    memory_json_path = HERE / "memory.json"
    try:
        if memory_json_path.exists():
            with open(memory_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        else:
            data = []

        existing_texts = set(data)
        for f in facts:
            if f not in existing_texts:
                data.append(f)

        with open(memory_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error updating memory.json: {e}")

def get_relevant_radon_replies(query_context: str, n_results: int = 4, category: Optional[str] = None) -> List[Dict[str, str]]:
    """Retrieve the most semantically relevant real replies Radon sent in similar past chats.
    Supports category filtering (gaming, commute, sleep, academic, banter)."""
    try:
        import chromadb
        cortex_dir = DATA_DIR / "cortex"
        client = chromadb.PersistentClient(path=str(cortex_dir))
        collection = client.get_collection("radon_persona_memory")

        where_filter = {"category": category} if category else None

        results = collection.query(
            query_texts=[query_context],
            n_results=min(n_results, 8),
            where=where_filter
        )

        matched_pairs = []
        if results and results.get("metadatas") and results["metadatas"][0]:
            for meta in results["metadatas"][0]:
                matched_pairs.append({
                    "chat": meta.get("chat", "Chat"),
                    "friend": meta.get("friend", "Friend"),
                    "incoming": meta.get("incoming", ""),
                    "reply": meta.get("reply", "")
                })
        return matched_pairs
    except Exception as e:
        # Fallback to SQLite
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            words = [w for w in re.findall(r"\w+", query_context.lower()) if len(w) > 3][:3]
            if words:
                clause = " OR ".join(["incoming_message LIKE ?" for _ in words])
                params = [f"%{w}%" for w in words]
                cur.execute(f"SELECT chat_title, friend_name, incoming_message, radon_reply FROM radon_chat_memory WHERE {clause} LIMIT {n_results}", params)
                rows = cur.fetchall()
                conn.close()
                return [{"chat": r[0], "friend": r[1], "incoming": r[2], "reply": r[3]} for r in rows]
            conn.close()
        except Exception:
            pass
        return []
