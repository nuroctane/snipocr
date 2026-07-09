"""OCR engine interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass
class OCRResult:
    text: str
    engine_name: str
    duration_ms: float
    language: str = ""


class OCREngine(Protocol):
    name: str

    def recognize(self, image: Image.Image) -> OCRResult:
        """Run OCR on a Pillow image and return structured text."""
        ...

    def available_languages(self) -> list[str]:
        """Return language tags the engine can use."""
        ...
