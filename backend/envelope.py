"""The envelope as a builder sees it: elements, their build-ups, their layers.

A bare class list is the wrong handle for envelope design, and it is wrong in a
way that quietly produces nonsense. "Material" does not say what the material is
part of -- the same insulant sits in an external wall and in a partition, so
varying its thickness thickens both. And the right handle is not the same for
every element:

    a window   is changed by swapping its Construction -- the whole glazed
               build-up, chosen among the ones the model defines;
    a wall     is usually not swapped whole. You keep the build-up and change
               the insulating layer inside it, most often its thickness.

So this module reconstructs what the surfaces say: which elements exist, which
constructions each element uses, which layers those constructions are made of,
and -- for every layer -- where else in the building it turns up. That last
point is what makes the difference between a design decision and an accident.

Nothing here is specific to a building. An element is a surface type crossed
with its boundary condition, which is how EnergyPlus already describes every
surface, so the same code names external walls in a house and in a hospital.
"""

import os
import re

import design_space
import idf_session

# DesignBuilder writes, for every construction on an interzone surface, its
# mirror image for the surface on the other side: "partition", "partition_Rev",
# "internal floor 35cm_Reversed_Rev". They are the same build-up seen from the
# other zone, never a design alternative, so they are never offered.
_MIRROR = re.compile(r'(_rev|_reversed)+$', re.IGNORECASE)


# A pane is called low-emissivity when a face emits less than this. Clear glass
# is about 0.84; coated faces sit near 0.04-0.2. A judgement, declared here.
LOW_E_EMISSIVITY = 0.2
_GASES = {'air': 'air', 'argon': 'argon', 'krypton': 'krypton', 'xenon': 'xenon'}


def glazing_layer(idf, name):
    """A window layer in words, from its own fields: what a name like "1004" is.

    Field names read from Energy+.idd 9.6: WindowMaterial:Glazing Thickness and
    Front/Back Side Infrared Hemispherical Emissivity; WindowMaterial:Gas Gas
    Type and Thickness; WindowMaterial:GasMixture Thickness and Gas 1 Type;
    WindowMaterial:SimpleGlazingSystem U-Factor and Solar Heat Gain Coefficient.
    """
    glass = idf.getobject('WINDOWMATERIAL:GLAZING', name)
    if glass is not None:
        mm = _num(getattr(glass, 'Thickness', None))
        eps = [e for e in (_num(getattr(glass, 'Front_Side_Infrared_Hemispherical_Emissivity', None)),
                           _num(getattr(glass, 'Back_Side_Infrared_Hemispherical_Emissivity', None)))
               if e is not None]
        low = ' low-e' if eps and min(eps) < LOW_E_EMISSIVITY else ''
        return f'glass {mm * 1000:g} mm{low}' if mm else f'glass{low}'
    gas = idf.getobject('WINDOWMATERIAL:GAS', name)
    if gas is not None:
        mm = _num(getattr(gas, 'Thickness', None))
        kind = _GASES.get(str(getattr(gas, 'Gas_Type', '')).lower(), str(getattr(gas, 'Gas_Type', '')))
        return f'{kind} {mm * 1000:g} mm' if mm else kind
    mix = idf.getobject('WINDOWMATERIAL:GASMIXTURE', name)
    if mix is not None:
        mm = _num(getattr(mix, 'Thickness', None))
        first = _GASES.get(str(getattr(mix, 'Gas_1_Type', '')).lower(), '')
        return f'{first} mixture {mm * 1000:g} mm' if mm else 'gas mixture'
    simple = idf.getobject('WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM', name)
    if simple is not None:
        return (f'simple glazing system U {getattr(simple, "U_Factor", "?")} W/m2K, '
                f'g {getattr(simple, "Solar_Heat_Gain_Coefficient", "?")}')
    return name


_SHADING_LAYERS = ('WINDOWMATERIAL:BLIND', 'WINDOWMATERIAL:SHADE', 'WINDOWMATERIAL:SCREEN',
                   'WINDOWMATERIAL:BLIND:EQUIVALENTLAYER', 'WINDOWMATERIAL:SHADE:EQUIVALENTLAYER',
                   'WINDOWMATERIAL:SCREEN:EQUIVALENTLAYER', 'WINDOWMATERIAL:DRAPE:EQUIVALENTLAYER')


def _is_shading_layer(idf, name):
    return any(idf.getobject(c, name) is not None for c in _SHADING_LAYERS)


def is_mirror(name):
    return bool(_MIRROR.search(name or ''))

# What makes an element: what kind of surface it is, and what it faces. Both come
# straight off the surface object, so no model needs to be recognised.
_ELEMENTS = [
    ('external_wall', 'External walls', 'wall', 'outdoors'),
    ('partition', 'Partitions', 'wall', 'surface'),
    ('basement_wall', 'Basement walls', 'wall', 'ground'),
    ('roof', 'Roof', 'roof', 'outdoors'),
    ('ceiling', 'Ceilings', 'ceiling', 'surface'),
    ('exposed_floor', 'Exposed floors', 'floor', 'outdoors'),
    ('ground_floor', 'Ground floors', 'floor', 'ground'),
    ('internal_floor', 'Internal floors', 'floor', 'surface'),
]

# A layer that conducts this poorly is doing the insulating. Stated here so it can
# be argued with: EnergyPlus classifies materials by physics, never by function.
INSULATION_CONDUCTIVITY = 0.1

# A layer given only a thermal resistance is not insulation by that fact alone:
# DesignBuilder exports every air cavity as a Material:NoMass, and the course
# models carry them at 0.15-0.18 m2K/W (E1_RES1's roof, the Office partitions).
# Below this resistance a massless layer is read as a cavity, not an insulant.
# A judgement, declared to be argued with; Material:AirGap is a cavity by class.
NOMASS_INSULATION_RESISTANCE = 0.25


def _num(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _layer_names(construction):
    fields = [f for f in construction.fieldnames
              if f == 'Outside_Layer' or f.startswith('Layer')]
    return [getattr(construction, f, '') for f in fields
            if getattr(construction, f, '')]


def _materials(idf):
    """Every layer the model defines, whatever class describes it.

    Each carries its own variable fields, taken from that very object, so the
    interval offered for an insulant brackets its actual thickness rather than
    the average of every material in the file.
    """
    found = {}
    for group in ('Material', 'Material:NoMass', 'Material:AirGap',
                  'Material:InfraredTransparent', 'WindowMaterial:Glazing',
                  'WindowMaterial:Gas', 'WindowMaterial:GasMixture',
                  'WindowMaterial:SimpleGlazingSystem', 'WindowMaterial:Blind',
                  'WindowMaterial:Shade', 'WindowMaterial:Screen'):
        for m in idf.idfobjects[group.upper()]:
            k = _num(getattr(m, 'Conductivity', None))
            thickness = _num(getattr(m, 'Thickness', None))
            resistance = _num(getattr(m, 'Thermal_Resistance', None))
            found[m.Name] = {
                'name': m.Name,
                'className': group,
                'fields': design_space.object_fields(m, group),
                'conductivity': k,
                'thickness': thickness,
                'resistance': resistance,
                'glazing': group.startswith('WindowMaterial'),
                # Two ways of being the insulating layer: conducting poorly, or
                # being described by a resistance too high for a cavity.
                'insulating': (k is not None and k < INSULATION_CONDUCTIVITY)
                              or (k is None and resistance is not None
                                  and group != 'Material:AirGap'
                                  and resistance >= NOMASS_INSULATION_RESISTANCE),
            }
    return found


# Glazed openings, split by what they sit in. A skylight and a facade window
# are different decisions -- different sun, different build-up -- and a model
# often glazes them differently (E1_RES1: double on the walls, triple on the
# roof), so one swap for both would put facade glass on the roof.
_GLAZED = ('window', 'glassdoor', 'tubulardaylightdome', 'tubulardaylightdiffuser')
FENESTRATION_ELEMENTS = ('window', 'skylight', 'door')


# Every surface class of the IDD's "Thermal Zones and Surfaces" group, with
# what its class alone says. The detailed classes carry a Surface Type and an
# Outside Boundary Condition field; the simplified ones are named for both
# (Wall:Exterior is a wall facing outdoors), and RoofCeiling/Wall/Floor:Detailed
# name the kind but keep the boundary field. None = read it from the object.
#               class                    kind       boundary
_OPAQUE_CLASSES = {
    'BUILDINGSURFACE:DETAILED':  (None,      None),
    'WALL:DETAILED':             ('wall',    None),
    'ROOFCEILING:DETAILED':      ('roof',    None),   # a ceiling unless it faces outdoors
    'FLOOR:DETAILED':            ('floor',   None),
    'WALL:EXTERIOR':             ('wall',    'outdoors'),
    'WALL:ADIABATIC':            ('wall',    'adiabatic'),
    'WALL:UNDERGROUND':          ('wall',    'ground'),
    'WALL:INTERZONE':            ('wall',    'surface'),
    'ROOF':                      ('roof',    'outdoors'),
    'CEILING:ADIABATIC':         ('ceiling', 'adiabatic'),
    'CEILING:INTERZONE':         ('ceiling', 'surface'),
    'FLOOR:GROUNDCONTACT':       ('floor',   'ground'),
    'FLOOR:ADIABATIC':           ('floor',   'adiabatic'),
    'FLOOR:INTERZONE':           ('floor',   'surface'),
}
#               class                    surface type
_FENESTRATION_CLASSES = {
    'FENESTRATIONSURFACE:DETAILED': None,
    'WINDOW':                       'window',
    'DOOR':                         'door',
    'GLAZEDDOOR':                   'glassdoor',
    'WINDOW:INTERZONE':             'window',
    'DOOR:INTERZONE':               'door',
    'GLAZEDDOOR:INTERZONE':         'glassdoor',
}
GLAZED_KINDS = _GLAZED


def _boundary(raw):
    """The Outside Boundary Condition keys, folded into what an element needs.

    Every ground model (Ground, Foundation, GroundFCfactorMethod, the slab and
    basement preprocessors) is ground; Zone is an interzone surface like Surface.
    """
    b = (raw or '').strip().lower()
    if b.startswith('ground') or b == 'foundation':
        return 'ground'
    if b == 'zone':
        return 'surface'
    return b


def _opaque_kind(surface):
    """(surface kind, boundary) of an opaque surface of any class."""
    kind, boundary = _OPAQUE_CLASSES.get(surface.key.upper(), (None, None))
    if kind is None:
        kind = (getattr(surface, 'Surface_Type', '') or '').strip().lower()
    if boundary is None:
        boundary = _boundary(getattr(surface, 'Outside_Boundary_Condition', ''))
    if surface.key.upper() == 'ROOFCEILING:DETAILED' and boundary != 'outdoors':
        kind = 'ceiling'
    return kind, boundary


def fenestration_kind(surface):
    """Window, door, glassdoor... of a subsurface of any class."""
    kind = _FENESTRATION_CLASSES.get(surface.key.upper())
    return kind or (getattr(surface, 'Surface_Type', '') or '').strip().lower()


def opaque_surfaces(idf):
    return [s for cls in _OPAQUE_CLASSES for s in idf.idfobjects.get(cls, [])]


def fenestration_surfaces(idf):
    return [s for cls in _FENESTRATION_CLASSES for s in idf.idfobjects.get(cls, [])]


def _hosts(idf):
    """Element of every opaque surface, by name, to place its openings."""
    return {(s.Name or '').upper(): _element_of(s) for s in opaque_surfaces(idf)}


def _element_of(surface, fenestration=False, hosts=None):
    """Which element a surface belongs to, read off the surface and its class.

    An opening takes its element from its host: in an external wall it is a
    window, in a roof a skylight, in a partition or an adiabatic wall it is
    not part of the envelope at all.
    """
    if fenestration:
        host = (hosts or {}).get((getattr(surface, 'Building_Surface_Name', '') or '').upper())
        if fenestration_kind(surface) not in _GLAZED:
            return 'door'
        if host == 'roof':
            return 'skylight'
        if host in ('external_wall', 'exposed_floor'):
            return 'window'
        return 'interior_window'
    kind, boundary = _opaque_kind(surface)
    return next((e[0] for e in _ELEMENTS if e[2] == kind and e[3] == boundary),
                'other_opaque')


def surface_objects(idf, element_id):
    """The surface objects that make up an element, of whatever class."""
    fenestration = element_id in FENESTRATION_ELEMENTS + ('interior_window',)
    hosts = _hosts(idf) if fenestration else None
    pool = fenestration_surfaces(idf) if fenestration else opaque_surfaces(idf)
    return [s for s in pool if _element_of(s, fenestration, hosts) == element_id]


def surfaces_of(idf, element_id):
    """The surfaces that make up an element, by name.

    A construction swap has to be written to these and to nothing else. Left
    as class-wide, "change the windows" would also change the doors, and
    "change the external walls" every partition in the building.
    """
    return [s.Name for s in surface_objects(idf, element_id)]


# Shading types whose device can be given as a material instead of a shaded
# construction (IDD, WindowShadingControl "Construction with Shading Name").
# Between-glass devices and switchable glazing need the construction.
_MATERIAL_SHADING = ('interiorshade', 'exteriorshade', 'interiorblind', 'exteriorblind',
                     'exteriorscreen')

SURFACE_REPORT = os.path.join('simulation_outputs', 'eplusout.eio')
TABLE_REPORT = os.path.join('simulation_outputs', 'eplustbl.tab')


def cardinal(azimuth):
    """North, east, south or west, in 90-degree sectors centred on each."""
    if azimuth is None:
        return ''
    a = azimuth % 360
    return 'N' if a >= 315 or a < 45 else 'E' if a < 135 else 'S' if a < 225 else 'W'


def _facing(eio=SURFACE_REPORT, table=TABLE_REPORT):
    """Azimuth and facing of each window, as EnergyPlus resolved them.

    Read from the probe simulation rather than computed from the vertices: the
    orientation depends on the coordinate system, the building north axis and
    the zone north axis, and EnergyPlus already applied all three. The upload
    adds `Output:Surfaces:List, Details` to the probe copy, so the .eio lists
    every surface with its azimuth; a model uploaded before that falls back on
    the "Exterior Fenestration" table, when the model writes one as text.
    """
    out = {}
    try:
        with open(eio, encoding='latin-1') as handle:
            header = None
            for line in handle:
                cells = [c.strip() for c in line.split(',')]
                if cells[0] == '! <HeatTransfer Surface>':
                    header = cells
                elif header and cells[0] == 'HeatTransfer Surface' and len(cells) >= len(header) - 1:
                    values = dict(zip(header, cells))
                    azimuth = _num(values.get('Azimuth {deg}'))
                    out[values['Surface Name'].upper()] = {'azimuth': azimuth, 'facing': cardinal(azimuth)}
    except OSError:
        pass
    if out:
        return out
    try:
        with open(table, encoding='latin-1') as handle:
            lines = handle.read().splitlines()
    except OSError:
        return out
    for i, line in enumerate(lines):
        if line.strip() != 'Exterior Fenestration':
            continue
        header = None
        for row in lines[i + 1:]:
            cells = row.split('	')
            if header is None:
                if 'Cardinal Direction' in cells:
                    header = cells
                continue
            if len(cells) < len(header) or not cells[1].strip() or cells[1].strip().lower() == 'total or average':
                break
            values = dict(zip(header, cells))
            out[cells[1].strip().upper()] = {
                'azimuth': _num(values.get('Azimuth [deg]')),
                'facing': (values.get('Cardinal Direction') or '').strip(),
            }
        break
    return out


def _shading_device(idf, control):
    """How a WindowShadingControl draws its device over a window.

    Returns (material, reason). A material means the device can be given as
    "Shading Device Material Name", and then fits any glazing a sample puts on
    the window -- given as a shaded construction instead, EnergyPlus requires
    its glass and gas layers to match the window's, and stops when a sample
    swaps the glazing. A reason means it cannot.
    """
    material = (getattr(control, 'Shading_Device_Material_Name', '') or '').strip()
    shaded_name = (getattr(control, 'Construction_with_Shading_Name', '') or '').strip()
    if not shaded_name:
        return material or None, None if material else 'it names no shading device.'
    kind = (getattr(control, 'Shading_Type', '') or '').replace(' ', '').lower()
    if kind not in _MATERIAL_SHADING:
        return None, f'its {control.Shading_Type} is part of the glazed construction.'
    shaded = idf.getobject('CONSTRUCTION', shaded_name)
    layers = _layer_names(shaded) if shaded is not None else []
    devices = [l for l in layers if _is_shading_layer(idf, l)]
    if len(devices) != 1 or devices[0] not in (layers[0], layers[-1]):
        return None, f'the shading layer of {shaded_name} cannot be told apart from the glazing.'
    return devices[0], None


# What the two setpoints of a WindowShadingControl mean, from the IDD notes on
# the fields: Setpoint is W/m2 for solar-based controls, W for cooling- or
# heating-based ones, deg C for temperature-based ones, and unused for the
# types listed; Setpoint 2 is used only by the four two-setpoint types, where
# it is the solar threshold and Setpoint the temperature.
_SETPOINT_UNUSED = {'alwayson', 'alwaysoff', 'onifscheduleallows', 'onifhighglare',
                    'meetdaylightilluminancesetpoint'}
_TWO_SETPOINTS = {'onifhighoutdoorairtempandhighsolaronwindow',
                  'onifhighoutdoorairtempandhighhorizontalsolar',
                  'onifhighzoneairtempandhighsolaronwindow',
                  'onifhighzoneairtempandhighhorizontalsolar'}


def setpoint_meaning(control_type):
    """(unit of Setpoint or None if unused, unit of Setpoint 2 or None)."""
    t = (control_type or '').replace(' ', '').lower()
    if t in _SETPOINT_UNUSED or not t:
        return None, None
    if t in _TWO_SETPOINTS:
        return 'C', 'W/m2'
    if 'solar' in t:
        return 'W/m2', None
    if 'temp' in t:
        return 'C', None
    return 'W', None


def shading_controls(idf, window_names=None):
    """The WindowShadingControl objects over these windows, with their setpoints."""
    wanted = {n.upper() for n in window_names} if window_names is not None else None
    out = []
    for c in idf.idfobjects['WINDOWSHADINGCONTROL']:
        wins = [getattr(c, f) for f in c.fieldnames
                if f.startswith('Fenestration_Surface_') and getattr(c, f, '')]
        if wanted is not None and not any(w.upper() in wanted for w in wins):
            continue
        unit1, unit2 = setpoint_meaning(c.Shading_Control_Type)
        out.append({'name': c.Name, 'shadingType': c.Shading_Type,
                    'controlType': c.Shading_Control_Type,
                    'setpoint': _num(getattr(c, 'Setpoint', None)), 'setpointUnit': unit1,
                    'setpoint2': _num(getattr(c, 'Setpoint_2', None)), 'setpoint2Unit': unit2,
                    'windows': wins})
    return out


def windows(idf=None):
    """Every window and skylight, with what a designer picks them by.

    Where it is (zone, wall, facing), what it is glazed with now, and the
    shading control over it, if any.
    """
    idf = idf or idf_session.get()
    hosts = _hosts(idf)
    walls = {(s.Name or '').upper(): s for s in opaque_surfaces(idf)}
    facing = _facing()
    # A window can sit under several controls, deployed in sequence.
    controls_of = {}
    for c in idf.idfobjects['WINDOWSHADINGCONTROL']:
        for f in c.fieldnames:
            if f.startswith('Fenestration_Surface_') and getattr(c, f, ''):
                controls_of.setdefault(getattr(c, f).upper(), []).append(c)
    out = []
    for f in fenestration_surfaces(idf):
        element = _element_of(f, fenestration=True, hosts=hosts)
        if element not in ('window', 'skylight'):
            continue
        wall = walls.get((f.Building_Surface_Name or '').upper())
        shading = []
        for control in controls_of.get(f.Name.upper(), []):
            material, reason = _shading_device(idf, control)
            shading.append({'control': control.Name, 'type': control.Shading_Type,
                            'material': material, 'blocked': reason})
        out.append({
            'name': f.Name,
            'className': design_space._proper_class_name([f], f.key),
            'element': element,
            'construction': f.Construction_Name,
            'wall': f.Building_Surface_Name,
            'zone': getattr(wall, 'Zone_Name', '') if wall is not None else '',
            **facing.get(f.Name.upper(), {'azimuth': None, 'facing': ''}),
            'shading': shading,
        })
    return out


def shading_rewrites(idf, window_names):
    """The shading controls over these windows, rewritten to take a material.

    Returns (rewrites, problems). Each rewrite is {control, material}: set
    "Shading Device Material Name" to the material and empty "Construction with
    Shading Name". Checked equivalent on Res_flat1 (identical annual meters,
    3 Oct 2026), and it is what lets a sample change the glazing under a blind.
    """
    wanted = {n.upper() for n in window_names}
    rewrites, problems = {}, []
    for w in windows(idf):
        if w['name'].upper() not in wanted:
            continue
        for s in w['shading']:
            if s['blocked']:
                problems.append(f'{w["name"]}: its glazing cannot be swapped, because {s["blocked"]}')
            elif s['control'] not in rewrites:
                control = idf.getobject('WINDOWSHADINGCONTROL', s['control'])
                if (getattr(control, 'Construction_with_Shading_Name', '') or '').strip():
                    rewrites[s['control']] = s['material']
    return [{'control': c, 'material': m} for c, m in rewrites.items()], problems


def elements(idf=None):
    """The building elements this model has, with what each is built from."""
    idf = idf or idf_session.get()

    materials = _materials(idf)

    constructions = {}
    for c in idf.idfobjects['CONSTRUCTION']:
        constructions[c.Name] = {'name': c.Name, 'layers': _layer_names(c)}

    # Where each construction is used, and by which element. A build-up shared
    # between an external wall and a partition is worth knowing about before you
    # decide to swap it.
    used_by = {}

    def note(construction_name, element_key):
        if construction_name:
            used_by.setdefault(construction_name, {}).setdefault(element_key, 0)
            used_by[construction_name][element_key] += 1

    # One surface per element is enough to ask which constructions the model
    # would accept there: the answer depends on the kind of surface, not on
    # which one.
    sample = {}

    for s in opaque_surfaces(idf):
        key = _element_of(s)
        sample.setdefault(key, s)
        note(getattr(s, 'Construction_Name', ''), key)

    # Windows are elements in their own right, and the handle on them is the
    # construction: you choose a glazed build-up, you do not retune a pane.
    hosts = _hosts(idf)
    for f in fenestration_surfaces(idf):
        key = _element_of(f, fenestration=True, hosts=hosts)
        sample.setdefault(key, f)
        note(getattr(f, 'Construction_Name', ''), key)

    # Which element each material ends up in, through every construction using it.
    material_reach = {}
    for name, construction in constructions.items():
        for layer in construction['layers']:
            reach = material_reach.setdefault(layer, {'constructions': set(),
                                                      'elements': set()})
            reach['constructions'].add(name)
            reach['elements'].update(used_by.get(name, {}).keys())

    catalogue = list(_ELEMENTS) + [('window', 'Windows', None, None),
                                   ('skylight', 'Skylights', None, None),
                                   ('door', 'Doors', None, None),
                                   ('interior_window', 'Interior windows', None, None),
                                   ('other_opaque', 'Other opaque surfaces', None, None)]

    glazed = windows(idf)
    out = []
    for key, label, _kind, _boundary in catalogue:
        builds = []
        for name, elements_using in used_by.items():
            if key not in elements_using or is_mirror(name):
                continue
            construction = constructions.get(name)
            if not construction:
                continue

            layers = []
            for layer in construction['layers']:
                material = materials.get(layer, {'name': layer, 'className': None,
                                                 'insulating': False, 'glazing': False,
                                                 'conductivity': None, 'thickness': None,
                                                 'resistance': None})
                reach = material_reach.get(layer, {'constructions': set(), 'elements': set()})
                layers.append({**material,
                               'inConstructions': len(reach['constructions']),
                               'inElements': sorted(reach['elements'] - {key}),
                               'shared': len(reach['elements'] - {key}) > 0})

            builds.append({
                'construction': name,
                'surfaces': elements_using[key],
                'layers': layers,
                'insulatingLayers': [l['name'] for l in layers if l['insulating']],
            })

        if not builds:
            continue

        builds.sort(key=lambda b: -b['surfaces'])

        # What a swap may choose from: every construction the model defines that
        # EnergyPlus would accept on this kind of surface, not only the ones in
        # use. A triple glazing defined and never assigned is exactly the option
        # a student wants to try.
        host = sample.get(key)
        # The class of the element's surfaces; a model may mix detailed and
        # simplified ones, and then each target carries its own.
        classes = sorted({design_space._proper_class_name([s], s.key) for s in surface_objects(idf, key)})
        cls = classes[0] if len(classes) == 1 else None
        meta = design_space._field_meta(host, 'Construction_Name') if host else {}
        alternatives = [a for a in (design_space._referenceable(idf, meta, host, 'Construction_Name')
                                    if host else []) if not is_mirror(a)]
        if key in ('window', 'skylight'):
            # A construction with a blind, shade or screen in it is the shaded
            # state a WindowShadingControl switches to, not a glazing to fit:
            # offered as an alternative it would leave the blind down all year.
            alternatives = [a for a in alternatives
                            if not any(_is_shading_layer(idf, l)
                                       for l in constructions.get(a, {}).get('layers', []))]

        out.append({
            'id': key,
            'label': label,
            'className': cls,
            'surfaces': sum(b['surfaces'] for b in builds),
            'constructions': builds,
            'alternatives': alternatives,
            # EnergyPlus accepts any opaque build-up on any opaque surface -- a
            # floor as an external wall -- so admissible is not the same as
            # sensible. Saying where each one is already used lets the panel
            # lead with this element's own and set the rest apart.
            'alternativeUse': {name: sorted(used_by.get(name, {}).keys())
                               for name in alternatives},
            # What each alternative is made of, outside to inside, so a choice
            # among glazings shows panes and gaps, not just names.
            'alternativeLayers': {name: constructions.get(name, {}).get('layers', [])
                                  for name in alternatives},
            'alternativeLayerLabels': {name: [glazing_layer(idf, l) for l in
                                              constructions.get(name, {}).get('layers', [])]
                                       for name in alternatives} if key in ('window', 'skylight') else {},
            # The two handles, and which one this element actually offers.
            'canSwapConstruction': len(builds) > 1 or key in FENESTRATION_ELEMENTS,
            # Windows are picked one by one, so each is listed with where it is.
            'members': [w for w in glazed if w['element'] == key] if key in ('window', 'skylight') else [],
            # The shading controls over those windows, with what their setpoints mean.
            'controls': shading_controls(idf, [w['name'] for w in glazed if w['element'] == key])
                        if key in ('window', 'skylight') else [],
            'insulants': sorted({name for b in builds for name in b['insulatingLayers']}),
        })

    return sorted(out, key=lambda e: -e['surfaces'])


def handles(idf=None):
    """The design handles the envelope offers, each anchored to an element.

    Two kinds, because the two are not interchangeable:

        'construction'  swap the build-up of this element for another the model
                        defines. This is how a window is changed.
        'layer'         change a layer inside the build-ups this element uses --
                        the thickness or the conductivity of the insulant. This
                        is how a wall is changed, and it carries a warning when
                        the layer also sits in another element.
    """
    found = []
    for element in elements(idf):
        alternatives = [b['construction'] for b in element['constructions']]

        if element['canSwapConstruction']:
            found.append({
                'kind': 'construction',
                'element': element['id'],
                'elementLabel': element['label'],
                'question': 'Which build-up for the {}?'.format(element['label'].lower()),
                'className': element['className'],
                'field': 'Construction_Name',
                'choices': alternatives,
                'surfaces': element['surfaces'],
            })

        for name in element['insulants']:
            layer = next((l for b in element['constructions'] for l in b['layers']
                          if l['name'] == name), None)
            if not layer:
                continue
            field = 'Thickness' if layer.get('thickness') is not None else 'Thermal_Resistance'
            found.append({
                'kind': 'layer',
                'element': element['id'],
                'elementLabel': element['label'],
                'question': 'How much insulation in the {}?'.format(element['label'].lower()),
                'className': layer['className'],
                'field': field,
                'objects': [name],
                'current': layer.get('thickness') if field == 'Thickness'
                           else layer.get('resistance'),
                'sharedWith': layer['inElements'],
                'inConstructions': layer['inConstructions'],
            })

    return found
