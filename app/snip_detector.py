"""Heuristics to decide whether a clipboard/file image is a screenshot capture."""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import psutil

from .platform_util import IS_MACOS, IS_WINDOWS

logger = logging.getLogger(__name__)

# Process basenames (lowercase) associated with OS screenshot tools.
SNIP_PROCESS_NAMES_WINDOWS = {
    "screenclippinghost.exe",
    "snippingtool.exe",
    "screensketch.exe",
}

SNIP_PROCESS_NAMES_MACOS = {
    "screencapture",
    "screenshot",
    "screencaptureui",
}

SNIP_PROCESS_NAMES = (
    SNIP_PROCESS_NAMES_WINDOWS
    if IS_WINDOWS
    else SNIP_PROCESS_NAMES_MACOS
    if IS_MACOS
    else SNIP_PROCESS_NAMES_WINDOWS | SNIP_PROCESS_NAMES_MACOS
)


def clipboard_owner_process_name() -> Optional[str]:
    """Return the process name that currently owns the clipboard (Windows only)."""
    if not IS_WINDOWS:
        return None
    try:
        import win32clipboard
        import win32process

        hwnd = win32clipboard.GetClipboardOwner()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return None
        return psutil.Process(pid).name().lower()
    except Exception as exc:  # noqa: BLE001
        logger.debug("clipboard owner lookup failed: %s", exc)
        return None


def looks_like_screenshot_filename(name: str) -> bool:
    n = name.lower()
    if not n.endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp", ".heic")):
        return False
    needles = (
        "screenshot",
        "screen shot",
        "snip",
        "capture",
        "bildschirmfoto",  # German
        "capture d’écran",
        "capture d'ecran",
    )
    return any(s in n for s in needles)


class SnipDetector:
    """Tracks recent snip-related process activity."""

    def __init__(self, window_seconds: float = 4.0) -> None:
        self.window_seconds = window_seconds
        self._last_snip_seen: float = 0.0
        self._poll_interval = 0.4
        self._last_poll: float = 0.0

    def mark_snip_activity(self) -> None:
        self._last_snip_seen = time.monotonic()

    def poll_processes(self) -> bool:
        """Return True if a snip-related process is currently running."""
        now = time.monotonic()
        if now - self._last_poll < self._poll_interval:
            return self.recently_armed()
        self._last_poll = now

        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").lower()
                # macOS process names often lack .exe; strip path-like noise
                base = name.split("/")[-1]
                if base in SNIP_PROCESS_NAMES or name in SNIP_PROCESS_NAMES:
                    self._last_snip_seen = now
                    return True
        except (psutil.Error, OSError) as exc:
            logger.debug("process poll failed: %s", exc)
        return self.recently_armed()

    def recently_armed(self) -> bool:
        if self._last_snip_seen <= 0:
            return False
        return (time.monotonic() - self._last_snip_seen) <= self.window_seconds

    def should_ocr(
        self,
        *,
        ocr_all_images: bool,
        image_width: int,
        image_height: int,
        min_width: int,
        min_height: int,
        from_screenshot_file: bool = False,
        filename: str = "",
    ) -> tuple[bool, str]:
        """
        Decide whether to run OCR.

        Returns (should_run, reason).
        """
        if image_width < min_width or image_height < min_height:
            return False, f"image too small ({image_width}x{image_height})"

        if ocr_all_images:
            return True, "ocr_all_clipboard_images"

        if from_screenshot_file:
            self.mark_snip_activity()
            return True, "screenshot file watcher"

        if filename and looks_like_screenshot_filename(filename):
            self.mark_snip_activity()
            return True, f"screenshot-like filename ({filename})"

        owner = clipboard_owner_process_name()
        if owner and owner in SNIP_PROCESS_NAMES:
            self.mark_snip_activity()
            return True, f"clipboard owner is {owner}"

        self.poll_processes()
        if self.recently_armed():
            return True, "snip process recently active"

        tool = "Screenshot" if IS_MACOS else "Snipping Tool"
        return (
            False,
            f"no recent {tool} activity (enable 'OCR all images' to always run)",
        )


def any_snip_process_running(names: Iterable[str] = SNIP_PROCESS_NAMES) -> bool:
    names_l = {n.lower() for n in names}
    try:
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower().split("/")[-1]
            if name in names_l:
                return True
    except (psutil.Error, OSError):
        return False
    return False
