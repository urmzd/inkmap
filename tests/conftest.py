"""A synthetic arm photo with a known answer, so the unwrap can be checked exactly."""

import numpy as np
import pytest
from PIL import Image

W, H = 400, 900
CX, HALF = 200, 90  # the arm is a vertical band, shoulder at the top
TOP, BOTTOM = 60, 840  # v = 0.1 at TOP, v = 0.9 at BOTTOM
U0 = 0.5  # the back of the arm faces the camera


def _v(y):
    return 0.1 + 0.8 * (y - TOP) / (BOTTOM - TOP)


@pytest.fixture
def arm_photo(tmp_path):
    """Skin-coloured band on a grey wall. The upper arm carries line work, with one
    bare window in it. Returns (path, bare window as (u_lo, u_hi, v_lo, v_hi))."""
    img = np.zeros((H, W, 3), np.float32)
    img[:] = (190, 190, 190)  # grey wall
    yy, xx = np.mgrid[0:H, 0:W]
    s = (xx - CX) / HALF
    on_arm = (np.abs(s) < 1) & (yy >= TOP) & (yy <= BOTTOM)
    theta = np.arcsin(np.clip(s, -1, 1))
    u = U0 + theta / (2 * np.pi)  # shoulder at the top: u grows to the right
    v = _v(yy)
    skin = np.array([215, 180, 155], np.float32)
    ink = (np.sin(u * 2 * np.pi * 40) > 0) ^ (np.sin(v * 2 * np.pi * 60) > 0)  # dense checks
    window = (0.46, 0.56, 0.30, 0.42)
    bare = (u > window[0]) & (u < window[1]) & (v > window[2]) & (v < window[3])
    dark = on_arm & ink & ~bare
    img[on_arm] = skin
    img[dark] = skin * 0.25
    path = tmp_path / "arm.png"
    Image.fromarray(img.astype(np.uint8)).save(path)
    return path, window


@pytest.fixture
def project_file(arm_photo, tmp_path):
    path, _ = arm_photo
    toml = tmp_path / "project.toml"
    toml.write_text(
        'name = "Test arm"\n'
        "[[photo]]\n"
        f'file = "{path.name}"\n'
        f"points = [[{CX}, {TOP}, {HALF}, 0.1, {U0}], [{CX}, {BOTTOM}, {HALF}, 0.9, {U0}]]\n"
    )
    return toml
