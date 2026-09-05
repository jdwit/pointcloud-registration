#!/usr/bin/env python3
"""Convert an E57 scan to the PLY these tools read, thinning it on the way.

E57 is what most scanning apps and survey scanners export. The rest of this
toolkit works on PLY and xyz, so this is the front door.

Thin while converting. A 24 million point room scan carries no more building
geometry than the same scan at 5 mm spacing, and every later step runs an order
of magnitude faster. Keep the original E57; this writes a new file.

    python e57_to_ply.py room.e57 room.ply [--voxel 0.005] [--scan all]
"""
import argparse
from pathlib import Path

import numpy as np


def read_scan(f, index):
    import pye57
    d = f.read_scan(index, ignore_missing_fields=True, colors=True, transform=True)
    xyz = np.stack([d["cartesianX"], d["cartesianY"], d["cartesianZ"]], 1).astype(np.float64)
    keys = ("colorRed", "colorGreen", "colorBlue")
    if all(k in d for k in keys):
        rgb = np.stack([d[k] for k in keys], 1).astype(np.float64)
        if rgb.max() > 1.5:
            rgb /= 255.0
    else:
        rgb = np.full_like(xyz, 0.6)
    ok = np.isfinite(xyz).all(1)
    return xyz[ok], np.clip(rgb[ok], 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--voxel", type=float, default=0.005,
                    help="voxel size in metres for thinning, 0 keeps every point")
    ap.add_argument("--scan", default="all", help="scan index inside the file, or all")
    args = ap.parse_args()

    import open3d as o3d
    import pye57

    f = pye57.E57(args.src)
    idx = range(f.scan_count) if args.scan == "all" else [int(args.scan)]
    print(f"{args.src}: {f.scan_count} scan(s), reading {len(list(idx))}")

    parts = []
    for i in idx:
        xyz, rgb = read_scan(f, i)
        print(f"  scan {i}: {len(xyz):,} points, bbox {np.round(xyz.max(0) - xyz.min(0), 2)} m")
        parts.append((xyz, rgb))
    xyz = np.vstack([p[0] for p in parts])
    rgb = np.vstack([p[1] for p in parts])

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(xyz)
    cloud.colors = o3d.utility.Vector3dVector(rgb)
    if args.voxel > 0:
        n0 = len(cloud.points)
        cloud = cloud.voxel_down_sample(args.voxel)
        print(f"thinned at {args.voxel * 1000:.0f} mm: {n0:,} -> {len(cloud.points):,} points "
              f"({len(cloud.points) / n0 * 100:.1f}%)")
    o3d.io.write_point_cloud(args.out, cloud)
    print(f"written: {args.out} ({Path(args.out).stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
