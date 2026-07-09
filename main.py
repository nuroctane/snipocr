"""
SnipOCR — automatic local OCR when you screenshot with Windows Snipping Tool.

Usage:
    python main.py
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from pathlib import Path

# Ensure project root is on sys.path when run as script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paths import logo_ico, logo_png
from app.result_ui import ResultPopup
from app.service import SnipOCRService
from app.tray import TrayApp

LOG_DIR = Path.home() / "AppData" / "Local" / "SnipOCR"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "snipocr.log"


def _apply_root_icon(root: tk.Tk) -> None:
    ico = logo_ico()
    png = logo_png(32)
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
    log.info("Starting SnipOCR — log: %s", LOG_FILE)

    # Hidden root for tk popups (must live on main thread).
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
            autohide_seconds=0,  # stay open when user asked
        )

    def on_quit() -> None:
        log.info("Quit requested")
        service.stop()
        tray.stop()
        root.after(0, root.destroy)

    tray = TrayApp(
        on_toggle_enabled=service.toggle_enabled,
        on_show_last=on_show_last,
        on_toggle_ocr_all=service.toggle_ocr_all,
        on_quit=on_quit,
        is_enabled=service.is_enabled,
        is_ocr_all=service.is_ocr_all,
    )

    service.on_result = on_result
    service.on_processing = on_processing

    try:
        service.start()
        tray.start()
    except Exception:
        log.exception("Failed to start")
        return 1

    log.info(
        "Ready. Snip with Win+Shift+S. OCR-all-images=%s. Languages: %s",
        service.is_ocr_all(),
        service.engine.available_languages(),
    )

    try:
        root.mainloop()
    finally:
        service.stop()
        tray.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
