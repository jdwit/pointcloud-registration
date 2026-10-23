# pointcloud-registration

A method and a small Python toolkit to register LiDAR scans of a building into one cloud. Checks show how accurate the result is.

A phone scan of a house gives several clouds. You get one per room, one per storey and one of the outside. Each cloud has its own frame, set by where the phone started. This toolkit puts those clouds onto each other. A free ICP over two storeys often puts the upper floor on the wrong ceiling. It then reports a better score for that result than for the right one.

## Core principle

**Measure each degree of freedom from the source that sets it best. Lock it. Let only the remaining unknowns move.**

Gravity levels a phone scan, so roll and pitch are already right. If you solve for them, you only add tilt. Four unknowns remain, and each has its own anchor:

| Unknown | Anchor | Reason |
|---|---|---|
| yaw | the masonry direction, modulo 90 degrees | thousands of wall normals vote. The result is stable to hundredths of a degree. |
| z | a horizontal plane in both clouds | a floor or the terrain. It is large and unambiguous, and there is only one. |
| xy | cross correlation of the wall footprints | it uses the whole plan, not one feature |
| the rest | point to plane refinement, translation only | the rotation stays where you measured it |

ICP does not decide anything here. It refines a pose that you already set by measurement. It can only translate.

**Check each step on a quantity that was not in the fit.** A fit always reports that it converged. The reason is that it minimised the distance it was steering on. These numbers show a registration that is a full room out:
- the distance from an inner wall to the facade behind it
- the height of a floor above the terrain
- a span that you measured with a laser distance meter.

## Run the demo without data

```bash
git clone https://github.com/jdwit/pointcloud-registration
cd pointcloud-registration
uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib \
    python demo/demo.py
```

The demo builds two synthetic scans of the same room, with the offset that two phone sessions typically have. It registers them and checks that the known transform comes back. On the reference machine it recovers the rotation to 0.05 degrees and the position to 3 mm.

## Toolkit

Each script prints what it decided and why. With `--json` it also writes that decision next to its output. Run the scripts with the same `uv run` prefix as the demo.

| Script | What it does |
|---|---|
| `inspect_cloud.py` | first look: points, extent, point spacing, floor level, masonry direction, height histogram |
| `heading.py` | relative rotation between two clouds, from the wall directions, with a plot of the full distribution |
| `find_pairs.py` | ranks your scans by overlap, so you know which pairs to register first |
| `e57_to_ply.py` | reads E57 and writes a thinned PLY |
| `clean.py` | removes statistical outliers, fragments outside the windows and loose clusters |
| `align.py` | main registration: yaw from the masonry, z from the floor planes, xy from footprint correlation, then translation-only refinement |
| `check_pair.py` | checks quantities that were not in the fit: wall thickness, floor above terrain, shared surfaces |
| `split_ground_groups.py` | repairs a scan that broke into chunks when ARKit lost tracking |
| `clip_footprint.py` | clips to a building outline, from an external reference or from the walls of the cloud |
| `merge.py` | merges two clouds and keeps the sharper one where they overlap |
| `views.py` | overlays two clouds for a visual check, and makes plans, sections, elevations and isometrics of the result |
| `pcloud.py` | the shared library, for your own steps |

Dependencies: open3d, numpy, scipy and matplotlib, plus pye57 for E57 input. Input formats: PLY (as Polycam and CloudCompare write it), E57 or plain xyz text.

## Documentation

- [references/workflow.md](references/workflow.md): the order of operations, the checks and the common mistakes
- [references/method.md](references/method.md): each step in detail, with the reasoning
- [references/pitfalls.md](references/pitfalls.md): problems I found in practice, with the numbers
- [references/worked-example.md](references/worked-example.md): one building from start to end

The scope is narrow: put separate scans onto each other, and show that they are in the right position. To place the result in a national grid, a site plan or a BIM authoring tool, you need other tools.

## Limits

At building scale, consumer LiDAR is renovation grade. Published figures put the error at 3 to 20 cm over spans of 10 to 15 m. The error is larger when you walk during the scan than when you stop and hold the phone still. That accuracy is sufficient for layout, volumes, routing and a 1:100 permit set. It is not sufficient for structural work or made-to-measure joinery. This toolkit makes the registration measurable. It does not make a phone a survey instrument. For the control measurements that a model needs, see [scan2bim-nl](https://github.com/jdwit/scan2bim-nl).

## Licence

MIT.
