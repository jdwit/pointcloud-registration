#!/usr/bin/env python3
"""Build two synthetic scans of the same room and register them.

No data of your own needed: this writes two clouds of one 6 by 4 m room, the
second rotated and shifted the way two phone scans of the same building differ,
runs align.py on them, and checks that the known transform comes back.

    uv run --python 3.11 --with open3d --with numpy --with scipy \
        --with matplotlib python demo/demo.py
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pcloud as pc  # noqa: E402

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
TRUE_YAW = 90.4          # what ARKit does to you between two sessions
TRUE_SHIFT = np.array([3.2, -1.7, 0.0])
NOISE_M = 0.003


def room(width=6.0, depth=4.0, height=2.7, step=0.012, seed=0):
    """Walls, floor and ceiling of one rectangular room, plus a partition."""
    rng = np.random.default_rng(seed)
    pts = []
    u = np.arange(0, width, step)
    v = np.arange(0, depth, step)
    z = np.arange(0, height, step)
    for y in (0.0, depth):
        uu, zz = np.meshgrid(u, z)
        pts.append(np.c_[uu.ravel(), np.full(uu.size, y), zz.ravel()])
    for x in (0.0, width):
        vv, zz = np.meshgrid(v, z)
        pts.append(np.c_[np.full(vv.size, x), vv.ravel(), zz.ravel()])
    # a partition and an alcove, so the plan is asymmetric and the match
    # cannot flip the room end for end
    zz, vv = np.meshgrid(z, np.arange(0, depth * 0.55, step))
    pts.append(np.c_[np.full(vv.size, width * 0.35), vv.ravel(), zz.ravel()])
    uu, zz = np.meshgrid(np.arange(width * 0.6, width, step), z)
    pts.append(np.c_[uu.ravel(), np.full(uu.size, depth * 0.7), zz.ravel()])
    vv, zz = np.meshgrid(np.arange(depth * 0.7, depth, step), z)
    pts.append(np.c_[np.full(vv.size, width * 0.6), vv.ravel(), zz.ravel()])
    for zc in (0.0, height):
        uu, vv = np.meshgrid(u[::3], v[::3])
        pts.append(np.c_[uu.ravel(), vv.ravel(), np.full(uu.size, zc)])
    p = np.vstack(pts)
    return p + rng.normal(0, NOISE_M, p.shape)


def main():
    a = room(seed=1)
    b = room(seed=2)
    T = pc.yaw_matrix(TRUE_YAW, TRUE_SHIFT)
    b = pc.apply(T, b)

    HERE.mkdir(exist_ok=True)
    pc.write_ply(HERE / "scan-a.ply", a, np.full_like(a, 0.6))
    pc.write_ply(HERE / "scan-b.ply", b, np.full_like(b, 0.6))
    print(f"wrote two synthetic scans of {len(a):,} points each")
    print(f"scan-b is scan-a rotated {TRUE_YAW} deg and moved {TRUE_SHIFT} m\n")

    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "align.py"), str(HERE / "scan-b.ply"),
         str(HERE / "scan-a.ply"), str(HERE / "aligned.ply"),
         "--json", str(HERE / "transform.json"), "--band", "0.3", "2.4"],
        check=True, text=True, capture_output=True)
    print(out.stdout)

    import json
    got = json.load(open(HERE / "transform.json"))
    yaw_err = (got["yaw_deg"] + TRUE_YAW) % 360
    yaw_err = min(yaw_err, 360 - yaw_err)
    t = np.array(got["transform"])[:3, 3]
    back = pc.apply(np.array(got["transform"]), pc.apply(T, np.zeros((1, 3))))[0]
    print(f"recovered yaw {got['yaw_deg']:.3f} deg against a true {TRUE_YAW} deg "
          f"applied to the source, so the residual rotation is {yaw_err:.3f} deg")
    print(f"a point that was at the origin lands {np.abs(back) * 1000} mm from it")
    print(f"median residual after registration: {got['median_residual_mm']:.1f} mm")

    ok = yaw_err < 0.15 and np.abs(back).max() < 0.05
    print("\nDEMO OK" if ok else "\nDEMO FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
