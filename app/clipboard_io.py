"""Read images from and write text to the Windows clipboard."""

from __future__ import annotations

import io
import struct
import time
from typing import Optional

import win32clipboard
import win32con
from PIL import Image

# Registered PNG clipboard format used by many modern apps / Snipping Tool.
CF_PNG = None


def _ensure_png_format() -> int:
    global CF_PNG
    if CF_PNG is None:
        CF_PNG = win32clipboard.RegisterClipboardFormat("PNG")
    return CF_PNG


def _open_clipboard(retries: int = 8, delay: float = 0.03) -> None:
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            win32clipboard.OpenClipboard()
            return
        except Exception as exc:  # noqa: BLE001 — clipboard can be locked
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not open clipboard: {last_err}")


def clipboard_has_image() -> bool:
    try:
        _open_clipboard()
        try:
            png = _ensure_png_format()
            return bool(
                win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB)
                or win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIBV5)
                or win32clipboard.IsClipboardFormatAvailable(png)
            )
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return False


def clipboard_has_text() -> bool:
    try:
        _open_clipboard()
        try:
            return bool(
                win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT)
                or win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT)
            )
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return False


def get_clipboard_text() -> Optional[str]:
    try:
        _open_clipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return data if isinstance(data, str) else None
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return None


def _dib_to_image(dib_bytes: bytes) -> Image.Image:
    """Convert CF_DIB payload (BITMAPINFOHEADER + pixels) to a Pillow image."""
    if len(dib_bytes) < 40:
        raise ValueError("DIB data too short")

    # Prepend a BITMAPFILEHEADER so Pillow can open as BMP.
    header_size = struct.unpack_from("<I", dib_bytes, 0)[0]
    # biSizeImage may be 0 for BI_RGB — compute from remaining data.
    file_size = 14 + len(dib_bytes)
    bmp_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 14 + header_size)
    return Image.open(io.BytesIO(bmp_header + dib_bytes)).convert("RGB")


def get_clipboard_image(retries: int = 8) -> Optional[Image.Image]:
    """Return a Pillow RGB image from the clipboard, or None if unavailable."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            _open_clipboard()
            try:
                png_fmt = _ensure_png_format()
                if win32clipboard.IsClipboardFormatAvailable(png_fmt):
                    data = win32clipboard.GetClipboardData(png_fmt)
                    if data:
                        return Image.open(io.BytesIO(data)).convert("RGB")

                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                    data = win32clipboard.GetClipboardData(win32con.CF_DIB)
                    if data:
                        return _dib_to_image(bytes(data))

                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIBV5):
                    data = win32clipboard.GetClipboardData(win32con.CF_DIBV5)
                    if data:
                        return _dib_to_image(bytes(data))

                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.03 * (attempt + 1))
    if last_err:
        raise RuntimeError(f"Failed to read clipboard image: {last_err}") from last_err
    return None


def set_clipboard_text(text: str) -> None:
    """Replace clipboard contents with Unicode text."""
    _open_clipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard_sequence_number() -> int:
    return int(win32clipboard.GetClipboardSequenceNumber())
