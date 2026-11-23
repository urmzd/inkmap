default: check

init:
    uv sync --group dev

build:
    uv build

test:
    uv run pytest

lint:
    uv run ruff check .

fmt:
    uv run ruff format .

typecheck:
    uv run ty check src/

check: fmt lint test

run *args="":
    uv run inkmap {{args}}

# Build the viewer page for the synthetic example
example:
    uv run python examples/synthetic/make_photos.py
    uv run inkmap build examples/synthetic/project.toml --out out/synthetic.html --debug out/debug

# Capture the README images from the example (needs Node 22+ and Chrome)
demo: example
    node scripts/capture.mjs out/synthetic.html showcase
