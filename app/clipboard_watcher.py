"""Win32 clipboard format listener (AddClipboardFormatListener)."""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable, Optional

import win32api
import win32con
import win32gui

logger = logging.getLogger(__name__)

WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3

user32 = ctypes.windll.user32
user32.AddClipboardFormatListener.argtypes = [wintypes.HWND]
user32.AddClipboardFormatListener.restype = wintypes.BOOL
user32.RemoveClipboardFormatListener.argtypes = [wintypes.HWND]
user32.RemoveClipboardFormatListener.restype = wintypes.BOOL


class ClipboardWatcher:
    """
    Runs a hidden message-only window on a background thread and invokes
    `on_update` whenever the clipboard contents change.
    """

    def __init__(self, on_update: Callable[[], None]) -> None:
        self._on_update = on_update
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._suppress_until = 0.0
        self._last_text_we_set: Optional[str] = None

    def suppress(self, seconds: float = 0.6, text: Optional[str] = None) -> None:
        """Ignore clipboard updates we cause ourselves when writing OCR text."""
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
        self._thread = threading.Thread(
            target=self._run,
            name="ClipboardWatcher",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("Clipboard watcher failed to start")

    def stop(self) -> None:
        self._stop.set()
        hwnd = self._hwnd
        if hwnd:
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _run(self) -> None:
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
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
            HWND_MESSAGE,
            0,
            wc.hInstance,
            None,
        )
        self._hwnd = hwnd

        if not user32.AddClipboardFormatListener(hwnd):
            err = ctypes.get_last_error()
            logger.error("AddClipboardFormatListener failed (err=%s)", err)
            self._ready.set()
            return

        logger.info("Clipboard listener active (hwnd=%s)", hwnd)
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
            self._hwnd = None
            logger.info("Clipboard listener stopped")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            if self.is_suppressed():
                logger.debug("Ignoring clipboard update (suppressed)")
                return 0
            try:
                self._on_update()
            except Exception:
                logger.exception("Error handling clipboard update")
            return 0
        if msg == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
