---
name: pointcloud-registration
description: Use when registering, aligning or merging 3D point clouds of a building - phone or Polycam LiDAR scans (PLY, XYZ; convert E57 or LAS first) of separate rooms, storeys, interior versus exterior, or a scan that has to end up in real world coordinates (RD, NAP, 3DBAG, georeferencing) or in Revit. Also for scans that broke into chunks through tracking loss, clouds that will not line up with ICP, cleaning fragments and duplicate coverage, and proving how accurate the result is.
---

# Aligning point clouds of a building

## Core principle

**Measure every degree of freedom from the source that pins it hardest, lock
it, and let only what is left move.**

A free ICP on building scans finds the wrong optimum with a better score than
the right one: two large flat planes (a floor on the wrong ceiling) beat a
small correct feature (a staircase) on point count every time. So ICP is never
the thing that decides. It only polishes a pose you already fixed by
measurement, and it is only ever allowed to translate.

## When to use

- Two or more scans of the same building that need to become one cloud
- A scan that must land in RD/NAP, on a plot, or in Revit
- A scan that broke into pieces at different heights (tracking loss)
- ICP runs, reports a fine fitness, and the result is visibly wrong
- Deciding, and defending, how accurate the finished cloud is

Not for: meshing, surface reconstruction, semantic segmentation, or clouds
from a survey grade scanner that already carry registered stations.

## Four degrees of freedom, not six

A phone scan is levelled by gravity, so roll and pitch are already right.
Solving for them only lets tilt in. What remains is yaw plus three shifts, and
each has its own anchor:

| Unknown | Anchor | Why that one |
|---|---|---|
| yaw | masonry direction, modulo 90 deg | thousands of wall normals vote; stable to hundredths of a degree |
| z | a horizontal plane in both clouds | a floor, or the terrain; large, unambiguous, one of a kind |
| xy | cross correlation of the wall footprints | uses the whole plan, not one feature |
| the rest | translation only point to plane refinement | rotation stays where it was measured |

ARKit picks an arbitrary north per session, so two scans of one building
usually differ by close to a quarter turn. `heading.py` measures it. If the
difference from a clean 90 degrees is more than about 0.8 deg, stop and find
out whether a scan is tilted or the building is out of square, before
registering anything.

## Order of operations

| Step | Tool | Note |
|---|---|---|
| 1. look at every cloud | `inspect_cloud.py` | points, extent, spacing, floor level, masonry direction |
| 2. repair tracking loss | `split_ground_groups.py` | two terrain levels in one scan is a broken scan, not a slope |
| 3. clean | `clean.py` | outliers, what escaped through windows, loose clusters |
| 4. measure the yaw | `heading.py` | plot the whole distribution, not just the peak |
| 5. register pairs | `align.py` | storey to storey, room to storey, scan to 3DBAG |
| 6. verify | `check_pair.py`, `views.py overlay` | on something that was not in the fit |
| 7. georeference | `align.py` against sampled 3DBAG, `--lock-z` | gives RD, NAP and true north in one step |
| 8. clip to the building | `clip_footprint.py` | outline from 3DBAG, not from the scan being clipped |
| 9. merge | `merge.py` | keeps the sharper cloud where they overlap |
| 10. deliver | `views.py show` | plans, sections, elevations, isometrics |

Interior against exterior is the hard pair: they see opposite faces of the same
wall, so they share no surface and ICP has nothing to grip. The route that
works is to scan a few metres indoors through an open door while doing the
exterior, isolate that patch with `clip_footprint.py --from-walls --margin
-0.5`, and register the interior onto that patch with `align.py`. See
[references/method.md](references/method.md).

## The verification rule

**A fit always reports it converged; it minimised the distance it was steering
on. Judge every step on a quantity that was not in the fit.**

| Check | Expected | Tool |
|---|---|---|
| inner wall to nearest facade | 250 to 400 mm for Dutch masonry around 1900 | `check_pair.py` |
| ground floor above terrain | a step for a house with a basement, near grade without | `check_pair.py` |
| facades stop at the 3DBAG eaves heights | within a few decimetres | `references/georeferencing-nl.md` |
| the same floor seen by two scans | under 20 mm apart | `pcloud.residuals` |
| outer walls of two storeys in plan | coincide; inner walls need not | `views.py overlay` |

State two accuracies separately and never average them: **placement on the
plot** (about 135 mm through 3DBAG) and **internal precision** (16 to 28 mm
scan to scan). They are different claims about different things.

## File discipline

```
originals/   untouched exports, never edited
stages/      one file per step, so any step can be revisited
work/        scripts, plots, and a small json per transform
```

Every transform gets a json next to its output with the angle, the shifts, the
residuals and the checks. Six weeks later that json is the only reason anyone
can believe the cloud.

## Running the tools

```bash
S=~/.claude/skills/pointcloud-registration/scripts   # or scripts/ in a clone of the repo
uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib \
    python $S/inspect_cloud.py scan.ply
```

All scripts take `--json` and print what they decided and why. `pcloud.py` is
the shared library; import it for anything the scripts do not cover.

## Common mistakes

| Mistake | What happens | Instead |
|---|---|---|
| free 6-DOF ICP | the upper storey lands on the wrong ceiling, with a better score | measure yaw and z, refine translation only |
| letting the refinement move a datum | 28 cm of national height traded for 2% overlap | `--lock-z` whenever z came from a plane or a datum |
| clipping on an outline built from all points | escaped fragments push the outline out, nothing gets clipped | build outlines from wall points, or from 3DBAG |
| filtering normals by sign | half the walls vanish, open3d normal signs are arbitrary | compare with `abs()` |
| merging chunks before their offsets are settled | the offset is frozen in and can no longer be removed | keep chunks in separate files until the last step |
| trusting a converged fit | it minimised its own metric | check a quantity outside the fit |
| correcting modelled source data by eye | two corrections, neither right, nobody can rebuild it | revert to the raw source and document the discrepancy |

More, with the actual numbers, in [references/pitfalls.md](references/pitfalls.md).

## References

- [references/method.md](references/method.md) - each step in detail and the reasoning behind it
- [references/pitfalls.md](references/pitfalls.md) - traps hit in practice and how they were resolved
- [references/georeferencing-nl.md](references/georeferencing-nl.md) - 3DBAG, AHN, PDOK, RD/NAP, and the route into Revit
- [references/worked-example.md](references/worked-example.md) - a full project end to end, with the numbers it produced
- [scan2bim-nl](https://github.com/jdwit/scan2bim-nl) - companion CLI for control measurements, Dutch open data and accuracy reporting
