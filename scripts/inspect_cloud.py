#!/usr/bin/env python3
"""First look at a cloud: size, extent, resolution, level, masonry direction.

Run this before anything else. It tells you whether the scan is metric and
level, where the floor is, and which way the walls run, which is what every
later step is anchored on.

    python inspect_cloud.py cloud.ply [more.ply ...]
"""
import sys

import numpy as np

import pcloud as pc


def report(path):
    xyz, rgb = pc.read_any(path)
    p, n = pc.normals(xyz, voxel=0.05)
    w, wn = pc.walls(p, n)
    g = pc.ground_z(p, n)
    print(f"\n{path}")
    print(f"  points     {len(xyz):,}")
    print(f"  bbox       {np.round(xyz.max(0) - xyz.min(0), 2)} m")
    print(f"  z range    {xyz[:, 2].min():.2f} to {xyz[:, 2].max():.2f}")
    print(f"  spacing    {pc.spacing(xyz) * 1000:.1f} mm median nearest neighbour")
    print(f"  floor      z = {g:+.3f} (lowest large horizontal plane)")
    print(f"  wall pts   {len(w):,} of {len(p):,} downsampled")
    if len(w) > 500:
        print(f"  masonry    {pc.manhattan(w, wn):.3f} deg modulo 90")
    hist, edges = np.histogram(xyz[:, 2], bins=np.arange(xyz[:, 2].min(), xyz[:, 2].max() + 0.5, 0.5))
    peaks = np.argsort(hist)[::-1][:4]
    lvl = ", ".join(f"z={edges[i]:+.2f} ({hist[i]:,})" for i in sorted(peaks))
    print(f"  z peaks    {lvl}   (floors and ceilings)")
    print(f"  colour     mean rgb {np.round(rgb.mean(0) * 255, 0)}")
    return xyz


def main(paths):
    clouds = [report(p) for p in paths]
    if len(clouds) > 1:
        print("\ncentres relative to the first cloud:")
        c0 = clouds[0].mean(0)
        for path, xyz in zip(paths[1:], clouds[1:]):
            print(f"  {path}: {np.round(xyz.mean(0) - c0, 2)} m")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
