"""OS detection and platform-specific paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

PLATFORM_NAME = (
    "windows" if IS_WINDOWS else "macos" if IS_MACOS else "linux" if IS_LINUX else sys.platform
)


def default_ocr_engine() -> str:
    if IS_WINDOWS:
        return "windows"
    if IS_MACOS:
        return "macos"
    return "auto"


def config_dir() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / "SnipOCR"
    elif IS_MACOS:
        path = Path.home() / "Library" / "Application Support" / "SnipOCR"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        path = Path(xdg) / "snipocr" if xdg else Path.home() / ".config" / "snipocr"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / "SnipOCR"
    elif IS_MACOS:
        path = Path.home() / "Library" / "Logs" / "SnipOCR"
    else:
        xdg = os.environ.get("XDG_STATE_HOME")
        path = Path(xdg) / "snipocr" if xdg else Path.home() / ".local" / "state" / "snipocr"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ui_font_family() -> str:
    if IS_MACOS:
        return "Helvetica Neue"
    if IS_WINDOWS:
        return "Segoe UI"
    return "Sans"


def screenshot_dirs() -> list[Path]:
    """Folders where OS screenshot tools commonly save image files."""
    home = Path.home()
    dirs: list[Path] = []
    if IS_WINDOWS:
        pics = Path(os.environ.get("USERPROFILE", str(home))) / "Pictures" / "Screenshots"
        dirs.append(pics)
    elif IS_MACOS:
        dirs.extend(
            [
                home / "Desktop",
                home / "Pictures" / "Screenshots",
            ]
        )
    else:
        dirs.append(home / "Pictures")
    return [d for d in dirs if d.exists()]


def snip_hotkey_hint() -> str:
    if IS_MACOS:
        return "⌘⇧4 (or ⌘⌃⇧4 to copy to clipboard)"
    if IS_WINDOWS:
        return "Win+Shift+S"
    return "your screenshot shortcut"


def snip_tool_name() -> str:
    if IS_MACOS:
        return "Screenshot / screencapture"
    if IS_WINDOWS:
        return "Snipping Tool"
    return "screenshot tool"
