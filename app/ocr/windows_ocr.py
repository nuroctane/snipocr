"""Windows.Media.Ocr backend — fully local, uses OS language packs."""

from __future__ import annotations

import asyncio
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


class WindowsOCREngine:
    name = "Windows OCR"

    def __init__(self, language: str = "en-US") -> None:
        self.language = language
        self._engine = None
        self._init_error: Optional[str] = None
        self._create_engine()

    def _create_engine(self) -> None:
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.media.ocr import OcrEngine

            lang_tag = self.language or "en-US"
            language = Language(lang_tag)

            if OcrEngine.is_language_supported(language):
                self._engine = OcrEngine.try_create_from_language(language)
            else:
                logger.warning(
                    "Language %s not supported for OCR — trying user profile languages",
                    lang_tag,
                )
                self._engine = OcrEngine.try_create_from_user_profile_languages()

            if self._engine is None:
                available = self.available_languages()
                self._init_error = (
                    f"No Windows OCR engine for '{lang_tag}'. "
                    f"Installed: {available or '(none)'}. "
                    "Install a Language.OCR pack (see scripts/install_ocr_lang.ps1)."
                )
                logger.error(self._init_error)
            else:
                recognizer = self._engine.recognizer_language
                self.language = recognizer.language_tag if recognizer else lang_tag
                logger.info("Windows OCR ready (language=%s)", self.language)
        except Exception as exc:  # noqa: BLE001
            self._init_error = f"Failed to init Windows OCR: {exc}"
            logger.exception(self._init_error)

    def available_languages(self) -> list[str]:
        try:
            from winrt.windows.media.ocr import OcrEngine

            langs = OcrEngine.available_recognizer_languages
            return [lang.language_tag for lang in langs]
        except Exception:
            return []

    def ready(self) -> bool:
        return self._engine is not None

    def init_error(self) -> Optional[str]:
        return self._init_error

    def recognize(self, image: Image.Image) -> OCRResult:
        if self._engine is None:
            raise RuntimeError(self._init_error or "Windows OCR not available")

        started = time.perf_counter()
        # Worker threads may already have an event loop policy; isolate safely.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Should not happen in our worker design; fall back to new loop in thread.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                text = pool.submit(lambda: asyncio.run(self._recognize_async(image))).result()
        else:
            text = asyncio.run(self._recognize_async(image))

        duration_ms = (time.perf_counter() - started) * 1000.0
        return OCRResult(
            text=text,
            engine_name=self.name,
            duration_ms=duration_ms,
            language=self.language,
        )

    async def _recognize_async(self, image: Image.Image) -> str:
        from winrt.windows.graphics.imaging import (
            BitmapAlphaMode,
            BitmapDecoder,
            BitmapPixelFormat,
            SoftwareBitmap,
        )
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        image = _downscale(image.convert("RGB"))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        stream = InMemoryRandomAccessStream()
        writer = stream.get_output_stream_at(0)
        data_writer = DataWriter(writer)
        data_writer.write_bytes(png_bytes)
        await data_writer.store_async()
        await data_writer.flush_async()
        data_writer.detach_stream()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        if bitmap.bitmap_pixel_format != BitmapPixelFormat.BGRA8:
            bitmap = SoftwareBitmap.convert(
                bitmap,
                BitmapPixelFormat.BGRA8,
                BitmapAlphaMode.PREMULTIPLIED,
            )

        result = await self._engine.recognize_async(bitmap)
        if result is None:
            return ""

        lines = [line.text for line in result.lines]
        return "\n".join(lines).strip()
