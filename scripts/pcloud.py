"""Shared helpers for point cloud registration.

Everything here works on plain numpy arrays; open3d is used only for
downsampling, normals, outlier removal and clustering. Keep it that way, it
makes the numbers easy to check and the scripts easy to compose.

Run anything in this directory with:
    uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib \
        python <script>.py ...
"""
import numpy as np

NP = {"char": "i1", "uchar": "u1", "short": "i2", "ushort": "u2", "int": "i4",
      "uint": "u4", "float": "f4", "double": "f8", "int8": "i1", "uint8": "u1",
      "int16": "i2", "uint16": "u2", "int32": "i4", "uint32": "u4",
      "float32": "f4", "float64": "f8"}


def read_ply(path):
    """Read a binary or ascii PLY into (xyz float64, rgb float64 in 0..1).

    Polycam writes doubles plus uchar colour, CloudCompare writes floats and
    sometimes adds normals or scalar fields. The header is parsed rather than
    assumed, so both just work.
    """
    with open(path, "rb") as fh:
        if fh.readline().strip() != b"ply":
            raise ValueError(f"{path} is not a PLY file")
        fmt = None
        n = None
        props = []
        in_vertex = False
        while True:
            line = fh.readline()
            if not line:
                raise ValueError("header runs to end of file")
            parts = line.decode("ascii", "replace").split()
            if not parts:
                continue
            if parts[0] == "format":
                fmt = parts[1]
            elif parts[0] == "element":
                in_vertex = parts[1] == "vertex"
                if in_vertex:
                    n = int(parts[2])
            elif parts[0] == "property" and in_vertex:
                if parts[1] == "list":
                    raise ValueError("list property in vertex is not supported")
                props.append((parts[2], parts[1]))
            elif parts[0] == "end_header":
                break
        if fmt == "ascii":
            data = np.loadtxt(fh, max_rows=n)
            cols = {name: data[:, i] for i, (name, _) in enumerate(props)}
        else:
            end = "<" if "little" in fmt else ">"
            dt = np.dtype([(name, end + NP[typ]) for name, typ in props])
            data = np.fromfile(fh, dtype=dt, count=n)
            cols = {name: data[name] for name, _ in props}

    xyz = np.stack([cols["x"], cols["y"], cols["z"]], 1).astype(np.float64)
    rgb = None
    for r, g, b in (("red", "green", "blue"), ("r", "g", "b"),
                    ("diffuse_red", "diffuse_green", "diffuse_blue")):
        if r in cols:
            rgb = np.stack([cols[r], cols[g], cols[b]], 1).astype(np.float64)
            if rgb.max() > 1.5:
                rgb /= 255.0
            break
    if rgb is None:
        rgb = np.full_like(xyz, 0.6)
    return xyz, np.clip(rgb, 0, 1)


def read_any(path):
    """PLY, or an x y z text file such as a sampled reference model."""
    if str(path).lower().endswith(".ply"):
        return read_ply(path)
    xyz = np.loadtxt(path)[:, :3]
    return xyz, np.full_like(xyz, 0.6)


def write_ply(path, xyz, rgb=None):
    import open3d as o3d
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(np.asarray(xyz, dtype=np.float64))
    if rgb is not None:
        pc.colors = o3d.utility.Vector3dVector(np.clip(np.asarray(rgb, dtype=np.float64), 0, 1))
    o3d.io.write_point_cloud(str(path), pc)
    return len(xyz)


def normals(xyz, voxel=0.05, radius=0.25, max_nn=30):
    """Downsample and estimate normals. Returns (points, normals).

    Normal signs are arbitrary in open3d. Always compare with abs(), never by
    sign, or half your walls disappear.
    """
    import open3d as o3d
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(xyz)
    d = pc.voxel_down_sample(voxel)
    d.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=max_nn))
    return np.asarray(d.points), np.asarray(d.normals)


def walls(pts, nrm, thr=0.3, zmin=None, zmax=None):
    """Near vertical surfaces: masonry, not floors or ceilings."""
    m = np.abs(nrm[:, 2]) < thr
    if zmin is not None:
        m &= pts[:, 2] > zmin
    if zmax is not None:
        m &= pts[:, 2] < zmax
    return pts[m], nrm[m]


def ground_z(pts, nrm, frac=0.25, bin_m=0.02, zmax=None):
    """Height of the lowest big horizontal plane: floor or terrain.

    Take the lowest bin that holds a serious share of the horizontal points,
    not a percentile. A percentile is dragged upwards by furniture tops and
    downwards by a few stray points under the floor; a lived in room has plenty
    of both. `frac` is the share of the fullest bin a bin must reach to count
    as a real plane.
    """
    flat = pts[np.abs(nrm[:, 2]) > 0.9]
    if len(flat) < 50:
        flat = pts
    z = flat[:, 2]
    if zmax is not None:
        z = z[z < zmax]
    hist, edges = np.histogram(z, bins=np.arange(z.min(), z.max() + bin_m, bin_m))
    thr = hist.max() * frac
    k = int(np.argmax(hist > thr))
    return float((edges[k] + edges[k + 1]) / 2)


def manhattan(pts, nrm, bin_deg=0.1, halfwin=8):
    """Dominant masonry direction, modulo 90 degrees.

    Thousands of wall points vote, and the peak bin is refined with its
    neighbours, so the answer is stable to a few hundredths of a degree. This
    is the only rotation source you should trust for a building.
    """
    az = np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) % 90.0
    hist, edges = np.histogram(az, bins=np.arange(0, 90 + bin_deg / 2, bin_deg))
    k = int(np.argmax(hist))
    idx = [(k + i) % len(hist) for i in range(-halfwin, halfwin + 1)]
    c = (edges[:-1] + edges[1:]) / 2
    ang = np.array([c[i] for i in idx])
    ang = ang[0] + ((ang - ang[0] + 45) % 90 - 45)
    wt = np.array([hist[i] for i in idx], dtype=float)
    return float((ang * wt).sum() / wt.sum() % 90.0)


def heading_spread(pts, nrm, bin_deg=0.1, window=6.0):
    """Half width at half maximum of the masonry peak, in degrees.

    This is the uncertainty of the yaw you just measured. A tripod scan of a
    brick wall gives a tenth of a degree; a fast handheld scan of a long room
    gives a degree or more, and over 15 m a degree is 260 mm. Refine within
    this window, never outside it.
    """
    az = np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) % 90.0
    peak = manhattan(pts, nrm)
    d = (az - peak + 45) % 90 - 45
    hist, edges = np.histogram(d, bins=np.arange(-window, window + bin_deg, bin_deg))
    c = (edges[:-1] + edges[1:]) / 2
    half = hist.max() / 2.0
    over = np.where(hist >= half)[0]
    if len(over) < 2:
        return 0.0
    return float(max(abs(c[over[0]]), abs(c[over[-1]])))


def rot2(deg):
    t = np.deg2rad(deg)
    return np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])


def yaw_matrix(deg, translation=(0.0, 0.0, 0.0)):
    T = np.eye(4)
    T[:2, :2] = rot2(deg)
    T[:3, 3] = translation
    return T


def apply(T, xyz):
    return xyz @ np.asarray(T)[:3, :3].T + np.asarray(T)[:3, 3]


def raster(xy, cell, lo, shape):
    i = np.floor((xy - lo) / cell).astype(int)
    ok = (i[:, 0] >= 0) & (i[:, 0] < shape[0]) & (i[:, 1] >= 0) & (i[:, 1] < shape[1])
    g = np.zeros(shape, dtype=np.float32)
    g[i[ok, 0], i[ok, 1]] = 1.0
    return g


def match_xy(dst_xy, src_xy, cell=0.05, half=16.0):
    """Coarse xy shift from cross correlation of two wall footprints.

    Both sets are centred first, so this only resolves the residual shift.
    Returns (shift, score); score is the peak divided by the source mass, so
    values are comparable between candidate rotations.
    """
    from scipy.signal import fftconvolve
    lo = np.array([-half, -half])
    shape = (int(2 * half / cell) + 1, int(2 * half / cell) + 1)
    a = raster(dst_xy - dst_xy.mean(0), cell, lo, shape)
    b = raster(src_xy - src_xy.mean(0), cell, lo, shape)
    corr = fftconvolve(a, b[::-1, ::-1], mode="same")
    k = int(np.argmax(corr))
    iy, ix = np.unravel_index(k, corr.shape)
    shift = (np.array([iy, ix]) - np.array(corr.shape) // 2) * cell
    return shift + (dst_xy.mean(0) - src_xy.mean(0)), float(corr.flat[k]) / max(1.0, b.sum())


def refine_translation(src, dst, dst_nrm, radii=(0.60, 0.35, 0.20, 0.12, 0.07, 0.04),
                       lock=(False, False, False), max_step=0.08, min_points=800,
                       iters=25, verbose=True):
    """Multi scale point to plane fit that may only translate.

    Rotation stays where you measured it. Axes flagged in `lock` are not
    allowed to move at all, which is how you keep a datum (a floor level, a
    national height) from being traded away for a percent of overlap.
    """
    from scipy.spatial import cKDTree
    tree = cKDTree(dst)
    t = np.zeros(3)
    free = ~np.array(lock, dtype=bool)
    for radius in radii:
        for _ in range(iters):
            d, idx = tree.query(src + t, k=1, distance_upper_bound=radius)
            m = np.isfinite(d)
            if m.sum() < min_points:
                break
            nn = dst_nrm[idx[m]]
            r = np.einsum("ij,ij->i", nn, dst[idx[m]] - (src[m] + t))
            w = np.maximum(0.0, 1.0 - (d[m] / radius) ** 2)
            A = (nn * w[:, None])[:, free]
            sol = np.zeros(3)
            sol[free] = np.linalg.lstsq(A, r * w, rcond=None)[0]
            step = np.clip(sol, -max_step, max_step)
            t = t + step
            if np.linalg.norm(step) < 2e-4:
                break
        if verbose:
            print(f"  radius {radius:.2f} -> {np.round(t * 1000, 1)} mm", flush=True)
    return t


def residuals(src, dst, label="", thresholds=(0.03, 0.05, 0.10)):
    """Nearest neighbour distances, the number every step gets judged on."""
    from scipy.spatial import cKDTree
    d, _ = cKDTree(dst).query(src, k=1)
    parts = " ".join(f"within {int(t * 100)} cm {100 * (d < t).mean():4.1f}%" for t in thresholds)
    print(f"  {label}median {np.median(d) * 1000:5.0f} mm, {parts}", flush=True)
    return d


def spacing(pts, n=20000, seed=0):
    """Median nearest neighbour distance: how fine the cloud resolves detail."""
    from scipy.spatial import cKDTree
    s = pts[np.random.default_rng(seed).choice(len(pts), min(n, len(pts)), replace=False)]
    d, _ = cKDTree(pts).query(s, k=2)
    return float(np.median(d[:, 1]))


def footprint_mask(ref_xy, query_xy, cell=0.10, margin=0.50, closing=7):
    """True for query points inside the outline of ref, grown by margin.

    Build the outline from wall points only when the reference is a scan:
    fragments that escaped through a window drag the outline outwards and then
    nothing gets clipped.
    """
    from scipy.ndimage import binary_closing, binary_dilation, binary_fill_holes
    lo = ref_xy.min(0) - 3.0
    shape = tuple(np.ceil((ref_xy.max(0) + 3.0 - lo) / cell).astype(int) + 1)
    i = np.floor((ref_xy - lo) / cell).astype(int)
    occ = np.zeros(shape, dtype=bool)
    occ[i[:, 0], i[:, 1]] = True
    solid = binary_fill_holes(binary_closing(occ, np.ones((closing, closing))))
    if margin > 0:
        k = int(margin / cell) * 2 + 1
        solid = binary_dilation(solid, np.ones((k, k)))
    elif margin < 0:
        from scipy.ndimage import binary_erosion
        k = int(-margin / cell) * 2 + 1
        solid = binary_erosion(solid, np.ones((k, k)))
    j = np.floor((query_xy - lo) / cell).astype(int)
    ok = (j[:, 0] >= 0) & (j[:, 0] < shape[0]) & (j[:, 1] >= 0) & (j[:, 1] < shape[1])
    keep = np.zeros(len(query_xy), dtype=bool)
    keep[ok] = solid[j[ok, 0], j[ok, 1]]
    return keep, float(solid.sum() * cell * cell)


def save_json(path, data):
    import json

    def plain(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))

    with open(path, "w") as fh:
        json.dump(data, fh, indent=2, default=plain)
    print(f"written: {path}", flush=True)
