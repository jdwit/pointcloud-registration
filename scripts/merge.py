#!/usr/bin/env python3
"""Merge clouds, dropping the coarser copy where they overlap.

Where two scans cover the same surface, keep the sharper one. Which is sharper
is measurable: the median distance between neighbouring points. The finer the
spacing, the finer the detail.

Only points inside the overlap are dropped, and only within a small radius, so
the edges of the detail scan keep their surroundings and no hole appears.

    python merge.py base.ply detail.ply out.ply [--radius 0.06]
    python merge.py a.ply b.ply out.ply --no-dedupe
"""
import argparse

import numpy as np

import pcloud as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("detail")
    ap.add_argument("out")
    ap.add_argument("--radius", type=float, default=0.06)
    ap.add_argument("--no-dedupe", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    from scipy.spatial import cKDTree

    B, bc = pc.read_any(args.base)
    D, dc = pc.read_any(args.detail)
    print(f"base {args.base}: {len(B):,} points")
    print(f"detail {args.detail}: {len(D):,} points")

    keep = np.ones(len(B), dtype=bool)
    sb = sd = None
    if not args.no_dedupe:
        lo, hi = D.min(0) - 0.05, D.max(0) + 0.05
        inbox = np.all((B >= lo) & (B <= hi), axis=1)
        print(f"base points inside the box of the detail scan: {int(inbox.sum()):,}")
        if inbox.sum() > 1000:
            sb, sd = pc.spacing(B[inbox]), pc.spacing(D)
            print(f"point spacing there: base {sb * 1000:.1f} mm, detail {sd * 1000:.1f} mm"
                  f" -> keeping the {'detail' if sd < sb else 'base'} scan")
            if sd < sb:
                d = np.full(len(B), np.inf)
                d[inbox], _ = cKDTree(D).query(B[inbox], k=1)
                keep = ~(inbox & (d < args.radius))
                print(f"dropped from the base within {args.radius * 100:.0f} cm of a "
                      f"detail point: {int((~keep).sum()):,}")

    xyz = np.vstack([B[keep], D])
    rgb = np.vstack([bc[keep], dc])
    pc.write_ply(args.out, xyz, rgb)
    print(f"written: {args.out}, {len(xyz):,} points "
          f"(was {len(B) + len(D):,}, so {len(B) + len(D) - len(xyz):,} duplicates removed)")
    if args.json:
        pc.save_json(args.json, {"base": args.base, "detail": args.detail, "output": args.out,
                                 "radius_m": args.radius, "dropped": int((~keep).sum()),
                                 "spacing_base_mm": None if sb is None else sb * 1000,
                                 "spacing_detail_mm": None if sd is None else sd * 1000,
                                 "points_out": len(xyz)})


if __name__ == "__main__":
    main()
