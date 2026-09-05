# The method, step by step

## 0. What the input is

Polycam on an iPhone Pro writes PLY with double coordinates and uchar colour,
no normals, no mesh, one file per scan, each in its own local frame centred
near the origin. Scale is metric and trustworthy; LiDAR measures distance.
Orientation is level, because the scan is gravity aligned. Everything else is
arbitrary per session.

Usable range is about 5 m. Beyond that the depth is inferred rather than
measured, which is why high gable ends scanned from the ground are the worst
part of any exterior scan, and why a selfie stick materially helps.

## 1. Inspect before anything else

`inspect_cloud.py` gives point count, extent, median point spacing, the
lowest large horizontal plane, the masonry direction, and the peaks in the
height histogram (the floors and ceilings). Read it before making any plan:

- two terrain levels metres apart means the scan broke, go to step 2
- a spacing of 6 mm against 22 mm tells you which cloud wins in an overlap
- the z peaks tell you which plane to use as the height anchor, and warn you
  when a storey has several ceiling levels

## 2. Repairing tracking loss

Symptom: one exterior scan holds two ground levels several metres apart.
ARKit lost tracking during a fast move (typically hoisting the phone on a
stick) and carried on in a shifted frame.

The split is **spatial, not chronological**: two connected areas in plan with a
border between them. `split_ground_groups.py` maps the ground height per half
metre cell, classifies the cells, cleans the border with a majority filter and
lifts the low group.

Take the lift from the ground in the cells right along the border, where the
two ought to join. In the case at hand that gave 3.018 m, against 3.25 m read
off the two peaks in the height histogram. The border value is the sharper
number because it compares the two sides at the place where they must agree.

Check the auto split with the printed terrain range and set `--split-z`
yourself if the largest gap is not where the two levels part.

Only the height is corrected this way. The sideways offset between the groups
cannot be solved by ICP, because the groups do not overlap; it has to come from
the ground that runs across the border and from walls that cross it. Keep the
groups in separate files until that is settled, because merging freezes an
offset you can no longer remove.

## 3. Cleaning

Two kinds of rubbish, two remedies:

- **Statistical outliers**: `nb_neighbors=20, std_ratio=2.0` removes sensor
  noise without eating detail.
- **Fragments outside the shell**: what escaped through a window or an open
  door. Clip on a footprint. Build that footprint from **wall points only**;
  built from all points, the escaped fragments drag the outline outwards and
  nothing is clipped. If you have an external outline of the building, use that
  instead: an outline that does not come from the scan being cleaned cannot
  inherit its errors.
- **Loose clusters**: DBSCAN at eps 0.25 m, keep clusters above a few thousand
  points. A house is one connected thing; a floating shred is not.

Margins that work: +0.50 m for the exterior (keeps gutter, overhang, reveals),
+0.15 m for the interior (an inner wall is always inside the facade, so
anything outside the outline escaped), -0.50 m to isolate what the exterior
scan caught through an open door.

## 4. Yaw from the masonry

`heading.py`. Filter for near vertical normals (`abs(nz) < 0.25`), take the
azimuth modulo 90 degrees, and refine the histogram peak with its neighbours.
Thousands of points vote, so the answer is stable to hundredths of a degree.

Plot the whole distribution, not just the peak. If two clouds give directions
that differ by more than a few tenths, the cause is usually different walls
dominating each scan (a scan that saw more of one wing), not a rotation error.
The distribution shows that; a single number hides it.

Open3D normal signs are arbitrary. Filtering by sign rather than by `abs()`
silently loses half the walls; that bug cost a west facade that "had zero
points".

## 5. Registering a pair

`align.py`: yaw from the masonry (four quarter turn candidates, scored by
footprint correlation), z from the difference between the two floor planes, xy
from the correlation peak, then a translation only point to plane refinement at
falling radii (0.60 down to 0.04 m).

Guards that earned their place:

- The height is **held** when it came from the floor planes. Free it only with
  `--free-z`, and only when nothing pins it.
- If the refinement makes the median residual worse, it is dropped. That means
  something outside the wall band is pulling; narrow `--band`.
- If the runner up yaw scores within 10 percent of the winner, the script says
  so. A near symmetric room cannot tell a half turn from a whole one by
  correlation alone. Decide it by eye with `views.py overlay` and force it with
  `--yaw`.
- `--z-dst` when the destination plane is not the lowest one in the cloud: a
  closet on the first floor must be matched to the first floor, not to the
  ground floor that also sits in the same file.

### Storey to storey

The shared feature is the staircase, and it needs care:

- Use only the **lowest treads**. Higher up, the downstairs scan no longer
  resolves individual treads and smears them into a slope, and that smear drags
  the fit askew. Afterwards, cut that smeared section out of the downstairs
  scan: it is not measurable geometry.
- Do not let a free optimisation choose the height. A ground floor with four
  ceiling levels 12 to 17 cm apart plus a stair that is nearly periodic along
  its own slope is exactly the shape that makes a wrong answer score well.
- Take the height from the ground floor **floor** instead: the upstairs scan
  started downstairs, so that plane is in both clouds, and unlike a ceiling
  there is only one of it.

### Room to storey

Same recipe, plus `--z-dst` for the right storey. Watch the near symmetry
warning: a hallway closet is close to square.

### Interior to exterior

They see opposite faces of the same wall, so they share no surface at all.

The route that works: while scanning outside, walk a few metres in through an
open door. That patch is the shared geometry. Isolate it with
`clip_footprint.py --from-walls --margin -0.5` (erode inwards so the facade
and the door frame drop out), then register the interior onto that patch with
`align.py`, and verify with `check_pair.py`.

An alternative exists on paper: window and door openings pass through the wall,
so a silhouette of the wall plane with its holes can be correlated from both
sides, and the wall thickness falls out as the residue. It was tried here and
gave implausible thicknesses of about a metre. It is documented for the case
where there is genuinely no shared patch, but it is not the first choice.

## 6. Refinement that may only translate

`pcloud.refine_translation` is the workhorse: multi scale point to plane with
a squared distance weight, iterating at falling radii, clipping each step to 8
cm, and refusing to move axes flagged as locked.

Lock an axis whenever its value is a **datum** rather than an estimate: a floor
level you measured, a height an external model states. Left free, an optimiser
will happily trade 28 cm of that height for two percent more overlap, and it
will report that as an improvement.

## 7. Merging

Where two scans cover the same surface, keep the sharper one, and measure which
that is: the median nearest neighbour distance says how fine the detail is (6.1
mm against 8.2 mm in the case at hand).

Drop only points inside the overlap and only within a small radius (6 cm), so
the edges of the detail scan keep their surroundings and no hole appears.

## 8. Looking at it

Numbers can be right while the whole is wrong.

- `views.py overlay` after every registration: two clouds in two colours, in
  plan and in two sections. Outer walls must coincide, inner walls need not,
  floors must stack, the stairs must run on.
- `views.py show` for the deliverable: isometrics, elevations, sections and
  plans in true colour, drawn back to front so you do not look straight through
  the facade at the back wall.

Reference heights on the sections (`--level 21.60 ridge`) turn a picture into a
check.
