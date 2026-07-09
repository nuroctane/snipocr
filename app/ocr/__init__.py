"""OCR engines and factory."""

from __future__ import annotations

import logging
from typing import Any

from ..platform_util import IS_MACOS, IS_WINDOWS, default_ocr_engine
from .base import OCREngine, OCRResult

logger = logging.getLogger(__name__)

__all__ = ["OCREngine", "OCRResult", "create_engine"]


def create_engine(engine_name: str = "auto", language: str = "en-US") -> Any:
    """
    Create the platform-appropriate OCR engine.

    engine_name: "auto" | "windows" | "macos" | aliases
    """
    name = (engine_name or "auto").strip().lower()
    if name in ("auto", "default", ""):
        name = default_ocr_engine()

    if name in ("windows", "windows_ocr", "win"):
        if not IS_WINDOWS:
            logger.warning("Windows OCR requested on non-Windows — attempting import anyway")
        from .windows_ocr import WindowsOCREngine

        return WindowsOCREngine(language=language)

    if name in ("macos", "mac", "vision", "apple"):
        if not IS_MACOS:
            logger.warning("macOS Vision OCR requested on non-macOS — attempting import anyway")
        from .macos_ocr import MacOSOCREngine

        return MacOSOCREngine(language=language)

    # Unknown: fall back to platform default
    fallback = default_ocr_engine()
    logger.warning("Unknown OCR engine %r — using %s", engine_name, fallback)
    return create_engine(fallback, language=language)
