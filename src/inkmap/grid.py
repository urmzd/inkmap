"""Draw a labelled pixel grid on a photo, to read control points off it."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def draw_grid(src: Path, dst: Path, step: int = 100) -> Path:
    img = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    line, text = (255, 255, 0, 140), (255, 255, 0, 255)
    for x in range(step, img.width, step):
        draw.line([(x, 0), (x, img.height)], fill=line, width=1)
        draw.text((x + 3, 2), str(x), fill=text)
    for y in range(step, img.height, step):
        draw.line([(0, y), (img.width, y)], fill=line, width=1)
        draw.text((3, y - 12), str(y), fill=text)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)
    return dst
