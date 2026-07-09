"""
SnipOCR — automatic local OCR when you take a screenshot.

Windows: Win+Shift+S (Snipping Tool) → OCR → clipboard text
macOS:   ⌘⇧4 / ⌘⌃⇧4 (Screenshot) → OCR → clipboard text

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import sys
import threading
import tkinter as tk
from pathlib import Path

# Ensure project root is on sys.path when run as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paths import logo_ico, logo_png
from app.platform_util import (
    IS_MACOS,
    IS_WINDOWS,
    PLATFORM_NAME,
    log_dir,
    snip_hotkey_hint,
    snip_tool_name,
)
from app.result_ui import ResultPopup
from app.service import SnipOCRService
from app.tray import TrayApp

LOG_DIR = log_dir()
LOG_FILE = LOG_DIR / "snipocr.log"


def _apply_root_icon(root: tk.Tk) -> None:
    png = logo_png(32)
    if IS_WINDOWS:
        ico = logo_ico()
        try:
            if ico.exists():
                root.iconbitmap(default=str(ico))
        except Exception:
            pass
    try:
        if png.exists():
            from PIL import Image, ImageTk

            root._snipocr_icon = ImageTk.PhotoImage(Image.open(png))  # type: ignore[attr-defined]
            root.iconphoto(True, root._snipocr_icon)  # type: ignore[attr-defined]
    except Exception:
        pass


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    setup_logging()
    log = logging.getLogger("snipocr")
    log.info("Starting SnipOCR on %s — log: %s", PLATFORM_NAME, LOG_FILE)

    if PLATFORM_NAME not in ("windows", "macos"):
        log.warning(
            "Unsupported platform %r — clipboard watching may be limited",
            PLATFORM_NAME,
        )

    # Hidden root for tk popups.
    # Windows: tk owns main thread.
    # macOS: AppKit/pystray owns main thread; tk runs on a secondary thread.
    root = tk.Tk()
    root.withdraw()
    root.title("SnipOCR")
    _apply_root_icon(root)

    service = SnipOCRService()
    settings = service.settings

    popup = ResultPopup(root, on_copy=service.copy_text)

    def on_result(result, image) -> None:
        if settings.show_popup:
            popup.show(
                result.text,
                image=image,
                engine_name=result.engine_name,
                duration_ms=result.duration_ms,
                language=result.language,
                autohide_seconds=settings.popup_autohide_seconds,
            )

    def on_processing(busy: bool) -> None:
        tray.set_processing(busy)

    def on_show_last() -> None:
        result, image = service.get_last()
        if result is None:
            tray.notify_balloon("SnipOCR", "No OCR result yet")
            return
        popup.show(
            result.text,
            image=image,
            engine_name=result.engine_name,
            duration_ms=result.duration_ms,
            language=result.language,
            autohide_seconds=0,
        )

    tray_holder: dict = {}

    def on_quit() -> None:
        log.info("Quit requested")
        service.stop()
        tray = tray_holder.get("tray")
        if tray:
            tray.stop()
        try:
            root.after(0, root.destroy)
        except Exception:
            pass

    tray = TrayApp(
        on_toggle_enabled=service.toggle_enabled,
        on_show_last=on_show_last,
        on_toggle_ocr_all=service.toggle_ocr_all,
        on_quit=on_quit,
        is_enabled=service.is_enabled,
        is_ocr_all=service.is_ocr_all,
    )
    tray_holder["tray"] = tray

    service.on_result = on_result
    service.on_processing = on_processing

    try:
        service.start()
        tray.start()
    except Exception:
        log.exception("Failed to start")
        return 1

    log.info(
        "Ready. Capture with %s (%s). OCR-all-images=%s. Languages: %s",
        snip_hotkey_hint(),
        snip_tool_name(),
        service.is_ocr_all(),
        service.engine.available_languages(),
    )

    if IS_MACOS:
        # pystray/AppKit must own the main thread on macOS.
        tk_thread = threading.Thread(
            target=root.mainloop,
            name="SnipOCRTk",
            daemon=True,
        )
        tk_thread.start()
        try:
            tray.run_main_thread()
        finally:
            service.stop()
            try:
                root.after(0, root.destroy)
            except Exception:
                pass
        return 0

    # Windows (and other): tk mainloop on main thread
    try:
        root.mainloop()
    finally:
        service.stop()
        tray.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
