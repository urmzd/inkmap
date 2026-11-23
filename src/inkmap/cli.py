"""Command line for inkmap."""

from __future__ import annotations

import json
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from inkmap import __version__

REPO = "urmzd/inkmap"

app = typer.Typer(
    help="Map photos of existing tattoos onto a 3D arm and find the bare skin.",
    no_args_is_help=True,
    add_completion=False,
)


class Format(StrEnum):
    human = "human"
    json = "json"


class State:
    format: Format = Format.human


state = State()


def emit(data: dict, human: str) -> None:
    """Structured result on stdout as JSON, or a short human line on stderr."""
    if state.format is Format.json:
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(human, err=True)


def fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(1)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"inkmap v{__version__}")
        raise typer.Exit()


@app.callback()
def main_options(
    format: Annotated[Format, typer.Option("--format", help="Output format.")] = Format.human,
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show the version.")
    ] = False,
) -> None:
    state.format = format


@app.command()
def frames(
    video: Annotated[Path, typer.Argument(help="Video of the arm turning.")],
    out: Annotated[Path, typer.Option("--out", "-o", help="Folder for the frames.")] = Path(
        "frames"
    ),
    count: Annotated[int, typer.Option("--count", "-n", min=1, help="How many frames.")] = 10,
) -> None:
    """Pull the sharpest frames out of a video."""
    from inkmap.frames import FfmpegError, extract

    try:
        paths = extract(video, out, count)
    except FfmpegError as e:
        raise fail(str(e)) from e
    emit({"frames": [str(p) for p in paths]}, f"wrote {len(paths)} frames to {out}")


@app.command()
def grid(
    image: Annotated[Path, typer.Argument(help="Photo to measure.")],
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output file.")] = None,
    step: Annotated[int, typer.Option("--step", min=10, help="Grid spacing in pixels.")] = 100,
) -> None:
    """Draw a labelled pixel grid on a photo, to read control points off it."""
    from inkmap.grid import draw_grid

    if not image.is_file():
        raise fail(f"image not found: {image}")
    target = out or image.with_name(f"{image.stem}-grid.png")
    draw_grid(image, target, step)
    emit({"grid": str(target)}, f"wrote {target}")


@app.command()
def build(
    project: Annotated[Path, typer.Argument(help="Project file (TOML).")],
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Viewer page to write.")] = None,
    debug: Annotated[
        Path | None, typer.Option("--debug", help="Also write the flat map and strips here.")
    ] = None,
) -> None:
    """Unwrap the photos, find the bare skin, and write the 3D viewer page."""
    from inkmap.project import ProjectError, load
    from inkmap.unwrap import build_map, write_debug
    from inkmap.viewer import build_html

    try:
        proj = load(project)
    except ProjectError as e:
        raise fail(str(e)) from e
    sleeve = build_map(proj)
    target = out or proj.root / f"{proj.slug}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_html(proj, sleeve))
    extra = [str(p) for p in write_debug(sleeve, debug)] if debug else []
    emit(
        {
            "viewer": str(target),
            "seen": round(sleeve.seen_fraction, 2),
            "areas": [a.as_dict() for a in sleeve.areas],
            "debug": extra,
        },
        f"wrote {target}\n"
        f"skin seen: {sleeve.seen_fraction:.0%}\n"
        + "\n".join(f"bare: {a.name} ({a.w:.1f} x {a.h:.1f} cm)" for a in sleeve.areas),
    )


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(f"inkmap v{__version__}")


@app.command()
def update(
    ref: Annotated[str, typer.Option("--ref", help="Tag or branch to install.")] = "main",
) -> None:
    """Update inkmap to the latest version from GitHub."""
    typer.echo(f"current version: {__version__}", err=True)
    cmd = ["uv", "tool", "install", "--force", f"git+https://github.com/{REPO}@{ref}"]
    try:
        result = subprocess.run(cmd, check=False)
    except FileNotFoundError as e:
        raise fail("uv is not installed. See https://docs.astral.sh/uv/") from e
    if result.returncode != 0:
        raise typer.Exit(1)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
