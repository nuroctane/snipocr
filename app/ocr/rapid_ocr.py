"""RapidOCR + ONNX Runtime backend — light, fast, cross-platform local OCR.

Works on Windows, macOS, and Linux. Models run fully offline after the first
download into the rapidocr package models directory (or a custom model_root_dir).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

import numpy as np
from PIL import Image

from .base import OCRResult

logger = logging.getLogger(__name__)

MAX_SIDE = 2000

# User-facing model size presets → RapidOCR ModelType values.
# "auto" resolves to the fastest valid combo for the selected language.
MODEL_PRESETS = ("auto", "small", "mobile", "server", "tiny")

# User-facing OCR version presets.
VERSION_PRESETS = ("auto", "PP-OCRv6", "PP-OCRv5", "PP-OCRv4")

# Acceleration: try platform EP when available, else CPU.
ACCEL_PRESETS = ("auto", "cpu", "dml", "coreml", "cuda")

# BCP-47 / common tags → RapidOCR LangRec value (string).
# See rapidocr.utils.typings.LangRec
_LANG_REC: dict[str, str] = {
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "en-au": "en",
    "zh": "ch",
    "zh-cn": "ch",
    "zh-hans": "ch",
    "zh-sg": "ch",
    "zh-tw": "chinese_cht",
    "zh-hk": "chinese_cht",
    "zh-mo": "chinese_cht",
    "zh-hant": "chinese_cht",
    "ja": "japan",
    "ja-jp": "japan",
    "ko": "korean",
    "ko-kr": "korean",
    "ar": "arabic",
    "fa": "arabic",
    "ur": "arabic",
    "ru": "cyrillic",
    "uk": "cyrillic",
    "bg": "cyrillic",
    "sr": "cyrillic",
    "mk": "cyrillic",
    "be": "cyrillic",
    "hi": "devanagari",
    "mr": "devanagari",
    "ne": "devanagari",
    "th": "th",
    "el": "el",
    "ta": "ta",
    "te": "te",
    "ka": "ka",
    # Latin-script European languages → latin rec model
    "de": "latin",
    "fr": "latin",
    "es": "latin",
    "it": "latin",
    "pt": "latin",
    "nl": "latin",
    "pl": "latin",
    "cs": "latin",
    "sk": "latin",
    "ro": "latin",
    "hu": "latin",
    "fi": "latin",
    "sv": "latin",
    "da": "latin",
    "nb": "latin",
    "nn": "latin",
    "no": "latin",
    "tr": "latin",
    "vi": "latin",
    "id": "latin",
    "ms": "latin",
    "tl": "latin",
    "fil": "latin",
    "hr": "latin",
    "sl": "latin",
    "lt": "latin",
    "lv": "latin",
    "et": "latin",
    "af": "latin",
    "ca": "latin",
    "eu": "latin",
    "gl": "latin",
    "is": "latin",
    "ga": "latin",
    "mt": "latin",
    "sq": "latin",
    "sw": "latin",
    "cy": "latin",
    # Special aliases
    "ch": "ch",
    "chinese": "ch",
    "chinese_cht": "chinese_cht",
    "japan": "japan",
    "korean": "korean",
    "arabic": "arabic",
    "cyrillic": "cyrillic",
    "devanagari": "devanagari",
    "latin": "latin",
    "multi": "ch",
    "auto": "ch",
}

# LangRec → LangDet (only ch / en / multi exist for detection).
_REC_TO_DET: dict[str, str] = {
    "en": "en",
    "ch": "ch",
    "ch_doc": "ch",
    "chinese_cht": "ch",
    "japan": "multi",
    "korean": "multi",
    "arabic": "multi",
    "cyrillic": "multi",
    "devanagari": "multi",
    "latin": "multi",
    "th": "multi",
    "el": "multi",
    "ta": "multi",
    "te": "multi",
    "ka": "multi",
    "eslav": "multi",
}


def normalize_lang_rec(language: str) -> str:
    """Map a user language tag to a RapidOCR LangRec string."""
    raw = (language or "en-US").strip().lower().replace("_", "-")
    if raw in _LANG_REC:
        return _LANG_REC[raw]
    short = raw.split("-", 1)[0]
    return _LANG_REC.get(short, "ch")


def normalize_lang_det(lang_rec: str) -> str:
    return _REC_TO_DET.get(lang_rec, "ch")


def _downscale(image: Image.Image) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if longest <= MAX_SIDE:
        return image
    scale = MAX_SIDE / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _assemble_text(boxes: Any, txts: Any) -> str:
    """Join detected lines top-to-bottom, left-to-right (screenshot-friendly)."""
    if not txts:
        return ""
    texts = [str(t).strip() for t in txts if t and str(t).strip()]
    if not texts:
        return ""
    if boxes is None:
        return "\n".join(texts)

    items: list[tuple[float, float, float, str]] = []
    for box, txt in zip(boxes, txts):
        if not txt or not str(txt).strip():
            continue
        try:
            pts = np.asarray(box, dtype=np.float64).reshape(-1, 2)
            ys = pts[:, 1]
            xs = pts[:, 0]
            y0 = float(ys.min())
            x0 = float(xs.min())
            height = float(max(ys.max() - ys.min(), 1.0))
            items.append((y0, x0, height, str(txt).strip()))
        except Exception:
            items.append((0.0, 0.0, 16.0, str(txt).strip()))

    if not items:
        return ""

    items.sort(key=lambda t: (t[0], t[1]))
    median_h = float(np.median([h for _, _, h, _ in items])) if items else 16.0
    line_thresh = max(10.0, median_h * 0.6)

    lines: list[list[tuple[float, str]]] = []
    current_y: Optional[float] = None
    current: list[tuple[float, str]] = []

    for y0, x0, _h, txt in items:
        if current_y is None or abs(y0 - current_y) <= line_thresh:
            if current_y is None:
                current_y = y0
            else:
                # keep a running average y for the line cluster
                current_y = (current_y + y0) / 2.0
            current.append((x0, txt))
        else:
            current.sort(key=lambda p: p[0])
            lines.append(current)
            current = [(x0, txt)]
            current_y = y0
    if current:
        current.sort(key=lambda p: p[0])
        lines.append(current)

    return "\n".join(" ".join(t for _, t in line) for line in lines).strip()


def _resolve_model_plan(
    *,
    lang_rec: str,
    model_type: str,
    ocr_version: str,
) -> tuple[str, str, str, str]:
    """
    Return (det_model, rec_model, det_version, rec_version) as string values.

    RapidOCR only ships certain (lang, model_type, version) combos. Prefer
    light models that actually exist for the requested language.
    """
    mt = (model_type or "auto").strip().lower()
    ver = (ocr_version or "auto").strip()
    if ver.lower() == "auto":
        ver = "auto"
    # Normalize version casing
    ver_map = {
        "auto": "auto",
        "pp-ocrv6": "PP-OCRv6",
        "ppocrv6": "PP-OCRv6",
        "v6": "PP-OCRv6",
        "pp-ocrv5": "PP-OCRv5",
        "ppocrv5": "PP-OCRv5",
        "v5": "PP-OCRv5",
        "pp-ocrv4": "PP-OCRv4",
        "ppocrv4": "PP-OCRv4",
        "v4": "PP-OCRv4",
    }
    ver = ver_map.get(ver.lower(), ver)

    # PP-OCRv6 small is the default fast path for Chinese/multilingual (incl. English).
    if mt in ("auto", "small"):
        if lang_rec in ("ch", "ch_doc") or ver in ("auto", "PP-OCRv6"):
            # English-only: en models are mobile/v4; ch small v6 also reads English well.
            if lang_rec == "en" and mt == "auto":
                # Prefer lighter dedicated English mobile models
                return "mobile", "mobile", "PP-OCRv4", "PP-OCRv4"
            if lang_rec == "en" and mt == "small":
                # No en+small combo → fall back to mobile v4
                return "mobile", "mobile", "PP-OCRv4", "PP-OCRv4"
            if lang_rec not in ("ch", "ch_doc") and mt == "small" and ver == "PP-OCRv6":
                # Non-Chinese langs rarely have v6 small; use mobile v4/v5 when possible
                return "mobile", "mobile", "PP-OCRv4", "PP-OCRv4"
            return "small", "small", "PP-OCRv6", "PP-OCRv6"
        if ver == "PP-OCRv5":
            return "mobile", "mobile", "PP-OCRv5", "PP-OCRv5"
        return "mobile", "mobile", "PP-OCRv4", "PP-OCRv4"

    if mt == "tiny":
        # Tiny only exists for limited combos; try and fall back in init if needed.
        if ver in ("auto", "PP-OCRv6"):
            return "tiny", "tiny", "PP-OCRv6", "PP-OCRv6"
        return "tiny", "tiny", ver if ver != "auto" else "PP-OCRv5", ver if ver != "auto" else "PP-OCRv5"

    if mt == "server":
        if ver in ("auto", "PP-OCRv6"):
            # server often on v4/v5; try v4 for broader availability
            return "server", "server", "PP-OCRv4", "PP-OCRv4"
        return "server", "server", ver, ver

    # mobile
    if ver in ("auto", "PP-OCRv6"):
        # mobile + v6 not always listed; prefer v4 mobile which is widely available
        if lang_rec in ("ch", "ch_doc"):
            return "mobile", "mobile", "PP-OCRv4", "PP-OCRv4"
        return "mobile", "mobile", "PP-OCRv4", "PP-OCRv4"
    return "mobile", "mobile", ver, ver


def _accel_params(accel: str) -> dict[str, Any]:
    """Build EngineConfig.onnxruntime.* params for the chosen accelerator."""
    a = (accel or "auto").strip().lower()
    params: dict[str, Any] = {
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_dml": False,
        "EngineConfig.onnxruntime.use_coreml": False,
        "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
    }
    if a in ("cpu", "none", "false", "0"):
        return params

    if a == "cuda":
        params["EngineConfig.onnxruntime.use_cuda"] = True
        return params
    if a == "dml":
        params["EngineConfig.onnxruntime.use_dml"] = True
        return params
    if a == "coreml":
        params["EngineConfig.onnxruntime.use_coreml"] = True
        return params

    # auto: enable platform-native EP when the ORT build exposes it.
    # ProviderConfig still checks availability and falls back to CPU.
    try:
        import sys

        import onnxruntime as ort

        providers = set(ort.get_available_providers())
        if sys.platform == "darwin" and "CoreMLExecutionProvider" in providers:
            params["EngineConfig.onnxruntime.use_coreml"] = True
        elif sys.platform == "win32" and "DmlExecutionProvider" in providers:
            params["EngineConfig.onnxruntime.use_dml"] = True
        elif "CUDAExecutionProvider" in providers:
            params["EngineConfig.onnxruntime.use_cuda"] = True
    except Exception:
        pass
    return params


def _build_params(
    *,
    lang_rec: str,
    lang_det: str,
    model_type: str,
    ocr_version: str,
    use_cls: bool,
    text_score: float,
    accel: str,
    intra_op_threads: int,
    inter_op_threads: int,
    max_side_len: int,
) -> dict[str, Any]:
    from rapidocr import EngineType, ModelType, OCRVersion

    det_mt, rec_mt, det_ver, rec_ver = _resolve_model_plan(
        lang_rec=lang_rec,
        model_type=model_type,
        ocr_version=ocr_version,
    )

    def _model(s: str) -> Any:
        return ModelType(s)

    def _ver(s: str) -> Any:
        return OCRVersion(s)

    # Lang enums — use string values RapidOCR accepts via OmegaConf
    from rapidocr import LangDet, LangRec

    try:
        det_lang = LangDet(lang_det)
    except Exception:
        det_lang = LangDet.CH
    try:
        rec_lang = LangRec(lang_rec)
    except Exception:
        rec_lang = LangRec.CH

    params: dict[str, Any] = {
        "Global.log_level": "error",
        "Global.text_score": float(text_score),
        "Global.use_det": True,
        "Global.use_cls": bool(use_cls),
        "Global.use_rec": True,
        "Global.max_side_len": int(max_side_len),
        "Global.return_word_box": False,
        "Det.engine_type": EngineType.ONNXRUNTIME,
        "Cls.engine_type": EngineType.ONNXRUNTIME,
        "Rec.engine_type": EngineType.ONNXRUNTIME,
        "Det.lang_type": det_lang,
        "Rec.lang_type": rec_lang,
        "Det.model_type": _model(det_mt),
        "Rec.model_type": _model(rec_mt),
        "Cls.model_type": ModelType.MOBILE,
        "Det.ocr_version": _ver(det_ver),
        "Rec.ocr_version": _ver(rec_ver),
        "Cls.ocr_version": OCRVersion.PPOCRV4,
        "EngineConfig.onnxruntime.intra_op_num_threads": int(intra_op_threads),
        "EngineConfig.onnxruntime.inter_op_num_threads": int(inter_op_threads),
    }
    params.update(_accel_params(accel))
    return params


class RapidOCREngine:
    """Cross-platform RapidOCR engine backed by ONNX Runtime."""

    name = "RapidOCR (ONNX)"

    def __init__(
        self,
        language: str = "en-US",
        *,
        model_type: str = "auto",
        ocr_version: str = "auto",
        use_cls: bool = True,
        text_score: float = 0.5,
        accel: str = "auto",
        intra_op_threads: int = -1,
        inter_op_threads: int = -1,
        max_side_len: int = MAX_SIDE,
    ) -> None:
        self.language = language or "en-US"
        self.model_type = (model_type or "auto").strip().lower()
        self.ocr_version = ocr_version or "auto"
        self.use_cls = bool(use_cls)
        self.text_score = float(text_score)
        self.accel = (accel or "auto").strip().lower()
        self.intra_op_threads = int(intra_op_threads)
        self.inter_op_threads = int(inter_op_threads)
        self.max_side_len = int(max_side_len)

        self._engine: Any = None
        self._init_error: Optional[str] = None
        self._lang_rec = normalize_lang_rec(self.language)
        self._lang_det = normalize_lang_det(self._lang_rec)
        self._resolved: dict[str, str] = {}
        self._lock = threading.Lock()
        self._create_engine()

    def _create_engine(self) -> None:
        try:
            from rapidocr import RapidOCR  # noqa: F401
        except ImportError as exc:
            self._init_error = (
                "RapidOCR is not installed. Install with: "
                "pip install rapidocr onnxruntime"
            )
            logger.error("%s (%s)", self._init_error, exc)
            return

        try:
            import onnxruntime  # noqa: F401
        except ImportError as exc:
            self._init_error = (
                "onnxruntime is not installed. Install with: pip install onnxruntime"
            )
            logger.error("%s (%s)", self._init_error, exc)
            return

        # Try preferred plan, then safe fallbacks.
        attempts: list[tuple[str, str, str]] = [
            (self.model_type, self.ocr_version, self._lang_rec),
            ("mobile", "PP-OCRv4", self._lang_rec),
            ("small", "PP-OCRv6", "ch"),
            ("mobile", "PP-OCRv4", "ch"),
        ]
        # Deduplicate while preserving order
        seen: set[tuple[str, str, str]] = set()
        unique_attempts: list[tuple[str, str, str]] = []
        for a in attempts:
            if a not in seen:
                seen.add(a)
                unique_attempts.append(a)

        last_error: Optional[Exception] = None
        for mt, ver, lang_rec in unique_attempts:
            lang_det = normalize_lang_det(lang_rec)
            try:
                params = _build_params(
                    lang_rec=lang_rec,
                    lang_det=lang_det,
                    model_type=mt,
                    ocr_version=ver,
                    use_cls=self.use_cls,
                    text_score=self.text_score,
                    accel=self.accel,
                    intra_op_threads=self.intra_op_threads,
                    inter_op_threads=self.inter_op_threads,
                    max_side_len=self.max_side_len,
                )
                from rapidocr import RapidOCR

                engine = RapidOCR(params=params)
                det_mt, rec_mt, det_ver, rec_ver = _resolve_model_plan(
                    lang_rec=lang_rec, model_type=mt, ocr_version=ver
                )
                self._engine = engine
                self._lang_rec = lang_rec
                self._lang_det = lang_det
                self._resolved = {
                    "lang_rec": lang_rec,
                    "lang_det": lang_det,
                    "det_model": det_mt,
                    "rec_model": rec_mt,
                    "det_version": det_ver,
                    "rec_version": rec_ver,
                    "accel": self.accel,
                }
                # Surface a friendly language tag
                self.language = lang_rec
                logger.info(
                    "RapidOCR ready (lang_rec=%s det=%s/%s rec=%s/%s accel=%s)",
                    lang_rec,
                    det_mt,
                    det_ver,
                    rec_mt,
                    rec_ver,
                    self.accel,
                )
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "RapidOCR init attempt failed (model=%s ver=%s lang=%s): %s",
                    mt,
                    ver,
                    lang_rec,
                    exc,
                )

        self._init_error = (
            f"Failed to init RapidOCR: {last_error}. "
            "Try: pip install -U rapidocr onnxruntime"
        )
        logger.error(self._init_error)

    def available_languages(self) -> list[str]:
        """Languages we can map to RapidOCR rec models."""
        # Unique short tags for UI / logging
        tags = sorted(
            {
                "en-US",
                "zh-CN",
                "zh-TW",
                "ja-JP",
                "ko-KR",
                "ar",
                "ru",
                "hi",
                "th",
                "el",
                "de",
                "fr",
                "es",
                "pt",
                "it",
                "vi",
                "latin",
                "multi",
            }
        )
        return tags

    def ready(self) -> bool:
        return self._engine is not None

    def init_error(self) -> Optional[str]:
        return self._init_error

    def resolved_config(self) -> dict[str, str]:
        return dict(self._resolved)

    def recognize(self, image: Image.Image) -> OCRResult:
        if self._engine is None:
            raise RuntimeError(self._init_error or "RapidOCR not available")

        started = time.perf_counter()
        with self._lock:
            text = self._recognize_sync(image)
        duration_ms = (time.perf_counter() - started) * 1000.0
        return OCRResult(
            text=text,
            engine_name=self.name,
            duration_ms=duration_ms,
            language=self.language,
        )

    def _recognize_sync(self, image: Image.Image) -> str:
        image = _downscale(image.convert("RGB"))
        # RapidOCR / OpenCV expect RGB or BGR numpy; RapidOCR load_img handles RGB arrays.
        arr = np.asarray(image)

        try:
            result = self._engine(arr, use_det=True, use_cls=self.use_cls, use_rec=True)
        except TypeError:
            # Older call signature
            result = self._engine(arr)

        if result is None:
            return ""

        # rapidocr>=3 returns RapidOCROutput dataclass
        txts = getattr(result, "txts", None)
        boxes = getattr(result, "boxes", None)

        if txts is not None:
            return _assemble_text(boxes, txts)

        # rapidocr-onnxruntime 1.x style: (list of [box, (text, score)], elapse)
        if isinstance(result, tuple) and len(result) >= 1:
            payload = result[0]
            if not payload:
                return ""
            lines_boxes = []
            lines_txts = []
            for item in payload:
                try:
                    box, rec = item[0], item[1]
                    text = rec[0] if isinstance(rec, (list, tuple)) else str(rec)
                    lines_boxes.append(box)
                    lines_txts.append(text)
                except Exception:
                    continue
            return _assemble_text(lines_boxes, lines_txts)

        return str(result).strip()
