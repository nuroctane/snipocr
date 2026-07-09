"""Lightweight Windows toast notifications."""

from __future__ import annotations

import logging

from .paths import logo_png

logger = logging.getLogger(__name__)


def notify(title: str, message: str, *, enabled: bool = True) -> None:
    if not enabled:
        return
    try:
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
    except Exception as exc:  # noqa: BLE001
        logger.debug("Toast failed (%s): %s — %s", exc, title, message)
