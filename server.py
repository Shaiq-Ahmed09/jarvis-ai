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
    import argparse
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. Core Universal Entrypoint")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port number (default: 8000 or PORT env)")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Host address (default: 0.0.0.0)")
    args, _ = parser.parse_known_args()

    print("=" * 65)
    print(f"[*] 🚀 J.A.R.V.I.S. Core Launching on port {args.port}...")
    print(f"[*] 👉 Open your Stark HUD at: http://localhost:{args.port}")
    print("=" * 65)
    uvicorn.run("backend.server:app", host=args.host, port=args.port, log_level="info")
