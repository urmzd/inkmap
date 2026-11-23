"""Map photos of existing tattoos onto a 3D body model and find the bare skin."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("inkmap")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
