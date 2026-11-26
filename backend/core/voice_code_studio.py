"""J.A.R.V.I.S. Live Voice-to-Code Studio
Generates production-grade code, modules, and unit tests from voice or text prompts,
writes the file directly to workspace, focuses VS Code, and executes test runs in the terminal.
"""
import os
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
_p = Path(__file__).resolve().parent
HERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent

from core.system_hands import open_in_vscode, send_keys_to_vscode

def build_code_prompt(description: str, target_file: str = "") -> str:
    """Prepare a strict developer prompt for high-fidelity code generation."""
    return f"""You are J.A.R.V.I.S.'s Master Software Architect. Write complete, production-ready, clean Python code for:
"{description}"

Target File: {target_file or "auto-detect appropriate path under core/ or tests/"}

Requirements:
1. Provide full, fully implemented code. No placeholders, no `# TODO`, no omissions.
2. Include type annotations, comprehensive docstrings, and error handling.
3. Include a robust unit test suite (using unittest or pytest) at the bottom or in a separate block.
4. Output ONLY valid Python code inside a single ```python ``` code block. No conversational filler.
"""

def extract_code_block(llm_output: str) -> str:
    """Extract clean source code from markdown fenced blocks."""
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_output.strip()

def determine_file_path(description: str, target_file: str = "") -> Path:
    """Derive appropriate file path inside the project workspace."""
    if target_file and target_file.strip():
        p = Path(target_file).expanduser().resolve()
        if not p.is_absolute():
            p = HERE / target_file
        return p

    d = description.lower()
    if "auth" in d or "jwt" in d:
        fname = "auth_jwt.py"
    elif "api" in d or "route" in d or "fastapi" in d:
        fname = "api_routes.py"
    elif "db" in d or "database" in d or "model" in d:
        fname = "db_models.py"
    elif "crawler" in d or "scraper" in d:
        fname = "scraper_module.py"
    elif "test" in d:
        fname = "test_feature.py"
    else:
        words = re.findall(r"[a-z0-9_]+", d)
        fname = f"{'_'.join(words[:3]) or 'generated_module'}.py"

    return HERE / "core" / fname

async def generate_and_inject_code(description: str, target_file: str = "", run_tests: bool = True) -> dict:
    """Generate production-ready code, write to disk, open in VS Code, and optionally run tests."""
    from openai import AsyncOpenAI
    key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    base_url = os.getenv("JARVIS_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    model = os.getenv("JARVIS_MODEL", "gemini-3.5-flash-lite")

    client = AsyncOpenAI(api_key=key, base_url=base_url)
    prompt = build_code_prompt(description, target_file)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a principal software engineer generating production-ready Python source code."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        raw_code = response.choices[0].message.content or ""
        clean_code = extract_code_block(raw_code)
    except Exception as e:
        return {"success": False, "error": f"Code generation error: {e}"}

    fpath = determine_file_path(description, target_file)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(clean_code, encoding="utf-8")

    # Open file in VS Code
    open_in_vscode(str(fpath))

    test_output = ""
    if run_tests:
        # Run test syntax / unit check in terminal
        cmd = f'python -m py_compile "{fpath}"'
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                test_output = "Syntax check PASSED."
                send_keys_to_vscode("terminal", f'python -m unittest "{fpath}"')
            else:
                test_output = f"Syntax warning: {r.stderr[:200]}"
        except Exception as ex:
            test_output = f"Test check skipped: {ex}"

    lines_count = len(clean_code.splitlines())
    return {
        "success": True,
        "file": str(fpath),
        "filename": fpath.name,
        "lines": lines_count,
        "test_status": test_output,
        "message": f"Generated {lines_count} lines of code in '{fpath.name}'. Opened active tab in VS Code. {test_output}"
    }
