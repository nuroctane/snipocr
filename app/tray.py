"""System tray / menu-bar icon and menu (Windows + macOS)."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageEnhance

from .ocr import engine_choices
from .ocr.rapid_ocr import ACCEL_PRESETS, MODEL_PRESETS
from .paths import logo_png
from .platform_util import IS_MACOS, IS_WINDOWS

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


def _model_label(model_type: str) -> str:
    labels = {
        "auto": "Auto (fastest for language)",
        "small": "Small (PP-OCRv6, recommended)",
        "mobile": "Mobile (lighter / older)",
        "server": "Server (heavier, more accurate)",
        "tiny": "Tiny (experimental)",
    }
    return labels.get(model_type, model_type)


def _accel_label(accel: str) -> str:
    labels = {
        "auto": "Auto (CoreML / DirectML / CUDA / CPU)",
        "cpu": "CPU only",
        "coreml": "CoreML (macOS)",
        "dml": "DirectML (Windows)",
        "cuda": "CUDA (NVIDIA)",
    }
    return labels.get(accel, accel)


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
        get_ocr_engine: Optional[Callable[[], str]] = None,
        set_ocr_engine: Optional[Callable[[str], str]] = None,
        get_rapidocr_model_type: Optional[Callable[[], str]] = None,
        set_rapidocr_model_type: Optional[Callable[[str], str]] = None,
        get_rapidocr_accel: Optional[Callable[[], str]] = None,
        set_rapidocr_accel: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.on_toggle_enabled = on_toggle_enabled
        self.on_show_last = on_show_last
        self.on_toggle_ocr_all = on_toggle_ocr_all
        self.on_quit = on_quit
        self.is_enabled = is_enabled
        self.is_ocr_all = is_ocr_all
        self.get_ocr_engine = get_ocr_engine or (lambda: "auto")
        self.set_ocr_engine = set_ocr_engine
        self.get_rapidocr_model_type = get_rapidocr_model_type or (lambda: "auto")
        self.set_rapidocr_model_type = set_rapidocr_model_type
        self.get_rapidocr_accel = get_rapidocr_accel or (lambda: "auto")
        self.set_rapidocr_accel = set_rapidocr_accel
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._processing = False

    def _build_icon(self):
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

        def engine_items() -> list:
            items = []
            for eid, label in engine_choices():

                def _make_handler(engine_id: str):
                    def _handler(icon=None, item=None) -> None:
                        if self.set_ocr_engine:
                            self.set_ocr_engine(engine_id)
                        if self._icon:
                            self._icon.update_menu()
                        self._refresh_icon()

                    return _handler

                def _make_checked(engine_id: str):
                    def _checked(item=None) -> bool:
                        return self.get_ocr_engine() == engine_id

                    return _checked

                items.append(
                    Item(
                        label,
                        _make_handler(eid),
                        checked=_make_checked(eid),
                        radio=True,
                    )
                )
            return items

        def model_items() -> list:
            items = []
            for mt in MODEL_PRESETS:

                def _make_handler(model_id: str):
                    def _handler(icon=None, item=None) -> None:
                        if self.set_rapidocr_model_type:
                            self.set_rapidocr_model_type(model_id)
                        if self._icon:
                            self._icon.update_menu()

                    return _handler

                def _make_checked(model_id: str):
                    def _checked(item=None) -> bool:
                        return self.get_rapidocr_model_type() == model_id

                    return _checked

                items.append(
                    Item(
                        _model_label(mt),
                        _make_handler(mt),
                        checked=_make_checked(mt),
                        radio=True,
                    )
                )
            return items

        def accel_items() -> list:
            # Only show platform-relevant accel options + auto/cpu/cuda
            presets = ["auto", "cpu"]
            if IS_MACOS:
                presets.append("coreml")
            if IS_WINDOWS:
                presets.append("dml")
            presets.append("cuda")
            # Keep order unique
            seen = set()
            ordered = []
            for p in presets:
                if p not in seen and p in ACCEL_PRESETS:
                    seen.add(p)
                    ordered.append(p)

            items = []
            for acc in ordered:

                def _make_handler(accel_id: str):
                    def _handler(icon=None, item=None) -> None:
                        if self.set_rapidocr_accel:
                            self.set_rapidocr_accel(accel_id)
                        if self._icon:
                            self._icon.update_menu()

                    return _handler

                def _make_checked(accel_id: str):
                    def _checked(item=None) -> bool:
                        return self.get_rapidocr_accel() == accel_id

                    return _checked

                items.append(
                    Item(
                        _accel_label(acc),
                        _make_handler(acc),
                        checked=_make_checked(acc),
                        radio=True,
                    )
                )
            return items

        menu = pystray.Menu(
            Item(enabled_text, self._toggle_enabled),
            Item(ocr_all_text, self._toggle_ocr_all),
            Item("Show last result", lambda: self.on_show_last()),
            pystray.Menu.SEPARATOR,
            Item("OCR engine", pystray.Menu(*engine_items())),
            Item("RapidOCR model", pystray.Menu(*model_items())),
            Item("RapidOCR acceleration", pystray.Menu(*accel_items())),
            pystray.Menu.SEPARATOR,
            Item("Quit", lambda: self._quit()),
        )

        self._icon = pystray.Icon(
            "SnipOCR",
            _load_tray_icon(disabled=not self.is_enabled()),
            "SnipOCR — listening for snips",
            menu,
        )
        return self._icon

    def start(self) -> None:
        """
        Start the tray icon.

        On Windows the icon runs on a daemon thread (tk owns the main thread).
        On macOS call `run_main_thread()` instead so AppKit owns the main thread.
        """
        if IS_MACOS:
            # Icon is built later on the main thread via run_main_thread().
            self._build_icon()
            return

        self._build_icon()
        self._thread = threading.Thread(
            target=self._icon.run,
            name="SnipOCRTray",
            daemon=True,
        )
        self._thread.start()

    def run_main_thread(self) -> None:
        """Block on the main thread running the menu-bar icon (macOS)."""
        if self._icon is None:
            self._build_icon()
        assert self._icon is not None
        self._icon.run()

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
            engine = self.get_ocr_engine()
            if self._processing:
                self._icon.title = "SnipOCR — OCR running…"
            elif not self.is_enabled():
                self._icon.title = "SnipOCR — disabled"
            else:
                self._icon.title = f"SnipOCR — listening ({engine})"
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
