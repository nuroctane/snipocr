"""Load and save SnipOCR settings (cross-platform config dir)."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .platform_util import config_dir, default_ocr_engine

DEFAULTS = {
    "enabled": True,
    "ocr_engine": "auto",
    "ocr_language": "en-US",
    "replace_clipboard_with_text": True,
    "ocr_all_clipboard_images": False,
    "show_popup": True,
    "popup_autohide_seconds": 8,
    "show_toast": True,
    "min_image_width": 32,
    "min_image_height": 32,
    "startup_with_windows": False,  # kept for backward compat; Windows only
    "watch_screenshot_folders": True,
    "collapse_single_newlines": False,
    "snip_process_window_seconds": 4.0,
}


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Settings:
    enabled: bool = True
    ocr_engine: str = "auto"
    ocr_language: str = "en-US"
    replace_clipboard_with_text: bool = True
    ocr_all_clipboard_images: bool = False
    show_popup: bool = True
    popup_autohide_seconds: int = 8
    show_toast: bool = True
    min_image_width: int = 32
    min_image_height: int = 32
    startup_with_windows: bool = False
    watch_screenshot_folders: bool = True
    collapse_single_newlines: bool = False
    snip_process_window_seconds: float = 4.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        # Migrate legacy default "windows" stored on non-Windows configs
        if kwargs.get("ocr_engine") == "windows" and default_ocr_engine() != "windows":
            # Only auto-migrate if this is clearly a stale default without user intent —
            # leave explicit "windows" if user set it; migration of pure defaults handled in load.
            pass
        return cls(**kwargs)


def load_settings() -> Settings:
    path = config_path()
    if not path.exists():
        settings = Settings(ocr_engine="auto")
        save_settings(settings)
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        merged = deepcopy(DEFAULTS)
        merged.update(raw if isinstance(raw, dict) else {})
        return Settings.from_dict(merged)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return Settings()


def save_settings(settings: Settings) -> None:
    path = config_path()
    path.write_text(
        json.dumps(settings.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
