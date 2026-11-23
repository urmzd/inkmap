"""Draw three synthetic photos of a tattooed arm, so the example needs no real person.

The "arm" is a cylinder with a painted sleeve. Each photo shows it from a different side.
Run:  uv run python examples/synthetic/make_photos.py
"""

from pathlib import Path

import numpy as np
from PIL import Image

W, H = 480, 960
CX, HALF, TOP, BOTTOM = 240, 105, 70, 890
V_TOP, V_BOTTOM = 0.08, 0.96
SKIN = np.array([214, 180, 156], np.float32)
WALL = np.array([196, 196, 198], np.float32)
VIEWS = {"front-outer": 0.2, "back": 0.5, "inner": 0.8}


def sleeve(u, v):
    """Ink density 0..1 at each (u, v): a lattice and bands, with two bare windows."""
    ink = np.zeros_like(u)
    # upper arm: a lattice of thin diagonal lines
    lattice = (np.abs(np.sin((u * 14 + v * 22) * np.pi)) < 0.12) | (
        np.abs(np.sin((u * 14 - v * 22) * np.pi)) < 0.12
    )
    ink = np.where((v > 0.1) & (v < 0.5) & lattice, 0.85, ink)
    # forearm: solid bands with a wave edge
    bands = np.sin(v * np.pi * 26 + np.sin(u * 2 * np.pi * 3) * 1.6) > 0.1
    ink = np.where((v >= 0.5) & (v < 0.95) & bands, 0.7, ink)
    # bare windows: the elbow point, and a patch on the inner upper arm
    elbow = ((u - 0.5) / 0.09) ** 2 + ((v - 0.53) / 0.055) ** 2 < 1
    patch = ((((u - 0.8 + 0.5) % 1) - 0.5) / 0.07) ** 2 + ((v - 0.26) / 0.07) ** 2 < 1
    return np.where(elbow | patch, 0.0, ink)


def photo(u0):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    s = (xx - CX) / HALF
    on_arm = (np.abs(s) < 1) & (yy >= TOP) & (yy <= BOTTOM)
    theta = np.arcsin(np.clip(s, -1, 1))
    u = (u0 + theta / (2 * np.pi)) % 1
    v = V_TOP + (V_BOTTOM - V_TOP) * (yy - TOP) / (BOTTOM - TOP)
    shade = 0.72 + 0.28 * np.cos(theta)  # darker toward the edges, like a real limb
    k = sleeve(u, v)[..., None]
    arm = (SKIN * (1 - k) + np.array([40, 42, 48], np.float32) * k) * shade[..., None]
    img = np.where(on_arm[..., None], arm, WALL)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    here = Path(__file__).parent
    for name, u0 in VIEWS.items():
        photo(u0).save(here / f"{name}.png")
        print(f"wrote {name}.png (u = {u0})")
