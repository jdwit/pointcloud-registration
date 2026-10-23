# Workflow

This workflow registers, aligns or merges separate 3D point clouds of a building.
The input is phone or Polycam LiDAR scans (PLY, XYZ, with E57 or LAS converted first).
The scans can cover separate rooms, storeys, or interior versus exterior.
A scan can also go onto an existing model of the same building.

## Core principle

**Measure every degree of freedom from the source that pins it hardest, lock
it, and let only the rest move.**

A free ICP on building scans finds the wrong optimum with a better score than
the right one. Two large flat planes (a floor on the wrong ceiling) beat a
small true feature (a staircase) on point count every time. So ICP never
decides. It only polishes a pose that you already set by measurement, and it
may only translate.

## When to use

- Two or more scans of the same building that need to become one cloud
- A scan that must go onto an existing model of the same building
- A scan that broke into pieces at different heights (tracking loss)
- ICP runs, reports a fine fitness, and the result is visibly wrong
- Deciding, and defending, how accurate the finished cloud is

Not for: meshing, surface reconstruction, semantic segmentation, or clouds
from a survey grade scanner that already carry registered stations.

## Four degrees of freedom, not six

Gravity levels a phone scan, so roll and pitch are already right.
If you solve for them, you only let tilt in. Yaw and three shifts remain, and
each has its own anchor:

| Unknown | Anchor | Why that one |
|---|---|---|
| yaw | masonry direction, modulo 90 deg | thousands of wall normals vote. Stable to hundredths of a degree |
| z | a horizontal plane in both clouds | a floor, or the terrain. Large, unambiguous, one of a kind |
| xy | cross correlation of the wall footprints | uses the whole plan, not one feature |
| the rest | translation only point to plane refinement | rotation stays where you measured it |

ARKit picks an arbitrary north per session, so two scans of one building
usually differ by close to a quarter turn. `heading.py` measures it. The
difference from a clean 90 degrees can be more than about 0.8 deg. Then stop,
and find out whether a scan tilts or the building is out of square, before you
register anything. Other scanners pick an arbitrary heading with no such
habit, and then any angle is normal.

**The width of the peak is the uncertainty of the yaw.** A tripod scan gives a
tenth of a degree. A fast handheld walk through a long room can give several
degrees, and one degree over 15 m is 260 mm. `align.py` measures that width and
lets the refinement search the yaw within it, and nowhere else.

## Order of operations

| Step | Tool | Note |
|---|---|---|
| 1. look at every cloud | `inspect_cloud.py` | points, extent, spacing, floor level, masonry direction |
| 2. repair tracking loss | `split_ground_groups.py` | two terrain levels in one scan mean a broken scan, not a slope |
| 3. clean | `clean.py` | outliers, what escaped through windows, loose clusters |
| 4. measure the yaw | `heading.py` | plot the whole distribution, not just the peak |
| 4b. find the pairs | `find_pairs.py` | which scans share a room, ranked |
| 5. register pairs | `align.py` | storey to storey, room to storey, scan to an existing model |
| 6. check | `check_pair.py`, `views.py overlay` | on something that was not in the fit |
| 7. clip to the building | `clip_footprint.py` | outline from an external reference, not from the scan you clip |
| 8. merge | `merge.py` | keeps the sharper cloud where they overlap |
| 9. deliver | `views.py show` | plans, sections, elevations, isometrics |

Interior against exterior is the hard pair. They see opposite faces of the same
wall, so they share no surface and ICP has nothing to grip. This route works:

1. While you scan the exterior, scan a few metres indoors through an open door.
2. Isolate that patch with `clip_footprint.py --from-walls --margin -0.5`.
3. Register the interior onto that patch with `align.py`.

See [method.md](method.md).

## The verification rule

**A fit always reports that it converged. It minimised the distance it steered
on. Judge every step on a quantity that was not in the fit.**

| Check | Expected | Tool |
|---|---|---|
| inner wall to nearest facade | 250 to 400 mm for Dutch masonry around 1900 | `check_pair.py` |
| ground floor above terrain | a step for a house with a basement, near grade without | `check_pair.py` |
| a hand measured dimension across the joint | within your scanner's error | laser distance meter |
| the same floor seen by two scans | under 20 mm apart | `pcloud.residuals` |
| outer walls of two storeys in plan | coincide. Inner walls need not | `views.py overlay` |

State the accuracy per joint, not once for the whole cloud. The pair you
registered on a staircase is not as good as the pair that shared a whole floor.
Scan to scan, this method achieved 16 to 28 mm on a real building. You can also
place the cloud against an external model. That placement carries the error of
that model and is a separate claim. Never average the two.

## File discipline

```
originals/   untouched exports, never edited
stages/      one file per step, so you can revisit any step
work/        scripts, plots, and a small json per transform
```

Every transform gets a json next to its output with the angle, the shifts, the
residuals and the checks. Six weeks later that json is the only reason anyone
can believe the cloud.

## Running the tools

Run the scripts from `scripts/` in a clone of the repo:

```bash
uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib \
    python scripts/inspect_cloud.py scan.ply
```

All scripts take `--json` and print what they decided and why. `pcloud.py` is
the shared library. Import it for anything the scripts do not cover.

## Common mistakes

| Mistake | What happens | Instead |
|---|---|---|
| free 6-DOF ICP | the upper storey lands on the wrong ceiling, with a better score | measure yaw and z, refine translation only |
| letting the refinement move a datum | 28 cm of a known height traded for 2% more overlap | `--lock-z` whenever z came from a plane or a datum |
| clipping on an outline built from all points | escaped fragments push the outline out, nothing gets clipped | build outlines from wall points, or from an external reference |
| filtering normals by sign | half the walls vanish, open3d normal signs are arbitrary | compare with `abs()` |
| merging chunks before you settle their offsets | the offset freezes in and you can no longer remove it | keep chunks in separate files until the last step |
| trusting a converged fit | it minimised its own metric | check a quantity outside the fit |
| adjusting modelled source data by eye | two corrections, neither right, nobody can rebuild it | revert to the raw source and document the discrepancy |

More, with the actual numbers, in [pitfalls.md](pitfalls.md).

## References

- [method.md](method.md) - each step in detail and the reasoning behind it
- [pitfalls.md](pitfalls.md) - problems I hit in practice and how I solved them
- [worked-example.md](worked-example.md) - a full project end to end, with the numbers it produced
- [scan2bim-nl](https://github.com/jdwit/scan2bim-nl) - companion CLI for control measurements, Dutch open data and accuracy reporting
