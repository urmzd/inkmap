import numpy as np

from inkmap.project import load
from inkmap.unwrap import U, V, build_map, render_base, render_outline, viewer_data


def cell(u, v):
    return int(v * V), int(u * U)


def test_ink_lands_where_the_photo_has_it(arm_photo, project_file):
    _, (u_lo, u_hi, v_lo, v_hi) = arm_photo
    sleeve = build_map(load(project_file))

    inside = sleeve.ink[
        cell(0, v_lo + 0.03)[0] : cell(0, v_hi - 0.03)[0],
        cell(u_lo + 0.02, 0)[1] : cell(u_hi - 0.02, 0)[1],
    ]
    around = sleeve.ink[cell(0, 0.55)[0] : cell(0, 0.65)[0], cell(0.46, 0)[1] : cell(0.56, 0)[1]]
    assert inside.mean() < 0.08, "the bare window must read as bare"
    assert around.mean() > 0.3, "the line work must read as ink"


def test_only_the_camera_side_is_seen(project_file):
    sleeve = build_map(load(project_file))
    assert sleeve.seen[cell(0.5, 0.5)], "the back faces the camera"
    assert not sleeve.seen[cell(0.0, 0.5)], "the front is hidden"
    assert not sleeve.seen[cell(0.5, 0.02)], "above the first point nothing is known"
    assert 0.25 < sleeve.seen_fraction < 0.5  # 144 degrees of 360, over most of the length


def test_bare_window_is_found_and_named(arm_photo, project_file):
    _, (u_lo, u_hi, v_lo, v_hi) = arm_photo
    sleeve = build_map(load(project_file))
    assert len(sleeve.areas) == 1
    area = sleeve.areas[0]
    assert area.name == "Upper arm, back"
    assert u_lo < area.u < u_hi and v_lo < area.v < v_hi
    assert sleeve.bare[cell(area.u, area.v)]
    assert not sleeve.bare[cell(0.5, 0.6)], "inked skin is not bare"


def test_the_wall_is_not_mistaken_for_skin(arm_photo, tmp_path):
    """Control points that are too wide reach onto the wall. The wall must not count as arm."""
    path, _ = arm_photo
    toml = tmp_path / "wide.toml"
    toml.write_text(
        f'[[photo]]\nfile = "{path.name}"\n'
        "points = [[200, 60, 150, 0.1, 0.5], [200, 840, 150, 0.9, 0.5]]\n"
    )
    sleeve = build_map(load(toml))
    edge = cell(0.5 + 0.19, 0.5)  # near the limit of the visible band: on the wall here
    assert not sleeve.seen[edge]


def test_renders_have_the_map_shape(project_file):
    sleeve = build_map(load(project_file))
    assert render_base(sleeve).size == (U, V)
    outline = np.asarray(render_outline(sleeve))
    assert outline.shape == (V, U, 4) and outline[..., 3].max() > 200
    data = viewer_data(sleeve)
    assert data["base"].startswith("data:image/jpeg;base64,")
    assert data["zones"][0]["name"] == "Upper arm, back"
