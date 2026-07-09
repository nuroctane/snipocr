"""macOS pasteboard image/text helpers (AppKit / PyObjC)."""

from __future__ import annotations

import io
import logging
import time
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


def _pasteboard():
    from AppKit import NSPasteboard

    return NSPasteboard.generalPasteboard()


def clipboard_has_image() -> bool:
    try:
        pb = _pasteboard()
        from AppKit import NSPasteboardTypePNG, NSPasteboardTypeTIFF

        types = set(pb.types() or [])
        if NSPasteboardTypePNG in types or NSPasteboardTypeTIFF in types:
            return True
        # Some apps use public.png / legacy names
        for t in types:
            name = str(t).lower()
            if "png" in name or "tiff" in name or "image" in name:
                return True
        return get_clipboard_image(retries=1) is not None
    except Exception as exc:  # noqa: BLE001
        logger.debug("clipboard_has_image failed: %s", exc)
        return False


def clipboard_has_text() -> bool:
    try:
        pb = _pasteboard()
        from AppKit import NSPasteboardTypeString

        return bool(pb.stringForType_(NSPasteboardTypeString))
    except Exception:
        return False


def get_clipboard_text() -> Optional[str]:
    try:
        pb = _pasteboard()
        from AppKit import NSPasteboardTypeString

        value = pb.stringForType_(NSPasteboardTypeString)
        return str(value) if value else None
    except Exception:
        return None


def get_clipboard_image(retries: int = 8) -> Optional[Image.Image]:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            img = _read_image_once()
            if img is not None:
                return img
            # Retry: Screenshot may still be writing to pasteboard
            time.sleep(0.03 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.03 * (attempt + 1))
    if last_err:
        raise RuntimeError(f"Failed to read clipboard image: {last_err}") from last_err
    return None


def _read_image_once() -> Optional[Image.Image]:
    pb = _pasteboard()
    from AppKit import NSPasteboardTypePNG, NSPasteboardTypeTIFF

    for ptype in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
        data = pb.dataForType_(ptype)
        if data is None:
            continue
        raw = bytes(data)
        if not raw:
            continue
        return Image.open(io.BytesIO(raw)).convert("RGB")

    # Fallback: NSImage → PNG/TIFF bytes
    try:
        from AppKit import NSImage

        nsimage = NSImage.alloc().initWithPasteboard_(pb)
        if nsimage is None:
            return None
        tiff = nsimage.TIFFRepresentation()
        if tiff is None:
            return None
        # Prefer decoding TIFF via Pillow (always available)
        return Image.open(io.BytesIO(bytes(tiff))).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        logger.debug("NSImage pasteboard fallback failed: %s", exc)

    # Last resort: Pillow ImageGrab
    try:
        from PIL import ImageGrab

        data = ImageGrab.grabclipboard()
        if isinstance(data, Image.Image):
            return data.convert("RGB")
    except Exception:
        pass
    return None


def set_clipboard_text(text: str) -> None:
    pb = _pasteboard()
    from AppKit import NSPasteboardTypeString

    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def get_clipboard_sequence_number() -> int:
    try:
        return int(_pasteboard().changeCount())
    except Exception:
        return 0
