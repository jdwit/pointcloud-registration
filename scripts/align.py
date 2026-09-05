#!/usr/bin/env python3
"""Align one cloud onto another with four degrees of freedom.

The three unknowns each come from the source that pins them hardest, and
nothing is left free afterwards:

    yaw    the masonry direction, thousands of wall points voting
    z      the difference between two horizontal planes, floor or terrain
    xy     cross correlation of the wall footprints, then a translation only
           point to plane refinement

Roll and pitch are not solved at all: a phone scan is levelled by gravity, so
they are already right, and letting them move only invites tilt.

Use this for cloud to cloud pairs that see the same surfaces: a room scan into
a storey, a storey into a building, a scan onto a sampled model of the same
building. For
interior against exterior, where the two see opposite sides of the same wall,
use align_interior_exterior.py instead.

    python align.py src.ply dst.ply out.ply --json t.json [--yaw 89.4]
                    [--z floor|ground|none] [--lock-z] [--band 0.5 5.0]
"""
import argparse

import numpy as np

import pcloud as pc


def prep(path, voxel, band, zref):
    xyz, rgb = pc.read_any(path)
    p, n = pc.normals(xyz, voxel=voxel)
    g = pc.ground_z(p, n) if zref is None else zref
    w, wn = pc.walls(p, n, thr=0.35, zmin=g + band[0], zmax=g + band[1])
    return xyz, rgb, p, n, g, w, wn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("out")
    ap.add_argument("--json", default=None)
    ap.add_argument("--yaw", type=float, default=None, help="skip the search, use this angle")
    ap.add_argument("--z", choices=("floor", "none"), default="floor")
    ap.add_argument("--z-dst", type=float, default=None,
                    help="known datum height in the destination, when the target carries one")
    ap.add_argument("--z-src", type=float, default=None,
                    help="the matching datum in the source. Needed when the two clouds see "
                         "several floors, such as a pair either side of a staircase, and the "
                         "lowest plane in each is not the same slab")
    ap.add_argument("--yaw-window", type=float, default=None,
                    help="degrees of yaw the refinement may search, either side of the "
                         "measured value. Default: the half width of the masonry peak "
                         "itself, capped at 3 degrees. Set 0 to lock the yaw hard")
    ap.add_argument("--free-z", action="store_true",
                    help="let the refinement move the height too; only when no floor plane "
                         "pins it, and check the residuals afterwards")
    ap.add_argument("--band", type=float, nargs=2, default=(0.5, 5.0),
                    help="wall band above the floor used for matching")
    ap.add_argument("--voxel", type=float, default=0.05)
    ap.add_argument("--cell", type=float, default=0.05)
    ap.add_argument("--radii", type=float, nargs="*",
                    default=(0.60, 0.35, 0.20, 0.12, 0.07, 0.04))
    args = ap.parse_args()

    sx, sc, sp, sn, sg, sw, swn = prep(args.src, args.voxel, args.band, args.z_src)
    dx, dc, dp, dn, dg, dw, dwn = prep(args.dst, args.voxel, args.band, args.z_dst)
    print(f"source {args.src}: {len(sx):,} points, floor z={sg:+.3f}, {len(sw):,} wall points")
    print(f"target {args.dst}: {len(dx):,} points, floor z={dg:+.3f}, {len(dw):,} wall points")

    a_s, a_d = pc.manhattan(sw, swn), pc.manhattan(dw, dwn)
    yaw0 = (a_d - a_s) % 90.0
    print(f"masonry: source {a_s:.3f}, target {a_d:.3f} -> yaw {yaw0:.3f} modulo 90")

    dz = (dg - sg) if args.z == "floor" else 0.0
    if args.z == "floor":
        print(f"height from the floor planes: {dz:+.3f} m")

    candidates = [args.yaw] if args.yaw is not None else [(yaw0 + 90 * q) % 360 for q in range(4)]
    scored = []
    for deg in candidates:
        moved = sw[:, :2] @ pc.rot2(deg).T
        shift, score = pc.match_xy(dw[:, :2], moved, cell=args.cell)
        print(f"  candidate {deg:7.3f} deg: score {score:.3f}, shift {np.round(shift, 2)} m")
        scored.append((score, deg, shift))
    scored.sort(reverse=True, key=lambda r: r[0])
    score, deg, shift = scored[0]
    print(f"chosen {deg:.3f} deg, score {score:.3f}")
    if len(scored) > 1 and scored[1][0] > 0.9 * score:
        print(f"  warning: {scored[1][1]:.3f} deg scores {scored[1][0]:.3f}, within 10% of the"
              " winner. A near symmetric room cannot tell a half turn apart from a whole one."
              " Decide it by eye with views.py overlay and force it with --yaw")

    lock_z = not args.free_z and args.z == "floor"
    T = pc.yaw_matrix(deg, (shift[0], shift[1], dz))
    src_w = pc.apply(T, sw)
    print("residuals of the wall band:")
    d0 = pc.residuals(src_w, dw, "coarse   ")

    # How well is the yaw actually pinned? The masonry peak answers that itself:
    # a sharp peak means hundredths of a degree, a smeared one means degrees, and
    # over a long room a degree is decimetres. Search inside that uncertainty
    # only, never outside it.
    spread = float(np.hypot(pc.heading_spread(sw, swn), pc.heading_spread(dw, dwn)))
    window = args.yaw_window if args.yaw_window is not None else min(spread, 3.0)
    print(f"masonry peak half width: source {pc.heading_spread(sw, swn):.2f}, "
          f"target {pc.heading_spread(dw, dwn):.2f} deg -> yaw searched over "
          f"+/- {window:.2f} deg")

    def place(dyaw):
        """Turn the coarse pose by dyaw about the source centroid, then refine."""
        c = src_w.mean(0)
        M = np.eye(4)
        M[:2, :2] = pc.rot2(dyaw)
        M[:3, 3] = c - M[:3, :3] @ c
        moved = pc.apply(M, src_w)
        t = pc.refine_translation(moved, dw, dwn, radii=tuple(args.radii),
                                  lock=(False, False, lock_z), verbose=False)
        dist, _ = tree.query(moved + t, k=1)
        return float(np.median(dist)), M, t

    from scipy.spatial import cKDTree
    tree = cKDTree(dw)
    best, best_dyaw = place(0.0), 0.0
    if window > 0.05:
        for step, span in ((0.5, window), (0.1, 0.8)):
            for dyaw in np.arange(best_dyaw - span, best_dyaw + span + step / 2, step):
                r = place(float(dyaw))
                if r[0] < best[0]:
                    best, best_dyaw = r, float(dyaw)
    med, M, t = best
    dyaw_applied = np.degrees(np.arctan2(M[1, 0], M[0, 0]))
    T = M @ T
    T[:3, 3] += t
    d1 = pc.residuals(pc.apply(T, sw), dw, "refined  ")
    print(f"yaw corrected by {dyaw_applied:+.2f} deg, fine translation "
          f"{np.round(t * 1000, 1)} mm"
          + (" (height held at the floor difference)" if lock_z else ""))
    if np.median(d1) > np.median(d0):
        print("  the refinement makes it worse, so it is dropped. Something outside the wall"
              " band is pulling: narrow --band, or pin an axis instead of freeing it")
        T = pc.yaw_matrix(deg, (shift[0], shift[1], dz))
        t = np.zeros(3)
        dyaw_applied = 0.0

    pc.write_ply(args.out, pc.apply(T, sx), sc)
    print(f"written: {args.out}, {len(sx):,} points")
    if args.json:
        pc.save_json(args.json, {
            "source": args.src, "target": args.dst, "output": args.out,
            "yaw_deg": deg, "raster_score": score, "coarse_shift_m": shift.tolist(),
            "dz_from_floors_m": dz, "fine_translation_mm": (t * 1000).tolist(),
            "yaw_correction_deg": round(float(dyaw_applied), 3),
            "yaw_window_deg": round(float(window), 3),
            "z_locked": bool(lock_z), "median_residual_mm": float(np.median(d1) * 1000),
            "transform": T.tolist(),
            "floor_src": sg, "floor_dst": dg})


if __name__ == "__main__":
    main()
