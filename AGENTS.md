# AGENTS.md

## Identity

**inkmap** maps photos of existing tattoos onto a 3D arm, finds the bare skin, and lets a person try new designs on it. It is a Python CLI that writes one self-contained HTML viewer.

## Architecture

```text
video ──frames──▶ photos ──grid──▶ project.toml (control points, by hand)
                                        │
                                      build
                                        │
        photo + points ──unwrap──▶ strip per photo ──stitch──▶ sleeve map (ink, seen)
                                                                   │
                                                              find bare areas
                                                                   │
              arm mesh + three.js + map ──────────────────▶ one viewer.html
```

- **Sleeve map.** A grid over `(v, u)`. `v` runs along the arm: 0 shoulder, 0.5 elbow, 1 wrist. `u` runs around it: 0 front, 0.25 outer, 0.5 back, 0.75 inner. Everything meets in this space: photos unwrap into it, the mesh carries it as texture coordinates, and the viewer draws designs in it.
- **Unwrap.** Each photo is a view of a cylinder. A texel at angle `t` from the centre line samples the pixel at `centre + across * half_width * sin(t)`. Only the middle 144 degrees are used.
- **Stitch.** Where photos overlap, the most face-on one wins (weight to the fourth power). Averaging gives ghosts, because the hand-placed points never agree exactly.
- **Viewer.** The page paints the baked map, then the user's designs, then the outlines, onto one canvas texture. Designs are drawn in centimetres, so they keep their shape where the arm gets thinner.

Use `tree` and `rg` to find files. Do not add a directory listing here.

## Commands

```sh
just init      # uv sync --group dev
just check     # ruff format, ruff check, pytest
just example   # build examples/synthetic into out/
just demo      # capture showcase/ images from the example (Node 22+, Chrome)
uv run inkmap build PROJECT.toml --out arm.html --debug debug
```

Rebuild the arm mesh (rarely needed):

```sh
curl -fsSLO https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/3dobjs/base.obj
uv run --no-project --with numpy --with trimesh --with scipy --with networkx --with shapely --with rtree \
  python scripts/extract_arm.py base.obj src/inkmap/assets/arm-left.json 0.05
```

## Code Style

- Python 3.12, `uv` only, `ruff` for format and lint, line length 100.
- CLI is `typer`. Results go to stdout as JSON with `--format json`, and to stderr as plain text otherwise.
- Keep `unwrap.py` free of file-format and CLI concerns. It takes a `Project` and returns arrays.
- The viewer is one HTML file with no build step and no network access. Nothing may be linked from a CDN.
- Comments say why. The cylinder maths and the detection thresholds need the reason next to them.
- Prose in docs: short sentences, active voice, no em dashes.

## Verification

- `just check` must pass.
- A change to `unwrap.py` needs a look at the output: run `just example` and open `out/debug/map.jpg`. The lattice must cross the seams between photos without a break. A break means the handedness or the stitching is wrong.
- A change to the viewer needs a look in a real browser, in light and dark, at desktop and phone width. `scripts/capture.mjs` shows how to drive headless Chrome with no dependencies. The page exposes `window.inkmap` for that purpose.

## Extension Guide

- **A new body part.** Add a mesh JSON next to `arm-left.json` with the same fields (`pos`, `nrm`, `uv`, `idx`, `circ`, `length`). The `uv` attribute must hold the same `(u, v)` sleeve coordinates. Then pass the mesh name through `Arm.load` and `viewer.build_html`.
- **A right arm.** Mirror the mesh in x and replace `u` with `1 - u`. Then check with a letter "F" design that nothing shows mirrored.
- **Automatic control points.** This is the largest gap. Any method must output the same `[x, y, half_width, v, u]` rows, so the rest of the pipeline does not change.
- **A new detection rule.** Add a key to `Detect` in `project.py`, use it in `find_bare`, and add a row to the README table.

## Lessons

These cost time to learn. Read them before you change the mapping.

### Mapping photos

- **Anchor on the elbow point.** It is the one landmark that is easy to see in most photos. Define it as `u = 0.5` and place every photo relative to it.
- **Handedness rule.** For a left arm seen from outside with the shoulder up, `u` grows to the viewer's right. In code, with `a` the shoulder-to-wrist direction in the image, `u` grows along `(a.y, -a.x)`. If the arm points up in the photo, `u` grows to the left.
- **Place by what is next to what, not by anatomy.** Guessing "this is the inner arm" from the pose was wrong twice. A raised arm rotates, so the triceps can face the camera. Trust which tattoo sits next to which, across photos.
- **The forearm twists.** The skin of the forearm turns against the upper arm when the hand turns. One `u` per photo is not enough, so `u` is set per control point.
- **Check for a mirrored source.** A phone's rear camera pointed at a mirror gives a mirrored image. A front-camera video is normally saved unmirrored. Find some text in the tattoo: if it reads correctly, the frame is not mirrored.
- **Perspective changes the scale along the arm.** The end near the camera is larger. Use several control points, and tie a shared landmark (a star, a letter) to the same `v` in every photo.
- **Widths that are too large pull in the wall.** The unwrap then reads wall as bare skin. The colour test (grey and bright is wall) removes most of it. Prefer a slightly narrow width.
- **Sharp frames are the pauses.** A turning arm blurs in between. `frames` takes the sharpest frame in each time window for that reason.

### Finding bare skin

- **Ink has hard edges. Shadows do not.** Darkness alone cannot tell a shaded elbow from a tattoo. Edge density can.
- **Highlights inside realism work are not bare skin.** A dense forearm piece has skin-toned highlights. `max_v` stops the search above the forearm for that reason. Lower it or raise it per person.
- **Unknown is not bare.** Skin that no photo showed must stay hatched. Filling it with skin colour looks finished and is wrong.
- **Normalise against local skin tone.** Lighting changes along and around the arm. Ink is measured as "darker than the brightest skin nearby", not as an absolute grey.

### The arm mesh

- **A procedural tube reads as a leg.** A real hand is what makes it an arm. The mesh comes from the MakeHuman base mesh, which is CC0.
- **Cut the shoulder with a vertical plane**, like a sleeveless shirt. A plane across the arm axis takes part of the chest with it.
- **Map around a smooth spine, not two straight bones.** With two segments, the `v` coordinate folds over itself on the outside of a bent elbow. The spine is two lines joined by a curve whose radius is larger than the arm.
- **Thicken along the normals.** Scaling about the bone axes leaves a step at the elbow.
- **Split the seam.** Triangles that cross `u = 0` get their own vertices with `u + 1`, and the texture repeats in `u`.
- **Give the cut face its own vertices and normals**, so the edge stays crisp. Smoothing a fan of 50 thin triangles gives a puckered cap.

### The viewer

- **`file://` blocks module imports from other files.** The three.js module is stored as base64 in the page and imported from a blob URL.
- **Draw every design three times**, at `u - 1`, `u` and `u + 1`, so it wraps across the seam.
- **Update the camera matrix before a raycast.** A click right after a view change otherwise hits the old view.
- **Multiply blending turns white paper into skin.** A dark drawing on white needs no cut-out. Levels are stretched per channel first, so off-white paper also vanishes.
- **Keep the user's work in `localStorage`, keyed by project.** It does not travel with the file. Say so when the file is shared.

### Tooling

- **zsh ties `$path` to `$PATH`.** A loop variable named `path` empties the command path.
- **zsh does not split unquoted variables.** Use an array for a list of frame numbers.
- **Homebrew ffmpeg may lack `drawtext`.** Draw labels with Pillow instead.
- **A browser automation server may already hold its profile.** Driving headless Chrome over the DevTools protocol with Node's built-in `WebSocket` needs no extra tool.

## Privacy

Photos and maps of a real person never go into this repository, an issue, or a screenshot. Test with `examples/synthetic`. If a real map is needed to reproduce a bug, keep it local.
