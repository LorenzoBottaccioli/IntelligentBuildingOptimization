"""Geometry check of ``window_to_wall.set_window_to_wall`` (not for students; no EnergyPlus run).

Usage, from the folder that holds ``window_to_wall.py`` and the course models (``test.idf``, ``example_idf.idf``,
``lab_building.idf``)::

    python check_window_to_wall.py [model.idf ...]

For every model and every ratio 0.01, 0.02, ... 0.99 the script edits a copy of the model twice:

* with the setter as it is (it refuses a ratio that does not fit and raises ``ValueError``), and
* with the setter's own check switched off, and then checks the edited model with code of its own:
  wall by wall, the windows add up to the requested fraction of the gross area of the wall (multiplier included),
  every window is still in the plane of its wall and inside the wall polygon, and no window overlaps another
  window or a door of the same wall.

The two must agree: the setter refuses a ratio exactly when the independent check finds a problem. The script prints,
per model, the largest ratio that is accepted, and ends with a synthetic wall 3 m high (vertex 1 at ``z = 3.0``), which
an earlier version of ``vertices()`` read as a triangle. The exit code is 1 if anything disagrees.
"""

import math
import sys

sys.path.insert(0, ".")

from bdopt import IDF, load_idf
from bdopt.idf import IDFObject

import window_to_wall as w2w

EPS = 1e-6


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def plane_of(points):
    """Origin and an orthonormal basis (u, v, normal) of the plane of a polygon."""
    o = points[0]
    u = unit(sub(points[1], o))
    normal = (0.0, 0.0, 0.0)
    for i in range(1, len(points) - 1):
        normal = cross(sub(points[i], o), sub(points[i + 1], o))
        if dot(normal, normal) > 1e-12:
            break
    normal = unit(normal)
    return o, u, unit(cross(normal, u)), normal


def to_2d(points, plane):
    o, u, v, _ = plane
    return [(dot(sub(p, o), u), dot(sub(p, o), v)) for p in points]


def convex_ccw(poly):
    area2 = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return poly if area2 > 0 else poly[::-1]


def inside(poly, p):
    """Point in a convex polygon (the walls of the course models are rectangles)."""
    poly = convex_ccw(poly)
    return all((poly[(i + 1) % len(poly)][0] - poly[i][0]) * (p[1] - poly[i][1])
               - (poly[(i + 1) % len(poly)][1] - poly[i][1]) * (p[0] - poly[i][0]) >= -EPS for i in range(len(poly)))


def overlap(p, q):
    """True if two convex polygons share area (separating-axis test; touching is not overlapping)."""
    for poly in (p, q):
        for i in range(len(poly)):
            ex, ey = poly[(i + 1) % len(poly)][0] - poly[i][0], poly[(i + 1) % len(poly)][1] - poly[i][1]
            axis = (-ey, ex)
            n = math.hypot(*axis)
            if n == 0:
                continue
            a = [(x * axis[0] + y * axis[1]) / n for x, y in p]
            b = [(x * axis[0] + y * axis[1]) / n for x, y in q]
            if max(a) <= min(b) + EPS or max(b) <= min(a) + EPS:
                return False
    return True


def problems_of(m, ratio):
    """List of problems found in the edited model ``m``; also the number of walls with windows."""
    problems, n_walls = [], 0
    walls = {o.name.strip().lower(): o for o in m.by_class("BuildingSurface:Detailed")
             if o.get(w2w.WALL_TYPE).strip().lower() == "wall" and o.get(w2w.WALL_BOUNDARY).strip().lower() == "outdoors"}
    subs = {}
    for s in m.by_class("FenestrationSurface:Detailed"):
        parent = s.get(w2w.WINDOW_WALL).strip().lower()
        if parent in walls:
            subs.setdefault(parent, []).append(s)
    for name, group in subs.items():
        windows = [s for s in group if s.get(w2w.WINDOW_TYPE).strip().lower() == "window"]
        if not windows:
            continue
        n_walls += 1
        wall_pts = w2w.vertices(walls[name], w2w.WALL_VERTICES)
        plane = plane_of(wall_pts)
        wall2d = to_2d(wall_pts, plane)
        total = sum(w2w.area(w2w.vertices(s, w2w.WINDOW_VERTICES)) * float(s.get(w2w.WINDOW_MULTIPLIER) or 1) for s in windows)
        got = total / w2w.area(wall_pts)
        if abs(got - ratio) > 1e-9:
            problems.append(f"{name}: ratio {got:.6f} instead of {ratio}")
        polys = []
        for s in group:
            pts = w2w.vertices(s, w2w.WINDOW_VERTICES)
            if any(abs(dot(sub(p, plane[0]), plane[3])) > 1e-6 for p in pts):
                problems.append(f"{s.name}: not in the plane of {name}")
            p2 = to_2d(pts, plane)
            if not all(inside(wall2d, p) for p in p2):
                problems.append(f"{s.name}: outside {name}")
            polys.append((s, p2))
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                if overlap(polys[i][1], polys[j][1]):
                    problems.append(f"{polys[i][0].name} overlaps {polys[j][0].name}")
    return problems, n_walls


def edit(idf, ratio, guard):
    """A copy of ``idf`` edited by the setter; with ``guard=False`` the setter's own fit check is switched off."""
    m = idf.copy()
    if guard:
        w2w.set_window_to_wall(m, ratio)
        return m
    keep = w2w._inside, w2w._overlap
    w2w._inside, w2w._overlap = (lambda polygon, p: True), (lambda p, q: False)
    try:
        w2w.set_window_to_wall(m, ratio)
    finally:
        w2w._inside, w2w._overlap = keep
    return m


def synthetic_3m_wall():
    """A 6 m x 3 m wall whose first vertex is the upper left corner (z = 3.0) with one window."""
    head = ["W1", "Wall", "C", "Z", "", "Outdoors", "", "SunExposed", "WindExposed", "0.5", "4"]
    wall = IDFObject("BuildingSurface:Detailed", head + ["0", "0", "3", "0", "0", "0", "6", "0", "0", "6", "0", "3"])
    # a window 3 m wide, 1 m high in the middle of the wall, first vertex at z = 2.0
    win = IDFObject("FenestrationSurface:Detailed", ["Win1", "Window", "G", "W1", "", "", "", "1", "4",
                                                    "1.5", "0", "2", "1.5", "0", "1", "4.5", "0", "1", "4.5", "0", "2"])
    idf = IDF([IDFObject("Version", ["9.6"]), wall, win])
    ok = True
    for ratio in (0.2, 0.5):
        m = idf.copy()
        w2w.set_window_to_wall(m, ratio)
        got = w2w.area(w2w.vertices(m.by_class("FenestrationSurface:Detailed")[0], w2w.WINDOW_VERTICES)) / 18.0
        print(f"synthetic 3 m wall, ratio {ratio}: achieved {got:.6f}")
        ok &= abs(got - ratio) < 1e-9
    try:                                    # above 2/3 the 3 m wide window, scaled about (3, 1.5), is wider than the wall
        w2w.set_window_to_wall(idf.copy(), 0.7)
        print("synthetic 3 m wall, ratio 0.7: NOT refused")
        ok = False
    except ValueError as e:
        print("synthetic 3 m wall, ratio 0.7: refused,", str(e)[:100])
    return ok


def main(models):
    bad = 0
    for path in models:
        idf = load_idf(path)
        accepted, refused_without_problem, silent_problem, walls = [], [], [], 0
        for k in range(1, 100):
            ratio = k / 100
            try:
                good = edit(idf, ratio, guard=True)
                refused = False
            except ValueError:
                refused = True
            problems, walls = problems_of(edit(idf, ratio, guard=False), ratio)
            if refused and not problems:
                refused_without_problem.append(ratio)
            if not refused:
                silent_problem += [ratio] if problems_of(good, ratio)[0] else []
                accepted.append(ratio)
        largest = accepted[-1] if accepted else None
        contiguous = accepted == [k / 100 for k in range(1, len(accepted) + 1)]
        print(f"{path}: {walls} walls with windows; setter accepts {len(accepted)} of 99 ratios, largest {largest}"
              f"{'' if contiguous else ' (NOT contiguous from 0.01)'}; refused although the independent check found nothing: "
              f"{refused_without_problem or 'none'}; accepted with a problem: {silent_problem or 'none'}")
        if refused_without_problem or silent_problem or not accepted:
            bad += 1
    if not synthetic_3m_wall():
        print("SYNTHETIC 3 m WALL FAILED")
        bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or ["test.idf", "example_idf.idf", "lab_building.idf"])
