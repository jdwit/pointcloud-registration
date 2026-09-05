#!/usr/bin/env python3
"""Relative rotation between two clouds, measured from the masonry.

ARKit picks an arbitrary north at the start of every scan session, so two
scans of the same building differ by a yaw that is usually close to a multiple
of 90 degrees. Measure it from the wall directions, then lock it; do not let
ICP look for it.

The plot shows the whole direction distribution, not just the peak. If the two
peaks disagree by more than a few tenths of a degree, the cause is different
walls dominating each scan, not a rotation error, and the plot is where you
see that.

    python heading.py a.ply b.ply [--zmin-a Z] [--zmin-b Z] [--plot out.png]
"""
import argparse

import numpy as np

import pcloud as pc


def peaks_of(path, zmin, voxel=0.04):
    xyz, _ = pc.read_any(path)
    p, n = pc.normals(xyz, voxel=voxel)
    w, wn = pc.walls(p, n, thr=0.25, zmin=zmin)
    az = np.degrees(np.arctan2(wn[:, 1], wn[:, 0])) % 90.0
    return w, wn, az, pc.manhattan(w, wn)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--zmin-a", type=float, default=None)
    ap.add_argument("--zmin-b", type=float, default=None)
    ap.add_argument("--plot", default=None)
    args = ap.parse_args()

    res = {}
    for label, path, zmin in (("a", args.a, args.zmin_a), ("b", args.b, args.zmin_b)):
        w, wn, az, ang = peaks_of(path, zmin)
        res[label] = (path, az, ang, len(w))
        print(f"{path}: {len(w):,} wall points, masonry direction {ang:.3f} deg")

    yaw = (res["a"][2] - res["b"][2]) % 90.0
    print(f"\nyaw to bring b onto a: {yaw:.3f} deg modulo 90")
    print("candidates to try: " + ", ".join(f"{(yaw + 90 * q) % 360:.3f}" for q in range(4)))
    off = min(abs(yaw), abs(90 - yaw))
    print(f"deviation from a clean quarter turn: {off:.3f} deg"
          f" ({off / 90 * 100:.1f}% of a right angle)")
    if off > 0.8:
        print("  more than 0.8 deg: check whether one scan is tilted, or whether the"
              " building itself is out of square, before trusting this")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(15, 9), dpi=140, sharex=True)
        for ax, label in zip(axes, ("a", "b")):
            path, az, ang, n = res[label]
            ax.hist(az, bins=np.arange(0, 90.05, 0.1))
            ax.axvline(ang, color="crimson", lw=0.8, ls="--")
            ax.set_title(f"{path}: wall directions modulo 90 deg, peak {ang:.3f}")
            ax.grid(alpha=0.3)
        axes[1].set_xlabel("direction modulo 90 degrees")
        fig.tight_layout()
        fig.savefig(args.plot)
        print(f"written: {args.plot}")


if __name__ == "__main__":
    main()
