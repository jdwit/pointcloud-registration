#!/usr/bin/env python3
"""Remove outliers, fragments outside the shell, and loose clusters.

Three kinds of rubbish, three remedies:

  statistical outliers   sensor noise, sparse and isolated
  fragments outside      what escaped through a window or an open door
  loose clusters         everything not connected to the building

The outline used for clipping is built from wall points only. Build it from
all points and the escaped fragments push the outline outwards, so nothing
gets clipped. With --outline you clip on an external reference instead,
such as a footprint from a survey or a model, which is stronger because it does
not come from the scan being cleaned.

    python clean.py in.ply out.ply [--outline ref.ply|ref.xyz] [--margin 0.20]
                    [--min-cluster 2000] [--json report.json]
"""
import argparse

import numpy as np

import pcloud as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--outline", default=None, help="reference cloud for the footprint")
    ap.add_argument("--margin", type=float, default=0.20)
    ap.add_argument("--cell", type=float, default=0.10)
    ap.add_argument("--nb-neighbors", type=int, default=20)
    ap.add_argument("--std-ratio", type=float, default=2.0)
    ap.add_argument("--min-cluster", type=int, default=0, help="0 disables cluster filtering")
    ap.add_argument("--eps", type=float, default=0.25)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    import open3d as o3d
    from scipy.spatial import cKDTree

    xyz, rgb = pc.read_any(args.src)
    n0 = len(xyz)
    print(f"{args.src}: {n0:,} points")

    if args.outline:
        ref, _ = pc.read_any(args.outline)
        ref_xy = ref[:, :2]
        closing = 7
    else:
        p, n = pc.normals(xyz, voxel=0.05, radius=0.15)
        w, _ = pc.walls(p, n)
        ref_xy = w[:, :2]
        closing = 21
    keep, area = pc.footprint_mask(ref_xy, xyz[:, :2], cell=args.cell,
                                   margin=args.margin, closing=closing)
    print(f"outline {area:.0f} m2 including the {args.margin} m margin; "
          f"outside it: {int((~keep).sum()):,} points ({(~keep).mean() * 100:.1f}%)")
    xyz, rgb = xyz[keep], rgb[keep]

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(xyz)
    cloud.colors = o3d.utility.Vector3dVector(rgb)
    cloud, _ = cloud.remove_statistical_outlier(nb_neighbors=args.nb_neighbors,
                                                std_ratio=args.std_ratio)
    n_out = len(xyz) - len(cloud.points)
    print(f"statistical outliers: {n_out:,} removed")
    xyz = np.asarray(cloud.points)
    rgb = np.asarray(cloud.colors)

    n_frag = 0
    if args.min_cluster > 0:
        d = cloud.voxel_down_sample(0.05)
        lab = np.array(d.cluster_dbscan(eps=args.eps, min_points=15, print_progress=False))
        dp = np.asarray(d.points)
        sizes = np.bincount(lab[lab >= 0]) if (lab >= 0).any() else np.array([0])
        big = set(np.where(sizes > args.min_cluster)[0].tolist())
        print(f"clusters: {len(sizes)}, largest {sizes.max():,} points, "
              f"{len(big)} above the threshold of {args.min_cluster}")
        _, nn = cKDTree(dp).query(xyz, k=1)
        keep2 = np.isin(lab[nn], list(big))
        n_frag = int((~keep2).sum())
        print(f"loose fragments: {n_frag:,} removed")
        xyz, rgb = xyz[keep2], rgb[keep2]

    pc.write_ply(args.out, xyz, rgb)
    print(f"written: {args.out}, {len(xyz):,} of {n0:,} points ({len(xyz) / n0 * 100:.1f}%)")
    if args.json:
        pc.save_json(args.json, {"source": args.src, "output": args.out, "points_in": n0,
                                 "points_out": len(xyz), "outside_outline": int((~keep).sum()),
                                 "outliers": int(n_out), "fragments": n_frag,
                                 "margin_m": args.margin})


if __name__ == "__main__":
    main()
