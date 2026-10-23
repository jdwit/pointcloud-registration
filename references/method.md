# The method, step by step

## 0. What the input is

Polycam on an iPhone Pro writes PLY with double coordinates and uchar colour.
It writes no normals and no mesh, and one file per scan. Each scan sits in its
own local frame, centred near the origin. Scale is metric and trustworthy,
because LiDAR measures distance. Orientation is level, because the scan is
gravity aligned. Everything else is arbitrary per session.

Usable range is about 5 m. Beyond that the scanner infers the depth instead of
measuring it. That is why high gable ends scanned from the ground are the worst
part of any exterior scan. It is also why a selfie stick helps.

## 1. Inspect before anything else

`inspect_cloud.py` gives point count, extent, median point spacing, the
lowest large horizontal plane, the masonry direction, and the peaks in the
height histogram (the floors and ceilings). Read it before you make any plan:

- two terrain levels metres apart mean the scan broke. Go to step 2
- a spacing of 6 mm against 22 mm tells you which cloud wins in an overlap
- the z peaks tell you which plane to use as the height anchor. They also warn
  you when a storey has several ceiling levels

## 2. Repairing tracking loss

Symptom: one exterior scan holds two ground levels several metres apart.
ARKit lost tracking during a fast move (typically hoisting the phone on a
stick) and continued in a shifted frame.

The split is **spatial, not chronological**: two connected areas in plan with a
border between them. `split_ground_groups.py` maps the ground height per half
metre cell and classifies the cells. Then it cleans the border with a majority
filter and lifts the low group.

Take the lift from the ground in the cells right along the border, where the
two ought to join. In the case at hand that gave 3.018 m, against 3.25 m read
off the two peaks in the height histogram. The border value is the sharper
number. It compares the two sides at the place where they must agree.

Check the auto split with the printed terrain range. Set `--split-z` yourself
if the largest gap is not where the two levels part.

This step sets only the height. ICP cannot solve the sideways offset between the
groups, because the groups do not overlap. That offset has to come from the
ground that runs across the border and from walls that cross it. Keep the
groups in separate files until you settle it. A merge freezes an offset that
you can no longer remove.

## 3. Cleaning

Two kinds of rubbish, two remedies:

- **Statistical outliers**: `nb_neighbors=20, std_ratio=2.0` removes sensor
  noise and keeps the detail.
- **Fragments outside the shell**: what escaped through a window or an open
  door. Clip on a footprint. Build that footprint from **wall points only**.
  If you build it from all points, the escaped fragments drag the outline
  outwards and nothing gets clipped. If you have an external outline of the
  building, use that instead. An outline that does not come from the scan you
  clean cannot inherit its errors.
- **Loose clusters**: DBSCAN at eps 0.25 m, keep clusters above a few thousand
  points. A house is one connected thing. A floating shred is not.

Margins that work:

- +0.50 m for the exterior (keeps gutter, overhang, reveals)
- +0.15 m for the interior. An inner wall is always inside the facade, so
  anything outside the outline escaped
- -0.50 m to isolate what the exterior scan caught through an open door

## 4. Yaw from the masonry

`heading.py`. Filter for near vertical normals (`abs(nz) < 0.25`), take the
azimuth modulo 90 degrees, and refine the histogram peak with its neighbours.
Thousands of points vote, so the answer is stable to hundredths of a degree.

Plot the whole distribution, not just the peak. Two clouds can give directions
that differ by more than a few tenths. The cause is usually that different
walls dominate each scan (a scan that saw more of one wing), not a rotation
error. The distribution shows that. A single number hides it.

Open3D normal signs are arbitrary. If you filter by sign instead of by
`abs()`, you lose half the walls without a warning. That bug once gave me a
west facade that "had zero points".

## 5. Registering a pair

`align.py` works in this order:

1. yaw from the masonry (four quarter turn candidates, scored by footprint
   correlation)
2. z from the difference between the two floor planes
3. xy from the correlation peak
4. a translation only point to plane refinement at falling radii (0.60 down to
   0.04 m)

Guards I added after real failures:

- The script **holds** the height when it came from the floor planes. Free it
  only with `--free-z`, and only when nothing pins it.
- If the refinement makes the median residual worse, the script drops it. That
  means something outside the wall band pulls on the fit. Narrow `--band`.
- If the runner up yaw scores within 10 percent of the winner, the script says
  so. In a near symmetric room, correlation alone cannot tell a half turn from
  a whole one. Decide it by eye with `views.py overlay` and force it with
  `--yaw`.
- Use `--z-dst` when the destination plane is not the lowest one in the cloud.
  For example, a closet on the first floor must match the first floor. It must
  not match the ground floor that also sits in the same file.

### Storey to storey

The shared feature is the staircase, and it needs care:

- Use only the **lowest treads**. Higher up, the downstairs scan no longer
  resolves individual treads and smears them into a slope. That smear drags
  the fit askew. Afterwards, cut that smeared section out of the downstairs
  scan. It is not measurable geometry.
- Do not let a free optimisation choose the height. Consider a ground floor
  with four ceiling levels 12 to 17 cm apart. Add a stair that is nearly
  periodic along its own slope. That shape makes a wrong answer score well.
- Take the height from the ground floor **floor** instead. The upstairs scan
  started downstairs, so that plane is in both clouds. Unlike a ceiling, there
  is only one of it.

### Room to storey

Same recipe, plus `--z-dst` for the right storey. Watch the near symmetry
warning. A hallway closet is close to square.

### Interior to exterior

They see opposite faces of the same wall, so they share no surface at all.

This route works:

1. While you scan outside, walk a few metres in through an open door. That
   patch is the shared geometry.
2. Isolate it with `clip_footprint.py --from-walls --margin -0.5`. The erosion
   inwards drops the facade and the door frame.
3. Register the interior onto that patch with `align.py`.
4. Check the result with `check_pair.py`.

An alternative exists on paper. Window and door openings pass through the
wall. So you can correlate a silhouette of the wall plane with its holes from
both sides, and the wall thickness falls out as the residue. I tried it here,
and it gave implausible thicknesses of about a metre. I document it for the
case where there is no shared patch at all. It is not the first choice.

## 6. Refinement that may only translate

`pcloud.refine_translation` does most of the work. It runs a multi scale point
to plane fit with a squared distance weight, at falling radii. It clips each
step to 8 cm and refuses to move axes flagged as locked.

Lock an axis whenever its value is a **datum** and not an estimate. Examples
are a floor level you measured, or a height an external model states. If you
leave the axis free, an optimiser can trade 28 cm of that height for two
percent more overlap. It then reports that as an improvement.

## 7. Merging

Where two scans cover the same surface, keep the sharper one, and measure which
one that is. The median nearest neighbour distance says how fine the detail is
(6.1 mm against 8.2 mm in the case at hand).

Drop only points inside the overlap and only within a small radius (6 cm).
Then the edges of the detail scan keep their surroundings and no hole appears.

## 8. Looking at it

Numbers can be right while the whole is wrong.

- `views.py overlay` after every registration: two clouds in two colours, in
  plan and in two sections. Outer walls must coincide, inner walls need not,
  floors must stack, the stairs must run on.
- `views.py show` for the deliverable: isometrics, elevations, sections and
  plans in true colour. It draws back to front, so you do not look through the
  facade at the back wall.

Reference heights on the sections (`--level 21.60 ridge`) make a picture into a
check.
