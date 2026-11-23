"""Pull the sharpest still frames out of a video with ffmpeg."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class FfmpegError(RuntimeError):
    pass


def _ffmpeg(*args: str) -> None:
    if not shutil.which("ffmpeg"):
        raise FfmpegError("ffmpeg is not installed. Install it, for example: brew install ffmpeg")
    result = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(result.stderr.strip() or "ffmpeg failed")


def blur_scores(video: Path) -> list[float]:
    """One blur score per frame. Lower is sharper."""
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "blur.txt"
        _ffmpeg("-i", str(video), "-vf", f"blurdetect,metadata=print:file={log}", "-f", "null", "-")
        return [float(x) for x in re.findall(r"lavfi\.blur=([\d.]+)", log.read_text())]


def pick_sharpest(scores: list[float], count: int) -> list[int]:
    """Split the video into `count` equal windows and take the sharpest frame of each.

    A phone video of a turning arm blurs whenever the arm moves, so the sharp frames
    are the pauses. One per window spreads the picks over the whole turn.
    """
    if not scores or count < 1:
        return []
    count = min(count, len(scores))
    picks = []
    for i in range(count):
        lo, hi = i * len(scores) // count, (i + 1) * len(scores) // count
        picks.append(min(range(lo, max(hi, lo + 1)), key=scores.__getitem__))
    return picks


def extract(video: Path, out_dir: Path, count: int = 10) -> list[Path]:
    video = Path(video)
    if not video.is_file():
        raise FfmpegError(f"video not found: {video}")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n in pick_sharpest(blur_scores(video), count):
        path = out_dir / f"frame-{n:05d}.png"
        _ffmpeg(
            "-i",
            str(video),
            "-vf",
            f"select=eq(n\\,{n})",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(path),
        )
        written.append(path)
    return written
