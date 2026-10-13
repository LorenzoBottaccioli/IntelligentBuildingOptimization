"""Floor plan of any model, from what EnergyPlus itself resolved.

The vertices in an IDF are not world coordinates: they depend on the coordinate system
(relative or world), the zone origin, the zone and building north axes, and on whether
the surface is a detailed one or a rectangular (origin, length, width) one. EnergyPlus
resolves all of that when it reads the model, and writes the result in two files:

* `eplusout.dxf` (from `Output:Surfaces:Drawing, DXF, Triangulate3DFace`): every surface
  as 3D faces in world coordinates. The layer of a face is its zone (name with ':' and
  spaces replaced by '_'), and a comment before the faces of each surface gives
  `<zone name>:<surface name>`;
* `eplusout.eio`: the table `HeatTransfer Surface` gives the class of every surface (Wall,
  Floor, Roof, Window...) and its area; `Zone Information` gives per zone the bounding box,
  centroid, multiplier and floor area.

The footprint of a zone is its floor: the faces of its surfaces of class Floor, seen from
above. The area of those faces is compared with the area EnergyPlus gives for the same
surfaces, which says whether the file was read completely. Nothing here depends on the
building.

    plan = build_plan(read_dxf('eplusout.dxf'), eio_tables('eplusout.eio'))
    svg = plan_svg(plan, level=0)
"""

import re
from xml.sax.saxutils import escape

HORIZONTAL_TOL = 1e-3          # m: a face is horizontal when its vertices differ less than this in z
AREA_TOL = 0.02                # the faces must add up to the area of the .eio within 2 %
MIN_AREA = 1e-6                # m2: degenerate faces are dropped


def layer_key(name):
    """The form in which a zone name is found in the DXF comments: ':' and spaces become '_'."""
    return re.sub(r'[^A-Z0-9]', '_', str(name).upper())


# ---- the two files -----------------------------------------------------------------

def read_dxf(path):
    """{'layers': [zone keys listed in the header], 'faces': [{'layer', 'surface', 'points'}]}; only 3DFACE entities.

    `surface` is the last comment before the face: '<zone>:<surface>' for the faces of a surface.
    """
    layers, faces = [], []
    with open(path, encoding='latin-1') as handle:
        lines = handle.read().splitlines()
    entity, layer, coords, comment, own = None, '', {}, '', ''

    def flush():
        if entity != '3DFACE' or not coords:
            return
        pts = []
        for i in range(4):
            if 10 + i in coords and 20 + i in coords and 30 + i in coords:
                pts.append((coords[10 + i], coords[20 + i], coords[30 + i]))
        if len(pts) == 4 and pts[3] == pts[2]:
            pts = pts[:3]
        if len(pts) >= 3:
            faces.append({'layer': layer, 'surface': own, 'points': pts})

    for i in range(0, len(lines) - 1, 2):
        code, value = lines[i].strip(), lines[i + 1].strip()
        if code == '999':
            comment = value
            m = re.match(r'Zone=\d+:(.*)$', value)
            if m:
                layers.append(m.group(1).upper())
        elif code == '0':
            flush()
            entity, layer, coords, own = value, '', {}, comment      # the comment written before the entity names it
        elif code == '8':
            layer = value
        elif entity == '3DFACE':
            try:
                number = int(code)
            except ValueError:
                continue
            if 10 <= number <= 33 and number % 10 <= 3 and number // 10 in (1, 2, 3):
                try:
                    coords[number] = float(value)
                except ValueError:
                    pass
    flush()
    return {'layers': layers, 'faces': faces}


def eio_tables(path):
    """{'zones': {UPPER name: row}, 'surfaces': {UPPER name: row}}, columns found by the file's own headers."""
    zones, surfaces, headers = {}, {}, {}
    try:
        handle = open(path, encoding='latin-1')
    except OSError:
        return {'zones': zones, 'surfaces': surfaces}
    with handle:
        for line in handle:
            cells = [c.strip() for c in line.rstrip('\r\n').split(',')]
            if not cells or not cells[0]:
                continue
            if cells[0] == '! <Zone Information>':
                headers['zone'] = cells
            elif cells[0] == '! <HeatTransfer Surface>':
                headers['surface'] = cells
            elif cells[0] == 'Zone Information' and 'zone' in headers:
                row = dict(zip(headers['zone'], cells))
                zones[row.get('Zone Name', '').upper()] = row
            elif cells[0] == 'HeatTransfer Surface' and 'surface' in headers:
                row = dict(zip(headers['surface'], cells))
                surfaces[row.get('Surface Name', '').upper()] = row
    return {'zones': zones, 'surfaces': surfaces}


def _num(raw):
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


# ---- geometry ----------------------------------------------------------------------

def _newell(points):
    """Area vector of a planar polygon (its length is the area, its direction the normal)."""
    nx = ny = nz = 0.0
    for (x1, y1, z1), (x2, y2, z2) in zip(points, points[1:] + points[:1]):
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return nx / 2, ny / 2, nz / 2


def _area3d(points):
    nx, ny, nz = _newell(points)
    return (nx * nx + ny * ny + nz * nz) ** 0.5


def _area_xy(points):
    return abs(_newell(points)[2])


def _inside(point, polygon):
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _label_point(polygons, areas):
    """Area-weighted centre of the footprint; the centre of the largest face if that falls outside."""
    total = sum(areas)
    cx = sum(sum(p[0] for p in poly) / len(poly) * a for poly, a in zip(polygons, areas)) / total
    cy = sum(sum(p[1] for p in poly) / len(poly) * a for poly, a in zip(polygons, areas)) / total
    if any(_inside((cx, cy), poly) for poly in polygons):
        return [cx, cy]
    big = polygons[max(range(len(areas)), key=areas.__getitem__)]
    return [sum(p[0] for p in big) / len(big), sum(p[1] for p in big) / len(big)]


def _bbox_of(info):
    box = [_num(info.get(k)) for k in ('Minimum X {m}', 'Minimum Y {m}', 'Maximum X {m}', 'Maximum Y {m}')]
    return box if None not in box and box[2] > box[0] and box[3] > box[1] else None


def outline(polygons, quantum=1e-3):
    """The boundary of the union of the polygons (the triangles of a floor) as a list of segments ((x, y), (x, y)).

    An edge shared by two triangles is walked in opposite directions and cancels. A vertex that lies on
    the edge of a neighbour (a T junction) first splits that edge, so the two halves cancel as well.
    """
    def key(p):
        return (round(p[0] / quantum), round(p[1] / quantum))

    where = {}
    for poly in polygons:
        for p in poly:
            where[key(p)] = p
    cell = max(max(k[0] for k in where) - min(k[0] for k in where),
               max(k[1] for k in where) - min(k[1] for k in where), 1) / 64.0
    grid = {}
    for k in where:
        grid.setdefault((int(k[0] // cell), int(k[1] // cell)), []).append(k)

    edges = set()
    for poly in polygons:
        ring = poly if _area_signed(poly) > 0 else poly[::-1]
        for a, b in zip(ring, ring[1:] + ring[:1]):
            ka, kb = key(a), key(b)
            if ka == kb:
                continue
            on = []
            for i in range(int(min(ka[0], kb[0]) // cell), int(max(ka[0], kb[0]) // cell) + 1):
                for j in range(int(min(ka[1], kb[1]) // cell), int(max(ka[1], kb[1]) // cell) + 1):
                    for kc in grid.get((i, j), ()):
                        if kc in (ka, kb):
                            continue
                        cross = (kb[0] - ka[0]) * (kc[1] - ka[1]) - (kb[1] - ka[1]) * (kc[0] - ka[0])
                        dot = (kc[0] - ka[0]) * (kb[0] - ka[0]) + (kc[1] - ka[1]) * (kb[1] - ka[1])
                        length = (kb[0] - ka[0]) ** 2 + (kb[1] - ka[1]) ** 2
                        if abs(cross) <= 2 * length ** 0.5 and 0 < dot < length:
                            on.append((dot, kc))
            chain = [ka] + [kc for _, kc in sorted(on)] + [kb]
            edges.update(zip(chain, chain[1:]))
    return [(where[a], where[b]) for a, b in edges if (b, a) not in edges]


def _area_signed(poly):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) / 2


# ---- the plan ----------------------------------------------------------------------

def build_plan(dxf, tables):
    """The plan of a model: {'zones': [...], 'levels': [...], 'unmatchedLayers': [...]}.

    dxf: read_dxf(); tables: eio_tables(). Each zone has one `kind`:
      floor    the faces of its surfaces of class Floor, whose area adds up (AREA_TOL) to the area
               EnergyPlus gives for those surfaces: `checked` says whether that comparison held;
      derived  the zone has no surface of class Floor: the horizontal faces that look down stand in;
      bbox     no floor face at all: the bounding box of the .eio;
      none     neither: the zone has no place on the plan.
    """
    zone_rows = tables['zones']
    by_key = {layer_key(n): n for n in zone_rows}
    owner = {layer_key(l): by_key.get(layer_key(l)) for l in {f['layer'] for f in dxf['faces']} | set(dxf['layers'])}
    per_zone = {n: {'floor': [], 'down': []} for n in zone_rows}
    floor_area_eio = {n: 0.0 for n in zone_rows}
    seen_surfaces = set()

    for face in dxf['faces']:
        zone = owner.get(layer_key(face['layer']))
        if zone is None:
            continue
        text = face['surface'].upper()
        prefix = zone + ':'
        name = text[len(prefix):] if text.startswith(prefix) else text
        row = tables['surfaces'].get(name)
        pts = face['points']
        if row and row.get('Surface Class', '').lower() == 'floor':
            per_zone[zone]['floor'].append(pts)
            if name not in seen_surfaces:
                seen_surfaces.add(name)
                floor_area_eio[zone] += _num(row.get('Area (Gross) {m2}')) or 0.0
        zs = [p[2] for p in pts]
        if max(zs) - min(zs) <= HORIZONTAL_TOL and _newell(pts)[2] < -MIN_AREA:
            per_zone[zone]['down'].append(pts)

    rows = []
    for name, info in zone_rows.items():
        mine = per_zone[name]
        faces = mine['floor'] or mine['down']
        faces = [f for f in faces if _area_xy(f) > MIN_AREA]
        row = {'name': info.get('Zone Name', name), 'key': layer_key(name), 'kind': 'none', 'checked': False,
               'areaFaces': 0.0, 'areaSurfaces': floor_area_eio[name], 'areaZone': _num(info.get('Floor Area {m2}')),
               'polygons': [], 'bbox': None, 'label': None, 'z': _num(info.get('Minimum Z {m}')),
               'multiplier': _num(info.get('Zone Multiplier')) or 1.0}
        if faces:
            polys = [[(p[0], p[1]) for p in f] for f in faces]
            areas = [_area_xy(f) for f in faces]
            xs = [p[0] for poly in polys for p in poly]
            ys = [p[1] for poly in polys for p in poly]
            row.update({'kind': 'floor' if mine['floor'] else 'derived', 'polygons': polys,
                        'areaFaces': sum(_area3d(f) for f in faces), 'bbox': [min(xs), min(ys), max(xs), max(ys)],
                        'label': _label_point(polys, areas), 'z': min(p[2] for f in faces for p in f)})
            ref = row['areaSurfaces']
            row['checked'] = bool(mine['floor']) and ref > 0 and abs(row['areaFaces'] - ref) <= AREA_TOL * ref
        else:
            box = _bbox_of(info)
            if box:
                row.update({'kind': 'bbox', 'bbox': box, 'label': [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
                            'polygons': [[(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]]})
        rows.append(row)

    # A level is a distinct height of the zone floor, counted from the lowest one (as in instrument.py).
    heights = sorted({round(r['z'], 1) for r in rows if r['z'] is not None and r['kind'] != 'none'})
    for r in rows:
        r['level'] = heights.index(round(r['z'], 1)) if r['z'] is not None and r['kind'] != 'none' else None
    levels = []
    for i, z in enumerate(heights):
        members = [r for r in rows if r['level'] == i]
        levels.append({'index': i, 'z': z, 'zones': [r['name'] for r in members],
                       'bbox': [min(r['bbox'][0] for r in members), min(r['bbox'][1] for r in members),
                                max(r['bbox'][2] for r in members), max(r['bbox'][3] for r in members)]})
    return {'zones': rows, 'levels': levels,
            'unmatchedLayers': sorted(l for l, n in owner.items() if n is None and not l.isdigit())}


def overlap_ratio(plan, level):
    """Largest share of the smaller bounding box covered by another zone of the same level (0..1).

    Zones of one level that sit on top of each other mean the model is not laid out in plan
    (several buildings at the origin, zones drawn as a stack): the plan should not be shown as a map.
    Two neighbours that share a wall do not overlap; the triangles of the demo (bounding boxes that cross) do.
    """
    boxes = [r['bbox'] for r in plan['zones'] if r['level'] == level and r['bbox']]
    worst = 0.0
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            if w > 0 and h > 0:
                small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                worst = max(worst, w * h / small if small > 0 else 0.0)
    return worst


# ---- drawing -----------------------------------------------------------------------

def plan_svg(plan, level=0, width=800, margin=0.06, labels=True):
    """SVG of one level, north up. Each zone is a <g id="zone-KEY"> with a filled path (class fill) and its outline (class edge)."""
    lv = next((l for l in plan['levels'] if l['index'] == level), None)
    if lv is None:
        return ''
    x0, y0, x1, y1 = lv['bbox']
    w, h = (x1 - x0) or 1.0, (y1 - y0) or 1.0
    pad = max(w, h) * margin
    vb = (x0 - pad, -(y1 + pad), w + 2 * pad, h + 2 * pad)
    font = max(w, h) * 0.03
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="{:.3f} {:.3f} {:.3f} {:.3f}" width="{}" '
             'height="{:.0f}">'.format(*vb, width, width * vb[3] / vb[2])]
    for r in plan['zones']:
        if r['level'] != level:
            continue
        d = ' '.join('M' + ' L'.join('{:.3f},{:.3f}'.format(x, -y) for x, y in poly) + 'Z' for poly in r['polygons'])
        edge = ' '.join('M{:.3f},{:.3f} L{:.3f},{:.3f}'.format(a[0], -a[1], b[0], -b[1]) for a, b in outline(r['polygons']))
        parts.append('<g id="zone-{}" data-zone="{}" data-kind="{}"><title>{}</title>'
                     '<path class="fill" d="{}" fill="#dfe7ef" stroke="#dfe7ef" stroke-width="{:.3f}" stroke-linejoin="round"/>'
                     '<path class="edge" d="{}" fill="none" stroke="#5b6b7b" stroke-width="{:.3f}" '
                     'stroke-linecap="round"/></g>'.format(r['key'], escape(r['name']), r['kind'], escape(r['name']), d,
                                                           max(w, h) * 0.0015, edge, max(w, h) * 0.004))
    if labels:
        for r in plan['zones']:
            if r['level'] == level and r['label']:
                parts.append('<text x="{:.3f}" y="{:.3f}" font-size="{:.3f}" text-anchor="middle" '
                             'fill="#33414f">{}</text>'.format(r['label'][0], -r['label'][1], font, escape(r['name'])))
    parts.append('</svg>')
    return '\n'.join(parts)


def markers(plan, level=0, margin=0.06):
    """{zone name: (x %, y %)} of the label point inside the SVG image, from the top left corner."""
    lv = next((l for l in plan['levels'] if l['index'] == level), None)
    if lv is None:
        return {}
    x0, y0, x1, y1 = lv['bbox']
    w, h = (x1 - x0) or 1.0, (y1 - y0) or 1.0
    pad = max(w, h) * margin
    return {r['name']: (round(100 * (r['label'][0] - (x0 - pad)) / (w + 2 * pad), 2),
                        round(100 * ((y1 + pad) - r['label'][1]) / (h + 2 * pad), 2))
            for r in plan['zones'] if r['level'] == level and r['label']}
