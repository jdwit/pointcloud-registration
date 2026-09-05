#!/usr/bin/env python3
"""Repair a scan that broke into chunks when the tracking was lost.

Symptom: one exterior scan holds two terrain levels metres apart. That is not
a slope, it is the phone losing its orientation halfway and carrying on in a
shifted frame.

The split is spatial, not chronological: two connected areas in plan with a
border between them. So map the ground height per half metre cell, classify
the cells into two groups, clean the border with a majority filter, and lift
the low group.

The lift comes from the ground in the cells right along the border, because
that is where the two ought to join. That is sharper than the distance between
the two peaks in the height histogram.

Only the height is corrected. The sideways offset between the groups is left
alone, and that stays possible only while the groups are separate files, so
they are written out separately on purpose.

    python split_ground_groups.py in.ply outdir [--split-z -3.1] [--cell 0.5]
                                  [--frame-deg 0.47]
"""
import argparse
from pathlib import Path

import numpy as np

import pcloud as pc


def ground_map(xy, z, cell, min_points=25):
    lo = xy.min(0)
    shape = tuple(np.ceil((xy.max(0) - lo) / cell).astype(int) + 1)
    idx = np.floor((xy - lo) / cell).astype(int)
    flat = idx[:, 0] * shape[1] + idx[:, 1]
    order = np.argsort(flat)
    fs, zs = flat[order], z[order]
    starts = np.searchsorted(fs, np.arange(shape[0] * shape[1]))
    ends = np.r_[starts[1:], len(fs)]
    g = np.full(shape[0] * shape[1], np.nan)
    for c in range(shape[0] * shape[1]):
        if ends[c] - starts[c] >= min_points:
            g[c] = np.percentile(zs[starts[c]:ends[c]], 8)
    return g.reshape(shape), flat, lo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("outdir")
    ap.add_argument("--cell", type=float, default=0.5)
    ap.add_argument("--split-z", type=float, default=None,
                    help="height between the two levels; default is the middle of the gap")
    ap.add_argument("--frame-deg", type=float, default=0.0,
                    help="rotate the grid to line up with the building")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    from scipy.ndimage import binary_closing, binary_dilation, binary_opening, median_filter

    xyz, rgb = pc.read_any(args.src)
    q = xyz.copy()
    if args.frame_deg:
        q[:, :2] = xyz[:, :2] @ pc.rot2(-args.frame_deg).T
    gmap, flat, _ = ground_map(q[:, :2], q[:, 2], args.cell)
    vals = gmap[~np.isnan(gmap)]
    print(f"{args.src}: {len(xyz):,} points, {len(vals)} filled ground cells, "
          f"terrain from {vals.min():.2f} to {vals.max():.2f}")

    mid = args.split_z
    if mid is None:
        srt = np.sort(vals)
        gaps = np.diff(srt)
        k = int(np.argmax(gaps[len(srt) // 10: -len(srt) // 10])) + len(srt) // 10
        mid = float((srt[k] + srt[k + 1]) / 2)
        print(f"largest gap in the terrain heights at z={mid:.2f}, used as the split")

    cls = np.where(np.isnan(gmap), -1, (gmap >= mid).astype(int))
    m = median_filter(np.where(cls < 0, 0, cls).astype(float), size=5)
    filled = np.where(cls < 0, -1, (m >= 0.5).astype(int))
    hi = binary_closing(binary_opening(filled == 1, np.ones((3, 3))), np.ones((3, 3)))
    low = binary_closing(binary_opening(filled == 0, np.ones((3, 3))), np.ones((3, 3)))
    zh = np.nanmedian(gmap[binary_dilation(low, np.ones((3, 3))) & hi])
    zl = np.nanmedian(gmap[binary_dilation(hi, np.ones((3, 3))) & low])
    dz = float(zh - zl)
    print(f"ground along the border: high side {zh:.3f}, low side {zl:.3f} -> lift {dz:+.3f} m")

    him = hi.reshape(-1)[flat]
    lowm = low.reshape(-1)[flat]
    rest = ~(him | lowm)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.src).stem
    report = {"cell_m": args.cell, "split_z": mid, "frame_deg": args.frame_deg, "lift_m": dz,
              "groups": {}}
    for name, mask, shift, note in (
            ("A-high", him, 0.0, "already on the right terrain level"),
            ("B-lifted", lowm, dz, "was too low, height corrected only, sideways position untouched"),
            ("C-rest", rest, 0.0, "border cells and cells with too few points, left alone")):
        pts = xyz[mask].copy()
        pts[:, 2] += shift
        path = out / f"{stem}-group-{name}.ply"
        pc.write_ply(path, pts, rgb[mask])
        print(f"  {path.name}: {int(mask.sum()):,} points, correction {shift:+.3f} m")
        report["groups"][name] = {"points": int(mask.sum()), "correction_m": shift, "note": note}
    print("\nkeep the groups separate until the sideways offset is settled; merging now"
          " freezes an offset you can no longer remove")
    if args.json:
        pc.save_json(args.json, report)


if __name__ == "__main__":
    main()
