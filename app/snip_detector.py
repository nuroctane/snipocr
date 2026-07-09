"""Heuristics to decide whether a clipboard image is a Snipping Tool capture."""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import psutil

logger = logging.getLogger(__name__)

SNIP_PROCESS_NAMES = {
    "screenclippinghost.exe",
    "snippingtool.exe",
    "screensketch.exe",  # older Snip & Sketch
}


def clipboard_owner_process_name() -> Optional[str]:
    """Return the process name that currently owns the clipboard, if any."""
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
                if name in SNIP_PROCESS_NAMES:
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
    ) -> tuple[bool, str]:
        """
        Decide whether to run OCR.

        Returns (should_run, reason).
        """
        if image_width < min_width or image_height < min_height:
            return False, f"image too small ({image_width}x{image_height})"

        if ocr_all_images:
            return True, "ocr_all_clipboard_images"

        owner = clipboard_owner_process_name()
        if owner and owner in SNIP_PROCESS_NAMES:
            self.mark_snip_activity()
            return True, f"clipboard owner is {owner}"

        # Refresh process state; snipping host often still alive briefly after capture.
        self.poll_processes()
        if self.recently_armed():
            return True, "snip process recently active"

        return False, "no recent Snipping Tool activity (enable 'OCR all images' to always run)"


def any_snip_process_running(names: Iterable[str] = SNIP_PROCESS_NAMES) -> bool:
    names_l = {n.lower() for n in names}
    try:
        for proc in psutil.process_iter(["name"]):
            name = (proc.info.get("name") or "").lower()
            if name in names_l:
                return True
    except (psutil.Error, OSError):
        return False
    return False
