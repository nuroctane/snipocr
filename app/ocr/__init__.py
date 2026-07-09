"""OCR engines and factory."""

from __future__ import annotations

import logging
from typing import Any

from ..platform_util import IS_MACOS, IS_WINDOWS, default_ocr_engine
from .base import OCREngine, OCRResult

logger = logging.getLogger(__name__)

__all__ = [
    "OCREngine",
    "OCRResult",
    "create_engine",
    "create_engine_from_settings",
    "engine_choices",
    "normalize_engine_name",
    "engine_display_name",
]


def engine_choices() -> list[tuple[str, str]]:
    """
    Return (id, label) pairs for the tray / docs.

    OS engines are only listed on their platform; RapidOCR is always listed.
    """
    choices: list[tuple[str, str]] = [("auto", "OS default (auto)")]
    if IS_WINDOWS:
        choices.append(("windows", "Windows OCR"))
    if IS_MACOS:
        choices.append(("macos", "macOS Vision"))
    choices.append(("rapid", "RapidOCR (ONNX)"))
    return choices


def engine_display_name(engine_id: str) -> str:
    for eid, label in engine_choices():
        if eid == engine_id:
            return label
    return engine_id or "auto"


def normalize_engine_name(engine_name: str) -> str:
    """Map aliases to canonical engine ids: auto | windows | macos | rapid."""
    name = (engine_name or "auto").strip().lower()
    if name in ("auto", "default", ""):
        return "auto"
    if name in ("windows", "windows_ocr", "win", "winrt"):
        return "windows"
    if name in ("macos", "mac", "vision", "apple", "apple_vision"):
        return "macos"
    if name in (
        "rapid",
        "rapidocr",
        "onnx",
        "onnxruntime",
        "ai",
        "local_ai",
        "neural",
    ):
        return "rapid"
    return name


def create_engine(
    engine_name: str = "auto",
    language: str = "en-US",
    *,
    rapidocr_model_type: str = "auto",
    rapidocr_ocr_version: str = "auto",
    rapidocr_use_cls: bool = True,
    rapidocr_text_score: float = 0.5,
    rapidocr_accel: str = "auto",
    rapidocr_intra_op_threads: int = -1,
    rapidocr_inter_op_threads: int = -1,
) -> Any:
    """
    Create an OCR engine.

    engine_name: "auto" | "windows" | "macos" | "rapid" (and aliases)
    """
    name = normalize_engine_name(engine_name)
    if name == "auto":
        name = default_ocr_engine()
        # On unsupported platforms, prefer RapidOCR over a missing OS engine.
        if name == "auto":
            name = "rapid"

    if name == "windows":
        if not IS_WINDOWS:
            logger.warning("Windows OCR requested on non-Windows — attempting import anyway")
        from .windows_ocr import WindowsOCREngine

        return WindowsOCREngine(language=language)

    if name == "macos":
        if not IS_MACOS:
            logger.warning("macOS Vision OCR requested on non-macOS — attempting import anyway")
        from .macos_ocr import MacOSOCREngine

        return MacOSOCREngine(language=language)

    if name == "rapid":
        from .rapid_ocr import RapidOCREngine

        return RapidOCREngine(
            language=language,
            model_type=rapidocr_model_type,
            ocr_version=rapidocr_ocr_version,
            use_cls=rapidocr_use_cls,
            text_score=rapidocr_text_score,
            accel=rapidocr_accel,
            intra_op_threads=rapidocr_intra_op_threads,
            inter_op_threads=rapidocr_inter_op_threads,
        )

    # Unknown: fall back to platform default, then rapid
    fallback = default_ocr_engine()
    if fallback == "auto":
        fallback = "rapid"
    logger.warning("Unknown OCR engine %r — using %s", engine_name, fallback)
    return create_engine(
        fallback,
        language=language,
        rapidocr_model_type=rapidocr_model_type,
        rapidocr_ocr_version=rapidocr_ocr_version,
        rapidocr_use_cls=rapidocr_use_cls,
        rapidocr_text_score=rapidocr_text_score,
        rapidocr_accel=rapidocr_accel,
        rapidocr_intra_op_threads=rapidocr_intra_op_threads,
        rapidocr_inter_op_threads=rapidocr_inter_op_threads,
    )


def create_engine_from_settings(settings: Any) -> Any:
    """Convenience: build engine from a Settings dataclass / object."""
    return create_engine(
        getattr(settings, "ocr_engine", "auto"),
        language=getattr(settings, "ocr_language", "en-US"),
        rapidocr_model_type=getattr(settings, "rapidocr_model_type", "auto"),
        rapidocr_ocr_version=getattr(settings, "rapidocr_ocr_version", "auto"),
        rapidocr_use_cls=getattr(settings, "rapidocr_use_cls", True),
        rapidocr_text_score=getattr(settings, "rapidocr_text_score", 0.5),
        rapidocr_accel=getattr(settings, "rapidocr_accel", "auto"),
        rapidocr_intra_op_threads=getattr(settings, "rapidocr_intra_op_threads", -1),
        rapidocr_inter_op_threads=getattr(settings, "rapidocr_inter_op_threads", -1),
    )
