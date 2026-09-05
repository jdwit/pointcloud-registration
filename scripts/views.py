#!/usr/bin/env python3
"""Look at the result. Numbers can be right while the whole is wrong.

  overlay   two clouds in two colours, in plan and in section. This is the
            check after every registration step: outer walls must coincide,
            inner walls need not, floors must stack, the stairs must run on.
  show      the finished cloud in true colour: isometrics, elevations,
            sections and floor plans.

Points are drawn back to front, otherwise you look straight through the
facade at the back wall.

    python views.py overlay a.ply b.ply out.png
    python views.py show cloud.ply outprefix [--ground 12.345] [--level 21.60 ridge]
"""
import argparse

import numpy as np

import pcloud as pc

A_COLOUR = "#1f77b4"
B_COLOUR = "#d62728"


def load(path, voxel):
    xyz, rgb = pc.read_any(path)
    import open3d as o3d
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(xyz)
    cloud.colors = o3d.utility.Vector3dVector(rgb)
    d = cloud.voxel_down_sample(voxel)
    return np.asarray(d.points), np.asarray(d.colors)


def camera(az, el):
    a, e = np.deg2rad(az), np.deg2rad(el)
    f = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    return f, r, np.cross(r, f)


def draw(ax, P, C, ctr, az, el, title, s=0.55):
    f, r, u = camera(az, el)
    d = (P - ctr) @ f
    o = np.argsort(d)[::-1]
    ax.scatter(((P - ctr) @ r)[o], ((P - ctr) @ u)[o], s=s, c=C[o], linewidths=0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=11)


def cmd_overlay(args, plt):
    Pa, _ = load(args.a, args.voxel)
    Pb, _ = load(args.b, args.voxel)
    print(f"{args.a}: {len(Pa):,}   {args.b}: {len(Pb):,} points after thinning")
    fig, axes = plt.subplots(1, 3, figsize=(24, 8), dpi=130)
    both = np.vstack([Pa, Pb])
    axes[0].scatter(Pa[:, 0], Pa[:, 1], s=0.4, c=A_COLOUR, alpha=0.35, linewidths=0, label=args.a)
    axes[0].scatter(Pb[:, 0], Pb[:, 1], s=0.4, c=B_COLOUR, alpha=0.35, linewidths=0, label=args.b)
    axes[0].set_title("plan: outer walls must coincide, inner walls need not")
    axes[0].legend(markerscale=20, fontsize=7, loc="upper right")
    for ax, axis, label in ((axes[1], 1, "section across"), (axes[2], 0, "section along")):
        cut = float(np.median(both[:, axis]))
        for P, colour in ((Pa, A_COLOUR), (Pb, B_COLOUR)):
            m = np.abs(P[:, axis] - cut) < args.band
            ax.scatter(P[m][:, 1 - axis], P[m][:, 2], s=0.5, c=colour, alpha=0.5, linewidths=0)
        ax.set_title(f"{label} at {'xy'[axis]} = {cut:.2f} m")
    for ax in axes:
        ax.set_aspect("equal")
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(args.out)
    print(f"written: {args.out}")


def cmd_show(args, plt):
    P, C = load(args.cloud, args.voxel)
    print(f"{len(P):,} points after thinning")
    ctr = np.r_[P[:, :2].mean(0), (P[:, 2].min() + P[:, 2].max()) / 2]
    g = args.ground if args.ground is not None else P[:, 2].min()

    fig, axes = plt.subplots(2, 2, figsize=(20, 17), dpi=150)
    for ax, (az, t) in zip(axes.ravel(), [(225, "from the south west"), (45, "from the north east"),
                                          (315, "from the north west"), (135, "from the south east")]):
        draw(ax, P, C, ctr, az, 25, f"Isometric {t}")
    fig.tight_layout()
    fig.savefig(f"{args.prefix}-1-iso.png", facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(22, 15), dpi=150)
    for ax, (az, t) in zip(axes.ravel(), [(90, "from the north"), (270, "from the south"),
                                          (0, "from the east"), (180, "from the west")]):
        draw(ax, P, C, ctr, az, 0, f"Elevation {t}")
    fig.tight_layout()
    fig.savefig(f"{args.prefix}-2-elevations.png", facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(22, 15), dpi=150)
    cuts = [(1, np.percentile(P[:, 1], 35)), (1, np.percentile(P[:, 1], 65)),
            (0, np.percentile(P[:, 0], 35)), (0, np.percentile(P[:, 0], 65))]
    for ax, (axis, cut) in zip(axes.ravel(), cuts):
        m = np.abs(P[:, axis] - cut) < args.band
        o = 1 - axis
        ax.scatter(P[m][:, o], P[m][:, 2], s=0.8, c=C[m], linewidths=0)
        for z, lab in args.level or []:
            ax.axhline(float(z), color="0.5", lw=0.5, ls="--")
            ax.text(ax.get_xlim()[0], float(z), f" {lab}", fontsize=7, va="bottom", color="0.35")
        ax.set_aspect("equal")
        ax.grid(alpha=0.15)
        ax.set_title(f"Section {'xy'[axis]} = {cut:.2f} m")
    fig.tight_layout()
    fig.savefig(f"{args.prefix}-3-sections.png", facecolor="white")
    plt.close(fig)

    bands = [(g - 2.2, g - 1.0, "basement"), (g + 0.6, g + 1.6, "ground floor"),
             (g + 4.0, g + 5.0, "first floor"), (g + 7.0, g + 8.0, "attic")]
    # a band with almost nothing in it says more about the slice than about the
    # building, so drop it rather than showing a sliver
    bands = [b for b in bands if ((P[:, 2] > b[0]) & (P[:, 2] < b[1])).sum() > 20000]
    fig, axes = plt.subplots(1, len(bands), figsize=(8 * len(bands), 9), dpi=150, squeeze=False)
    for ax, (lo, hi, t) in zip(axes[0], bands):
        m = (P[:, 2] > lo) & (P[:, 2] < hi)
        ax.scatter(P[m][:, 0], P[m][:, 1], s=0.7, c=C[m], linewidths=0)
        ax.set_aspect("equal")
        ax.grid(alpha=0.15)
        ax.set_title(f"Plan {t}, {int(m.sum()):,} points")
    fig.tight_layout()
    fig.savefig(f"{args.prefix}-4-plans.png", facecolor="white")
    plt.close(fig)
    print(f"written: {args.prefix}-1-iso.png, -2-elevations.png, -3-sections.png, -4-plans.png")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("overlay")
    o.add_argument("a")
    o.add_argument("b")
    o.add_argument("out")
    o.add_argument("--voxel", type=float, default=0.03)
    o.add_argument("--band", type=float, default=0.9)
    s = sub.add_parser("show")
    s.add_argument("cloud")
    s.add_argument("prefix")
    s.add_argument("--voxel", type=float, default=0.025)
    s.add_argument("--band", type=float, default=0.9)
    s.add_argument("--ground", type=float, default=None)
    s.add_argument("--level", nargs=2, action="append", metavar=("Z", "LABEL"))
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (cmd_overlay if args.cmd == "overlay" else cmd_show)(args, plt)


if __name__ == "__main__":
    main()
