"""Core orchestration: clipboard/screenshot image → OCR → clipboard text + UI."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from pathlib import Path
from typing import Optional

from PIL import Image

from . import clipboard_io
from .clipboard_watcher import ClipboardWatcher
from .notifications import notify
from .ocr import (
    create_engine_from_settings,
    engine_display_name,
    normalize_engine_name,
)
from .ocr.base import OCRResult
from .ocr.rapid_ocr import MODEL_PRESETS
from .platform_util import PLATFORM_NAME, snip_hotkey_hint
from .screenshot_watcher import ScreenshotFolderWatcher
from .settings import Settings, load_settings, save_settings
from .snip_detector import SnipDetector

logger = logging.getLogger(__name__)


class SnipOCRService:
    def __init__(self) -> None:
        self.settings: Settings = load_settings()
        self.detector = SnipDetector(
            window_seconds=self.settings.snip_process_window_seconds
        )
        self.engine = create_engine_from_settings(self.settings)
        self.watcher = ClipboardWatcher(on_update=self._on_clipboard_update)
        self.folder_watcher: Optional[ScreenshotFolderWatcher] = None
        self._lock = threading.Lock()
        self._engine_lock = threading.Lock()
        self._last_result: Optional[OCRResult] = None
        self._last_image: Optional[Image.Image] = None
        self._last_seq = 0
        self._recent_hashes: dict[str, float] = {}
        self._process_poller_stop = threading.Event()
        self._process_poller: Optional[threading.Thread] = None

        # UI hooks set by main
        self.on_result = None  # Callable[[OCRResult, Image.Image], None]
        self.on_status = None  # Callable[[str], None]
        self.on_processing = None  # Callable[[bool], None]

    def start(self) -> None:
        if not self.engine.ready():
            msg = self.engine.init_error() or "OCR engine unavailable"
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

        if self.settings.watch_screenshot_folders:
            self.folder_watcher = ScreenshotFolderWatcher(
                on_image=self._on_screenshot_file
            )
            self.folder_watcher.start()

        logger.info(
            "SnipOCR service started (platform=%s enabled=%s engine=%s hotkey=%s)",
            PLATFORM_NAME,
            self.settings.enabled,
            getattr(self.engine, "name", self.settings.ocr_engine),
            snip_hotkey_hint(),
        )

    def stop(self) -> None:
        self._process_poller_stop.set()
        self.watcher.stop()
        if self.folder_watcher:
            self.folder_watcher.stop()
            self.folder_watcher = None
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

    def get_ocr_engine(self) -> str:
        return normalize_engine_name(self.settings.ocr_engine)

    def get_ocr_engine_label(self) -> str:
        return engine_display_name(self.get_ocr_engine())

    def set_ocr_engine(self, engine_name: str) -> str:
        """Switch OCR backend and rebuild the engine. Returns canonical id."""
        name = normalize_engine_name(engine_name)
        self.settings.ocr_engine = name
        save_settings(self.settings)
        self._reload_engine(notify_user=True)
        return name

    def get_rapidocr_model_type(self) -> str:
        mt = (self.settings.rapidocr_model_type or "auto").strip().lower()
        return mt if mt in MODEL_PRESETS else "auto"

    def set_rapidocr_model_type(self, model_type: str) -> str:
        mt = (model_type or "auto").strip().lower()
        if mt not in MODEL_PRESETS:
            mt = "auto"
        self.settings.rapidocr_model_type = mt
        save_settings(self.settings)
        if self.get_ocr_engine() == "rapid":
            self._reload_engine(notify_user=True)
        else:
            notify(
                "SnipOCR",
                f"RapidOCR model set to {mt} (switch engine to RapidOCR to use)",
                enabled=self.settings.show_toast,
            )
        return mt

    def get_rapidocr_accel(self) -> str:
        a = (self.settings.rapidocr_accel or "auto").strip().lower()
        return a if a else "auto"

    def set_rapidocr_accel(self, accel: str) -> str:
        a = (accel or "auto").strip().lower()
        if a not in ("auto", "cpu", "dml", "coreml", "cuda"):
            a = "auto"
        self.settings.rapidocr_accel = a
        save_settings(self.settings)
        if self.get_ocr_engine() == "rapid":
            self._reload_engine(notify_user=True)
        else:
            notify(
                "SnipOCR",
                f"RapidOCR accel set to {a}",
                enabled=self.settings.show_toast,
            )
        return a

    def _reload_engine(self, *, notify_user: bool = False) -> None:
        with self._engine_lock:
            self.engine = create_engine_from_settings(self.settings)
            label = engine_display_name(self.get_ocr_engine())
            ready = getattr(self.engine, "ready", lambda: True)()
            if not ready:
                err = getattr(self.engine, "init_error", lambda: None)() or "not ready"
                logger.error("OCR engine reload failed: %s", err)
                if notify_user:
                    notify("SnipOCR", f"{label}: {err}", enabled=True)
                return
            detail = ""
            resolved = getattr(self.engine, "resolved_config", None)
            if callable(resolved):
                cfg = resolved()
                if cfg:
                    detail = (
                        f" [{cfg.get('rec_model', '')}/"
                        f"{cfg.get('rec_version', '')} {cfg.get('lang_rec', '')}]"
                    )
            logger.info(
                "OCR engine ready: %s (%s)%s",
                getattr(self.engine, "name", label),
                self.get_ocr_engine(),
                detail,
            )
            if notify_user:
                notify(
                    "SnipOCR",
                    f"OCR engine: {label}{detail}",
                    enabled=self.settings.show_toast,
                )

    def get_last(self) -> tuple[Optional[OCRResult], Optional[Image.Image]]:
        return self._last_result, self._last_image

    def copy_text(self, text: str) -> None:
        self.watcher.suppress(seconds=0.8, text=text)
        clipboard_io.set_clipboard_text(text)

    def _image_fingerprint(self, image: Image.Image) -> str:
        # Small fingerprint to de-dupe clipboard + file double delivery
        thumb = image.copy()
        thumb.thumbnail((64, 64))
        raw = thumb.tobytes()
        return hashlib.sha1(raw).hexdigest()

    def _seen_recently(self, fingerprint: str, window: float = 2.5) -> bool:
        now = time.monotonic()
        # prune
        self._recent_hashes = {
            k: t for k, t in self._recent_hashes.items() if now - t < 30.0
        }
        prev = self._recent_hashes.get(fingerprint)
        if prev is not None and (now - prev) < window:
            return True
        self._recent_hashes[fingerprint] = now
        return False

    def _on_clipboard_update(self) -> None:
        if not self.settings.enabled:
            return
        if self.watcher.is_suppressed():
            return

        if not clipboard_io.clipboard_has_image():
            return

        try:
            seq = clipboard_io.get_clipboard_sequence_number()
            if seq == self._last_seq:
                return
            self._last_seq = seq
        except Exception:
            pass

        # Capture tools sometimes fire before image data is fully available.
        time.sleep(0.05)

        if not self._lock.acquire(blocking=False):
            logger.debug("OCR already in progress — skip clipboard")
            return

        thread = threading.Thread(
            target=self._process_image_job,
            kwargs={
                "source": "clipboard",
                "from_screenshot_file": False,
                "filename": "",
            },
            name="SnipOCRWorker",
            daemon=True,
        )
        thread.start()

    def _on_screenshot_file(self, path: Path, image: Image.Image) -> None:
        if not self.settings.enabled:
            return
        if not self._lock.acquire(blocking=False):
            logger.debug("OCR already in progress — skip file %s", path.name)
            return

        thread = threading.Thread(
            target=self._process_image_job,
            kwargs={
                "source": "file",
                "image": image,
                "from_screenshot_file": True,
                "filename": path.name,
            },
            name="SnipOCRFileWorker",
            daemon=True,
        )
        thread.start()

    def _process_image_job(
        self,
        *,
        source: str,
        image: Optional[Image.Image] = None,
        from_screenshot_file: bool = False,
        filename: str = "",
    ) -> None:
        try:
            if self.on_processing:
                self.on_processing(True)

            if image is None:
                image = clipboard_io.get_clipboard_image()
            if image is None:
                logger.debug("No image readable from %s", source)
                return

            fp = self._image_fingerprint(image)
            if self._seen_recently(fp):
                logger.debug("Skipping duplicate image (fingerprint match)")
                return

            w, h = image.size
            should, reason = self.detector.should_ocr(
                ocr_all_images=self.settings.ocr_all_clipboard_images,
                image_width=w,
                image_height=h,
                min_width=self.settings.min_image_width,
                min_height=self.settings.min_image_height,
                from_screenshot_file=from_screenshot_file,
                filename=filename,
            )
            logger.info(
                "OCR gate: %s (%s) source=%s image=%sx%s",
                should,
                reason,
                source,
                w,
                h,
            )
            if not should:
                return

            with self._engine_lock:
                engine = self.engine
            if not engine.ready():
                notify(
                    "SnipOCR",
                    engine.init_error() or "OCR engine not ready",
                    enabled=self.settings.show_toast,
                )
                return

            result = engine.recognize(image)
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
            logger.exception("Failed to process image from %s", source)
            notify("SnipOCR", "OCR failed — see log", enabled=self.settings.show_toast)
        finally:
            if self.on_processing:
                self.on_processing(False)
            self._lock.release()
