"""Lightweight Windows toast notifications."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify(title: str, message: str, *, enabled: bool = True) -> None:
    if not enabled:
        return
    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="SnipOCR",
            title=title,
            msg=message,
            duration="short",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Toast failed (%s): %s — %s", exc, title, message)
