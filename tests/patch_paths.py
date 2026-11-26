from pathlib import Path

files = [
    Path("backend/core/database.py"),
    Path("backend/core/git_devops.py"),
    Path("backend/core/instagram.py"),
    Path("backend/core/intruder_sentinel.py"),
    Path("backend/core/memory_vector.py"),
    Path("backend/core/quantum_p2p.py"),
    Path("backend/core/radon_persona_cortex.py"),
    Path("backend/core/self_patcher.py"),
    Path("backend/core/voice_clone.py"),
    Path("backend/core/voice_code_studio.py"),
    Path("core/database.py"),
    Path("core/git_devops.py"),
    Path("core/instagram.py"),
    Path("core/intruder_sentinel.py"),
    Path("core/memory_vector.py"),
    Path("core/quantum_p2p.py"),
    Path("core/radon_persona_cortex.py"),
    Path("core/self_patcher.py"),
    Path("core/voice_clone.py"),
    Path("core/voice_code_studio.py"),
]

for p in files:
    if not p.exists():
        continue
    txt = p.read_text(encoding="utf-8")
    orig = txt
    txt = txt.replace('HERE = Path(__file__).resolve().parent.parent', '_p = Path(__file__).resolve().parent\nHERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent')
    txt = txt.replace('HERE = Path(__file__).parent.parent', '_p = Path(__file__).resolve().parent\nHERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent')
    txt = txt.replace('DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")', '_p = Path(__file__).resolve().parent\nHERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent\nDATA_DIR = str(HERE / "data")')
    txt = txt.replace('WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))', '_p = Path(__file__).resolve().parent\nHERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent\nWORKSPACE_DIR = str(HERE)')
    if txt != orig:
        p.write_text(txt, encoding="utf-8")
        print(f"Updated {p}")
