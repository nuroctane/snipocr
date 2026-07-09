#!/usr/bin/env python3
"""Pre-download default RapidOCR ONNX models for offline use.

Usage:
    python scripts/download_rapidocr_models.py
    python scripts/download_rapidocr_models.py --check
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Download / verify RapidOCR models")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run rapidocr check after download",
    )
    args = parser.parse_args()

    try:
        import rapidocr  # noqa: F401
    except ImportError:
        print("rapidocr is not installed. Run: pip install rapidocr onnxruntime", file=sys.stderr)
        return 1

    # Prefer the CLI entry points when available
    try:
        from rapidocr.main import main as rapidocr_cli  # type: ignore
    except Exception:
        rapidocr_cli = None

    print("Downloading default RapidOCR models…")
    # Instantiate default engine — triggers model download into package models/
    try:
        from rapidocr import RapidOCR

        eng = RapidOCR(params={"Global.log_level": "info"})
        # Tiny warmup so rec model is definitely resolved
        import numpy as np

        img = np.ones((64, 256, 3), dtype=np.uint8) * 255
        eng(img)
        print("Default models ready.")
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        print("You can also run: rapidocr download_models", file=sys.stderr)
        return 1

    if args.check:
        import subprocess

        print("Running: rapidocr check")
        rc = subprocess.call([sys.executable, "-m", "rapidocr.cli", "check"])
        if rc != 0:
            rc = subprocess.call(["rapidocr", "check"])
        return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
