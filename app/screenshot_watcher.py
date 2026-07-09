"""Watch common screenshot folders for newly saved capture files."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from .platform_util import screenshot_dirs
from .snip_detector import looks_like_screenshot_filename

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class ScreenshotFolderWatcher:
    """
    Polls known screenshot directories for new image files.

    Fires `on_image(path, image)` shortly after a matching file appears and
    finishes writing. Designed for Cmd+Shift+3/4 (macOS file saves) and
    Win+PrtScn (Windows Pictures\\Screenshots).
    """

    def __init__(
        self,
        on_image: Callable[[Path, Image.Image], None],
        *,
        poll_seconds: float = 0.75,
        max_age_seconds: float = 8.0,
    ) -> None:
        self.on_image = on_image
        self.poll_seconds = poll_seconds
        self.max_age_seconds = max_age_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seen: dict[str, float] = {}  # path -> mtime when processed
        self._bootstrap_done = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="ScreenshotFolderWatcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _run(self) -> None:
        dirs = screenshot_dirs()
        logger.info(
            "Screenshot folder watcher dirs: %s",
            [str(d) for d in dirs] or "(none found)",
        )
        # Bootstrap: ignore existing files so we don't OCR the whole Desktop.
        self._scan(process_new=False)
        self._bootstrap_done = True

        while not self._stop.is_set():
            try:
                self._scan(process_new=True)
            except Exception:
                logger.exception("Screenshot folder scan failed")
            self._stop.wait(self.poll_seconds)

    def _scan(self, *, process_new: bool) -> None:
        now = time.time()
        for folder in screenshot_dirs():
            try:
                entries = list(folder.iterdir())
            except OSError:
                continue
            for path in entries:
                try:
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in IMAGE_SUFFIXES:
                        continue
                    if not looks_like_screenshot_filename(path.name):
                        # On macOS Desktop, only process screenshot-like names.
                        # Always allow Pictures/Screenshots folder contents.
                        if folder.name.lower() != "screenshots":
                            continue

                    stat = path.stat()
                    mtime = stat.st_mtime
                    key = str(path.resolve())
                    age = now - mtime
                    if age > self.max_age_seconds and self._bootstrap_done:
                        continue

                    prev = self._seen.get(key)
                    if prev is not None and prev == mtime:
                        continue

                    # Wait until size is stable (file finished writing).
                    size1 = stat.st_size
                    time.sleep(0.12)
                    try:
                        size2 = path.stat().st_size
                        mtime2 = path.stat().st_mtime
                    except OSError:
                        continue
                    if size1 != size2:
                        continue

                    self._seen[key] = mtime2
                    if not process_new:
                        continue
                    if age > self.max_age_seconds:
                        continue

                    try:
                        image = Image.open(path).convert("RGB")
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Could not open screenshot %s: %s", path, exc)
                        continue

                    logger.info("New screenshot file: %s (%sx%s)", path.name, *image.size)
                    self.on_image(path, image)
                except OSError:
                    continue

        # Bound memory of seen map
        if len(self._seen) > 500:
            items = sorted(self._seen.items(), key=lambda kv: kv[1], reverse=True)[:200]
            self._seen = dict(items)
