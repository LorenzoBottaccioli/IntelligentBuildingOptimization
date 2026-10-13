# Floor plan: generator and corpus check

`backend/floorplan.py` builds the plan of any model from two files EnergyPlus writes itself:

* `eplusout.dxf` (from `Output:Surfaces:Drawing, DXF, Triangulate3DFace`): every surface as 3D faces in **world
  coordinates**, one layer per zone, one comment per surface (`<zone>:<surface>`) written before its faces;
* `eplusout.eio` (from `Output:Surfaces:List, Details`): the class (Wall, Floor, Roof, Window...) and area of every
  surface, and the table `Zone Information`.

The vertices of the IDF are not used: coordinate system, zone origin, north axes and rectangular surfaces are already
resolved. The footprint of a zone is its surfaces of class Floor; their area is compared with the area EnergyPlus gives
for the same surfaces (`checked`). Without a Floor surface the downward horizontal faces stand in (`derived`), without
faces the bounding box of the `.eio` (`bbox`), without that the zone has no place (`none`).

Not used as a reference: the `Floor Area` column of `Zone Information`. In the demo it says 50.48 m2 for a triangle
whose floor surface is 56.25 m2 in the same file (the surface table agrees with the geometry).

## The corpus (EnergyPlus 9.6, 685 ExampleFiles, design days only, 11 Oct 2026)

```
python tests/floorplan/generate_geometry.py --eplus C:\EnergyPlusV9-6-0 --work %TEMP%\geometry
python tests/floorplan/generate_geometry.py --eplus C:\EnergyPlusV9-6-0 --work %TEMP%\geometry --retry   # after the first pass
python tests/floorplan/measure_floorplans.py --work %TEMP%\geometry --out results.json --gallery gallery.html
```

The run keeps only the DXF, the EIO and the error file (63 MB for the corpus), takes about 1 minute with 8 workers, and
stages what an example finds next to itself (`..\datasets`, data files, a weather file for design days).

| | models |
|---|---|
| plan drawn, every zone from its floor surface and every area matching | 616 |
| plan drawn, one model with 3 zones from the downward horizontal faces (`AtticRoof_RadiantBarriers`) | 1 |
| zones lie on top of each other (not a map): `WindowTests`, `WindowTestsSimple` | 2 |
| model has no zone (plant, piping, lights only) | 29 |
| EnergyPlus could not run it here: Python plugin 19, basement/slab preprocessors 4, files missing from the install 5, parametric templates 3, other 6 | 37 |

Of the 619 models with zones that EnergyPlus ran: 617 give a plan (99.7 %). Zones: 4 226 of 4 229 from a Floor surface, 3
derived, none on the bounding box or without a place; 4 226 of 4 229 floor areas match EnergyPlus' own surface areas.

* Levels (distinct floor heights, as in `instrument.py`): median 1, p90 2, maximum 10. Zones on the busiest level: median
  3, p90 5, maximum 59; 5 models have more than 40 on one level (hospitals and the outpatient clinic): a page should show
  the zones that are instrumented, not all of them.
* Stacking is measured on a 120-cell grid: the overlapped share of the covered plan. The corpus has a gap: 0.05 and
  below (an office inside the footprint of a storage zone in the two warehouses: the model says so) against 0.55 (ten
  test rooms in a staircase). The limit is 0.25.
* The plan is in the coordinates of the model (building axes), not rotated to true north.

## Not covered

* The 37 models that did not run here (their geometry was not read at all).
* Real floor plans are not available for comparison: "correct" means that the faces EnergyPlus uses add up, and the
  pictures of a sample (hospital, clinic, school, large office, high-rise, rotated five-zone) were looked at.
* Zones with a multiplier are drawn once; a zone that spans several levels is placed at its lowest floor.
* Windows, doors and walls are not drawn.
