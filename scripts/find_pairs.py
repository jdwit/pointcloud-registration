#!/usr/bin/env python3
"""Which of these scans overlap, and which pair should you register first?

Scan a house room by room and you end up with twenty clouds and no idea which
ones share enough surface to be registered to each other. File names help, but
they lie: two scans called hall and entrance can be the same space or two
different floors.

This measures it. Every pair is coarsely aligned the way align.py would do it,
and scored on the share of wall points that then land within a tolerance of the
other cloud. Pairs that share a room score high, pairs that share a doorway
score low but not zero, pairs that share nothing score near zero.

Work down the ranking: register the strongest pair first, then hang the rest
off what you already have.

    python find_pairs.py clouds/*.ply [--json pairs.json] [--tol 0.10]
"""
import argparse
import itertools
from pathlib import Path

import numpy as np

import pcloud as pc


def prepare(path, voxel, band):
    xyz, _ = pc.read_any(path)
    p, n = pc.normals(xyz, voxel=voxel)
    g = pc.ground_z(p, n)
    w, wn = pc.walls(p, n, thr=0.35, zmin=g + band[0], zmax=g + band[1])
    return {"path": path, "name": Path(path).stem, "floor": g, "walls": w,
            "normals": wn, "heading": pc.manhattan(w, wn) if len(w) > 500 else None,
            "points": len(xyz), "extent": (xyz.max(0) - xyz.min(0)).round(2).tolist()}


def score_pair(a, b, tol, cell):
    """Best coarse fit of b onto a, as the share of b's walls that land on a."""
    from scipy.spatial import cKDTree
    if a["heading"] is None or b["heading"] is None:
        return None
    tree = cKDTree(a["walls"])
    dz = a["floor"] - b["floor"]
    yaw0 = (a["heading"] - b["heading"]) % 90.0
    best = None
    for q in range(4):
        deg = (yaw0 + 90 * q) % 360
        moved = b["walls"].copy()
        moved[:, :2] = b["walls"][:, :2] @ pc.rot2(deg).T
        shift, _ = pc.match_xy(a["walls"][:, :2], moved[:, :2], cell=cell)
        moved[:, :2] += shift
        moved[:, 2] += dz
        d, _ = tree.query(moved, k=1)
        hit = float((d < tol).mean())
        if best is None or hit > best[0]:
            best = (hit, deg, shift, float(np.median(d)))
    hit, deg, shift, med = best
    return {"a": a["name"], "b": b["name"], "share_within_tol": round(hit, 3),
            "median_mm": round(med * 1000, 1), "yaw_deg": round(deg, 3),
            "shift_m": np.round(shift, 3).tolist(), "dz_m": round(dz, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clouds", nargs="+")
    ap.add_argument("--tol", type=float, default=0.10)
    ap.add_argument("--band", type=float, nargs=2, default=(0.4, 2.2))
    ap.add_argument("--voxel", type=float, default=0.06)
    ap.add_argument("--cell", type=float, default=0.05)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    prepped = []
    for path in args.clouds:
        d = prepare(path, args.voxel, args.band)
        print(f"{d['name']:24s} {d['points']:>10,} points, extent {d['extent']}, "
              f"floor {d['floor']:+.2f}, {len(d['walls']):>6,} wall points, "
              f"heading {d['heading']:.2f}" if d["heading"] is not None else
              f"{d['name']:24s} no usable walls")
        prepped.append(d)

    print(f"\nscoring {len(prepped) * (len(prepped) - 1) // 2} pairs at a "
          f"{args.tol * 100:.0f} cm tolerance", flush=True)
    rows = []
    for a, b in itertools.combinations(prepped, 2):
        r = score_pair(a, b, args.tol, args.cell)
        if r:
            rows.append(r)
            print(".", end="", flush=True)
    rows.sort(key=lambda r: -r["share_within_tol"])
    print("\n\nranking, strongest first:")
    print(f"{'share':>6}  {'median':>8}  {'yaw':>8}  pair")
    for r in rows:
        mark = "  <- register these" if r["share_within_tol"] > 0.5 else ""
        print(f"{r['share_within_tol']:6.3f}  {r['median_mm']:7.0f}mm  "
              f"{r['yaw_deg']:7.2f}  {r['a']} + {r['b']}{mark}")
    print("\nA share above about 0.5 means a shared room. Between 0.2 and 0.5 is")
    print("usually a shared doorway or a sliver, worth checking by eye. Below that")
    print("the two clouds have nothing in common and the pose is meaningless.")
    if args.json:
        pc.save_json(args.json, {"tolerance_m": args.tol, "band": list(args.band),
                                 "pairs": rows})


if __name__ == "__main__":
    main()
