"""Project file: which photos to use and where the arm is in each one."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Point:
    """One station along the arm in a photo.

    x, y: centre of the arm in pixels. half_width: half the arm width in pixels,
    measured across the arm. v: position along the arm (0 shoulder, 0.5 elbow, 1 wrist).
    u: which part of the arm faces the camera at the centre line
    (0 front, 0.25 outer, 0.5 back, 0.75 inner).
    """

    x: float
    y: float
    half_width: float
    v: float
    u: float


@dataclass(frozen=True)
class Photo:
    file: Path
    points: tuple[Point, ...]

    @property
    def name(self) -> str:
        return self.file.stem


@dataclass(frozen=True)
class Detect:
    """Settings for finding bare skin."""

    max_ink: float = 0.42
    max_edges: float = 0.021
    min_radius_cm: float = 0.5
    min_area_cm2: float = 5.0
    max_v: float = 0.62
    max_areas: int = 7


@dataclass(frozen=True)
class Project:
    name: str
    root: Path
    photos: tuple[Photo, ...]
    detect: Detect = field(default_factory=Detect)

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-") or "project"


class ProjectError(ValueError):
    """The project file is missing something or has a wrong value."""


def load(path: Path) -> Project:
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError as e:
        raise ProjectError(f"project file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{path}: {e}") from e

    root = path.parent
    raw_photos = data.get("photo", [])
    if not raw_photos:
        raise ProjectError(f"{path}: add at least one [[photo]] table")

    photos = []
    for i, raw in enumerate(raw_photos, 1):
        if "file" not in raw:
            raise ProjectError(f"{path}: photo {i} has no 'file'")
        file = (root / raw["file"]).resolve()
        if not file.is_file():
            raise ProjectError(f"{path}: photo {i}: file not found: {file}")
        rows = raw.get("points", [])
        if len(rows) < 2:
            raise ProjectError(f"{path}: photo {i} needs at least 2 points")
        if any(len(r) != 5 for r in rows):
            raise ProjectError(f"{path}: photo {i}: each point is [x, y, half_width, v, u]")
        points = tuple(Point(*map(float, r)) for r in rows)
        vs = [p.v for p in points]
        if vs != sorted(vs) or len(set(vs)) != len(vs):
            raise ProjectError(f"{path}: photo {i}: list points from shoulder to wrist (v rising)")
        photos.append(Photo(file=file, points=points))

    known = Detect.__dataclass_fields__
    extra = set(data.get("detect", {})) - set(known)
    if extra:
        raise ProjectError(f"{path}: unknown [detect] keys: {', '.join(sorted(extra))}")
    return Project(
        name=str(data.get("name", path.stem)),
        root=root,
        photos=tuple(photos),
        detect=Detect(**data.get("detect", {})),
    )
