"""Assemble the single-file viewer page."""

from __future__ import annotations

import base64
import html
import json
from importlib import resources

from inkmap.project import Project
from inkmap.unwrap import SleeveMap, viewer_data


def build_html(project: Project, sleeve: SleeveMap) -> str:
    """Return one self-contained HTML page: 3D library, arm mesh and map are all inside.

    The page must open from a file:// URL with no network, so nothing is linked.
    """
    assets = resources.files("inkmap.assets")
    page = assets.joinpath("viewer.html").read_text()
    three = base64.b64encode(assets.joinpath("three.module.min.js").read_bytes()).decode()
    arm = assets.joinpath("arm-left.json").read_text()
    parts = {
        "__TITLE__": html.escape(project.name),
        "__SLUG__": html.escape(project.slug, quote=True),
        "__THREE_B64__": three,
        "__ARM_JSON__": arm,
        "__MAP_JSON__": json.dumps(viewer_data(sleeve)),
    }
    for key, value in parts.items():
        if key not in page:
            raise RuntimeError(f"viewer template has no {key} placeholder")
        page = page.replace(key, value)
    return page
