"""J.A.R.V.I.S. Mark VII Stark HUD Theme & Aesthetic Presets Engine.
Manages executive design styles, frosted glassmorphism parameters,
color harmonies (Refined Cyan, Electric Amber, Stealth Carbon, Sol Overwatch),
and typography hierarchy profiles.
"""

from typing import Dict, Any, List, Optional
import json

THEME_PRESETS: Dict[str, Dict[str, Any]] = {
    "executive_minimal": {
        "id": "executive_minimal",
        "name": "Stark Executive Minimal",
        "description": "Refined obsidian glass, minimalist cybernetic typography, balanced cyan & electric amber accents.",
        "vars": {
            "--bg": "#02060b",
            "--panel": "rgba(4, 11, 20, 0.76)",
            "--panel-border": "rgba(0, 240, 255, 0.16)",
            "--cyan": "#00f0ff",
            "--cyan-dim": "rgba(0, 240, 255, 0.12)",
            "--cyan-glow": "rgba(0, 240, 255, 0.28)",
            "--amber": "#ffb020",
            "--amber-dim": "rgba(255, 176, 32, 0.12)",
            "--amber-glow": "rgba(255, 176, 32, 0.32)",
            "--emerald": "#00ff88",
            "--red": "#ff385c",
            "--txt": "#edf7fa",
            "--dim": "#7096a8",
            "--glass-blur": "18px",
            "--card-bg": "linear-gradient(135deg, rgba(255, 255, 255, 0.025) 0%, rgba(0, 240, 255, 0.01) 100%), rgba(3, 8, 16, 0.65)",
            "--card-border": "rgba(0, 240, 255, 0.14)",
            "--glow-intensity": "0.85"
        }
    },
    "mark_vii_classic": {
        "id": "mark_vii_classic",
        "name": "Mark VII Stark Arc Classic",
        "description": "Vibrant high-contrast holographic cyan, electric arc reactor pulses, and intense cybernetic overlays.",
        "vars": {
            "--bg": "#03080e",
            "--panel": "rgba(6, 20, 32, 0.85)",
            "--panel-border": "rgba(0, 240, 255, 0.25)",
            "--cyan": "#00f0ff",
            "--cyan-dim": "rgba(0, 240, 255, 0.18)",
            "--cyan-glow": "rgba(0, 240, 255, 0.45)",
            "--amber": "#ffaa00",
            "--amber-dim": "rgba(255, 170, 0, 0.18)",
            "--amber-glow": "rgba(255, 170, 0, 0.45)",
            "--emerald": "#00ff88",
            "--red": "#ff3344",
            "--txt": "#e2f4f8",
            "--dim": "#628a9c",
            "--glass-blur": "14px",
            "--card-bg": "rgba(0, 240, 255, 0.04)",
            "--card-border": "rgba(0, 240, 255, 0.2)",
            "--glow-intensity": "1.0"
        }
    },
    "stealth_tactical": {
        "id": "stealth_tactical",
        "name": "Stealth Carbon Tactical",
        "description": "Ultra-dark matte obsidian with sharp emerald telemetry, subdued lighting, and zero glare.",
        "vars": {
            "--bg": "#010305",
            "--panel": "rgba(3, 7, 12, 0.88)",
            "--panel-border": "rgba(0, 255, 136, 0.16)",
            "--cyan": "#00e5a3",
            "--cyan-dim": "rgba(0, 229, 163, 0.12)",
            "--cyan-glow": "rgba(0, 229, 163, 0.25)",
            "--amber": "#ffaa00",
            "--amber-dim": "rgba(255, 170, 0, 0.12)",
            "--amber-glow": "rgba(255, 170, 0, 0.25)",
            "--emerald": "#00ff88",
            "--red": "#ff3355",
            "--txt": "#dce8e4",
            "--dim": "#5c7970",
            "--glass-blur": "16px",
            "--card-bg": "rgba(2, 6, 10, 0.75)",
            "--card-border": "rgba(0, 255, 136, 0.15)",
            "--glow-intensity": "0.6"
        }
    },
    "sol_amber_overwatch": {
        "id": "sol_amber_overwatch",
        "name": "Sol Amber Overwatch",
        "description": "Solar radiation spectrum with rich electric amber primary, bronze glass, and deep cyan sub-frequencies.",
        "vars": {
            "--bg": "#060402",
            "--panel": "rgba(14, 9, 4, 0.82)",
            "--panel-border": "rgba(255, 170, 0, 0.22)",
            "--cyan": "#ffaa00",
            "--cyan-dim": "rgba(255, 170, 0, 0.14)",
            "--cyan-glow": "rgba(255, 170, 0, 0.38)",
            "--amber": "#00f0ff",
            "--amber-dim": "rgba(0, 240, 255, 0.14)",
            "--amber-glow": "rgba(0, 240, 255, 0.38)",
            "--emerald": "#00ffaa",
            "--red": "#ff4444",
            "--txt": "#f8f0e2",
            "--dim": "#9c8262",
            "--glass-blur": "20px",
            "--card-bg": "rgba(255, 170, 0, 0.04)",
            "--card-border": "rgba(255, 170, 0, 0.18)",
            "--glow-intensity": "0.9"
        }
    }
}

class HUDThemeManager:
    """Manages active aesthetic presets and HUD design configurations."""

    def __init__(self):
        self.active_theme_id: str = "executive_minimal"
        self.density_mode: str = "normal"  # "compact" | "normal" | "spacious"
        self.glass_blur_enabled: bool = True

    def get_active_theme(self) -> Dict[str, Any]:
        preset = THEME_PRESETS.get(self.active_theme_id, THEME_PRESETS["executive_minimal"])
        return {
            "active_id": self.active_theme_id,
            "name": preset["name"],
            "description": preset["description"],
            "density_mode": self.density_mode,
            "glass_blur_enabled": self.glass_blur_enabled,
            "vars": preset["vars"],
            "available_presets": [
                {"id": p["id"], "name": p["name"], "description": p["description"]}
                for p in THEME_PRESETS.values()
            ]
        }

    def set_theme(self, theme_id: str, density_mode: Optional[str] = None) -> Dict[str, Any]:
        if theme_id in THEME_PRESETS:
            self.active_theme_id = theme_id
        if density_mode in ["compact", "normal", "spacious"]:
            self.density_mode = density_mode
        return self.get_active_theme()

    def cycle_next_theme(self) -> Dict[str, Any]:
        keys = list(THEME_PRESETS.keys())
        idx = keys.index(self.active_theme_id) if self.active_theme_id in keys else 0
        next_id = keys[(idx + 1) % len(keys)]
        return self.set_theme(next_id)

_theme_manager_instance: Optional[HUDThemeManager] = None

def get_hud_theme_manager() -> HUDThemeManager:
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = HUDThemeManager()
    return _theme_manager_instance
