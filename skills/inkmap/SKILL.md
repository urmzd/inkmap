---
name: inkmap
description: >
  Map photos or a video of a tattooed arm onto a 3D model with the inkmap CLI: pull sharp
  frames, place control points, build the viewer, and check the result. Use when someone
  wants to see their existing tattoos on a 3D arm, find the bare skin left for new work,
  or try a design on the arm before a session. Do NOT use for drawing the design itself.
argument-hint: "<video or photo folder>"
metadata:
  title: Map tattoos with inkmap
  category: tools
---

# Map tattoos with inkmap

## What you produce

One HTML page with a 3D arm that carries the person's existing ink, outlines around the bare
areas, and controls to place new designs. It works offline and can be sent to a tattoo artist.

## Steps

1. **Get the source.** Ask for a slow video of the arm turning a full circle, sleeve rolled up,
   arm straight, plain wall behind it, even light. Photos work too: at least four sides.
2. **Pull frames.** `inkmap frames video.mp4 --out frames --count 12`
3. **Choose three to five frames.** Each must show a different side. Prefer frames where the
   arm is sharp and fully in view. Look at every frame yourself before you choose.
4. **Read coordinates.** `inkmap grid frames/frame-00168.png` writes a copy with a pixel grid.
5. **Write the project file.** One `[[photo]]` table per frame, with points from the shoulder
   end to the wrist end. See the format below.
6. **Build.** `inkmap build project.toml --out arm.html --debug debug`
7. **Check the strips.** Open `debug/strip-<photo>.jpg`. Fix the points and build again until
   each strip passes the checks below.
8. **Check the map.** Open `debug/map.jpg`, then open `arm.html` and turn the arm.
9. **Report honestly.** Say how much of the skin was seen, and that hatched skin is unknown.

## Control points

Each point is `[x, y, half_width, v, u]`.

| Value | Meaning | How to find it |
|-------|---------|----------------|
| `x, y` | Centre of the arm, in pixels | Halfway between the two edges of the arm |
| `half_width` | Half the arm width, in pixels | Measure across the arm, not along the image axes |
| `v` | Along the arm: 0 shoulder, 0.5 elbow, 1 wrist | Start from the elbow at 0.5 |
| `u` | Around the arm: 0 front, 0.25 outer, 0.5 back, 0.75 inner | See "Which side" below |

Rules:

- Put a point at the elbow, at each end of the visible arm, and wherever the arm bends or
  changes width.
- For a tilted arm, `half_width` is the vertical half-extent times the cosine of the tilt.
- Estimate a slightly narrow width. A wide one pulls the wall into the map.
- Give a shared landmark the same `v` in every photo. This matters more than exact ends.

## Which side faces the camera

1. Find the point of the elbow. It is `u = 0.5`.
2. Turn the photo in your head so the shoulder is at the top. Then `u` grows to the right.
3. If the elbow point is at the centre of the arm, the photo's `u` is 0.5.
4. If the elbow point is toward the right edge, the photo's `u` is lower than 0.5.
   At the edge of the visible band the difference is about 0.2.
5. For a photo that does not show the elbow point, use a tattoo that is also in a photo you
   already placed. Work out its `u` there, then solve for this photo.
6. Do not assign a side from anatomy alone. A raised arm rotates. Trust what sits next to what.
7. Give the forearm its own `u` when the hand is turned differently between photos.

## Checks on a strip

- **No grey at the sides.** Grey is wall. Narrow `half_width` or move the centre.
- **Straight things stay straight.** A line of text that bends means a missing control point.
- **Text is not mirrored.** If it is, the source image was mirrored. Flip the photo first.
- **A landmark sits at the same height** in two strips that both show it.

## Checks on the map

- **Patterns continue across photos.** A step at a seam means the `u` values disagree.
- **Outlines sit on skin you would call bare.** If they sit on highlights inside a dense
  piece, lower `max_v` or `max_ink` in a `[detect]` table.
- **A bare area you can see has no outline.** Raise `max_edges` a little. Shadows on a bony
  elbow raise the edge count.

## Limits to state

- Left arm only. A generic arm, not a scan.
- Positions can be off by a few centimetres.
- Never commit or upload the person's photos or map.
