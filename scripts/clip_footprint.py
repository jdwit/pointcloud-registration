#!/usr/bin/env python3
"""Clip a cloud to a building outline taken from a reference.

Best is an outline that does not come from the scan being clipped: a sampled
model of the building, or a surveyed footprint. Then it cannot inherit the
scan's own errors. Failing that, use --from-walls on a cloud of the outside.

Margin, in metres:

    +0.50  exterior: keeps gutter, overhang and reveals
    +0.15  interior: an inner wall is always inside the facade, so anything
           outside the outline escaped through a window
    -0.50  isolate what the exterior scan caught through an open door: erode
           inwards so the facade itself and the door frame drop out

    python clip_footprint.py in.ply ref.xyz out.ply [--margin 0.5] [--invert]
"""
import argparse

import numpy as np

import pcloud as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("ref", help="reference cloud whose outline is used, PLY or xyz")
    ap.add_argument("out")
    ap.add_argument("--margin", type=float, default=0.50)
    ap.add_argument("--cell", type=float, default=0.10)
    ap.add_argument("--closing", type=int, default=7)
    ap.add_argument("--invert", action="store_true", help="keep what falls outside instead")
    ap.add_argument("--zmin", type=float, default=None, help="also drop everything below this height")
    ap.add_argument("--from-walls", action="store_true",
                    help="build the outline from the wall points of the reference instead of all "
                         "of them; needed when the reference is a scan with terrain or greenery")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    xyz, rgb = pc.read_any(args.src)
    ref, _ = pc.read_any(args.ref)
    if args.from_walls:
        p, n = pc.normals(ref, voxel=0.05, radius=0.15)
        g = pc.ground_z(p, n)
        w, _ = pc.walls(p, n, zmin=g + 0.3)
        print(f"outline from {len(w):,} wall points above z={g + 0.3:+.2f}")
        ref = w
        args.closing = max(args.closing, 21)
    keep, area = pc.footprint_mask(ref[:, :2], xyz[:, :2], cell=args.cell,
                                   margin=args.margin, closing=args.closing)
    if args.invert:
        keep = ~keep
    if args.zmin is not None:
        keep &= xyz[:, 2] > args.zmin
        print(f"below z={args.zmin:+.2f} dropped as well")
    print(f"{args.src}: {len(xyz):,} points")
    print(f"outline {area:.0f} m2 with a {args.margin:+.2f} m margin")
    print(f"kept: {int(keep.sum()):,} ({keep.mean() * 100:.1f}%)")
    pc.write_ply(args.out, xyz[keep], rgb[keep])
    print(f"written: {args.out}")
    if args.json:
        pc.save_json(args.json, {"source": args.src, "reference": args.ref, "output": args.out,
                                 "margin_m": args.margin, "area_m2": area,
                                 "points_in": len(xyz), "points_out": int(keep.sum())})


if __name__ == "__main__":
    main()
