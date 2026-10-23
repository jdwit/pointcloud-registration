# Pitfalls, with the numbers that exposed them

Each of these cost time on a real project. Each entry gives the symptom, the
cause and the fix.

## The fit converges onto the wrong plane

**Symptom.** Free ICP puts the upper storey one floor thickness too low, on the
wrong ceiling. It scores better there than in the right place.

**Cause.** The ground floor had four ceiling levels 12 to 17 cm apart, and a
staircase is nearly periodic along its own slope. Two large flat planes yield
more inlier points than a small true feature. So the wrong pose wins on the
metric that the fit optimises.

**Fix.** Take the height from the ground floor floor plane. It appears in both
scans and is unique. Never let the optimiser choose between candidate planes.

## The staircase drags the fit askew

**Symptom.** Registering on the whole staircase gives a worse result than
registering on part of it.

**Cause.** Above about 10 cm off the floor, the downstairs scan no longer
resolves the treads. It smears them into a smooth slope. A fit of a sharp
stair against a smear pulls the pose along the slope.

**Fix.** Use only the lowest treads (`ZTOP = 0.10`). Afterwards, cut the
smeared section out of the downstairs scan. It is not measurable geometry.
Result: median 16 mm on the lowest treads, 9 mm agreement on the ground floor
floor, rotation residual 0.02 deg.

## The correction that made it worse

**Symptom.** Coarse pose gives a median residual of 44 mm. After refinement it
is 251 mm, and the height ran away by 824 mm.

**Cause.** The refinement could move an axis that the floor planes already
pinned. Something outside the wall band (a ceiling, a lower storey) pulled it
there.

**Fix.** Lock z when it came from a plane. Drop a refinement that increases
the median residual. `align.py` now does both. Same case with the guards:
44 mm coarse, 40 mm refined, height untouched.

## Two percent of overlap for 28 centimetres of height

**Symptom.** ICP against an external model of the same building improves the
fitness a little by lowering the whole cloud 28 cm.

**Cause.** The model states a terrain height. That height was the one value in
the whole exercise with an independent source. It is a datum, not a variable,
but ICP has no way of knowing that.

**Fix.** Solve only x and y against the model and hold z at the datum.
`--lock-z` does that.

## Half the walls disappear

**Symptom.** A facade "has zero points" when you filter wall normals by sign.

**Cause.** Open3D normal orientation is arbitrary. A plane can come back with
its normals pointing either way.

**Fix.** Always compare with `abs()`. To find planes, bin the coordinate
along the axis in 5 cm slices and look for peaks. Do not trust the normal
direction.

## Nothing gets clipped

**Symptom.** Clipping on the building outline removes almost no points. Yet the
cloud visibly contains a garden.

**Cause.** I built the outline from all points. So the fragments that escaped
through the windows pushed the outline outwards to include themselves.

**Fix.** Build the outline from wall points only. Better, use an external
footprint of the building that does not come from this scan at all.

## Clipping on a model outline eats the building

**Symptom.** A vestibule is missing from the delivered cloud. So are strips
along two facades and the whole terrace area: 201,000 points of real
measurement, gone.

**Cause.** I clipped the cloud to the footprint of a national building
model, with a margin that looked generous. But that footprint is the simplified
outline of the volume, not the line of your facade. The model smooths away a
bay, a porch, a vestibule or a chamfered corner. So they fall outside the
outline.

**Fix.** For this reason, `clean.py` does not clip to a footprint by default.
Remove outliers and loose clusters, and leave the rest in. Those two steps
cannot remove anything attached to the building. A cloud with too much garden
costs the modeller nothing. A cloud without a vestibule costs a site visit.

**If you do clip**, plot what fell away before you accept it, in plan and in
colour. A point count does not show the mistake. A picture does.

## A vertical constraint that was not there

**Symptom.** The interior sat floating above the exterior. On a house with a
basement, forcing them together looked wrong.

**Cause.** I assumed that the ground floor of a house with a basement cannot
sit at terrain level. It can. The small patch of floor just inside the back
door is a real anchor, and it put the floor 0.07 m above the terrain.

**Fix.** Let the shared floor patch decide. Then check the number for
plausibility instead of assuming it in advance.

## Chunks merged too early

**Symptom.** After you lift a broken off chunk to the right height, you can no
longer find the sideways offset.

**Cause.** The two chunks do not overlap. Once they are in one file, nothing
distinguishes them.

**Fix.** Keep the chunks as separate files with separate transforms until you
settle the sideways offset. At that point I equalised only the height. That
is a deliberate, documented, partial result.

## Adjusting modelled data by eye

**Symptom.** A roof from an external building model looked off centre over the
scanned walls. I measured the ridge at 680 mm off the centre between the
facades. Then I computed two successive corrections (145 mm in y, then 182 mm
in x). Neither made the roof sit right.

**Cause.** Part of the measured asymmetry came from the measurement band
itself. Above a certain height the west side has no interior wall at all, only
a stairwell. So "clearance" there was metres instead of centimetres, and it
skewed every average. Also, that model is fitted to airborne lidar with a
reported RMSE of 0.14 m. A shift of that order is inside its own noise.

**Fix.** I reverted both corrections and delivered the roof in the model's
original pose, with the discrepancy documented. Anyone can re-derive the source
data. Nobody can reproduce a hand tuned correction. I kept the computed values
in a json in case someone wants them.

**General rule.** Before you adjust modelled reference data against your scan,
check whether the difference exceeds the stated accuracy of that model. If it
does not, document it and leave it alone.

## The 0.6 degree that is not an error

**Symptom.** Interior and exterior differ by 89.4 deg, not 90 deg.

**Cause and reading.** Either the building is out of square (normal for 1900
construction) or a scan is slightly tilted. Against the axes of the external
model, the final cloud sits 0.64 deg off. Over a 15 m facade that is 167 mm.
That is a property of the building, not of the registration. The modeller
needs to know it, so that they do not force walls onto the grid.

**Fix.** Report it. Above roughly 0.8 deg, investigate before you register.

## The masonry anchor is only as sharp as its own peak

**Symptom.** You do every step right, and a room scan still lands 12 cm out
against a cloud of the same rooms.

**Cause.** I measured the yaw from the masonry direction and then locked it,
as the method says. But on this scanner the direction histogram is a hill about
six degrees wide, not a spike a tenth of a degree wide. If you lock the peak of
a six degree hill, you lock in a random peak position. One degree over a 15 m
room is 260 mm.

**Fix.** Measure the width of the peak, not just its position. Let the
refinement search the yaw inside that width and nowhere else. `align.py` does
this by default. It reports the half width per cloud and searches plus or minus
that much, capped at 3 degrees. On a scan with a sharp peak the window comes out
at a tenth of a degree and nothing changes. On the smeared scan it recovered
1.9 degrees and took the median residual from 125 mm to 74 mm.

**Read it as a quality number.** A half width under half a degree means a scan
that held its heading. Several degrees means the scan drifted during the walk.
No rigid transform will fit it better than that drift.

## A corridor matches anywhere

**Symptom.** In a ranking of which scans overlap, one narrow hallway scan came
out as the best match for eight different rooms. That included rooms on the
other floor.

**Cause.** Its wall points are two parallel planes. Two parallel planes pin one
direction and leave sliding along the corridor free. So they fit against any
pair of parallel walls in the building.

**Fix.** Do not trust a pairing whose matched points all share one wall
direction. Check that the overlap contains both directions before you believe
it. Prefer pairs that share a corner.

## Two files, one scan

**Symptom.** A pair scored a perfect 1.000 with a median of 0 mm.

**Cause.** Two files in the folder were byte for byte the same scan under
different names.

**Fix.** Check for duplicates before you spend a day registering them. A
perfect score means a duplicate.
