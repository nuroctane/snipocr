"""Resolved paths for app assets and data."""

from __future__ import annotations

from pathlib import Path

# Repository root (parent of app/)
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def logo_png(size: str | int | None = None) -> Path:
    """
    Prefer sized asset if present, else master logo.png.

    size: e.g. 64, 256, "512" or None for assets/logo.png
    """
    if size is None:
        return ASSETS / "logo.png"
    path = ASSETS / f"logo-{size}.png"
    if path.exists():
        return path
    icon = ASSETS / f"icon-{size}.png"
    if icon.exists():
        return icon
    return ASSETS / "logo.png"


def logo_ico() -> Path:
    return ASSETS / "logo.ico"
