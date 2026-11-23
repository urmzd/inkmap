import pytest

from inkmap.project import ProjectError, load


def test_loads_photos_and_defaults(project_file):
    proj = load(project_file)
    assert proj.name == "Test arm" and proj.slug == "test-arm"
    assert len(proj.photos) == 1 and len(proj.photos[0].points) == 2
    assert proj.detect.max_v == 0.62


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("", "at least one"),
        ('[[photo]]\nfile = "missing.png"\npoints = [[1,2,3,0,0],[1,2,3,1,0]]\n', "file not found"),
        ('[[photo]]\nfile = "arm.png"\npoints = [[1,2,3,0,0]]\n', "at least 2 points"),
        ('[[photo]]\nfile = "arm.png"\npoints = [[1,2,3,0],[1,2,3,1]]\n', "half_width, v, u"),
        (
            '[[photo]]\nfile = "arm.png"\npoints = [[1,2,3,0.9,0],[1,2,3,0.1,0]]\n',
            "shoulder to wrist",
        ),
        (
            '[detect]\nbogus = 1\n[[photo]]\nfile = "arm.png"\n'
            "points = [[1,2,3,0,0],[1,2,3,1,0]]\n",
            "unknown",
        ),
    ],
)
def test_bad_project_files_say_what_is_wrong(arm_photo, tmp_path, body, message):
    toml = tmp_path / "bad.toml"
    toml.write_text(body)
    with pytest.raises(ProjectError, match=message):
        load(toml)
