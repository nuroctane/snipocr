"""Load and save SnipOCR settings from %APPDATA%\\SnipOCR\\config.json."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from pathlib import Path


DEFAULTS = {
    "enabled": True,
    "ocr_engine": "windows",
    "ocr_language": "en-US",
    "replace_clipboard_with_text": True,
    "ocr_all_clipboard_images": False,
    "show_popup": True,
    "popup_autohide_seconds": 8,
    "show_toast": True,
    "min_image_width": 32,
    "min_image_height": 32,
    "startup_with_windows": False,
    "collapse_single_newlines": False,
    "snip_process_window_seconds": 4.0,
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / "SnipOCR"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Settings:
    enabled: bool = True
    ocr_engine: str = "windows"
    ocr_language: str = "en-US"
    replace_clipboard_with_text: bool = True
    ocr_all_clipboard_images: bool = False
    show_popup: bool = True
    popup_autohide_seconds: int = 8
    show_toast: bool = True
    min_image_width: int = 32
    min_image_height: int = 32
    startup_with_windows: bool = False
    collapse_single_newlines: bool = False
    snip_process_window_seconds: float = 4.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)


def load_settings() -> Settings:
    path = config_path()
    if not path.exists():
        settings = Settings()
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
