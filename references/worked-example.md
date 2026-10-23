# Worked example

A detached brick villa from 1900, four handheld scans turned into one cloud.
The numbers come from a real project. The building is not named.

## The inputs

| Scan | Points | Note |
|---|---|---|
| exterior | 2,586,560 | broke into two chunks through tracking loss |
| ground floor | 1,890,640 | four ceiling levels, 12 to 17 cm apart |
| first floor | 1,765,680 | started downstairs, so it carries the ground floor floor |
| a walk in closet | 377,240 | scanned later, 6.1 mm spacing against 8.2 mm |
| an existing model of the building, sampled | 259,730 | used as the external reference for the outside |

Phone: an iPhone Pro in LiDAR room mode. I scanned the high gable parts with
the phone on a 3 m selfie stick.

## The chain

1. **Exterior repair.** Two terrain levels 3 m apart, split spatially on half
   metre cells, low group lifted 3.018 m. That lift came from the ground in the
   cells along the border. It is sharper than the 3.25 m that the two peaks in
   the height histogram suggested. The groups stayed separate files.
2. **Storey to storey.** First floor onto ground floor: rotation 178.357 deg
   from the masonry, height from the ground floor floor, shift from the lowest
   treads of the staircase. Checks: 16 mm median on the treads, 71 percent
   within 2 cm, floor agreement 9 mm, rotation residual 0.02 deg. 13 of 17 wall
   planes fall within 14 mm. The four exceptions are stud walls and boxed in
   shafts, not registration error.
3. **Interior into the exterior.** During the exterior scan I walked a few
   metres in through the back door. That gave 304,627 points of kitchen,
   utility room and hall, isolated by eroding the footprint 0.5 m inwards.
   Rotation 270.15 deg, height from the two floor planes (2.459 m), xy from the
   footprint correlation. Then a translation only refinement against that
   patch. Checks: inner wall to facade 299 mm median, which is ordinary masonry
   for 1900. The ground floor sits 0.07 m above terrain.
4. **Closet into the first floor.** 89.40 deg, height from the floor difference
   of 3.416 m, 51.6 percent of points within 3 cm, median 28 mm. Deduplicated
   against the storey scan at 6 cm. The closet scan is sharper, so the merge
   dropped 133,703 storey points inside the overlap.
5. **Onto the external model.** Registered onto the sampled model of the same
   building: facade direction for the yaw, footprint correlation for xy. The
   height stayed at the terrain value that the model states. Verified against
   the model's eaves heights. The facades run out where the model says the
   eaves are.
6. **Clipped and cleaned.** Removed everything outside the model's footprint
   plus a margin (0.50 m outside, 0.15 m inside). Then statistical outliers,
   then DBSCAN fragments.
7. **Roof.** Taken from the model above the level where the scan stops, as a
   separate layer in its own colour.

## Result

Two deliverables, 4.58 M points without the modelled roof and 4.65 M with it.
Two versions on purpose: measured data alone for tracing walls, plus the
modelled roof for heights and shading studies.

Stated accuracy, in the readme that travels with the cloud:

- internal precision 16 to 28 mm scan to scan
- placement against the external model carries that model's own error, about
  135 mm here. It is a separate claim
- above the eaves the data comes from the model, not from measurement
- the building sits 0.64 deg off the model's axes, which is 167 mm over a 15 m
  facade. Do not force walls onto those axes

## Two things left unresolved on purpose

- I equalised the exterior chunks only in height. I never solved their sideways
  offset, because they do not overlap. The readme states that limitation.
- I delivered the modelled roof in its original pose. I computed two
  corrections from the scan and reverted both. The difference was inside the
  stated 0.14 m RMSE of the roof model. See [pitfalls.md](pitfalls.md).
