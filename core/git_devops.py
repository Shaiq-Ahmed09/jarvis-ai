"""J.A.R.V.I.S. Deep Git & GitHub Auto-DevOps Engine
Autonomous Git commit, push, diff inspection, and GitHub PR creation using local tools/gh/gh.exe and git.
"""
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
HERE = Path(__file__).resolve().parent.parent
LOCAL_GH = HERE / "tools" / "gh" / "gh.exe"
LOCAL_GIT = HERE / "tools" / "git" / "cmd" / "git.exe"

def get_git_cmd() -> str:
    """Resolve active git executable."""
    if LOCAL_GIT.exists():
        return str(LOCAL_GIT)
    return "git"

def get_gh_cmd() -> str:
    """Resolve active GitHub CLI executable."""
    if LOCAL_GH.exists():
        return str(LOCAL_GH)
    return "gh"

def run_git(args: list[str], cwd: Path = None) -> tuple[int, str]:
    """Execute git command and return (code, output)."""
    cmd = [get_git_cmd()] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or HERE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except Exception as e:
        return 1, str(e)

def run_gh(args: list[str], cwd: Path = None) -> tuple[int, str]:
    """Execute GitHub CLI command and return (code, output)."""
    cmd = [get_gh_cmd()] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or HERE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=45
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except Exception as e:
        return 1, str(e)

def inspect_git_status(cwd: Path = None) -> dict:
    """Inspect repository status, branch name, and uncommitted modifications."""
    repo = cwd or HERE
    code, status_out = run_git(["status", "-s"], repo)
    _, branch_out = run_git(["branch", "--show-current"], repo)
    _, diff_stat = run_git(["diff", "--stat"], repo)
    
    modified_files = [line.strip() for line in status_out.splitlines() if line.strip()]
    return {
        "branch": branch_out.strip() or "main",
        "modified_count": len(modified_files),
        "modified_files": modified_files[:15],
        "diff_stat": diff_stat[:800],
        "has_changes": len(modified_files) > 0
    }

def generate_conventional_commit_message(diff_text: str) -> str:
    """Generate a clean conventional commit message using Gemini or heuristic analysis."""
    # Heuristic fallback
    dt = diff_text.lower()
    prefix = "feat"
    scope = "core"
    
    if "fix" in dt or "bug" in dt or "error" in dt:
        prefix = "fix"
    elif "test" in dt:
        prefix = "test"
    elif "doc" in dt or "readme" in dt:
        prefix = "docs"
    elif "refactor" in dt or "clean" in dt:
        prefix = "refactor"

    if "workspace" in dt or "layout" in dt:
        desc = "add autonomous workspace layouts and window snap grid"
    elif "file" in dt or "organizer" in dt:
        desc = "integrate autonomous downloads and desktop file organizer"
    elif "git" in dt or "devops" in dt:
        desc = "implement autonomous GitHub DevOps pipeline and commit automation"
    elif "clipboard" in dt:
        desc = "build persistent semantic clipboard history cortex"
    elif "intruder" in dt or "sentinel" in dt:
        desc = "add optical webcam intruder sentinel and screen lock"
    elif "code" in dt or "studio" in dt:
        desc = "integrate live voice-to-code generator studio"
    elif "price" in dt or "tracker" in dt:
        desc = "implement autonomous web price drop tracker"
    else:
        desc = "update J.A.R.V.I.S. autonomous system hands and workstation capabilities"

    return f"{prefix}({scope}): {desc}"

def ship_git_update(
    repo_path: str = None,
    commit_message: str = "",
    branch: str = None,
    create_pr: bool = False,
    pr_title: str = "",
    pr_body: str = ""
) -> dict:
    """Execute complete autonomous Git commit, push, and optional GitHub Pull Request."""
    target_repo = Path(repo_path).expanduser().resolve() if repo_path else HERE
    status = inspect_git_status(target_repo)
    
    if not status["has_changes"]:
        return {
            "success": True,
            "message": "Working tree is clean. No uncommitted modifications to ship, Sir."
        }
        
    active_branch = branch or status["branch"] or "main"
    
    # 1. Stage all changes
    code, stage_out = run_git(["add", "-A"], target_repo)
    if code != 0:
        return {"success": False, "error": f"Failed staging changes: {stage_out}"}
        
    # 2. Get Diff for commit message formulation
    _, diff_out = run_git(["diff", "--cached"], target_repo)
    msg = commit_message.strip()
    if not msg:
        msg = generate_conventional_commit_message(diff_out)
        
    # 3. Commit
    code, commit_out = run_git(["commit", "-m", msg], target_repo)
    if code != 0:
        return {"success": False, "error": f"Commit failed: {commit_out}"}
        
    # 4. Push to remote
    code, push_out = run_git(["push", "origin", active_branch], target_repo)
    push_success = (code == 0)
    
    # 5. Create Pull Request if requested via gh.exe
    pr_url = ""
    if create_pr and push_success:
        title = pr_title or msg
        body = pr_body or f"Autonomous pull request generated by J.A.R.V.I.S. on branch `{active_branch}`."
        code_pr, pr_out = run_gh(["pr", "create", "--title", title, "--body", body, "--head", active_branch], target_repo)
        if code_pr == 0:
            pr_url = pr_out.strip()
            
    return {
        "success": True,
        "branch": active_branch,
        "commit_message": msg,
        "pushed": push_success,
        "push_output": push_out[:200],
        "pr_url": pr_url,
        "message": f"Committed: '{msg}' on `{active_branch}`. Push: {'Success' if push_success else push_out[:100]}." + (f" PR: {pr_url}" if pr_url else "")
    }
