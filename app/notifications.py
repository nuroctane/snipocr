"""Cross-platform desktop notifications."""

from __future__ import annotations

import logging
import subprocess

from .paths import logo_png
from .platform_util import IS_MACOS, IS_WINDOWS

logger = logging.getLogger(__name__)


def notify(title: str, message: str, *, enabled: bool = True) -> None:
    if not enabled:
        return
    try:
        if IS_WINDOWS:
            _notify_windows(title, message)
        elif IS_MACOS:
            _notify_macos(title, message)
        else:
            logger.info("Notify: %s — %s", title, message)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Toast failed (%s): %s — %s", exc, title, message)


def _notify_windows(title: str, message: str) -> None:
    from winotify import Notification, audio

    icon = logo_png(256)
    if not icon.exists():
        icon = logo_png()

    kwargs = {
        "app_id": "SnipOCR",
        "title": title,
        "msg": message,
        "duration": "short",
    }
    if icon.exists():
        kwargs["icon"] = str(icon)

    toast = Notification(**kwargs)
    toast.set_audio(audio.Default, loop=False)
    toast.show()


def _notify_macos(title: str, message: str) -> None:
    # Escape for AppleScript string literals
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    script = f'display notification "{esc(message)}" with title "{esc(title)}"'
    subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        timeout=5,
    )
