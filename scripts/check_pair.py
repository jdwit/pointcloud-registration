#!/usr/bin/env python3
"""Judge a registration on something that was not in the fit.

A fit always reports that it converged. That says nothing: it minimised the
very distance it was steering on. So test a quantity the optimiser never saw
and that has a known value in the real world.

  thickness   distance from an inner wall to the nearest facade. Dutch masonry
              from around 1900 gives 250 to 400 mm. Two metres means the
              interior landed a room too far, however good the residuals look.
  floor       height of the ground floor above the terrain. A house with a
              basement sits a step up, a house without sits near grade.
  overlap     residuals on the part the two clouds really share.

    python check_pair.py interior.ply exterior.ply [--band 1.0 2.5] [--json out.json]
"""
import argparse

import numpy as np

import pcloud as pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("interior")
    ap.add_argument("exterior")
    ap.add_argument("--band", type=float, nargs=2, default=(1.0, 2.5),
                    help="height band above the terrain used for the wall comparison")
    ap.add_argument("--expect-thickness", type=float, nargs=2, default=(0.25, 0.40))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    from scipy.spatial import cKDTree

    ix, _ = pc.read_any(args.interior)
    ex, _ = pc.read_any(args.exterior)
    ip, inr = pc.normals(ix, voxel=0.04, radius=0.2)
    ep, enr = pc.normals(ex, voxel=0.04, radius=0.2)
    zg = pc.ground_z(ep, enr)
    print(f"terrain in the exterior scan: z = {zg:+.3f}")

    zf = pc.ground_z(ip, inr)
    print(f"ground floor in the interior scan: z = {zf:+.3f}")
    print(f"check 1, floor above terrain: {zf - zg:+.2f} m")

    facade, _ = pc.walls(ep, enr, zmin=zg + args.band[0], zmax=zg + args.band[1])
    inner, _ = pc.walls(ip, inr, zmin=zg + args.band[0], zmax=zg + args.band[1])
    print(f"facade points {len(facade):,}, inner wall points {len(inner):,}")
    d, _ = cKDTree(facade).query(inner, k=1)
    sel = (d > 0.10) & (d < 0.80)
    med = float(np.median(d[sel])) if sel.any() else float("nan")
    print(f"check 2, inner wall to nearest facade: median {med * 1000:.0f} mm over "
          f"{int(sel.sum()):,} points (expected {args.expect_thickness[0] * 1000:.0f} to "
          f"{args.expect_thickness[1] * 1000:.0f} mm)")
    verdict = args.expect_thickness[0] <= med <= args.expect_thickness[1]
    print("  " + ("plausible" if verdict else
                  "NOT plausible: the registration is probably off by a whole wall or room"))

    d2, _ = cKDTree(ep).query(ip, k=1)
    close = d2 < 0.25
    print(f"check 3, shared surfaces: {int(close.sum()):,} interior points within 25 cm of the "
          f"exterior scan, median {np.median(d2[close]) * 1000:.0f} mm there"
          if close.any() else "check 3, shared surfaces: none, the clouds do not touch")

    if args.json:
        pc.save_json(args.json, {"interior": args.interior, "exterior": args.exterior,
                                 "terrain_z": zg, "floor_z": zf,
                                 "floor_above_terrain_m": zf - zg,
                                 "wall_thickness_median_mm": med * 1000,
                                 "thickness_plausible": bool(verdict),
                                 "shared_points": int(close.sum())})


if __name__ == "__main__":
    main()
