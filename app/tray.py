"""System tray icon and menu."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageEnhance

from .paths import logo_png

logger = logging.getLogger(__name__)


def _load_tray_icon(*, processing: bool = False, disabled: bool = False) -> Image.Image:
    """Load branded logo for the tray; fall back to a simple geometric mark."""
    path = logo_png(64)
    if not path.exists():
        path = logo_png()
    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
    except Exception:
        img = _fallback_icon()

    if processing:
        # Warm the blue accents slightly so the tray shows activity.
        overlay = Image.new("RGBA", img.size, (245, 166, 35, 48))
        img = Image.alpha_composite(img, overlay)
    elif disabled:
        img = ImageEnhance.Color(img).enhance(0.15)
        img = ImageEnhance.Brightness(img).enhance(0.65)

    return img


def _fallback_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 8, 56, 56), outline=(235, 245, 255, 255), width=3)
    draw.line((18, 28, 40, 28), fill=(235, 245, 255, 255), width=3)
    draw.line((18, 36, 46, 36), fill=(90, 180, 255, 255), width=3)
    draw.line((18, 44, 36, 44), fill=(235, 245, 255, 255), width=3)
    return img


class TrayApp:
    def __init__(
        self,
        *,
        on_toggle_enabled: Callable[[], bool],
        on_show_last: Callable[[], None],
        on_toggle_ocr_all: Callable[[], bool],
        on_quit: Callable[[], None],
        is_enabled: Callable[[], bool],
        is_ocr_all: Callable[[], bool],
    ) -> None:
        self.on_toggle_enabled = on_toggle_enabled
        self.on_show_last = on_show_last
        self.on_toggle_ocr_all = on_toggle_ocr_all
        self.on_quit = on_quit
        self.is_enabled = is_enabled
        self.is_ocr_all = is_ocr_all
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._processing = False

    def start(self) -> None:
        import pystray
        from pystray import MenuItem as Item

        def enabled_text(_item=None) -> str:
            return "Disable SnipOCR" if self.is_enabled() else "Enable SnipOCR"

        def ocr_all_text(_item=None) -> str:
            return (
                "Disable OCR all images"
                if self.is_ocr_all()
                else "Enable OCR all images"
            )

        menu = pystray.Menu(
            Item(enabled_text, self._toggle_enabled),
            Item(ocr_all_text, self._toggle_ocr_all),
            Item("Show last result", lambda: self.on_show_last()),
            Item("Quit", lambda: self._quit()),
        )

        self._icon = pystray.Icon(
            "SnipOCR",
            _load_tray_icon(disabled=not self.is_enabled()),
            "SnipOCR — listening for snips",
            menu,
        )
        self._thread = threading.Thread(
            target=self._icon.run,
            name="SnipOCRTray",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _refresh_icon(self) -> None:
        if not self._icon:
            return
        try:
            self._icon.icon = _load_tray_icon(
                processing=self._processing,
                disabled=not self.is_enabled(),
            )
            if self._processing:
                self._icon.title = "SnipOCR — OCR running…"
            elif not self.is_enabled():
                self._icon.title = "SnipOCR — disabled"
            else:
                self._icon.title = "SnipOCR — listening for snips"
        except Exception:
            pass

    def set_processing(self, processing: bool) -> None:
        self._processing = processing
        self._refresh_icon()

    def notify_balloon(self, title: str, message: str) -> None:
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _toggle_enabled(self, _icon=None, _item=None) -> None:
        self.on_toggle_enabled()
        self._refresh_icon()
        if self._icon:
            self._icon.update_menu()

    def _toggle_ocr_all(self, _icon=None, _item=None) -> None:
        self.on_toggle_ocr_all()
        if self._icon:
            self._icon.update_menu()

    def _quit(self) -> None:
        self.on_quit()
