import json

from typer.testing import CliRunner

from inkmap import __version__
from inkmap.cli import app
from inkmap.frames import pick_sharpest

runner = CliRunner()


def test_version_command_and_flag():
    assert runner.invoke(app, ["version"]).stdout.strip() == f"inkmap v{__version__}"
    assert runner.invoke(app, ["--version"]).stdout.strip() == f"inkmap v{__version__}"


def test_build_writes_a_self_contained_page(project_file, tmp_path):
    out = tmp_path / "arm.html"
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "build",
            str(project_file),
            "--out",
            str(out),
            "--debug",
            str(tmp_path / "debug"),
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["areas"][0]["name"] == "Upper arm, back"
    page = out.read_text()
    assert "<title>Test arm</title>" in page
    for placeholder in ("__TITLE__", "__SLUG__", "__THREE_B64__", "__ARM_JSON__", "__MAP_JSON__"):
        assert placeholder not in page
    assert "http://" not in page.split("<script")[0], "the page must not link to the network"
    assert (tmp_path / "debug" / "map.jpg").is_file()
    assert (tmp_path / "debug" / "strip-arm.jpg").is_file()


def test_build_reports_a_bad_project(tmp_path):
    result = runner.invoke(app, ["build", str(tmp_path / "nope.toml")])
    assert result.exit_code == 1
    assert "project file not found" in result.output


def test_grid_writes_next_to_the_photo(arm_photo):
    path, _ = arm_photo
    result = runner.invoke(app, ["grid", str(path)])
    assert result.exit_code == 0
    assert path.with_name("arm-grid.png").is_file()


def test_pick_sharpest_takes_one_frame_per_window():
    scores = [5, 1, 5, 5, 5, 0.5, 5, 5, 2, 5]
    assert pick_sharpest(scores, 2) == [1, 5]
    assert pick_sharpest(scores, 20) == list(range(10))
    assert pick_sharpest([], 3) == []
