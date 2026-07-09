"""Apple Vision framework OCR — fully local on macOS."""

from __future__ import annotations

import io
import logging
import time
from typing import Optional

from PIL import Image

from .base import OCRResult

logger = logging.getLogger(__name__)

MAX_SIDE = 2000


def _downscale(image: Image.Image) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if longest <= MAX_SIDE:
        return image
    scale = MAX_SIDE / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


class MacOSOCREngine:
    name = "macOS Vision OCR"

    def __init__(self, language: str = "en-US") -> None:
        self.language = language or "en-US"
        self._init_error: Optional[str] = None
        self._ok = False
        try:
            import Vision  # noqa: F401
            from Foundation import NSData  # noqa: F401
            from Quartz import (  # noqa: F401
                CGImageSourceCreateImageAtIndex,
                CGImageSourceCreateWithData,
            )

            self._ok = True
            logger.info("macOS Vision OCR ready (language=%s)", self.language)
        except Exception as exc:  # noqa: BLE001
            self._init_error = (
                f"Failed to init macOS Vision OCR: {exc}. "
                "Install: pip install pyobjc-framework-Vision pyobjc-framework-Quartz "
                "pyobjc-framework-Cocoa"
            )
            logger.error(self._init_error)

    def available_languages(self) -> list[str]:
        # Vision negotiates languages internally; report configured preference.
        return [self.language, "en-US", "en"]

    def ready(self) -> bool:
        return self._ok

    def init_error(self) -> Optional[str]:
        return self._init_error

    def recognize(self, image: Image.Image) -> OCRResult:
        if not self._ok:
            raise RuntimeError(self._init_error or "macOS Vision OCR not available")

        started = time.perf_counter()
        text = self._recognize_sync(image)
        duration_ms = (time.perf_counter() - started) * 1000.0
        return OCRResult(
            text=text,
            engine_name=self.name,
            duration_ms=duration_ms,
            language=self.language,
        )

    def _recognize_sync(self, image: Image.Image) -> str:
        import Vision
        from Foundation import NSData
        from Quartz import CGImageSourceCreateImageAtIndex, CGImageSourceCreateWithData

        image = _downscale(image.convert("RGB"))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        ns_data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
        source = CGImageSourceCreateWithData(ns_data, None)
        if source is None:
            raise RuntimeError("Could not create CGImageSource from PNG")
        cg_image = CGImageSourceCreateImageAtIndex(source, 0, None)
        if cg_image is None:
            raise RuntimeError("Could not create CGImage for OCR")

        request = Vision.VNRecognizeTextRequest.alloc().init()
        # Accurate is better for screenshots; still local and fast enough.
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        try:
            request.setUsesLanguageCorrection_(True)
        except Exception:
            pass

        # BCP-47 → Vision language codes (often just "en")
        lang = self.language or "en-US"
        short = lang.split("-")[0]
        try:
            request.setRecognitionLanguages_([lang, short, "en"])
        except Exception:
            try:
                request.setRecognitionLanguages_([short])
            except Exception:
                pass

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg_image, None
        )
        # PyObjC may return bool or (bool, error) depending on bridge version.
        outcome = handler.performRequests_error_([request], None)
        if isinstance(outcome, tuple):
            success, error = outcome[0], outcome[1] if len(outcome) > 1 else None
        else:
            success, error = bool(outcome), None
        if not success:
            msg = str(error) if error else "unknown Vision error"
            raise RuntimeError(f"Vision OCR failed: {msg}")

        observations = request.results() or []
        lines: list[str] = []
        for obs in observations:
            candidates = obs.topCandidates_(1)
            if not candidates:
                continue
            candidate = candidates[0]
            string = candidate.string() if hasattr(candidate, "string") else None
            if string is None and hasattr(candidate, "string_"):
                string = candidate.string_()
            if string:
                lines.append(str(string))

        return "\n".join(lines).strip()
