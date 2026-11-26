"""J.A.R.V.I.S. Autonomous Code Self-Patching Runtime.
Enables autonomous diagnostic scanning, AST validation, dry-run sandbox diffing,
pre-patch rollback snapshotting, and atomic self-healing of workstation code modules.
"""

import ast
import difflib
import json
import os
from pathlib import Path
import py_compile
import shutil
import tempfile
import time
from typing import Dict, List, Optional, Any, Tuple

_p = Path(__file__).resolve().parent
HERE = _p.parent.parent if _p.parent.name == "backend" else _p.parent
WORKSPACE_DIR = str(HERE)
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
PATCHES_BACKUP_DIR = os.path.join(DATA_DIR, "backups", "patches")
PATCH_HISTORY_FILE = os.path.join(DATA_DIR, "patch_history.json")

class CodeSelfPatcher:
    def __init__(self):
        os.makedirs(PATCHES_BACKUP_DIR, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if os.path.exists(PATCH_HISTORY_FILE):
            try:
                with open(PATCH_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Self-Patcher] Error reading patch history: {e}")
        return []

    def _save_history(self):
        try:
            with open(PATCH_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"[Self-Patcher] Error writing patch history: {e}")

    def run_code_diagnostics(self) -> Dict[str, Any]:
        """Perform comprehensive AST and compilation diagnostics across all workspace Python files."""
        files_to_check = ["server.py"]
        core_dir = os.path.join(WORKSPACE_DIR, "core")
        if os.path.exists(core_dir):
            for root, _, filenames in os.walk(core_dir):
                for fn in filenames:
                    if fn.endswith(".py") and not fn.startswith("__"):
                        rel = os.path.relpath(os.path.join(root, fn), WORKSPACE_DIR)
                        files_to_check.append(rel)

        results = []
        clean_count = 0
        total_functions = 0
        total_loc = 0

        for rel_path in files_to_check:
            abs_path = os.path.join(WORKSPACE_DIR, rel_path)
            if not os.path.exists(abs_path):
                continue

            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    source = f.read()

                loc = len(source.splitlines())
                total_loc += loc

                # AST syntax and node inspection
                tree = ast.parse(source, filename=rel_path)
                fn_count = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
                total_functions += fn_count

                # Bytecode compile test
                py_compile.compile(abs_path, doraise=True)

                results.append({
                    "file": rel_path,
                    "status": "NOMINAL",
                    "lines_of_code": loc,
                    "function_count": fn_count,
                    "issues": []
                })
                clean_count += 1
            except Exception as err:
                results.append({
                    "file": rel_path,
                    "status": "ANOMALY_DETECTED",
                    "lines_of_code": 0,
                    "function_count": 0,
                    "issues": [str(err)]
                })

        health_pct = round((clean_count / max(1, len(files_to_check))) * 100, 1)

        return {
            "health_score": health_pct,
            "overall_status": "OPTIMAL" if health_pct == 100.0 else "WARNING",
            "checked_modules": len(files_to_check),
            "clean_modules": clean_count,
            "total_lines_of_code": total_loc,
            "total_functions_indexed": total_functions,
            "module_diagnostics": results,
            "timestamp": time.strftime("%H:%M:%S")
        }

    def inspect_file(self, rel_path: str, start_line: int = 1, end_line: int = 100) -> Dict[str, Any]:
        """Safely inspect a range of lines in a workspace file."""
        abs_path = os.path.join(WORKSPACE_DIR, rel_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Module '{rel_path}' does not exist.")

        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(total, end_line)

        snippet = "".join(lines[start_idx:end_idx])
        return {
            "file": rel_path,
            "total_lines": total,
            "start_line": start_idx + 1,
            "end_line": end_idx,
            "snippet": snippet
        }

    def generate_unified_diff(self, original_text: str, modified_text: str, filename: str) -> str:
        """Generate human-readable unified diff."""
        orig_lines = original_text.splitlines(keepends=True)
        mod_lines = modified_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines, mod_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=3
        )
        return "".join(diff)

    def apply_patch(
        self,
        rel_path: str,
        target_block: str,
        replacement_block: str,
        reason: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Atomically test, snapshot, and apply a surgical code patch with rollback safety."""
        abs_path = os.path.join(WORKSPACE_DIR, rel_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Cannot patch non-existent file: {rel_path}")

        with open(abs_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        if target_block not in original_content:
            raise ValueError(
                f"Target block not found in {rel_path}. Verify whitespace and line formatting exactly."
            )

        patched_content = original_content.replace(target_block, replacement_block, 1)
        diff_text = self.generate_unified_diff(original_content, patched_content, rel_path)

        # 1. Sandbox Compilation / AST Validation
        if rel_path.endswith(".py"):
            try:
                ast.parse(patched_content, filename=rel_path)
                with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
                    tmp.write(patched_content)
                    tmp_name = tmp.name
                try:
                    py_compile.compile(tmp_name, doraise=True)
                finally:
                    if os.path.exists(tmp_name):
                        os.remove(tmp_name)
            except Exception as comp_err:
                raise ValueError(f"Self-patch aborted: Sandbox AST/bytecode compilation failed: {comp_err}")

        if dry_run:
            return {
                "dry_run": True,
                "status": "VALIDATION_PASSED",
                "file": rel_path,
                "reason": reason,
                "diff": diff_text,
                "message": "Dry-run validation successful. Zero syntax anomalies detected, Sir."
            }

        # 2. Pre-Patch Rollback Snapshot Creation
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        sanitized_fn = rel_path.replace("/", "_").replace("\\", "_")
        snapshot_filename = f"{timestamp_str}_{sanitized_fn}.bak"
        snapshot_abs = os.path.join(PATCHES_BACKUP_DIR, snapshot_filename)

        with open(snapshot_abs, "w", encoding="utf-8") as f:
            f.write(original_content)

        # 3. Atomic Write
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(patched_content)

        # 4. Post-write live bytecode verification
        if rel_path.endswith(".py"):
            try:
                py_compile.compile(abs_path, doraise=True)
            except Exception as live_err:
                # Emergency auto-revert from snapshot
                shutil.copyfile(snapshot_abs, abs_path)
                raise RuntimeError(
                    f"Live compilation failed after write: {live_err}. Automatically reverted file from snapshot!"
                )

        # Record in history ledger
        patch_record = {
            "id": f"patch_{secrets.token_hex(4)}",
            "file": rel_path,
            "timestamp": time.time(),
            "timestamp_formatted": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
            "snapshot_file": snapshot_filename,
            "diff_summary": diff_text[:500]
        }
        self.history.append(patch_record)
        self._save_history()

        return {
            "dry_run": False,
            "status": "PATCH_APPLIED",
            "file": rel_path,
            "reason": reason,
            "snapshot_created": snapshot_filename,
            "diff": diff_text,
            "message": f"Autonomous self-patch committed successfully to '{rel_path}', Sir."
        }

    def rollback_latest_patch(self) -> Dict[str, Any]:
        """Rollback the most recent patch from pre-patch snapshot."""
        if not self.history:
            return {"status": "NO_PATCHES", "message": "No patch history on record to rollback, Sir."}

        last_patch = self.history[-1]
        rel_path = last_patch["file"]
        snapshot_filename = last_patch["snapshot_file"]
        snapshot_abs = os.path.join(PATCHES_BACKUP_DIR, snapshot_filename)

        if not os.path.exists(snapshot_abs):
            raise FileNotFoundError(f"Snapshot backup '{snapshot_filename}' not found on disk.")

        abs_path = os.path.join(WORKSPACE_DIR, rel_path)
        shutil.copyfile(snapshot_abs, abs_path)

        popped = self.history.pop()
        self._save_history()

        return {
            "status": "ROLLBACK_SUCCESSFUL",
            "restored_file": rel_path,
            "reverted_patch_id": popped.get("id"),
            "reason": popped.get("reason"),
            "message": f"Successfully rolled back '{rel_path}' to pre-patch state from snapshot, Sir."
        }

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Return list of available rollback snapshots."""
        return self.history

# Global singleton
_self_patcher_instance: Optional[CodeSelfPatcher] = None

def get_code_self_patcher() -> CodeSelfPatcher:
    global _self_patcher_instance
    if _self_patcher_instance is None:
        _self_patcher_instance = CodeSelfPatcher()
    return _self_patcher_instance
