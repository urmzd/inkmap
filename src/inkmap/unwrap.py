"""Unwrap photos of an arm onto a flat sleeve map, then find the bare skin.

The sleeve map is a grid over (v, u):

- v runs along the arm: 0 at the shoulder, 0.5 at the elbow, 1 at the wrist.
- u runs around the arm: 0 front, 0.25 outer, 0.5 back (the elbow point), 0.75 inner.

Seen from outside with the shoulder at the top, u grows to the viewer's right.
Each photo is treated as a view of a cylinder: a point at angle t from the centre
line appears at ``centre + across * half_width * sin(t)``.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from inkmap.project import Detect, Photo, Project

U, V = 720, 1440  # texels around the arm, and from shoulder to wrist
VISIBLE = np.radians(72)  # past this angle the skin is too foreshortened to trust
SKIN = np.array([217.0, 185.0, 162.0])
INK = np.array([44.0, 46.0, 52.0])
UNSEEN = np.array([178.0, 166.0, 158.0])
OUTLINE_RGB = (47, 123, 255)
WRIST_END = 0.975  # the sleeve stops here; the hand stays plain skin


@dataclass(frozen=True)
class Arm:
    """What the map needs to know about the 3D arm: its size."""

    circumference_cm: np.ndarray  # one value per row of the map
    length_cm: float

    @classmethod
    def load(cls, name: str = "arm-left.json") -> Arm:
        data = json.loads(resources.files("inkmap.assets").joinpath(name).read_text())
        bins = np.asarray(data["circ"], float)
        rows = np.interp(np.linspace(0, 1, V), (np.arange(len(bins)) + 0.5) / len(bins), bins)
        return cls(circumference_cm=rows, length_cm=float(data["length"]))


@dataclass(frozen=True)
class Area:
    name: str
    u: float
    v: float
    w: float  # cm
    h: float  # cm
    area: float  # cm2

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "u": round(self.u, 3),
            "v": round(self.v, 3),
            "w": round(self.w, 1),
            "h": round(self.h, 1),
            "area": round(self.area, 1),
        }


@dataclass(frozen=True)
class SleeveMap:
    ink: np.ndarray  # (V, U) 0..1, how much ink is on the skin
    seen: np.ndarray  # (V, U) bool, false where no photo showed the skin
    bare: np.ndarray  # (V, U) bool, the bare areas that passed every test
    areas: tuple[Area, ...]
    strips: dict[str, np.ndarray]  # per photo: the unwrapped colour strip, for checking

    @property
    def seen_fraction(self) -> float:
        rows = slice(int(0.05 * V), int(0.95 * V))
        return float(self.seen[rows].mean())


def unwrap_photo(photo: Photo) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (ink, weight, colour strip) for one photo, each on the (V, U) grid."""
    img = np.asarray(Image.open(photo.file).convert("RGB")).astype(np.float32)
    height, width = img.shape[:2]
    p = np.array([[q.x, q.y, q.half_width, q.v, q.u] for q in photo.points])
    vs = np.linspace(0, 1, V)
    inside = (vs >= p[0, 3]) & (vs <= p[-1, 3])
    cx, cy, hw, u0 = (np.interp(vs, p[:, 3], p[:, k]) for k in (0, 1, 2, 4))

    # direction of the arm in the image, shoulder to wrist, smoothed over a short span
    d = 0.04
    ax = np.interp(vs + d, p[:, 3], p[:, 0]) - np.interp(vs - d, p[:, 3], p[:, 0])
    ay = np.interp(vs + d, p[:, 3], p[:, 1]) - np.interp(vs - d, p[:, 3], p[:, 1])
    head, tail = vs < p[0, 3] + d, vs > p[-1, 3] - d
    ax[head], ay[head] = p[1, 0] - p[0, 0], p[1, 1] - p[0, 1]
    ax[tail], ay[tail] = p[-1, 0] - p[-2, 0], p[-1, 1] - p[-2, 1]
    norm = np.maximum(np.hypot(ax, ay), 1e-9)
    ax, ay = ax / norm, ay / norm
    across_x, across_y = ay, -ax  # the way u grows across the frame

    us = (np.arange(U) + 0.5) / U
    theta = 2 * np.pi * (((us[None, :] - u0[:, None]) + 0.5) % 1.0 - 0.5)
    x = cx[:, None] + across_x[:, None] * hw[:, None] * np.sin(theta)
    y = cy[:, None] + across_y[:, None] * hw[:, None] * np.sin(theta)
    ok = (np.abs(theta) < VISIBLE) & inside[:, None]
    ok &= (x >= 1) & (x < width - 2) & (y >= 1) & (y < height - 2)

    coords = [np.clip(y, 0, height - 1), np.clip(x, 0, width - 1)]
    rgb = np.stack([ndi.map_coordinates(img[:, :, c], coords, order=1) for c in range(3)], -1)
    lum = rgb @ np.array([0.21, 0.72, 0.07]) / 255
    # grey and bright is wall or ceiling, not arm: skin is warm, ink is dark
    ok &= ~(((rgb[..., 0] - rgb[..., 2]) < 20) & (lum > 0.5))
    weight = np.where(ok, np.cos(np.clip(theta, -VISIBLE, VISIBLE)) ** 1.5, 0.0)

    ink = _ink(lum, ok)
    strip = np.where(ok[..., None], rgb, 40).astype(np.uint8)
    return ink, weight, strip


def _ink(lum: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """How much darker each texel is than bare skin would be at that place."""
    column = np.full(U, np.nan)
    has = ok.any(axis=0)
    if has.any():
        masked = np.where(ok, lum, np.nan)
        column[has] = np.nanpercentile(masked[:, has], 90, axis=0)
    fill = np.nanmedian(column) if has.any() else 0.6
    column = ndi.gaussian_filter1d(np.nan_to_num(column, nan=fill), 14, mode="wrap")

    small = np.where(ok, lum, 0)[::4, ::4]
    local = ndi.percentile_filter(small, 92, size=(46, 28), mode="nearest")
    local = np.kron(local, np.ones((4, 4)))[:V, :U]
    ref = np.maximum(local, 0.9 * column[None, :])
    ref = np.maximum(ndi.gaussian_filter(ref, 6), 0.2)
    ink = np.clip(1 - lum / ref, 0, 1)
    return np.clip((ink - 0.07) / 0.5, 0, 1)


def build_map(project: Project, arm: Arm | None = None) -> SleeveMap:
    arm = arm or Arm.load()
    total = np.zeros((V, U))
    wsum = np.zeros((V, U))
    cover = np.zeros((V, U))
    strips = {}
    for photo in project.photos:
        ink, weight, strip = unwrap_photo(photo)
        sharp = weight**4  # where photos overlap, the most face-on one wins
        total += ink * sharp
        wsum += sharp
        cover = np.maximum(cover, weight)
        strips[photo.name] = strip

    ink = np.where(wsum > 0, total / np.maximum(wsum, 1e-9), 0)
    ink = ndi.gaussian_filter(ink, 0.8)
    seen = ndi.binary_closing(cover > 0.12, iterations=3)
    past_wrist = np.linspace(0, 1, V) > WRIST_END
    ink[past_wrist] = 0
    seen[past_wrist] = True

    bare, areas = find_bare(ink, seen, arm, project.detect)
    return SleeveMap(ink=ink, seen=seen, bare=bare, areas=areas, strips=strips)


def find_bare(
    ink: np.ndarray, seen: np.ndarray, arm: Arm, cfg: Detect
) -> tuple[np.ndarray, tuple[Area, ...]]:
    """Bare skin is seen, light, free of hard edges, and wide enough to hold a design.

    Ink has hard edges and shadows do not. Counting edges is what tells a shaded
    bare patch from a tattoo.
    """
    vs = np.linspace(0, 1, V)[:, None]
    wrap = ("nearest", "wrap")
    density = ndi.gaussian_filter(ink, (10, 8), mode=wrap)
    grad = ndi.gaussian_gradient_magnitude(ink, 1.3, mode=wrap)
    edges = ndi.gaussian_filter(grad, (11, 9), mode=wrap)
    bare = seen & (density < cfg.max_ink) & (edges < cfg.max_edges)
    bare &= (vs > 0.03) & (vs < cfg.max_v)

    cm_v = arm.length_cm / V
    cm_u = float(arm.circumference_cm.mean()) / U
    ry, rx = max(1, int(cfg.min_radius_cm / cm_v)), max(1, int(cfg.min_radius_cm / cm_u))
    yy, xx = np.mgrid[-ry : ry + 1, -rx : rx + 1]
    disc = (yy / ry) ** 2 + (xx / rx) ** 2 <= 1

    # work on three turns side by side so an area that crosses u = 0 stays in one piece
    tile = np.concatenate([bare, bare, bare], axis=1)
    tile = ndi.binary_opening(tile, structure=disc)
    tile = ndi.binary_closing(tile, structure=disc[::2, ::2])
    labels, count = ndi.label(tile[:, U // 2 : U // 2 + 2 * U])

    keep = np.zeros((V, U), bool)
    found = []
    for i in range(1, count + 1):
        ys, xs = np.nonzero(labels == i)
        xs = xs + U // 2
        centre = xs.mean()
        if not (centre >= U and centre < 2 * U):
            continue  # this is the copy from a neighbouring turn
        area = len(ys) * cm_v * cm_u
        if area < cfg.min_area_cm2:
            continue
        keep[ys, xs % U] = True
        v = ys.mean() / V
        u = (centre / U) % 1
        circ = float(np.interp(v, np.linspace(0, 1, V), arm.circumference_cm))
        w = (np.percentile(xs, 95) - np.percentile(xs, 5)) / U * circ
        h = (np.percentile(ys, 95) - np.percentile(ys, 5)) / V * arm.length_cm
        found.append(Area(name=_name(u, v), u=float(u), v=float(v), w=w, h=h, area=area))

    found.sort(key=lambda a: -a.area)
    found = found[: cfg.max_areas]
    counts: dict[str, int] = {}
    named = []
    for a in found:
        counts[a.name] = counts.get(a.name, 0) + 1
        suffix = f" {counts[a.name]}" if counts[a.name] > 1 else ""
        named.append(Area(a.name + suffix, a.u, a.v, a.w, a.h, a.area))
    return keep, tuple(named)


def _name(u: float, v: float) -> str:
    part = "Upper arm" if v < 0.42 else "Elbow" if v < 0.6 else "Forearm"
    if u < 0.125 or u >= 0.875:
        side = "front"
    elif u < 0.375:
        side = "outer"
    elif u < 0.625:
        side = "back"
    else:
        side = "inner"
    return f"{part}, {side}"


def render_base(m: SleeveMap) -> Image.Image:
    """Clay skin with the existing ink on it. Unseen skin is hatched, not guessed."""
    k = (m.ink**0.85 * 0.93)[..., None]
    base = SKIN * (1 - k) + INK * k
    yy, xx = np.mgrid[0:V, 0:U]
    hatch = (((xx + yy) // 5) % 2)[..., None] * 9.0
    soft = np.clip(ndi.gaussian_filter(m.seen.astype(float), 5) * 2, 0, 1)[..., None]
    base = np.where(m.seen[..., None], base * soft + UNSEEN * (1 - soft), UNSEEN - hatch)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def render_outline(m: SleeveMap) -> Image.Image:
    """A transparent layer with a line around each bare area."""
    tile = np.concatenate([m.bare, m.bare, m.bare], axis=1)
    inner = ndi.binary_erosion(tile, iterations=3)[:, U : 2 * U]
    line = m.bare & ~inner
    alpha = np.clip(ndi.gaussian_filter(line.astype(float), 0.7) * 1.6, 0, 1)
    out = np.zeros((V, U, 4), np.uint8)
    out[..., :3] = OUTLINE_RGB
    out[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def _data_uri(img: Image.Image, fmt: str, **save) -> str:
    buf = io.BytesIO()
    img.save(buf, fmt, **save)
    mime = "image/jpeg" if fmt == "JPEG" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def viewer_data(m: SleeveMap) -> dict:
    """The map in the form the viewer page reads."""
    return {
        "base": _data_uri(render_base(m), "JPEG", quality=90),
        "outline": _data_uri(render_outline(m), "PNG"),
        "zones": [a.as_dict() for a in m.areas],
        "seen": round(m.seen_fraction, 2),
    }


def write_debug(m: SleeveMap, out_dir: Path) -> list[Path]:
    """Write the flat map and the per-photo strips, for checking the control points."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    flat = render_base(m).convert("RGBA")
    flat.alpha_composite(render_outline(m))
    path = out_dir / "map.jpg"
    flat.convert("RGB").save(path, quality=90)
    written.append(path)
    for name, strip in m.strips.items():
        path = out_dir / f"strip-{name}.jpg"
        Image.fromarray(strip).save(path, quality=88)
        written.append(path)
    return written
