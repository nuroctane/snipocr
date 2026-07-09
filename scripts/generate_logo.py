"""Regenerate SnipOCR geometric logo assets into assets/."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"


def draw_logo(size: int, pad_ratio: float = 0.14) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    pad = int(size * pad_ratio)
    stroke = max(2, size // 48)
    thin = max(1, size // 72)
    color = (235, 245, 255, 255)
    accent = (90, 180, 255, 255)
    dim = (120, 140, 160, 255)

    x0, y0, x1, y1 = pad, pad, size - pad, size - pad
    d.rectangle([x0, y0, x1, y1], outline=dim, width=max(1, thin))

    arm = int(size * 0.14)
    for cx, cy, dx, dy in [
        (x0, y0, 1, 1),
        (x1, y0, -1, 1),
        (x0, y1, 1, -1),
        (x1, y1, -1, -1),
    ]:
        d.line([(cx, cy), (cx + dx * arm, cy)], fill=color, width=stroke)
        d.line([(cx, cy), (cx, cy + dy * arm)], fill=color, width=stroke)

    ix0 = int(size * 0.28)
    ix1 = int(size * 0.72)
    mid = size // 2
    line_gap = int(size * 0.09)
    bar_h = max(2, size // 40)

    d.rounded_rectangle(
        [ix0, mid - line_gap - bar_h, int(size * 0.58), mid - line_gap + bar_h // 2],
        radius=bar_h,
        fill=color,
    )
    d.rounded_rectangle(
        [ix0, mid - bar_h // 2, ix1, mid + bar_h // 2],
        radius=bar_h,
        fill=accent,
    )
    d.rounded_rectangle(
        [ix0, mid + line_gap - bar_h // 2, int(size * 0.65), mid + line_gap + bar_h // 2],
        radius=bar_h,
        fill=color,
    )

    tip = [
        (int(size * 0.68), int(size * 0.30)),
        (int(size * 0.78), int(size * 0.30)),
        (int(size * 0.78), int(size * 0.40)),
    ]
    d.polygon(tip, fill=accent)

    sx = int(size * 0.55)
    d.line(
        [(sx, mid - line_gap - bar_h * 2), (sx, mid + line_gap + bar_h * 2)],
        fill=accent,
        width=max(1, thin),
    )
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    master = draw_logo(1024)
    master.save(OUT / "logo.png", "PNG")
    master.save(OUT / "logo-1024.png", "PNG")
    for size in (512, 256):
        draw_logo(size).save(OUT / f"logo-{size}.png", "PNG")
    for size in (128, 64, 32):
        draw_logo(size).save(OUT / f"icon-{size}.png", "PNG")
    icos = [draw_logo(s) for s in (16, 32, 48, 64, 128, 256)]
    icos[-1].save(
        OUT / "logo.ico",
        format="ICO",
        sizes=[(im.width, im.height) for im in icos],
    )
    print(f"Wrote logo assets to {OUT}")


if __name__ == "__main__":
    main()
