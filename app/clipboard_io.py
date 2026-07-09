"""Cross-platform clipboard image/text helpers."""

from __future__ import annotations

import logging
from typing import Optional

from PIL import Image

from .platform_util import IS_MACOS, IS_WINDOWS

logger = logging.getLogger(__name__)


def clipboard_has_image() -> bool:
    if IS_WINDOWS:
        from . import clipboard_io_win as impl

        return impl.clipboard_has_image()
    if IS_MACOS:
        from . import clipboard_io_mac as impl

        return impl.clipboard_has_image()
    return _grab_clipboard_image() is not None


def clipboard_has_text() -> bool:
    if IS_WINDOWS:
        from . import clipboard_io_win as impl

        return impl.clipboard_has_text()
    if IS_MACOS:
        from . import clipboard_io_mac as impl

        return impl.clipboard_has_text()
    return get_clipboard_text() is not None


def get_clipboard_text() -> Optional[str]:
    if IS_WINDOWS:
        from . import clipboard_io_win as impl

        return impl.get_clipboard_text()
    if IS_MACOS:
        from . import clipboard_io_mac as impl

        return impl.get_clipboard_text()
    return None


def get_clipboard_image(retries: int = 8) -> Optional[Image.Image]:
    if IS_WINDOWS:
        from . import clipboard_io_win as impl

        return impl.get_clipboard_image(retries=retries)
    if IS_MACOS:
        from . import clipboard_io_mac as impl

        return impl.get_clipboard_image(retries=retries)
    return _grab_clipboard_image()


def set_clipboard_text(text: str) -> None:
    if IS_WINDOWS:
        from . import clipboard_io_win as impl

        impl.set_clipboard_text(text)
        return
    if IS_MACOS:
        from . import clipboard_io_mac as impl

        impl.set_clipboard_text(text)
        return
    raise RuntimeError(f"set_clipboard_text is not supported on this platform")


def get_clipboard_sequence_number() -> int:
    if IS_WINDOWS:
        from . import clipboard_io_win as impl

        return impl.get_clipboard_sequence_number()
    if IS_MACOS:
        from . import clipboard_io_mac as impl

        return impl.get_clipboard_sequence_number()
    return 0


def _grab_clipboard_image() -> Optional[Image.Image]:
    try:
        from PIL import ImageGrab

        data = ImageGrab.grabclipboard()
        if isinstance(data, Image.Image):
            return data.convert("RGB")
    except Exception as exc:  # noqa: BLE001
        logger.debug("ImageGrab.grabclipboard failed: %s", exc)
    return None
