# pointcloud-registration

Registering handheld LiDAR scans of a building: a method that works, a small
toolkit that implements it, and the traps that cost me days.

Point a phone at a house and you get several clouds that each live in their own
world: one per room, one per storey, one of the outside, each in whatever frame
the phone happened to start in. Getting them into one cloud, and that cloud into
real world coordinates, is where consumer scanning usually falls apart. Run a
free ICP over two storeys and it will happily put the upper floor on the wrong
ceiling and report a better score for it than for the right answer.

## The core principle

**Measure every degree of freedom from the source that pins it hardest, lock it,
and let only what is left move.**

A phone scan is levelled by gravity, so roll and pitch are already right;
solving for them only lets tilt in. That leaves four unknowns, each with its own
anchor:

| Unknown | Anchor | Why that one |
|---|---|---|
| yaw | the masonry direction, modulo 90 degrees | thousands of wall normals vote, stable to hundredths of a degree |
| z | a horizontal plane in both clouds | a floor or the terrain: large, unambiguous, one of a kind |
| xy | cross correlation of the wall footprints | uses the whole plan, not one feature |
| the rest | translation only point to plane refinement | rotation stays where it was measured |

ICP never decides anything here. It polishes a pose you already fixed by
measurement, and it is only ever allowed to translate.

And then: **judge every step on a quantity that was not in the fit.** A fit
always reports that it converged; it minimised the distance it was steering on.
The distance from an inner wall to the facade behind it, the height of a floor
above the terrain, whether the facades stop where the national roof model says
the eaves are: those are the numbers that catch a registration that is a whole
room out.

## Try it without any data

```bash
git clone https://github.com/jdwit/pointcloud-registration
cd pointcloud-registration
uv run --python 3.11 --with open3d --with numpy --with scipy --with matplotlib \
    python demo/demo.py
```

The demo builds two synthetic scans of the same room, offset the way two phone
sessions differ, registers them and checks the known transform comes back. On
the reference machine it recovers the rotation to 0.05 degrees and the position
to 3 mm.

## The toolkit

Every script prints what it decided and why, and takes `--json` to write that
decision next to its output. Run them with the same `uv run` prefix as above.

| Script | What it does |
|---|---|
| `inspect_cloud.py` | first look: points, extent, point spacing, floor level, masonry direction, height histogram |
| `heading.py` | relative rotation between two clouds, from the wall directions, with the full distribution plotted |
| `clean.py` | statistical outliers, fragments that escaped through windows, loose clusters |
| `align.py` | the workhorse: yaw from the masonry, z from the floor planes, xy from footprint correlation, then translation only refinement |
| `check_pair.py` | verification on quantities that were not in the fit: wall thickness, floor above terrain, shared surfaces |
| `split_ground_groups.py` | repairs a scan that broke into chunks when ARKit lost tracking |
| `clip_footprint.py` | clip to a building outline, from an external reference or from the cloud's own walls |
| `merge.py` | merge two clouds, keeping the sharper one where they overlap |
| `views.py` | overlay two clouds to check a registration by eye; plans, sections, elevations and isometrics of the result |
| `vegetation.py` | trees and shrubs out of a colour scan, for shading studies |
| `pcloud.py` | the shared library, if you want to build your own step |

Dependencies are open3d, numpy, scipy and matplotlib. Input is PLY (as Polycam
and CloudCompare write it) or plain xyz text; convert E57 or LAS first.

## Use it as a Claude skill

The repo doubles as a [Claude Code](https://claude.com/claude-code) skill: the
method, the traps and the tool descriptions are written for an agent as much as
for a person.

```bash
git clone https://github.com/jdwit/pointcloud-registration \
    ~/.claude/skills/pointcloud-registration
```

Claude then picks it up whenever you ask it to align, merge or georeference
scans, and follows the same discipline instead of reaching for a free ICP.

## Documentation

- [SKILL.md](SKILL.md) - the method in short, with the order of operations
- [references/method.md](references/method.md) - each step in detail and the reasoning
- [references/pitfalls.md](references/pitfalls.md) - what went wrong in practice, with the numbers
- [references/georeferencing-nl.md](references/georeferencing-nl.md) - 3DBAG, AHN and PDOK, RD and NAP, and the route into Revit without float precision errors
- [references/worked-example.md](references/worked-example.md) - one building end to end

The georeferencing chapter is specific to the Netherlands, because that is where
the free national building model and terrain data made it easy. The rest of the
method has nothing Dutch about it.

## What this is not

Consumer LiDAR at building scale is renovation grade: published figures put the
error at 3 to 20 cm over 10 to 15 m spans, worse when you walk rather than stop
and hold. That is fine for layout, volumes, routing and a 1:100 permit set, and
it is not fine for structural work or made to measure joinery. This toolkit
makes the registration honest and puts numbers on it; it does not turn a phone
into a survey instrument. For the control measurements that keep a model
defensible, see [scan2bim-nl](https://github.com/jdwit/scan2bim-nl).

## Licence

MIT.
