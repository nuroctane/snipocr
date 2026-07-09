"""Popup window showing OCR results."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from .paths import logo_ico, logo_png
from .platform_util import IS_WINDOWS, ui_font_family

logger = logging.getLogger(__name__)


class ResultPopup:
    """
    Thread-safe OCR result popup.

    Call `show(...)` from any thread; UI work is marshalled onto the tk mainloop.
    """

    def __init__(self, root: tk.Tk, on_copy: Optional[Callable[[str], None]] = None) -> None:
        self.root = root
        self.on_copy = on_copy
        self._win: Optional[tk.Toplevel] = None
        self._text: Optional[tk.Text] = None
        self._meta: Optional[tk.StringVar] = None
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._logo_photo: Optional[ImageTk.PhotoImage] = None
        self._hide_job: Optional[str] = None
        self._pinned = False

    def show(
        self,
        text: str,
        *,
        image: Optional[Image.Image] = None,
        engine_name: str = "",
        duration_ms: float = 0.0,
        language: str = "",
        autohide_seconds: int = 8,
    ) -> None:
        def _open() -> None:
            self._open_window(
                text,
                image=image,
                engine_name=engine_name,
                duration_ms=duration_ms,
                language=language,
                autohide_seconds=autohide_seconds,
            )

        self.root.after(0, _open)

    def show_last(self) -> None:
        def _raise() -> None:
            if self._win and self._win.winfo_exists():
                self._win.deiconify()
                self._win.lift()
                self._win.focus_force()

        self.root.after(0, _raise)

    def _open_window(
        self,
        text: str,
        *,
        image: Optional[Image.Image],
        engine_name: str,
        duration_ms: float,
        language: str,
        autohide_seconds: int,
    ) -> None:
        if self._win is None or not self._win.winfo_exists():
            self._build_window()

        assert self._win is not None
        assert self._text is not None
        assert self._meta is not None

        self._pinned = False
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)

        meta_parts = []
        if engine_name:
            meta_parts.append(engine_name)
        if language:
            meta_parts.append(language)
        if duration_ms:
            meta_parts.append(f"{duration_ms:.0f} ms")
        self._meta.set(" · ".join(meta_parts) if meta_parts else "")

        if image is not None:
            thumb = image.copy()
            thumb.thumbnail((280, 120))
            self._photo = ImageTk.PhotoImage(thumb)
            self._thumb_label.configure(image=self._photo)
            self._thumb_label.image = self._photo  # type: ignore[attr-defined]
        else:
            self._thumb_label.configure(image="")
            self._photo = None

        self._position_near_cursor()
        self._win.deiconify()
        self._win.lift()
        self._win.attributes("-topmost", True)

        if self._hide_job:
            try:
                self.root.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None

        if autohide_seconds and autohide_seconds > 0:
            self._hide_job = self.root.after(
                int(autohide_seconds * 1000),
                self._auto_hide,
            )

    def _auto_hide(self) -> None:
        self._hide_job = None
        if self._pinned:
            return
        if self._win and self._win.winfo_exists():
            self._win.withdraw()

    def _apply_window_icon(self, win: tk.Toplevel | tk.Tk) -> None:
        png = logo_png(32)
        if IS_WINDOWS:
            ico = logo_ico()
            try:
                if ico.exists():
                    win.iconbitmap(default=str(ico))
            except Exception:
                pass
        try:
            if png.exists():
                self._logo_photo = ImageTk.PhotoImage(Image.open(png))
                win.iconphoto(True, self._logo_photo)
        except Exception:
            pass

    def _build_window(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("SnipOCR")
        win.geometry("420x360")
        win.minsize(320, 240)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.withdraw()
        self._apply_window_icon(win)

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(frame)
        header.pack(fill=tk.X, pady=(0, 6))
        try:
            mark = Image.open(logo_png(32)).convert("RGBA")
            mark = mark.resize((28, 28), Image.Resampling.LANCZOS)
            self._header_logo = ImageTk.PhotoImage(mark)
            ttk.Label(header, image=self._header_logo).pack(side=tk.LEFT, padx=(0, 8))
        except Exception:
            self._header_logo = None  # type: ignore[assignment]
        font_family = ui_font_family()
        ttk.Label(header, text="SnipOCR", font=(font_family, 11, "bold")).pack(
            side=tk.LEFT
        )

        self._thumb_label = ttk.Label(frame)
        self._thumb_label.pack(anchor=tk.W, pady=(0, 6))

        self._text = tk.Text(frame, wrap=tk.WORD, height=12, font=(font_family, 10))
        self._text.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(btn_row, text="Copy", command=self._copy).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Copy clean", command=self._copy_clean).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(btn_row, text="Pin", command=self._toggle_pin).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(btn_row, text="Close", command=win.withdraw).pack(side=tk.RIGHT)

        self._meta = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self._meta, foreground="#666").pack(
            anchor=tk.W, pady=(6, 0)
        )

        self._win = win

    def _position_near_cursor(self) -> None:
        if not self._win:
            return
        try:
            x = self.root.winfo_pointerx() + 16
            y = self.root.winfo_pointery() + 16
            self._win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _current_text(self) -> str:
        if not self._text:
            return ""
        return self._text.get("1.0", "end-1c")

    def _copy(self) -> None:
        text = self._current_text()
        if self.on_copy:
            self.on_copy(text)
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def _copy_clean(self) -> None:
        text = self._current_text()
        cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if self.on_copy:
            self.on_copy(cleaned)
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(cleaned)

    def _toggle_pin(self) -> None:
        self._pinned = not self._pinned
