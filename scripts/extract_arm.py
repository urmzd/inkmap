"""Build the arm mesh for the viewer from the MakeHuman base mesh (CC0).

Usage:
    python scripts/extract_arm.py base.obj src/inkmap/assets/arm-left.json [cut]

`cut` moves the shoulder cut outward, in decimetres from the shoulder joint (default 0.05).
Needs numpy, trimesh, scipy, networkx, shapely and rtree. See AGENTS.md for the full command
and for why each step is there.

Steps: keep the body faces near the arm, cut the shoulder with a vertical plane, push the
surface out along its normals to thicken it, smooth it twice (Loop), compute the sleeve
coordinates around a smooth spine, stand the arm upright, add a flat cut face, split the seam.
"""

import sys, json, base64, collections
import numpy as np, trimesh

src, out = sys.argv[1], sys.argv[2]
CUT = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05
verts, faces, groups, g = [], [], collections.defaultdict(list), "none"
for line in open(src):
    p = line.split()
    if not p: continue
    if p[0] == "v": verts.append([float(x) for x in p[1:4]])
    elif p[0] == "g": g = p[1]
    elif p[0] == "f":
        idx = [int(t.split("/")[0]) - 1 for t in p[1:]]
        groups[g].append(idx)
V = np.array(verts)
joint = lambda n: V[np.unique(np.array(groups[n]).ravel())].mean(axis=0)
Sh, El, Wr = joint("joint-l-shoulder"), joint("joint-l-elbow"), joint("joint-l-hand")
print("joints", Sh.round(2), El.round(2), Wr.round(2), "| body bounds", V.min(0).round(2), V.max(0).round(2))
d1, d2 = El - Sh, Wr - El
L1, L2 = np.linalg.norm(d1), np.linalg.norm(d2); d1 /= L1; d2 /= L2
print("upper", L1.round(2), "fore", L2.round(2), "bend deg", np.degrees(np.arccos(d1 @ d2)).round(1))

body = [f for f in groups["body"]]
tris = []
for f in body:
    for k in range(1, len(f) - 1): tris.append([f[0], f[k], f[k + 1]])
tris = np.array(tris)

# keep faces near the arm axis: past the shoulder plane and within a radius of the shoulder-wrist polyline
def axis_dist(P):
    out = np.full(len(P), 1e9)
    for A, d, L in ((Sh, d1, L1), (El, d2, L2 * 1.9)):
        t = np.clip((P - A) @ d, 0, L); out = np.minimum(out, np.linalg.norm(P - (A + np.outer(t, d)), axis=1))
    return out
keepv = axis_dist(V) < 1.7
keepf = keepv[tris].all(axis=1)
m = trimesh.Trimesh(V, tris[keepf], process=False); m.remove_unreferenced_vertices()
# clean armhole cut: a vertical plane just outside the shoulder joint, like a sleeveless shirt
m = trimesh.intersections.slice_mesh_plane(m, plane_normal=[1.0, 0, 0], plane_origin=[Sh[0] + CUT, 0, 0], cap=False)
m.merge_vertices()
parts = m.split(only_watertight=False); m = max(parts, key=lambda q: len(q.faces))
m = trimesh.Trimesh(np.array(m.vertices), np.array(m.faces), process=False)
print("arm part", len(m.vertices), "verts", len(m.faces), "faces", "watertight", m.is_watertight)

# smooth spine: straight upper arm, rounded elbow, straight forearm that runs on through the hand
ra = 0.9
def spine():
    pts = [Sh - d1 * 1.0 + d1 * k * (1.0 + L1 - ra) / 400 for k in range(400)]
    P0, P1, P2 = El - d1 * ra, El, El + d2 * ra
    pts += [(1 - s) ** 2 * P0 + 2 * s * (1 - s) * P1 + s * s * P2 for s in np.linspace(0, 1, 400, endpoint=False)]
    pts += [P2 + d2 * k * (L2 * 1.9 - ra) / 900 for k in range(901)]
    C = np.array(pts); T = np.gradient(C, axis=0); T /= np.linalg.norm(T, axis=1)[:, None]
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    return C, T, arc
SC, ST, SA = spine()
iS = int(np.argmin(np.linalg.norm(SC - Sh, axis=1))); iE = 400 + 200; iW = int(np.argmin(np.linalg.norm(SC - Wr, axis=1)))
aS, aE, aW = SA[iS], SA[iE], SA[iW]
up, front = np.array([0, 1.0, 0]), np.array([0, 0, 1.0])
SF = front[None, :] - (ST @ front)[:, None] * ST; SF /= np.linalg.norm(SF, axis=1)[:, None]
SL = np.cross(ST, SF); SL *= np.sign(SL @ up)[:, None]
def sleeve(Pp):
    near = np.empty(len(Pp), int)
    for s in range(0, len(Pp), 2000):
        chunk = Pp[s:s + 2000]; near[s:s + 2000] = np.argmin(((chunk[:, None, :] - SC[None]) ** 2).sum(-1), axis=1)
    a = SA[near] - aS
    v = np.where(a < aE - aS, 0.5 * a / (aE - aS), 0.5 + 0.5 * (a - (aE - aS)) / (aW - aE))
    r = Pp - SC[near]
    u = (np.arctan2((r * SL[near]).sum(1), (r * SF[near]).sum(1)) / (2 * np.pi)) % 1.0
    return u, v, np.linalg.norm(r, axis=1)

# bulk the arm up: push the surface out along its normals, fading to nothing at the wrist
_, vb, _ = sleeve(np.array(m.vertices))
w = np.clip((1.0 - vb) / 0.2, 0, 1); w = w * w * (3 - 2 * w)
m = trimesh.Trimesh(np.array(m.vertices) + np.array(m.vertex_normals) * (0.10 * w)[:, None], m.faces, process=False)

v2, f2 = trimesh.remesh.subdivide_loop(m.vertices, m.faces, iterations=2)
m = trimesh.Trimesh(v2, f2, process=False)
print("subdivided", len(m.vertices), "verts", len(m.faces), "faces")
P, N = np.array(m.vertices), np.array(m.vertex_normals)
near0 = np.argmin(((P[::50, None, :] - SC[None]) ** 2).sum(-1), axis=1)
if ((P[::50] - SC[near0]) * N[::50]).sum(1).mean() < 0:
    m = trimesh.Trimesh(P, np.array(m.faces)[:, ::-1], process=False); N = np.array(m.vertex_normals); print("flipped faces")
uu, vv, rr = sleeve(P)
# flat cut face at the shoulder, with its own normals so the edge stays crisp
F0 = np.array(m.faces)
es = np.sort(np.concatenate([F0[:, [0, 1]], F0[:, [1, 2]], F0[:, [2, 0]]]), axis=1)
uq, ct = np.unique(es, axis=0, return_counts=True); bnd = uq[ct == 1]
adj = collections.defaultdict(list)
for a_, b_ in bnd: adj[int(a_)].append(int(b_)); adj[int(b_)].append(int(a_))
loop, prev, cur = [int(bnd[0][0])], None, int(bnd[0][0])
while True:
    nxt = [n for n in adj[cur] if n != prev and n not in loop]
    if not nxt: break
    prev, cur = cur, nxt[0]; loop.append(cur)
print("cut rim", len(loop), "of", len(adj), "boundary verts; plane spread", np.ptp(P[loop][:, 0]).round(4))
capN = np.array([-1.0, 0, 0]); cen = P[loop].mean(axis=0)
n0 = len(P); ring_idx = list(range(n0, n0 + len(loop))); cidx = n0 + len(loop)
P = np.vstack([P, P[loop], cen[None]]); N = np.vstack([N, np.tile(capN, (len(loop) + 1, 1))])
uu = np.concatenate([uu, uu[loop], [0.0]]); vv = np.concatenate([vv, np.full(len(loop) + 1, -1.0)]); rr = np.concatenate([rr, rr[loop], [0.0]])
capF = []
for i in range(len(loop)):
    a_, b_ = ring_idx[i], ring_idx[(i + 1) % len(loop)]
    tri = [a_, b_, cidx]
    if np.cross(P[b_] - P[a_], P[cidx] - P[a_]) @ capN < 0: tri = [b_, a_, cidx]
    capF.append(tri)
ALLF = np.vstack([np.array(m.faces), np.array(capF)])
print("v range", vv.min().round(2), vv.max().round(2))

# stand the arm up: shoulder at the top, wrist straight below, front still facing +Z
dall = Wr - Sh; dall /= np.linalg.norm(dall)
y = -dall; z = front - (front @ y) * y; z /= np.linalg.norm(z); x = np.cross(y, z)
R = np.stack([x, y, z]); scale = 10.0
P = ((P - Sh) @ R.T) * scale; N = N @ R.T
print("bounds cm", P.min(0).round(1), P.max(0).round(1))

# circumference by position along the arm
bins = 64; circ = []
for i in range(bins):
    sel = (vv >= i / bins) & (vv < (i + 1) / bins) & (vv >= 0) & (vv <= 1)
    circ.append(float(2 * np.pi * rr[sel].mean() * scale) if sel.sum() > 4 else 0.0)
for i in range(bins):
    if circ[i] == 0: circ[i] = next((c for c in circ[i:] if c), 0) or next((c for c in reversed(circ[:i]) if c), 25.0)
print("circumference cm: shoulder %.1f bicep %.1f elbow %.1f forearm %.1f wrist %.1f" % (circ[2], circ[14], circ[32], circ[40], circ[62]))

# split the seam: triangles that cross u = 0/1 get their own vertices with u shifted by one
uu[n0:] = 0.25
F = ALLF; pos, nrm, uv, idx = list(P), list(N), [[a, b] for a, b in zip(uu, vv)], []
cache = {}
for tri in F:
    us = uu[tri]
    if us.max() - us.min() > 0.5:
        new = []
        for k in tri:
            if uu[k] < 0.5:
                if k not in cache:
                    cache[k] = len(pos); pos.append(P[k]); nrm.append(N[k]); uv.append([uu[k] + 1, vv[k]])
                new.append(cache[k])
            else: new.append(int(k))
        idx.append(new)
    else: idx.append([int(k) for k in tri])
pos, nrm, uv, idx = np.array(pos, np.float32), np.array(nrm, np.float32), np.array(uv, np.float32), np.array(idx, np.uint16)
b64 = lambda a: base64.b64encode(a.tobytes()).decode()
json.dump({"pos": b64(pos), "nrm": b64((np.clip(nrm, -1, 1) * 127).astype(np.int8)), "uv": b64(uv), "idx": b64(idx),
           "count": len(pos), "circ": [round(c, 2) for c in circ], "length": round(float((aW - aS) * scale), 2)}, open(out, "w"))
print("wrote", out, len(pos), "verts", len(idx), "tris")
