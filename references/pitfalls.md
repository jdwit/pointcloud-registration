# Traps, with the numbers that exposed them

Each of these cost time on a real project. They are listed as symptom, cause,
fix.

## The fit converges beautifully onto the wrong plane

**Symptom.** Free ICP puts the upper storey one floor thickness too low, on the
wrong ceiling, and scores better there than in the right place.

**Cause.** The ground floor had four ceiling levels 12 to 17 cm apart, and a
staircase is nearly periodic along its own slope. Two large flat planes yield
more inlier points than a small correct feature, so the wrong pose wins on the
metric being optimised.

**Fix.** Take the height from the ground floor floor plane, which appears in
both scans and is unique, and never let the optimiser choose between candidate
planes.

## The staircase drags the fit askew

**Symptom.** Registering on the whole staircase gives a worse result than
registering on part of it.

**Cause.** Above about 10 cm off the floor, the downstairs scan no longer
resolves the treads; it smears them into a smooth slope. Fitting a sharp stair
against a smear pulls the pose along the slope.

**Fix.** Use only the lowest treads (`ZTOP = 0.10`), and afterwards cut the
smeared section out of the downstairs scan; it is not measurable geometry.
Result: median 16 mm on the lowest treads, 9 mm agreement on the ground floor
floor, rotation residual 0.02 deg.

## The correction that made it worse

**Symptom.** Coarse pose gives a median residual of 44 mm; after refinement it
is 251 mm, with the height run away by 824 mm.

**Cause.** The refinement was allowed to move an axis that was already pinned
by the floor planes, and something outside the wall band (a ceiling, a lower
storey) pulled it there.

**Fix.** Lock z when it came from a plane; drop a refinement that increases the
median residual. Both are now built into `align.py`. Same case with the guards:
44 mm coarse, 40 mm refined, height untouched.

## Two percent of overlap for 28 centimetres of height

**Symptom.** ICP against an external model of the same building improves the
fitness a little by lowering the whole cloud 28 cm.

**Cause.** The model states a terrain height, and that height was the one value
in the whole exercise that was known independently. It is a datum, not a
variable, but ICP has no way of knowing that.

**Fix.** Solve only x and y against the model and hold z at the datum. That is
what `--lock-z` does.

## Half the walls disappear

**Symptom.** A facade "has zero points" when filtering wall normals by sign.

**Cause.** Open3D normal orientation is arbitrary; a plane can come back with
its normals pointing either way.

**Fix.** Always compare with `abs()`. For finding planes, bin the coordinate
along the axis in 5 cm slices and look for peaks, rather than trusting the
normal direction.

## Nothing gets clipped

**Symptom.** Clipping on the building outline removes almost no points, even
though there is visibly a garden in the cloud.

**Cause.** The outline was built from all points, so the very fragments that
escaped through the windows pushed the outline outwards to include themselves.

**Fix.** Build the outline from wall points only, or better, from an external
footprint of the building that does not come from this scan at all.

## Clipping on a model outline eats the building

**Symptom.** A vestibule is missing from the delivered cloud. So are strips
along two facades and the whole terrace area: 201,000 points of real
measurement, gone.

**Cause.** The cloud had been clipped to the footprint of a national building
model with a generous looking margin. But that footprint is the simplified
outline of the volume, not the line of your gevel. A bay, a porch, a vestibule,
a chamfered corner: all of that is smoothed away in the model and therefore
falls outside the outline.

**Fix.** Clipping to a footprint is off by default in `clean.py` for this
reason. Remove outliers and loose clusters, which cannot delete anything that
is attached to the building, and leave the rest in. A cloud with too much
garden costs the modeller nothing; a cloud missing a vestibule costs a site
visit.

**If you do clip**, plot what fell away before you accept it, in plan and in
colour. The mistake is invisible in a point count and obvious in a picture.

## A vertical constraint that was not there

**Symptom.** The interior sat floating above the exterior, and forcing them
together looked wrong on a house with a basement.

**Cause.** An assumption that a ground floor of a house with a basement cannot
sit at terrain level. It can. The little patch of floor just inside the back
door is a real anchor, and it put the floor 0.07 m above the terrain.

**Fix.** Let the shared floor patch decide, then check the number for
plausibility instead of assuming it in advance.

## Chunks merged too early

**Symptom.** After lifting a broken off chunk to the right height, the sideways
offset can no longer be found.

**Cause.** The two chunks do not overlap, so once they are in one file there is
nothing left that distinguishes them.

**Fix.** Keep the chunks as separate files with separate transforms until the
sideways offset is settled. Only height was equalised at that point; that is a
deliberate, documented, partial result.

## Correcting modelled data by eye

**Symptom.** A roof taken from an external building model looked off centre
over the scanned walls. Two successive corrections were computed (145 mm in y,
then 182 mm in x, after measuring the ridge at 680 mm off the centre between
the facades) and neither made the roof sit right.

**Cause.** Part of the measured asymmetry came from the measurement band
itself. Above a certain height the west side has no interior wall at all, only
a stairwell, so "clearance" there was metres rather than centimetres and skewed
every average. And that model is fitted to airborne lidar with a reported RMSE
of 0.14 m; a shift of that order is inside its own noise.

**Fix.** Both corrections were reverted and the roof was delivered in the
model's original pose, with the discrepancy documented. Source data that
anyone can re-derive beats a hand tuned correction nobody can reproduce. The
computed values were kept in a json in case someone wants them.

**General rule.** Before correcting modelled reference data against your scan,
check whether the difference exceeds the stated accuracy of that model. If it
does not, document it and leave it alone.

## The 0.6 degree that is not an error

**Symptom.** Interior and exterior differ by 89.4 deg, not 90 deg.

**Cause and reading.** Either the building is out of square (normal for 1900
construction) or a scan is slightly tilted. Measured against the axes of the
external model, the final cloud sits 0.64 deg off, which over a 15 m facade is
167 mm. That is a property of the building, not of the registration, and the
modeller needs to know it so they do not force walls onto the grid.

**Fix.** Report it. Above roughly 0.8 deg, investigate before registering.

## The masonry anchor is only as sharp as its own peak

**Symptom.** Everything is done right and a room scan still lands 12 cm out
against a cloud of the same rooms.

**Cause.** The yaw was measured from the masonry direction and then locked, as
it should be, but on this scanner the direction histogram is a hill about six
degrees wide instead of a spike a tenth of a degree wide. Locking the peak of a
six degree hill locks in whatever the peak happened to be, and one degree over
a 15 m room is 260 mm.

**Fix.** Measure the width of the peak, not just its position, and let the
refinement search the yaw inside that width and nowhere else. `align.py` does
this by default: it reports the half width per cloud and searches plus or minus
that much, capped at 3 degrees. On a scan with a sharp peak the window comes out
at a tenth of a degree and nothing changes; on the smeared one it recovered
1.9 degrees and took the median residual from 125 mm to 74 mm.

**Read it as a quality number.** A half width under half a degree means a scan
that held its heading. Several degrees means the scan drifted while walking,
and no rigid transform will fit it better than that drift.

## A corridor matches anywhere

**Symptom.** In a ranking of which scans overlap, one narrow hallway scan came
out as the best match for eight different rooms, including rooms on the other
floor.

**Cause.** Its wall points are two parallel planes. Two parallel planes pin one
direction and leave sliding along the corridor completely free, so they fit
against any pair of parallel walls in the building.

**Fix.** Do not trust a pairing whose matched points all share one wall
direction. Check that the overlap contains both directions before believing it,
and prefer pairs that share a corner.

## Two files, one scan

**Symptom.** A pair scored a perfect 1.000 with a median of 0 mm.

**Cause.** Two files in the folder were byte for byte the same scan under
different names.

**Fix.** Worth knowing before you spend a day registering them. A perfect score
is a duplicate, not a triumph.
