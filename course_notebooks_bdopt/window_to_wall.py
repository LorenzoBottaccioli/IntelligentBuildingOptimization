"""Window-to-wall ratio as a bdopt design variable (replaces ``besos.parameters.wwr``).

bdopt edits *fields* of the model, not geometry. A geometry edit is written as a ``GenericSelector``: a function
``setter(idf, value)`` that bdopt calls, on a copy of the model, with the value of the design variable.

What this setter does, wall by wall:

* it takes the outdoor walls (``BuildingSurface:Detailed`` with Surface Type = Wall and Outside Boundary Condition =
  Outdoors) that already carry windows (``FenestrationSurface:Detailed`` with Surface Type = Window);
* it scales every window of such a wall about its own centre, in the plane of the wall, by the same factor, so
  that the windows of the wall add up to ``ratio`` times the gross area of the wall (doors and glass doors count in
  the wall area, are not touched, and are not windows);
* it creates and deletes nothing: a wall without windows stays without windows (BESOS' ``wwr`` deleted the windows
  and built new, centred ones with geomeppy);
* **it refuses a ratio it cannot reach**: if a scaled window would leave its wall or overlap another window, a door
  or a glass door, it raises ``ValueError`` and writes nothing. A window can only grow where there is room.

How far it goes, measured on the course models (geometry, in steps of 0.01 of the ratio; see ``tests/``):

* ``test.idf``: every ratio from 0.05 to 0.83 (the two windows of its west wall meet above that);
* ``example_idf.idf``: up to 0.46 (the glass door of the south wall stops windows 3 and 4 above that);
* ``lab_building.idf``: up to 0.28. Its windows are not centred in their walls: the smaller window of
  ``Block1B:Livingroom_Wall_4_0_0`` starts 4 cm above the floor line of its wall, so any growth about its centre
  pushes it through the floor line. This is why the Lab does not use it.

``wwr()`` takes the range as an argument; choose it for your model. The field positions are those of EnergyPlus 9.6
(see the constants), so the model must be a 9.6 model.

Two things to know when you read the numbers (checked with EnergyPlus 9.6, ``Output:Table:SummaryReports``
``EnvelopeSummary``, "Window-Wall Ratio"):

* the ratio is imposed wall by wall, on the walls that already have windows. A wall without windows (the east wall of
  ``lab_building.idf`` has only a door) stays without, so the ratio of the whole building is lower: at ``ratio = 0.28``
  EnergyPlus reports 22.3 % for ``lab_building.idf``;
* EnergyPlus reports the *opening* area, which includes the window frame: at ``ratio = 0.5`` it reports 52.4 % for
  ``test.idf`` (the glass itself is 50 % of the wall).

Simulated for a year with the Torino weather file, ``test.idf`` at 0.2 / 0.5 / 0.8 gives district cooling 17.3 / 27.8 /
38.4 MWh and district heating 11.6 / 12.7 / 14.7 MWh, and ``lab_building.idf`` at 0.1 / 0.2 / 0.28 gives cooling
0.72 / 1.42 / 2.12 MWh and heating 5.08 / 4.82 / 4.70 MWh. Cooling grows with the glass in both models; heating grows in
one and falls in the other, so the sign of the effect on heating depends on the model (solar gain against heat loss: we
did not separate the two).
"""

import math

from bdopt import GenericSelector, Parameter, RangeParameter

# field positions in the EnergyPlus 9.6 Input Data Dictionary (Energy+.idd); the Name is field 0
WALL_TYPE, WALL_BOUNDARY = 1, 5                  # BuildingSurface:Detailed: Surface Type, Outside Boundary Condition
WALL_VERTICES = 11                               # BuildingSurface:Detailed: Vertex 1 X-coordinate ("Number of Vertices" is field 10)
WINDOW_TYPE, WINDOW_WALL, WINDOW_MULTIPLIER = 1, 3, 7  # FenestrationSurface:Detailed: Surface Type, Building Surface Name, Multiplier
WINDOW_VERTICES = 9                              # FenestrationSurface:Detailed: Vertex 1 X-coordinate ("Number of Vertices" is field 8)

TOLERANCE = 1e-6                                 # metres: touching an edge is not leaving the wall, nor overlapping


def vertices(obj, first):
    """``[(x, y, z), ...]``: the vertices of a surface, whose coordinates start at field ``first`` and run to the end.

    The field right before them says how many vertices there are; it is only used to check the count (it may be
    blank or ``autocalculate``).
    """
    f = list(obj.fields)
    while f and not f[-1].strip():          # blank fields at the end are not coordinates
        f.pop()
    values = f[first:]
    n = len(values) // 3
    declared = f[first - 1].strip().lower() if first - 1 < len(f) else ""
    if len(values) % 3 or n < 3 or (declared not in ("", "autocalculate") and int(float(declared)) != n):
        raise ValueError(f"{obj.class_name} {obj.name!r}: {len(values)} coordinates after field {first - 1} "
                         f"({declared!r}), not the vertices of a surface in the EnergyPlus 9.6 layout")
    v = [float(x) for x in values]
    return [tuple(v[3 * i:3 * i + 3]) for i in range(n)]


def area(points):
    """Area of a planar polygon given by its vertices (half the norm of the vector area)."""
    sx = sy = sz = 0.0
    for i, (x1, y1, z1) in enumerate(points):
        x2, y2, z2 = points[(i + 1) % len(points)]
        sx += y1 * z2 - z1 * y2
        sy += z1 * x2 - x1 * z2
        sz += x1 * y2 - y1 * x2
    return 0.5 * math.sqrt(sx * sx + sy * sy + sz * sz)


# -- do the scaled windows still fit in their wall? (checks in the plane of the wall) ---------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _flatten(wall):
    """A function that gives 2-D coordinates, in the plane of ``wall``, to 3-D points of that plane."""
    o = wall[0]
    u = _unit(_sub(wall[1], o))
    normal = (0.0, 0.0, 0.0)
    for i in range(1, len(wall) - 1):
        normal = _cross(_sub(wall[i], o), _sub(wall[i + 1], o))
        if _dot(normal, normal) > 1e-12:
            break
    v = _cross(_unit(normal), u)
    return lambda points: [(_dot(_sub(p, o), u), _dot(_sub(p, o), v)) for p in points]


def _inside(polygon, p):
    """True if the 2-D point ``p`` is in the polygon or on its edge (to ``TOLERANCE``)."""
    inside = False
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        ex, ey = b[0] - a[0], b[1] - a[1]
        if ex == 0 and ey == 0:
            continue
        t = max(0.0, min(1.0, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / (ex * ex + ey * ey)))
        if math.hypot(p[0] - a[0] - t * ex, p[1] - a[1] - t * ey) <= TOLERANCE:
            return True
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < a[0] + (p[1] - a[1]) * ex / ey:
            inside = not inside
    return inside


def _overlap(p, q):
    """True if two convex 2-D polygons share area (separating-axis test; touching is not overlapping)."""
    for poly in (p, q):
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            n = math.hypot(b[0] - a[0], b[1] - a[1])
            if n == 0:
                continue
            axis = (-(b[1] - a[1]) / n, (b[0] - a[0]) / n)
            sp = [x * axis[0] + y * axis[1] for x, y in p]
            sq = [x * axis[0] + y * axis[1] for x, y in q]
            if max(sp) <= min(sq) + TOLERANCE or max(sq) <= min(sp) + TOLERANCE:
                return False
    return True


def set_window_to_wall(idf, ratio):
    """Scale the windows of every outdoor wall so that, wall by wall, window area / wall area = ``ratio``.

    Raises ``ValueError``, and changes nothing, if the windows cannot grow that much without leaving their wall or
    overlapping each other, a door or a glass door.
    """
    if not 0 < ratio < 1:
        raise ValueError(f"the window-to-wall ratio must be between 0 and 1, not {ratio}")
    version = idf.version
    if version is not None and (version.major, version.minor) != (9, 6):
        raise ValueError(f"this setter uses the field positions of EnergyPlus 9.6, the model is {version}")
    walls = {o.name.strip().lower(): o for o in idf.by_class("BuildingSurface:Detailed")
             if o.get(WALL_TYPE).strip().lower() == "wall" and o.get(WALL_BOUNDARY).strip().lower() == "outdoors"}
    on_wall = {}
    for s in idf.by_class("FenestrationSurface:Detailed"):
        wall = s.get(WINDOW_WALL).strip().lower()
        if wall in walls:
            on_wall.setdefault(wall, []).append(s)

    edits = []                                      # (window, first field, new coordinates): written after all checks
    for wall, subsurfaces in on_wall.items():
        group = [s for s in subsurfaces if s.get(WINDOW_TYPE).strip().lower() == "window"]
        if not group:
            continue
        wall_points = vertices(walls[wall], WALL_VERTICES)
        geometry = [vertices(w, WINDOW_VERTICES) for w in group]
        now = sum(area(points) * float(w.get(WINDOW_MULTIPLIER) or 1) for w, points in zip(group, geometry))
        k = math.sqrt(ratio * area(wall_points) / now)  # linear scale factor: areas scale with k squared
        scaled = []
        for points in geometry:
            centre = [sum(p[i] for p in points) / len(points) for i in range(3)]
            scaled.append([tuple(centre[j] + k * (p[j] - centre[j]) for j in range(3)) for p in points])

        flat = _flatten(wall_points)
        wall_2d = flat(wall_points)
        fixed = [(s, flat(vertices(s, WINDOW_VERTICES))) for s in subsurfaces if all(s is not w for w in group)]  # doors, glass doors
        grown = [(w, flat(points)) for w, points in zip(group, scaled)]
        for w, shape in grown:
            if not all(_inside(wall_2d, p) for p in shape):
                raise ValueError(f"window-to-wall ratio {ratio} cannot be reached: window {w.name!r} would leave its wall "
                                 f"{walls[wall].name!r}. The windows only grow in place; choose a smaller ratio.")
        for i, (w, shape) in enumerate(grown):
            for other, other_shape in grown[i + 1:] + fixed:
                if _overlap(shape, other_shape):
                    raise ValueError(f"window-to-wall ratio {ratio} cannot be reached: window {w.name!r} would overlap "
                                     f"{other.name!r} on wall {walls[wall].name!r}. The windows only grow in place; "
                                     "choose a smaller ratio.")
        edits += [(w, points) for w, points in zip(group, scaled)]

    for w, points in edits:
        for i, p in enumerate(points):
            for j in range(3):
                w.set(WINDOW_VERTICES + 3 * i + j, p[j])


def wwr(min_val=0.1, max_val=0.8, name="Window-to-wall ratio"):
    """A bdopt ``Parameter`` that varies the window-to-wall ratio between ``min_val`` and ``max_val``."""
    return Parameter(GenericSelector(set_window_to_wall, name=name), RangeParameter(min_val, max_val), name=name)
