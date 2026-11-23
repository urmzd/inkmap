"""Body parts that inkmap can map.

A part is a 3D mesh plus the words used for places on it. Every part shares one skin
coordinate system: v runs along the part and u runs around it. That is what lets the
unwrap, the detection and the viewer stay the same for every part.

The arm is the first part. Other limbs fit the same model. Flat regions (back, chest) will
need a different way to unwrap a photo, but can reuse everything after that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Part:
    key: str  # the name used in a project file
    label: str  # the word the viewer uses, for example "arm"
    mesh: str  # asset file with the mesh and its skin coordinates
    sections: tuple[tuple[float, str], ...]  # (upper limit of v, name), from v = 0 up
    sides: tuple[str, str, str, str]  # names for the quarters centred on u = 0, 0.25, 0.5, 0.75
    end_v: float  # past this the skin is left plain (for an arm: the hand)

    def area_name(self, u: float, v: float) -> str:
        """A short name for a place on the part, for example "Elbow, back"."""
        section = next((name for limit, name in self.sections if v < limit), self.sections[-1][1])
        side = self.sides[int(((u % 1) + 0.125) * 4) % 4]
        return f"{section}, {side}"


LEFT_ARM = Part(
    key="left-arm",
    label="arm",
    mesh="arm-left.json",
    sections=((0.42, "Upper arm"), (0.6, "Elbow"), (1.01, "Forearm")),
    sides=("front", "outer", "back", "inner"),
    end_v=0.975,
)

PARTS: dict[str, Part] = {p.key: p for p in (LEFT_ARM,)}
DEFAULT = LEFT_ARM.key


def get(key: str) -> Part:
    try:
        return PARTS[key]
    except KeyError:
        known = ", ".join(sorted(PARTS))
        raise KeyError(f"unknown part '{key}'. Supported: {known}") from None
