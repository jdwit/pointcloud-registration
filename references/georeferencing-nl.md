# Georeferencing a scan in the Netherlands, and the route into Revit

## Why 3DBAG is the anchor

A phone scan has no idea where it is. The cheapest way to give it real world
coordinates, true north and a height above NAP in one step is to register it
onto the national building model.

3DBAG (TU Delft, CC BY 4.0) publishes a LoD2.2 model per building, derived from
the AHN airborne lidar survey. It is in RD (EPSG:28992) for x and y and NAP for
z, in metres. Reported accuracy is RMSE 0.14 m.

It fits our exterior scan directly: both describe the **outer** face of the
facade, so there is no wall thickness in between, unlike the interior case.

Sample the LoD2.2 surface into a point cloud (an xyz file is enough; keep a
local variant with the RD offset removed) and register with `align.py`:

- yaw from the facade direction of both
- xy from the footprint correlation
- z **not** fitted: 3DBAG puts the terrain at a stated NAP height and that
  value is the link to the national system. Use `--lock-z`.

Then verify on something outside the fit: the 3DBAG eaves heights are where
your facades should stop. In the worked example, eaves between 2.8 and 6.8 m
above terrain against a scan that ran out at about 5.8 m; consistent, and it
also marks where scan data ends and model data begins.

## What comes from where

| Source | Gives | Note |
|---|---|---|
| 3DBAG LoD2.2 | roof planes, ridges, eaves, footprint, volume | RMSE 0.14 m; no dormers, no chimney detail |
| AHN (via PDOK WCS) | terrain and surface heights, 0.5 m grid | toposolid, garden levels |
| PDOK Locatieserver | address to RD coordinates, BAG id | the origin of your local frame |
| PDOK Kadastrale Kaart | parcel boundary | plot as surveyed data, not traced |
| PDOK aerial orthophoto | roof plan, chimneys, trees | 8 cm per pixel |
| the scan | everything you can reach from the ground | up to about 5 m per shot |

`~/Projects/scan2bim-nl` fetches all of these (`scan2bim fetch all`) and needs
no API key or account.

## Two accuracies, never averaged

State them separately, in the readme that travels with the cloud:

- **Placement on the plot**, about 135 mm, inherited from 3DBAG. This is the
  number for solar studies, plot drawings and neighbour relations. It is the
  same role a surveyor's RTK GPS targets play, with 3DBAG standing in for the
  targets.
- **Internal precision**, 16 to 28 mm scan to scan. This is the number for
  room dimensions and wall positions inside the building.

Also state where measured data stops. In the worked example: above 5.8 m over
terrain everything comes from 3DBAG modelling, not from the scan.

Consumer LiDAR at building scale is renovation grade: 3 to 20 cm over 10 to 15
m spans, worse when walking rather than stopping. Fine for layout, volumes and
a 1:100 permit set; not fine for structural work or made to measure joinery.
The honest way to state what a particular scan achieved is a control network
measured with a laser distance meter, which is what `scan2bim control check`
is for.

## Orientation numbers the modeller needs

Work these out once and put them in the readme:

| Item | Where it comes from | Shape of the value |
|---|---|---|
| RD origin of the local frame | the translation you removed from the 3DBAG model | 155123.45, 462987.10 |
| terrain level | 3DBAG, per building | 12.345 m NAP |
| geographic position | RD to WGS84 conversion of that origin | 52.0731 N, 4.9312 E |
| meridian convergence, RD grid north against true north | computed at the site | -0.18 deg for the middle of the country |
| building rotation against the RD grid | the masonry direction you measured | 0.64 deg was 167 mm over a 15 m facade |

The values in the last column are an example, not your building's.

Meridian convergence matters for sun studies only marginally (0.1773 deg is
about 43 seconds of solar motion), but a modeller who does not know the
building itself is 0.64 deg off the grid will force walls onto the axes and
lose 167 mm across the facade.

## Getting it into Revit without float errors

**Do not place the cloud at its real RD coordinates.** Revit works in single
precision internally and shows visible rounding in snapping and sections beyond
roughly 16 km from its internal origin. RD puts a Dutch site at about 500 km.

The route that works:

1. Keep the geometry at the local origin, where the registration left it.
2. Convert PLY to RCP with Autodesk ReCap.
3. Insert > Point Cloud, positioning **Auto - Origin to Internal**.
4. Set the Survey Point to your RD offset (x, y, 0) with angle
   to true north 0, since the cloud is already RD oriented.
5. Set the Project Location to the geographic coordinates, so sun studies are
   right.

That gives the real world link through Shared Coordinates while all geometry
stays near the origin. Exports to IFC or DWG carry the shared coordinates.

Deliver two versions of the cloud, with and without the modelled roof. The
modeller wants measured data alone when tracing walls, and the roof when
checking heights and shading.
