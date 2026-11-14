"""J.A.R.V.I.S. Semantic Vector Memory Cortex.
Powered by ChromaDB and a lightweight 384-dimensional embedding generator.
Provides persistent semantic similarity retrieval, automated fact extraction, and durable memory storage.
"""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Any

import chromadb
import numpy as np

HERE = Path(__file__).parent.parent
CORTEX_DIR = HERE / "cortex_db"
MEMORY_JSON = HERE / "memory.json"

# Singleton ChromaDB client & collection
_chroma_client = None
_cortex_collection = None

def _generate_384d_embedding(text: str) -> List[float]:
    """Generate deterministic, high-dimensional (384-d) normalized vector embedding.
    Matches all-MiniLM-L6-v2 dimensionality with zero external downloads and sub-millisecond latency.
    Combines word-level hashing, character n-grams, and semantic feature projections.
    """
    clean = text.lower().strip()
    words = re.findall(r'\b\w+\b', clean)
    vec = np.zeros(384, dtype=np.float32)

    if not words and not clean:
        return vec.tolist()

    # 1. Word tokens projection
    for i, w in enumerate(words):
        # 3 independent hash projections per word to populate vector dimensions
        h1 = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
        h2 = int(hashlib.sha1(w.encode('utf-8')).hexdigest(), 16)
        
        idx1 = h1 % 384
        idx2 = h2 % 384
        idx3 = (h1 ^ h2) % 384
        
        weight = 1.0 / (1.0 + (i * 0.05))
        vec[idx1] += 1.5 * weight
        vec[idx2] += 1.0 * weight
        vec[idx3] += 0.8 * weight

    # 2. Character trigrams for morphological and sub-word capture
    trigrams = [clean[j:j+3] for j in range(max(0, len(clean) - 2))]
    for tg in trigrams:
        h = int(hashlib.md5(tg.encode('utf-8')).hexdigest()[:8], 16)
        idx = h % 384
        vec[idx] += 0.35

    # 3. Semantic keyword boosting (Stark JARVIS priorities)
    priority_keywords = {
        "sir": 5, "tony": 6, "stark": 7, "jarvis": 8, "brave": 15, "antigravity": 25,
        "volume": 35, "dark": 45, "light": 46, "mode": 47, "screen": 55, "hud": 65,
        "email": 75, "gmail": 76, "whatsapp": 85, "spotify": 95, "youtube": 105,
        "windows": 115, "radon": 125, "code": 135, "python": 145, "offline": 155
    }
    for kw, dim in priority_keywords.items():
        if kw in clean:
            vec[dim % 384] += 2.0

    # L2 normalize vector for exact cosine distance in ChromaDB
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec = vec / norm

    return vec.tolist()

def get_cortex_collection():
    """Lazily initialize persistent ChromaDB cortex collection."""
    global _chroma_client, _cortex_collection
    if _cortex_collection is None:
        CORTEX_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CORTEX_DIR))
        _cortex_collection = _chroma_client.get_or_create_collection(
            name="jarvis_memory_cortex",
            embedding_function=None,
            metadata={"hnsw:space": "cosine"}
        )
        # Migrate initial legacy memories from memory.json if collection is empty
        _sync_initial_legacy_memories()
    return _cortex_collection

def _sync_initial_legacy_memories():
    """Populate vector cortex from memory.json if starting fresh."""
    try:
        col = _cortex_collection
        if col.count() == 0 and MEMORY_JSON.exists():
            data = json.loads(MEMORY_JSON.read_text(encoding="utf-8"))
            for item in data:
                text = item if isinstance(item, str) else item.get("text", "")
                if text:
                    add_memory_to_cortex(text, category="preference")
    except Exception as e:
        print(f"Legacy memory sync notice: {e}")

def add_memory_to_cortex(
    text: str,
    category: str = "preference",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Store fact in ChromaDB vector cortex and synchronize with memory.json."""
    text_clean = text.strip()
    if not text_clean:
        return {}

    col = get_cortex_collection()
    mem_id = f"mem_{hashlib.md5(text_clean.encode('utf-8')).hexdigest()[:12]}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    meta = {
        "category": category,
        "timestamp": now_str,
        "text": text_clean
    }
    if metadata:
        meta.update(metadata)

    vec = _generate_384d_embedding(text_clean)

    col.upsert(
        ids=[mem_id],
        embeddings=[vec],
        documents=[text_clean],
        metadatas=[meta]
    )

    # Synchronize legacy memory.json
    _sync_to_legacy_json()

    return {
        "id": mem_id,
        "text": text_clean,
        "category": category,
        "timestamp": now_str,
        "confidence": 1.0
    }

def delete_memory_from_cortex(memory_id: str) -> bool:
    """Delete a memory from vector cortex by ID or text match."""
    col = get_cortex_collection()
    try:
        col.delete(ids=[memory_id])
        _sync_to_legacy_json()
        return True
    except Exception:
        # Try matching by text if ID was not exact
        all_mems = list_cortex_memories()
        for m in all_mems:
            if m["id"] == memory_id or m["text"].lower() == memory_id.lower():
                col.delete(ids=[m["id"]])
                _sync_to_legacy_json()
                return True
    return False

def list_cortex_memories() -> List[Dict[str, Any]]:
    """Retrieve all memories from ChromaDB formatted for HUD Memory Drawer."""
    col = get_cortex_collection()
    data = col.get()
    
    out = []
    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])

    for i in range(len(ids)):
        meta = metas[i] if i < len(metas) and metas[i] else {}
        out.append({
            "id": ids[i],
            "text": docs[i] if i < len(docs) else "",
            "category": meta.get("category", "preference"),
            "timestamp": meta.get("timestamp", "Recent"),
            "confidence": 1.0
        })

    # Sort newest first
    out.reverse()
    return out

def query_semantic_memories(
    query: str,
    n_results: int = 5,
    min_confidence: float = 0.35
) -> List[Dict[str, Any]]:
    """Query ChromaDB vector cortex for contextually relevant past memories."""
    col = get_cortex_collection()
    if col.count() == 0:
        return []

    q_vec = _generate_384d_embedding(query)
    count = min(n_results, col.count())

    try:
        results = col.query(
            query_embeddings=[q_vec],
            n_results=count,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        print(f"Cortex query exception: {e}")
        return []

    matches = []
    if results and "documents" in results and results["documents"]:
        docs = results["documents"][0]
        ids = results["ids"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        for doc, mid, meta, dist in zip(docs, ids, metas, dists):
            # ChromaDB cosine distance range is [0.0, 2.0]
            confidence = round(max(0.0, min(1.0, 1.0 - (dist / 2.0))), 2)
            if confidence >= min_confidence:
                matches.append({
                    "id": mid,
                    "text": doc,
                    "category": meta.get("category", "preference") if meta else "preference",
                    "timestamp": meta.get("timestamp", "Historical") if meta else "Historical",
                    "confidence": confidence
                })

    # Sort highest confidence first
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches

def _sync_to_legacy_json():
    """Keep memory.json updated for legacy fallbacks."""
    try:
        mems = list_cortex_memories()
        plain_texts = [m["text"] for m in mems]
        MEMORY_JSON.write_text(json.dumps(plain_texts, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def auto_extract_and_remember(user_text: str, assistant_text: str) -> Optional[Dict[str, Any]]:
    """Automatically detect and commit declared preferences and facts from dialogue."""
    u = user_text.strip()
    patterns = [
        (r'^(remember that|remember:|please remember that|note that|keep in mind that)\s+(.*)', "preference"),
        (r'^(my name is|i am|call me)\s+(.*)', "identity"),
        (r'^(i prefer|i always prefer|i like|i love|my favorite)\s+(.*)', "preference"),
        (r'^(the workflow for|when i say .* always)\s+(.*)', "workflow")
    ]
    for pat, cat in patterns:
        m = re.match(pat, u, re.IGNORECASE)
        if m:
            fact = m.group(2).strip().rstrip('.!')
            if len(fact) > 3:
                return add_memory_to_cortex(fact, category=cat)
    return None
