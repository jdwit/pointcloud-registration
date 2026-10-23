#!/usr/bin/env python3
"""Remove outliers, fragments outside the shell, and loose clusters.

Two kinds of rubbish that are always safe to remove:

  statistical outliers   sensor noise, sparse and isolated
  loose clusters         fragments connected to nothing, typically what escaped
                         through a window

Clipping to a footprint is a third option and it is off by default, because it
is the one that can delete real building. A footprint from a national model is
the simplified outline of the volume, not your gevel: a bay window, a porch or
a vestibule sits outside it and gets cut. Only clip when you know the outline
is at least as detailed as the building, and look at what fell away.

    python clean.py in.ply out.ply [--min-cluster 2000] [--json report.json]
    python clean.py in.ply out.ply --outline survey.xyz --margin 0.5   # opt in
"""
import argparse

import numpy as np

import pcloud as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--outline", default=None,
                    help="clip to the footprint of this reference cloud. Off by default")
    ap.add_argument("--outline-from-walls", action="store_true",
                    help="clip to the footprint of the cloud's own wall points")
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

    n_clipped = 0
    if args.outline or args.outline_from_walls:
        if args.outline:
            ref, _ = pc.read_any(args.outline)
            ref_xy, closing = ref[:, :2], 7
        else:
            p, n = pc.normals(xyz, voxel=0.05, radius=0.15)
            w, _ = pc.walls(p, n)
            ref_xy, closing = w[:, :2], 21
        keep, area = pc.footprint_mask(ref_xy, xyz[:, :2], cell=args.cell,
                                       margin=args.margin, closing=closing)
        n_clipped = int((~keep).sum())
        print(f"outline {area:.0f} m2 including the {args.margin} m margin; "
              f"outside it: {n_clipped:,} points ({(~keep).mean() * 100:.1f}%)")
        print("  look at what fell away before you keep this: a footprint cuts bays,")
        print("  porches and vestibules that the outline does not know about")
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
                                 "points_out": len(xyz), "clipped_by_outline": n_clipped,
                                 "outliers": int(n_out), "fragments": n_frag,
                                 "margin_m": args.margin if n_clipped else None})


if __name__ == "__main__":
    main()
