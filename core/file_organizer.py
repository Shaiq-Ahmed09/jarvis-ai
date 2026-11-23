"""J.A.R.V.I.S. Autonomous File & Downloads Auto-Organizer
Categorizes files across Downloads and Desktop into structured folders (/Documents, /Installers, /Images, /Code, /Media, /Archives).
Features intelligent OCR renaming for screenshots based on on-screen text content.
"""
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

CATEGORY_EXTENSIONS = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".epub", ".rtf", ".odt"],
    "Images": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff"],
    "Media": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".sql", ".rs", ".go", ".cpp", ".c", ".h", ".java", ".sh", ".ps1"],
    "Installers": [".exe", ".msi", ".dmg", ".iso", ".apk"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
}

EXT_TO_CATEGORY = {}
for cat, exts in CATEGORY_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_CATEGORY[ext.lower()] = cat

def get_ocr_keywords(image_path: Path, max_words: int = 4) -> str:
    """Extract prominent headline keywords from an image using RapidOCR or fallback regex."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        res, _ = engine(str(image_path))
        if res:
            texts = [r[1] for r in res if len(r[1].strip()) > 3]
            clean_words = []
            for t in texts:
                words = re.findall(r"[A-Za-z0-9_-]{3,}", t)
                for w in words:
                    if w.lower() not in ["screenshot", "window", "desktop", "image", "screen", "untitled", "chrome", "edge"]:
                        clean_words.append(w)
                        if len(clean_words) >= max_words:
                            break
                if len(clean_words) >= max_words:
                    break
            if clean_words:
                return "_".join(clean_words)
    except Exception:
        pass
    return ""

def organize_directory(target_dir: str = "downloads", ocr_rename_screenshots: bool = True) -> dict:
    """Sort loose files in target directory into organized category folders."""
    home = Path.home()
    if target_dir.lower() in ["downloads", "download"]:
        dir_path = home / "Downloads"
    elif target_dir.lower() in ["desktop"]:
        dir_path = home / "Desktop"
    else:
        dir_path = Path(target_dir).expanduser().resolve()

    if not dir_path.exists():
        return {"success": False, "error": f"Directory not found: {dir_path}"}

    moved_count = 0
    renamed_screenshots = 0
    categories_used = set()
    errors = []

    # Excluded files and folders
    excluded_names = {
        "desktop.ini", "thumbs.db", ".ds_store", ".gitignore",
        "documents", "images", "media", "code", "installers", "archives", "screenshots"
    }

    try:
        items = list(dir_path.iterdir())
    except Exception as e:
        return {"success": False, "error": f"Failed reading directory: {e}"}

    for item in items:
        # Skip directories, system files, and shortcuts
        if item.is_dir() or item.name.lower() in excluded_names or item.name.startswith("."):
            continue
        if item.suffix.lower() in [".lnk", ".url"]:
            continue

        ext = item.suffix.lower()
        cat = EXT_TO_CATEGORY.get(ext)

        # Check if file is a recent screenshot to OCR-rename
        if ocr_rename_screenshots and ext in [".png", ".jpg", ".jpeg"]:
            is_screenshot_name = any(k in item.name.lower() for k in ["screenshot", "screen shot", "snip", "capture"])
            if is_screenshot_name:
                try:
                    ocr_tag = get_ocr_keywords(item)
                    date_tag = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d")
                    tag_part = f"_{ocr_tag}" if ocr_tag else ""
                    new_name = f"Screenshot_{date_tag}{tag_part}{ext}"
                    new_path = dir_path / new_name
                    if not new_path.exists() and new_name != item.name:
                        item.rename(new_path)
                        item = new_path
                        renamed_screenshots += 1
                except Exception as ex:
                    errors.append(f"Screenshot rename error on {item.name}: {ex}")

        # Move to category subfolder
        if cat:
            dest_dir = dir_path / cat
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / item.name

            # Avoid collision
            if dest_file.exists():
                stem = item.stem
                counter = 1
                while dest_file.exists():
                    dest_file = dest_dir / f"{stem}_{counter}{ext}"
                    counter += 1

            try:
                shutil.move(str(item), str(dest_file))
                moved_count += 1
                categories_used.add(cat)
            except Exception as ex:
                errors.append(f"Move error on {item.name}: {ex}")

    return {
        "success": True,
        "directory": str(dir_path),
        "files_organized": moved_count,
        "screenshots_ocr_renamed": renamed_screenshots,
        "categories": list(categories_used),
        "message": f"Organized {moved_count} file(s) into {len(categories_used)} folders in {dir_path.name}. OCR-renamed {renamed_screenshots} screenshot(s)."
    }
