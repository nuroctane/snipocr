"""System tray icon and menu."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def _make_icon(color: str = "#2D7FF9") -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill=color)
    # Simple "T" for text
    draw.rectangle((20, 18, 44, 24), fill="white")
    draw.rectangle((29, 24, 35, 48), fill="white")
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
            _make_icon(),
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

    def set_processing(self, processing: bool) -> None:
        if not self._icon:
            return
        try:
            color = "#F5A623" if processing else "#2D7FF9"
            self._icon.icon = _make_icon(color)
            self._icon.title = (
                "SnipOCR — OCR running…" if processing else "SnipOCR — listening for snips"
            )
        except Exception:
            pass

    def notify_balloon(self, title: str, message: str) -> None:
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _toggle_enabled(self, _icon=None, _item=None) -> None:
        self.on_toggle_enabled()
        if self._icon:
            self._icon.update_menu()

    def _toggle_ocr_all(self, _icon=None, _item=None) -> None:
        self.on_toggle_ocr_all()
        if self._icon:
            self._icon.update_menu()

    def _quit(self) -> None:
        self.on_quit()
