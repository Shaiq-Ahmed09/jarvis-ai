"""
J.A.R.V.I.S. Core Universal Entrypoint
======================================
Architectural Root Gateway for Stark Industries J.A.R.V.I.S.
Routes execution directly to backend/server.py while maintaining
seamless root and subfolder compatibility.

Usage:
    python server.py
  or:
    python backend/server.py
"""

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

# Re-export core attributes for backward compatibility
from backend.server import (
    app,
    TOOLS,
    extract_action_intent,
    JarvisSession,
    lifespan
)

if __name__ == "__main__":
    import uvicorn
    print("=" * 65)
    print("[*] 🚀 J.A.R.V.I.S. Core Launching from backend/server.py...")
    print("[*] 👉 Open your Stark HUD at: http://localhost:8765")
    print("=" * 65)
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8765, log_level="info")
