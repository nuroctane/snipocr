"""Cross-platform clipboard change watcher."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .platform_util import IS_MACOS, IS_WINDOWS

logger = logging.getLogger(__name__)


class ClipboardWatcher:
    """
    Invokes `on_update` whenever the clipboard contents change.

    Windows: AddClipboardFormatListener message window.
    macOS / other: poll pasteboard changeCount / sequence number.
    """

    def __init__(self, on_update: Callable[[], None]) -> None:
        self._on_update = on_update
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._suppress_until = 0.0
        self._last_text_we_set: Optional[str] = None
        self._impl_stop: Optional[Callable[[], None]] = None

    def suppress(self, seconds: float = 0.6, text: Optional[str] = None) -> None:
        self._suppress_until = time.monotonic() + seconds
        if text is not None:
            self._last_text_we_set = text

    def is_suppressed(self) -> bool:
        return time.monotonic() < self._suppress_until

    def last_text_we_set(self) -> Optional[str]:
        return self._last_text_we_set

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        target = self._run_windows if IS_WINDOWS else self._run_poll
        self._thread = threading.Thread(target=target, name="ClipboardWatcher", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("Clipboard watcher failed to start")

    def stop(self) -> None:
        self._stop.set()
        if self._impl_stop:
            try:
                self._impl_stop()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _fire(self) -> None:
        if self.is_suppressed():
            logger.debug("Ignoring clipboard update (suppressed)")
            return
        try:
            self._on_update()
        except Exception:
            logger.exception("Error handling clipboard update")

    # ── Windows native listener ──────────────────────────────────────────

    def _run_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        import win32api
        import win32con
        import win32gui

        wm_clipboardupdate = 0x031D
        hwnd_message = -3

        user32 = ctypes.windll.user32
        user32.AddClipboardFormatListener.argtypes = [wintypes.HWND]
        user32.AddClipboardFormatListener.restype = wintypes.BOOL
        user32.RemoveClipboardFormatListener.argtypes = [wintypes.HWND]
        user32.RemoveClipboardFormatListener.restype = wintypes.BOOL

        hwnd_holder: dict[str, int] = {}

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == wm_clipboardupdate:
                self._fire()
                return 0
            if msg == win32con.WM_CLOSE:
                win32gui.DestroyWindow(hwnd)
                return 0
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = wnd_proc
        wc.lpszClassName = f"SnipOCRClipboardListener_{id(self)}_{time.time_ns()}"
        wc.hInstance = win32api.GetModuleHandle(None)
        class_atom = win32gui.RegisterClass(wc)

        hwnd = win32gui.CreateWindow(
            class_atom,
            "SnipOCR Clipboard Listener",
            0,
            0,
            0,
            0,
            0,
            hwnd_message,
            0,
            wc.hInstance,
            None,
        )
        hwnd_holder["hwnd"] = hwnd

        if not user32.AddClipboardFormatListener(hwnd):
            logger.error("AddClipboardFormatListener failed")
            self._ready.set()
            return

        def _stop_impl() -> None:
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass

        self._impl_stop = _stop_impl
        logger.info("Clipboard listener active (Windows hwnd=%s)", hwnd)
        self._ready.set()

        try:
            while not self._stop.is_set():
                if win32gui.PumpWaitingMessages():
                    break
                time.sleep(0.02)
        finally:
            try:
                user32.RemoveClipboardFormatListener(hwnd)
            except Exception:
                pass
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.DestroyWindow(hwnd)
            except Exception:
                pass
            try:
                win32gui.UnregisterClass(wc.lpszClassName, wc.hInstance)
            except Exception:
                pass
            logger.info("Clipboard listener stopped")

    # ── macOS / generic poll ─────────────────────────────────────────────

    def _run_poll(self) -> None:
        from . import clipboard_io

        try:
            last = clipboard_io.get_clipboard_sequence_number()
        except Exception:
            last = -1

        platform = "macOS" if IS_MACOS else "poll"
        logger.info("Clipboard listener active (%s poll)", platform)
        self._ready.set()

        while not self._stop.is_set():
            try:
                seq = clipboard_io.get_clipboard_sequence_number()
                if seq != last:
                    last = seq
                    self._fire()
            except Exception:
                logger.exception("Clipboard poll error")
            self._stop.wait(0.25)

        logger.info("Clipboard listener stopped")
