"""
J.A.R.V.I.S. Desktop AI Bubble - Root Launcher
=============================================
Forwards execution to desktop_bubble.main.
Allows running 'python main.py' directly from repository root.
"""
import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "desktop_bubble"
sys.path.insert(0, str(_DIR))

from main import main

if __name__ == "__main__":
    main()
