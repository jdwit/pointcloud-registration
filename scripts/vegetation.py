#!/usr/bin/env python3
"""Find trees and shrubs in a colour scan, for shading studies.

Leaves are the one thing in a garden that is reliably greener than everything
around it, so the excess green index separates them from brick, roof and
paving without any training. Cluster what is left and each tree becomes an
object with a position, a footprint and a height, which is what a solar study
needs to model the shade.

    python vegetation.py exterior.ply --ground 12.345 [--out veg.ply]
"""
import argparse

import numpy as np

import pcloud as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--ground", type=float, default=None)
    ap.add_argument("--exg", type=float, default=18.0, help="threshold on 2G - R - B, 0..255")
    ap.add_argument("--eps", type=float, default=0.6)
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    import open3d as o3d

    xyz, rgb = pc.read_any(args.src)
    c = rgb * 255.0
    exg = 2 * c[:, 1] - c[:, 0] - c[:, 2]
    m = exg > args.exg
    print(f"{args.src}: {len(xyz):,} points, green {int(m.sum()):,} ({m.mean() * 100:.1f}%)")
    g = args.ground if args.ground is not None else np.percentile(xyz[:, 2], 1)

    veg = o3d.geometry.PointCloud()
    veg.points = o3d.utility.Vector3dVector(xyz[m])
    veg.colors = o3d.utility.Vector3dVector(rgb[m])
    d = veg.voxel_down_sample(0.10)
    lab = np.array(d.cluster_dbscan(eps=args.eps, min_points=args.min_points, print_progress=False))
    dp = np.asarray(d.points)
    objects = []
    for k in range(lab.max() + 1):
        q = dp[lab == k]
        if len(q) < 200:
            continue
        objects.append({"points": len(q),
                        "centre_xy": np.round(q[:, :2].mean(0), 2).tolist(),
                        "footprint_m": np.round(q[:, :2].max(0) - q[:, :2].min(0), 2).tolist(),
                        "top_above_ground_m": round(float(q[:, 2].max() - g), 2),
                        "base_above_ground_m": round(float(q[:, 2].min() - g), 2)})
    objects.sort(key=lambda o: -o["points"])
    print(f"{len(objects)} vegetation objects above the noise:")
    for o in objects:
        print(f"  at {o['centre_xy']}, footprint {o['footprint_m']} m, "
              f"top {o['top_above_ground_m']:+.2f} m above ground, {o['points']:,} points")
    if args.out:
        pc.write_ply(args.out, xyz[m], rgb[m])
        print(f"written: {args.out}")
    if args.json:
        pc.save_json(args.json, {"source": args.src, "ground": g, "exg_threshold": args.exg,
                                 "objects": objects})


if __name__ == "__main__":
    main()
