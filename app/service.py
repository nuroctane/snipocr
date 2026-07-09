"""Core orchestration: clipboard image → OCR → clipboard text + UI."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Optional

from PIL import Image

from . import clipboard_io
from .clipboard_watcher import ClipboardWatcher
from .notifications import notify
from .ocr import create_engine
from .ocr.base import OCRResult
from .settings import Settings, load_settings, save_settings
from .snip_detector import SnipDetector

logger = logging.getLogger(__name__)


class SnipOCRService:
    def __init__(self) -> None:
        self.settings: Settings = load_settings()
        self.detector = SnipDetector(
            window_seconds=self.settings.snip_process_window_seconds
        )
        self.engine = create_engine(
            self.settings.ocr_engine,
            language=self.settings.ocr_language,
        )
        self.watcher = ClipboardWatcher(on_update=self._on_clipboard_update)
        self._lock = threading.Lock()
        self._busy = False
        self._last_result: Optional[OCRResult] = None
        self._last_image: Optional[Image.Image] = None
        self._last_seq = 0
        self._process_poller_stop = threading.Event()
        self._process_poller: Optional[threading.Thread] = None

        # UI hooks set by main
        self.on_result = None  # Callable[[OCRResult, Image.Image], None]
        self.on_status = None  # Callable[[str], None]
        self.on_processing = None  # Callable[[bool], None]

    def start(self) -> None:
        if not self.engine.ready():
            msg = self.engine.init_error() or "Windows OCR unavailable"
            logger.error(msg)
            notify("SnipOCR", msg, enabled=True)

        self.watcher.start()
        self._process_poller_stop.clear()
        self._process_poller = threading.Thread(
            target=self._poll_snip_processes,
            name="SnipProcessPoller",
            daemon=True,
        )
        self._process_poller.start()
        logger.info("SnipOCR service started (enabled=%s)", self.settings.enabled)

    def stop(self) -> None:
        self._process_poller_stop.set()
        self.watcher.stop()
        logger.info("SnipOCR service stopped")

    def _poll_snip_processes(self) -> None:
        while not self._process_poller_stop.is_set():
            self.detector.poll_processes()
            self._process_poller_stop.wait(0.35)

    def is_enabled(self) -> bool:
        return self.settings.enabled

    def toggle_enabled(self) -> bool:
        self.settings.enabled = not self.settings.enabled
        save_settings(self.settings)
        state = "enabled" if self.settings.enabled else "disabled"
        notify("SnipOCR", f"SnipOCR {state}", enabled=self.settings.show_toast)
        return self.settings.enabled

    def is_ocr_all(self) -> bool:
        return self.settings.ocr_all_clipboard_images

    def toggle_ocr_all(self) -> bool:
        self.settings.ocr_all_clipboard_images = not self.settings.ocr_all_clipboard_images
        save_settings(self.settings)
        state = "ON" if self.settings.ocr_all_clipboard_images else "OFF"
        notify(
            "SnipOCR",
            f"OCR all clipboard images: {state}",
            enabled=self.settings.show_toast,
        )
        return self.settings.ocr_all_clipboard_images

    def get_last(self) -> tuple[Optional[OCRResult], Optional[Image.Image]]:
        return self._last_result, self._last_image

    def copy_text(self, text: str) -> None:
        self.watcher.suppress(seconds=0.8, text=text)
        clipboard_io.set_clipboard_text(text)

    def _on_clipboard_update(self) -> None:
        if not self.settings.enabled:
            return
        if self.watcher.is_suppressed():
            return

        # Avoid re-processing pure text pastes we (or the user) made.
        if not clipboard_io.clipboard_has_image():
            return

        try:
            seq = clipboard_io.get_clipboard_sequence_number()
            if seq == self._last_seq:
                return
            self._last_seq = seq
        except Exception:
            pass

        # Snipping Tool sometimes fires before image data is fully available.
        time.sleep(0.05)

        if not self._lock.acquire(blocking=False):
            logger.debug("OCR already in progress — skip")
            return

        thread = threading.Thread(
            target=self._process_clipboard_image,
            name="SnipOCRWorker",
            daemon=True,
        )
        thread.start()

    def _process_clipboard_image(self) -> None:
        try:
            if self.on_processing:
                self.on_processing(True)

            image = clipboard_io.get_clipboard_image()
            if image is None:
                logger.debug("No image readable from clipboard")
                return

            w, h = image.size
            should, reason = self.detector.should_ocr(
                ocr_all_images=self.settings.ocr_all_clipboard_images,
                image_width=w,
                image_height=h,
                min_width=self.settings.min_image_width,
                min_height=self.settings.min_image_height,
            )
            logger.info("OCR gate: %s (%s) image=%sx%s", should, reason, w, h)
            if not should:
                return

            if not self.engine.ready():
                notify(
                    "SnipOCR",
                    self.engine.init_error() or "OCR engine not ready",
                    enabled=self.settings.show_toast,
                )
                return

            result = self.engine.recognize(image)
            text = result.text
            if self.settings.collapse_single_newlines and text:
                text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
                result = OCRResult(
                    text=text,
                    engine_name=result.engine_name,
                    duration_ms=result.duration_ms,
                    language=result.language,
                )

            self._last_result = result
            self._last_image = image.copy()

            if not text.strip():
                notify(
                    "SnipOCR",
                    "No text detected — image left on clipboard",
                    enabled=self.settings.show_toast,
                )
                return

            if self.settings.replace_clipboard_with_text:
                self.watcher.suppress(seconds=0.8, text=text)
                clipboard_io.set_clipboard_text(text)
                logger.info(
                    "OCR ok (%s, %.0f ms): %d chars",
                    result.engine_name,
                    result.duration_ms,
                    len(text),
                )

            if self.on_result:
                self.on_result(result, image)

            notify(
                "SnipOCR",
                f"Text copied ({result.duration_ms:.0f} ms)",
                enabled=self.settings.show_toast,
            )
        except Exception:
            logger.exception("Failed to process clipboard image")
            notify("SnipOCR", "OCR failed — see log", enabled=self.settings.show_toast)
        finally:
            if self.on_processing:
                self.on_processing(False)
            self._lock.release()
