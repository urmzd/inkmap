#!/bin/sh
# install.sh: installs the inkmap CLI with uv from GitHub.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/urmzd/inkmap/main/install.sh | sh
#
# Environment variables:
#   INKMAP_VERSION: git ref to install (branch, tag, or commit, e.g. "v0.1.0"); defaults to "main"

set -eu

REPO="urmzd/inkmap"

err() {
    echo "Error: $1" >&2
    exit 1
}

main() {
    if ! command -v uv >/dev/null 2>&1; then
        err "uv is required but not found on PATH. Install it from https://docs.astral.sh/uv/ and run this script again."
    fi

    ref="${INKMAP_VERSION:-main}"

    echo "Installing inkmap ($ref) with uv..."
    uv tool install --force "git+https://github.com/${REPO}@${ref}"

    if command -v inkmap >/dev/null 2>&1; then
        inkmap version
    else
        echo "Installed inkmap. Run 'uv tool update-shell' and restart your shell to add it to PATH."
    fi
}

main
