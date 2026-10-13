"""What this particular building lets you optimise, discovered from the model itself.

The student chooses what to vary -- the platform does not decide for them. So
nothing here is a curated list of "the right" design variables. Instead the model
is walked object by object and each field is judged against the IDD, which is
EnergyPlus' own description of what that field is: its type, its units, the
bounds it accepts, and the values a choice field allows.

That makes the answer specific to the building in front of you. A model with no
WindowShadingControl never offers shading setpoints; one with Schedule:Constant
objects offers their values; one whose windows are not on exterior walls cannot
be asked for a window-to-wall ratio, and is told why.

    options(idf)       everything this model can be asked to optimise, in one list
    discover(idf)      the field-level half of that: bounds, units, alternatives
    capabilities(idf)  the half that needs more than a field write
    apply(idf, design) write a chosen design point into the model

A capability such as the window-to-wall ratio is not a special case with its own
story: it is one option among the rest. The only question worth asking of any of
them is whether this model can do it. If it cannot, it is not among that model's
options; if it can, it sits beside the others.

The problem a student defines is written for the library their Jupyter runs:
notebook_cell() returns the BESOS cell, or the bdopt one (bdopt_cell.py) when
engine.surrogate_engine() says "bdopt".
"""

import re

import bdopt_cell
import design_sections
import engine
import idf_rules
import idf_session

ALL_OBJECTS = '*'

# problem.json: 1 keeps the fields as eppy names them; 2 adds, to every variable and every
# target, where the field sits in the IDF object (fieldIndex, 0 = the name) and what the
# IDD calls it (iddField). bdopt addresses a field by one of those two, never by eppy's name.
SCHEMA_VERSION = 2

# Fields that name or reference things rather than describe them. Varying a name
# breaks references instead of changing a design.
_NON_DESIGN = {'name', 'key'}
_NAMEISH = ('_name', 'name_')

# EnergyPlus classes whose contents are bookkeeping, not design.
_SKIP_CLASSES = {
    'Version', 'Building', 'SimulationControl', 'Timestep', 'RunPeriod',
    'Site:Location', 'GlobalGeometryRules', 'Output:Variable', 'Output:Meter',
    'Output:VariableDictionary', 'Output:Diagnostics', 'Output:Table:SummaryReports',
    'OutputControl:Table:Style', 'Output:SQLite', 'Output:EnergyManagementSystem',
    'ExternalInterface', 'Sizing:Parameters', 'ConvergenceLimits',
    'HeatBalanceAlgorithm', 'SurfaceConvectionAlgorithm:Inside',
    'SurfaceConvectionAlgorithm:Outside', 'ShadowCalculation',
    'ZoneAirHeatBalanceAlgorithm', 'ZoneAirContaminantBalance',
    'ScheduleTypeLimits', 'Sizing:Zone', 'DesignSpecification:OutdoorAir',
}
# Prefixes only, and deliberately narrow: an earlier 'Zone' prefix here also
# swallowed ZoneVentilation and ZoneInfiltration, which are design classes.
# Surfaces stay in: their Construction Name is how a student swaps a window or a
# wall for a different build-up. Their geometry fields are filtered out below by
# _SKIP_SUBSTRINGS instead, so the structure is protected without hiding the
# design decision the surface carries.
_SKIP_PREFIXES = ('EnergyManagementSystem:', 'ExternalInterface:', 'Output:',
                  'Shading:', 'SizingPeriod:', 'Site:Ground',
                  'ZoneCapacitanceMultiplier')
_SKIP_EXACT_EXTRA = {'Zone', 'ZoneList', 'ZoneGroup', 'Schedule:Day:Hourly',
                     'Schedule:Day:Interval', 'Schedule:Week:Daily',
                     'Schedule:Week:Compact', 'Schedule:Year'}

# Geometry vertices are structure, not design parameters.
_SKIP_SUBSTRINGS = ('vertex', 'coordinate', 'number_of_vertices')

# Purely a display hint so the panel can surface familiar variables first.
# It restricts nothing: everything discovered stays selectable.
_FAMILIAR = {
    ('Material', 'Thickness'), ('Material', 'Conductivity'),
    # A massless layer has neither thickness nor conductivity: the resistance is
    # the only thing it says, and the only thing worth varying on it. Left out,
    # the panel led with its solar absorptance and buried the design knob.
    ('Material:NoMass', 'Thermal_Resistance'),
    ('WindowMaterial:Glazing', 'Solar_Transmittance_at_Normal_Incidence'),
    ('WindowMaterial:Gas', 'Thickness'),
    ('WindowMaterial:SimpleGlazingSystem', 'UFactor'),
    ('WindowMaterial:SimpleGlazingSystem', 'Solar_Heat_Gain_Coefficient'),
    ('ZoneVentilation:DesignFlowRate', 'Air_Changes_per_Hour'),
    ('ZoneInfiltration:DesignFlowRate', 'Air_Changes_per_Hour'),
    ('Lights', 'Watts_per_Zone_Floor_Area'),
    ('ElectricEquipment', 'Watts_per_Zone_Floor_Area'),
    ('WindowShadingControl', 'Setpoint'), ('WindowShadingControl', 'Setpoint_2'),
    ('WindowMaterial:Blind', 'Slat_Angle'),
    ('Schedule:Constant', 'Hourly_Value'),
    ('People', 'Zone_Floor_Area_per_Person'),
}


# Whether a field is live on a given object is answered by idf_rules, which was
# read out of the EnergyPlus documentation and checked against the IDD. It used
# to be a table transcribed by hand here, and that table was wrong: it spelled
# People's per-area field People_per_Zone_Floor_Area by analogy with Lights,
# where the IDD says People_per_Floor_Area, so the inert field stayed on offer.
#
# The sizing half of that question does not need transcribing at all: the IDD
# marks the fields EnergyPlus works out for itself with \autosizable and
# \autocalculatable, 742 of them, and eppy exposes both. Asking the IDD covers
# every class, including ones nobody has read the documentation for -- the
# transcribed table had missed View Factor to Ground, which sits on autocalculate
# in seven of the nine models here and was being offered as a variable.
def _sized_by_energyplus(obj, field, meta=None):
    """True when this object leaves the field for EnergyPlus to work out."""
    value = str(getattr(obj, field, '') or '').strip().lower()
    if value not in ('autosize', 'autocalculate'):
        return False
    meta = meta if meta is not None else _field_meta(obj, field)
    return 'autosizable' in meta or 'autocalculatable' in meta


def _inert_reason(obj, class_name, field, meta=None):
    """Why this field would do nothing on this object, or None if it is live."""
    if _sized_by_energyplus(obj, field, meta):
        return ('EnergyPlus sizes this field itself; whatever is entered here is '
                'replaced during sizing.')
    if (class_name or '').upper() == 'WINDOWSHADINGCONTROL' and \
            (field or '').replace(' ', '_').lower() in ('setpoint', 'setpoint_2'):
        import envelope  # envelope imports this module
        unit1, unit2 = envelope.setpoint_meaning(getattr(obj, 'Shading_Control_Type', ''))
        used = unit1 if (field or '').replace(' ', '_').lower() == 'setpoint' else unit2
        if used is None:
            return (f'its Shading Control Type {obj.Shading_Control_Type} does not use this '
                    'setpoint (IDD note on the field).')
    return idf_rules.why_inert(obj, class_name, field)


def _first(seq):
    return seq[0] if isinstance(seq, list) and seq else (seq if seq else None)


def _num(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# eppy keys idfobjects in upper case ('LIGHTS'), while the IDD spells classes
# properly ('Lights'). Every comparison here folds case, or the exclusion lists
# and the familiarity hint silently match nothing.
_SKIP_CLASSES_CF = {c.casefold() for c in (_SKIP_CLASSES | _SKIP_EXACT_EXTRA)}
_SKIP_PREFIXES_CF = tuple(p.casefold() for p in _SKIP_PREFIXES)
_FAMILIAR_CF = {(c.casefold(), f.casefold()) for c, f in _FAMILIAR}


def _is_skippable(class_name):
    cf = class_name.casefold()
    if cf in _SKIP_CLASSES_CF:
        return True
    return any(cf.startswith(p) for p in _SKIP_PREFIXES_CF)


def _proper_class_name(objects, fallback):
    """The class name as the IDD spells it.

    eppy reports the spelling the IDF file happened to use, so a model written in
    upper case yields 'PEOPLE'. The IDD carries the canonical name, which is what
    a student would look up in the EnergyPlus documentation.
    """
    try:
        idd = objects[0].objidd
        name = idd[0].get('idfobj') if isinstance(idd, list) and idd else None
        if isinstance(name, str) and name:
            return name
    except Exception:
        pass
    key = getattr(objects[0], 'key', None)
    return key if isinstance(key, str) and key else fallback


def _field_meta(obj, field):
    try:
        return obj.getfieldidd(field) or {}
    except Exception:
        return {}


def _bounds(meta):
    """Bounds as EnergyPlus itself states them, exclusive markers included."""
    lo = _num(_first(meta.get('minimum'))) if 'minimum' in meta else None
    hi = _num(_first(meta.get('maximum'))) if 'maximum' in meta else None
    if lo is None and 'minimum>' in meta:
        lo = _num(_first(meta.get('minimum>')))
    if hi is None and 'maximum<' in meta:
        hi = _num(_first(meta.get('maximum<')))
    return lo, hi


def _suggest(values, lo, hi):
    """A starting interval bracketing what the model already uses.

    Bounded by the IDD where it says anything; otherwise spread around the
    current value, so the student begins from something meaningful rather than
    an empty box.
    """
    present = [v for v in values if v is not None]
    if not present:
        return (lo if lo is not None else 0.0, hi if hi is not None else 1.0)
    mid = sum(present) / len(present)
    if mid == 0:
        s_lo, s_hi = 0.0, 1.0
    else:
        s_lo, s_hi = mid * 0.5, mid * 1.5
    s_lo = max(s_lo, lo) if lo is not None else s_lo
    s_hi = min(s_hi, hi) if hi is not None else s_hi
    if s_hi <= s_lo:
        s_hi = s_lo + (abs(s_lo) * 0.5 or 1.0)
        if hi is not None:
            s_hi = min(s_hi, hi)
    return round(s_lo, 6), round(s_hi, 6)


def _varyable(obj, field, meta):
    """Can this field carry a design decision at all?"""
    low = field.lower()
    if any(s in low for s in _SKIP_SUBSTRINGS):
        return None

    kind = (_first(meta.get('type')) or '').lower()

    # Judge by type before name. "Construction Name" and "Schedule Name" both end
    # in _name, yet they are the very decisions a student wants -- swap the window
    # build-up, swap the shading schedule. Only the object's own identity, and
    # untyped name-like fields, are off limits.
    if kind == 'object-list' and meta.get('validobjects'):
        return None if low == 'name' else 'reference'

    if low in _NON_DESIGN or low.endswith(_NAMEISH) or low.startswith('name'):
        return None

    if kind in ('real', 'integer'):
        return 'number'
    if kind == 'choice' and meta.get('key'):
        return 'choice'
    if kind == 'object-list' and meta.get('validobjects'):
        # A reference to another object: swapping it is a design decision --
        # a different window build-up, a different schedule. The candidates are
        # whatever objects of the valid classes this model actually contains,
        # so this needs no list of ours and works on any building.
        return 'reference'
    return None


_WINDOW_MATERIALS = ('WINDOWMATERIAL:GLAZING', 'WINDOWMATERIAL:GAS',
                     'WINDOWMATERIAL:GASMIXTURE', 'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM',
                     'WINDOWMATERIAL:BLIND', 'WINDOWMATERIAL:SHADE',
                     'WINDOWMATERIAL:SCREEN', 'WINDOWMATERIAL:GLAZINGGROUP:THERMOCHROMIC')


def _glazing_names(idf):
    names = set()
    for cls in _WINDOW_MATERIALS:
        for o in idf.idfobjects.get(cls, []):
            if getattr(o, 'Name', ''):
                names.add(o.Name)
    return names


def _construction_is_window(construction, glazing):
    layers = [getattr(construction, f, '') for f in construction.fieldnames
              if f == 'Outside_Layer' or f.startswith('Layer_')]
    layers = [l for l in layers if l]
    return bool(layers) and any(l in glazing for l in layers)


def _schedule_type(idf, name):
    """The ScheduleTypeLimits a schedule declares, so alternatives can be told apart."""
    for cls in ('SCHEDULE:CONSTANT', 'SCHEDULE:COMPACT', 'SCHEDULE:YEAR', 'SCHEDULE:FILE'):
        for o in idf.idfobjects.get(cls, []):
            if getattr(o, 'Name', '') == name:
                return getattr(o, 'Schedule_Type_Limits_Name', '') or ''
    return ''


# EnergyPlus names its reference groups, and the name says what the reference is
# for: SurfaceNames, ZoneNames, OutFaceEnvNames and NodeNames answer "where is
# this", while ConstructionNames and ScheduleNames answer "what is it made of"
# and "when does it run". Only the second kind carries a design decision --
# repointing a window at a different wall moves the building, it does not
# optimise it. Marked rather than hidden: the student can still reach them.
# 'surf' rather than 'surface': EnergyPlus abbreviates in several group names,
# and AllHeatTranSurfNames -- what SurfaceProperty:ConvectionCoefficients points
# at -- slipped through a check that spelled the word out in full.
_TOPOLOGY_HINTS = ('surf', 'zone', 'node', 'branch', 'outfaceenv', 'space',
                   'airloop', 'plantloop', 'outdoorair')


def _is_topology(meta):
    groups = [g.lower() for g in (meta.get('object-list') or [])]
    if not groups:
        return False
    return all(any(h in g for h in _TOPOLOGY_HINTS) for g in groups)


def _referenceable(idf, meta, host=None, field=''):
    """Objects this model offers as values for an object-list field.

    Offering every object of the valid classes would propose a floor build-up as
    a replacement window, which EnergyPlus refuses outright. Where the model says
    enough to tell candidates apart -- a construction's layers are glazing or they
    are not -- the list is narrowed to what can actually be substituted.
    """
    names, seen = [], set()
    for cls in meta.get('validobjects', []):
        for o in idf.idfobjects.get(cls.upper(), []):
            name = getattr(o, 'Name', '')
            if name and name not in seen:
                seen.add(name)
                names.append((name, o, cls.upper()))

    if field == 'Construction_Name' and host is not None:
        glazing = _glazing_names(idf)
        if glazing:
            import envelope  # envelope imports this module
            # Glazed or opaque, from the Surface Type field or, on the
            # simplified classes (Window, Wall:Exterior...), from the class.
            host_is_window = envelope.fenestration_kind(host) in envelope.GLAZED_KINDS
            if host_is_window:
                names = [n for n in names
                         if n[2] == 'CONSTRUCTION' and _construction_is_window(n[1], glazing)]
            else:
                names = [n for n in names
                         if n[2] != 'CONSTRUCTION' or not _construction_is_window(n[1], glazing)]

    return [n[0] for n in names]


def _reference_labels(idf, field, choices):
    """Extra wording for choices whose name alone does not say what they are."""
    if not field.endswith('Schedule_Name'):
        return None
    labels = {}
    for name in choices:
        kind = _schedule_type(idf, name)
        if kind:
            labels[name] = kind
    return labels or None


def discover(idf=None, include_all=False):
    """Every design decision this model actually exposes.

    `include_all` False keeps the list to classes that carry design intent;
    True holds nothing back, for a student who knows what they are looking for.
    """
    idf = idf or idf_session.get()
    found = []

    for class_name, objects in idf.idfobjects.items():
        if not objects:
            continue
        if not include_all and _is_skippable(class_name):
            continue

        sample = objects[0]
        proper = _proper_class_name(objects, class_name)
        for field in sample.fieldnames:
            meta = _field_meta(sample, field)
            kind = _varyable(sample, field, meta)
            if not kind:
                continue

            named, inert = [], []
            for o in objects:
                raw = getattr(o, field, '')
                if raw in ('', None):
                    continue
                reason = _inert_reason(o, proper, field, meta)
                if reason:
                    # Populated, but something on the object switches it off.
                    # Recorded with the reason rather than dropped: a student who
                    # goes looking for a variable deserves to be told why it is
                    # not on offer.
                    inert.append({'name': getattr(o, 'Name', '') or class_name,
                                  'reason': reason})
                    continue
                item = {'name': getattr(o, 'Name', '') or class_name,
                        'value': _num(raw) if kind == 'number' else raw}
                if kind == 'reference':
                    # Which objects may be substituted depends on this object,
                    # not on its class: in a model with both windows and doors,
                    # the same field accepts glazing on one and an opaque
                    # build-up on the other.
                    item['choices'] = _referenceable(idf, meta, o, field)
                named.append(item)
            if not named:
                # Either this building never sets the field, or every object
                # that does has it switched off. Keep the latter, flagged, so the
                # panel can explain the absence instead of showing nothing.
                if inert:
                    found.append({
                        'className': proper, 'field': field,
                        'label': field.replace('_', ' '), 'kind': kind,
                        'unit': _first(meta.get('units')) or '',
                        'objects': [], 'objectCount': 0,
                        'inertObjects': inert[:20], 'inert': True,
                        'inertReason': inert[0]['reason'],
                        'familiar': (proper.casefold(), field.casefold()) in _FAMILIAR_CF,
                        'documented': idf_rules.is_covered(proper),
                    })
                continue

            entry = {
                'className': proper,
                'field': field,
                'label': field.replace('_', ' '),
                'kind': kind,
                'unit': _first(meta.get('units')) or '',
                'note': ' '.join(meta.get('note', []))[:240] or None,
                'objects': named[:200],
                'objectCount': len(named),
                'inertObjects': inert[:20],
                'inert': False,
                'topology': False,
                # False means no documentation section covering this class has
                # been read -- unknown, not verified safe.
                'documented': idf_rules.is_covered(proper),
                'constraints': idf_rules.constraints_for(proper),
                'familiar': (proper.casefold(), field.casefold()) in _FAMILIAR_CF,
            }

            if kind == 'number':
                lo, hi = _bounds(meta)
                entry['min'], entry['max'] = lo, hi
                entry['suggestedMin'], entry['suggestedMax'] = _suggest(
                    [n['value'] for n in named], lo, hi)
            elif kind == 'choice':
                entry['choices'] = meta.get('key', [])
            else:
                union, seen = [], set()
                for item in named:
                    for c in item.get('choices', []):
                        if c not in seen:
                            seen.add(c)
                            union.append(c)
                entry['choices'] = union
                entry['choiceLabels'] = _reference_labels(idf, field, union)
                entry['referenceClasses'] = sorted(meta.get('validobjects', []))
                entry['topology'] = _is_topology(meta)
                entry['referenceGroups'] = list(meta.get('object-list') or [])
                # Keep the field only if some object actually has an alternative.
                if not any(len(i.get('choices', [])) > 1 for i in named):
                    continue

            found.append(entry)

    found.sort(key=lambda e: (not e['familiar'], e['className'], e['field']))
    return found


def wwr_feasibility(idf):
    """Which exterior walls could take a window-to-wall ratio, and which could not.

    Having windows on exterior walls is not enough. BESOS applies the ratio with
    geomeppy's set_wwr, which selects walls whose Outside Boundary Condition is
    Outdoors and then, for each one:

        raises  if any subsurface on the wall is not a window -- a door on the
                same wall stops it, and the exercise models are full of them;
        raises  if the windows on that wall do not share one construction;
        deletes every subsurface on the wall and creates a single new window.

    That last point is not a precondition but it is the reason to say this out
    loud: applying a window-to-wall ratio discards the fenestration the model
    came with. A student should know that before choosing it as a variable.
    """
    walls = {}
    for surface in idf.idfobjects['BuildingSurface:Detailed']:
        if (getattr(surface, 'Surface_Type', '') or '').lower() != 'wall':
            continue
        if (getattr(surface, 'Outside_Boundary_Condition', '') or '').lower() != 'outdoors':
            continue
        walls[surface.Name] = []

    for sub in idf.idfobjects['FenestrationSurface:Detailed']:
        host = getattr(sub, 'Building_Surface_Name', '')
        if host in walls:
            walls[host].append(sub)

    eligible, blocked, bare = [], [], []
    for name, subs in walls.items():
        if not subs:
            bare.append(name)
            continue
        kinds = {(getattr(s, 'Surface_Type', '') or '').lower() for s in subs}
        if kinds - {'window'}:
            blocked.append({'wall': name,
                            'reason': 'carries {} as well as windows'.format(
                                ', '.join(sorted(kinds - {'window'})))})
            continue
        constructions = {getattr(s, 'Construction_Name', '') for s in subs}
        if len(constructions) > 1:
            blocked.append({'wall': name,
                            'reason': 'its {} windows do not share one construction'.format(
                                len(subs))})
            continue
        eligible.append(name)

    return {'eligible': eligible, 'blocked': blocked, 'bareWalls': bare,
            'exteriorWalls': len(walls)}


def capabilities(idf=None):
    """Selectors that need more than a field write, and whether this model supports them.

    Window-to-wall ratio rewrites fenestration geometry, so it needs BESOS' own
    wwr selector, and it only works on walls that pass geomeppy's checks. Saying
    which walls are excluded, and why, is more useful than a bare yes or no.
    """
    idf = idf or idf_session.get()
    f = wwr_feasibility(idf)

    if not f['exteriorWalls']:
        detail = 'il modello non dichiara pareti esterne'
        available = False
    elif not f['eligible']:
        first = f['blocked'][0]['reason'] if f['blocked'] else 'nessuna parete esterna ha finestre'
        detail = 'nessuna parete utilizzabile: {}'.format(first)
        available = False
    else:
        detail = '{} pareti esterne utilizzabili su {}'.format(
            len(f['eligible']), f['exteriorWalls'])
        if f['blocked']:
            detail += '; {} escluse (es. {})'.format(
                len(f['blocked']), f['blocked'][0]['reason'])
        available = True

    return [{
        'id': 'wwr',
        'label': 'Rapporto finestra/parete',
        'available': available,
        'detail': detail,
        'eligibleWalls': len(f['eligible']),
        'blockedWalls': f['blocked'][:20],
        'exteriorWalls': f['exteriorWalls'],
        'viaBesos': True,
        'destructive': True,
        'note': 'Riscrive la geometria: va applicato tramite BESOS, e sostituisce '
                'le finestre esistenti su ogni parete interessata con una sola.',
    }]


# How a building is reasoned about, rather than how EnergyPlus files it. A
# student looking for the insulation thickness looks for the wall, not for the
# class Material; the IDD organises input, not thought.
#
# This is presentation only. Every option stays selectable, and a class that
# matches nothing here still appears, under 'altro' -- so a model using classes
# nobody anticipated loses nothing.
FAMILIES = [
    ('involucro_opaco', 'Involucro opaco',
     'Muri, copertura, solai: di cosa sono fatti e quanto isolano.',
     ('Material', 'Material:NoMass', 'Material:AirGap', 'Material:InfraredTransparent',
      'Construction', 'InternalMass', 'BuildingSurface:Detailed',
      'SurfaceProperty:ConvectionCoefficients')),
    ('involucro_trasparente', 'Involucro trasparente',
     'Vetri, telai e quanta superficie vetrata.',
     ('WindowMaterial:Glazing', 'WindowMaterial:Gas', 'WindowMaterial:GasMixture',
      'WindowMaterial:SimpleGlazingSystem', 'WindowProperty:FrameAndDivider',
      'FenestrationSurface:Detailed', 'Window', 'WindowMaterial:Blind',
      'WindowMaterial:Shade', 'WindowMaterial:Screen', 'WindowShadingControl')),
    ('guadagni', 'Guadagni interni',
     'Persone, illuminazione, apparecchiature: il calore prodotto dentro.',
     ('People', 'Lights', 'ElectricEquipment', 'OtherEquipment', 'GasEquipment',
      'HotWaterEquipment', 'SteamEquipment', 'WaterUse:Equipment',
      'ZoneContaminantSourceAndSink:Generic:Constant')),
    ('aria', 'Ventilazione e infiltrazioni',
     "Quanta aria entra, voluta o no.",
     ('ZoneVentilation:DesignFlowRate', 'ZoneVentilation:WindandStackOpenArea',
      'ZoneInfiltration:DesignFlowRate', 'ZoneInfiltration:EffectiveLeakageArea',
      'ZoneInfiltration:FlowCoefficient', 'ZoneMixing', 'ZoneCrossMixing',
      'DesignSpecification:ZoneAirDistribution')),
    ('impianto', 'Impianto',
     'Come si scalda e si raffresca, e con quale resa.',
     ('ZoneHVAC:IdealLoadsAirSystem', 'ZoneHVAC:EquipmentList',
      'ZoneHVAC:Baseboard:Convective:Water', 'ZoneHVAC:Baseboard:RadiantConvective:Water',
      'Boiler:HotWater', 'Chiller:Electric:EIR', 'Coil:Heating:Water',
      'Coil:Cooling:Water', 'Pump:VariableSpeed', 'Pump:ConstantSpeed',
      'Fan:VariableVolume', 'Fan:ConstantVolume', 'Fan:OnOff', 'Fan:SystemModel')),
    ('regolazione', 'Regolazione e comfort',
     'Le temperature obiettivo e il controllo della luce naturale.',
     ('ThermostatSetpoint:DualSetpoint', 'ThermostatSetpoint:SingleHeating',
      'ThermostatSetpoint:SingleCooling', 'ZoneControl:Thermostat',
      'ZoneControl:Humidistat', 'Daylighting:Controls',
      'OutputControl:IlluminanceMap:Style')),
    ('profili', 'Profili di utilizzo',
     "Quando l'edificio e' occupato e in funzione.",
     ('Schedule:Compact', 'Schedule:Constant', 'Schedule:File', 'Schedule:Day:List',
      'RunPeriodControl:SpecialDays')),
]

_FAMILY_OF = {}
for _key, _label, _blurb, _classes in FAMILIES:
    for _cls in _classes:
        _FAMILY_OF[_cls.casefold()] = _key


def family_of(class_name):
    """Which building system a class belongs to, or 'altro' when unclassified."""
    return _FAMILY_OF.get((class_name or '').casefold(), 'altro')


def envelope_layers(idf=None):
    """The two different things EnergyPlus means by envelope, kept apart.

    A Material is one layer and its physics: thickness, conductivity, density.
    A Construction is an ordered stack of those layers, and it is what a surface
    actually references. The distinction is not pedantry, it decides what a
    design variable means:

        vary a Material   -> every Construction containing that layer changes,
                             and with it every surface built from them. In the
                             first exercise model one plasterboard sits in 16 of
                             the 42 constructions.
        vary a Construction -> one assembly is swapped for another that already
                             exists in the model, and only the surfaces using it
                             move.

    A student who thickens an insulant expecting to touch an external wall may
    also be thickening the party walls. Reporting the reach is the honest way to
    let them choose knowingly.
    """
    idf = idf or idf_session.get()

    layer_fields = lambda c: [f for f in c.fieldnames
                              if f == 'Outside_Layer' or f.startswith('Layer')]

    used_by = {}
    constructions = []
    for c in idf.idfobjects['Construction']:
        layers = [getattr(c, f, '') for f in layer_fields(c)]
        layers = [l for l in layers if l]
        constructions.append({'name': c.Name, 'layers': layers,
                              'layerCount': len(layers)})
        for layer in layers:
            used_by.setdefault(layer, []).append(c.Name)

    on_surface = {}
    for group in ('BuildingSurface:Detailed', 'FenestrationSurface:Detailed'):
        for surface in idf.idfobjects[group]:
            name = getattr(surface, 'Construction_Name', '')
            if name:
                on_surface[name] = on_surface.get(name, 0) + 1

    materials = []
    for group in ('Material', 'Material:NoMass', 'Material:AirGap',
                  'WindowMaterial:Glazing', 'WindowMaterial:Gas',
                  'WindowMaterial:SimpleGlazingSystem'):
        for m in idf.idfobjects[group]:
            in_constructions = used_by.get(m.Name, [])
            materials.append({
                'name': m.Name,
                'className': group,
                'usedInConstructions': sorted(in_constructions),
                'reach': sum(on_surface.get(c, 0) for c in in_constructions),
            })

    for c in constructions:
        c['surfaces'] = on_surface.get(c['name'], 0)

    return {'materials': sorted(materials, key=lambda m: -len(m['usedInConstructions'])),
            'constructions': sorted(constructions, key=lambda c: -c['surfaces']),
            'note': 'Un materiale e uno strato; una stratigrafia e la sequenza di '
                    'strati che una superficie usa. Cambiare un materiale si '
                    'propaga a tutte le stratigrafie che lo contengono.'}


def by_family(idf=None):
    """The model's options grouped the way a building is thought about.

    Returns the families this particular building actually has, each with its
    options split into the ones it can vary and the ones it cannot, so a panel
    can show a short list of systems instead of two hundred flat rows.
    """
    idf = idf or idf_session.get()

    buckets = {}
    for opt in options(idf):
        detail = opt['detail']
        cls = detail.get('className') if isinstance(detail, dict) else None
        key = family_of(cls) if opt['group'] != 'geometry' else 'involucro_trasparente'
        buckets.setdefault(key, []).append(opt)

    known = [(k, label, blurb) for k, label, blurb, _ in FAMILIES]
    known.append(('altro', 'Altro', 'Classi non ancora ricondotte a un sistema.'))

    out = []
    for key, label, blurb in known:
        entries = buckets.get(key) or []
        if not entries:
            continue
        available = [e for e in entries if e['available']]
        out.append({
            'id': key,
            'label': label,
            'blurb': blurb,
            'available': len(available),
            'unavailable': len(entries) - len(available),
            'familiar': sum(1 for e in available
                            if isinstance(e['detail'], dict) and e['detail'].get('documented')),
            'options': entries,
        })
    return out


def object_fields(obj, class_name=None):
    """The variable fields of one object, with that object's own values.

    discover() aggregates a field across every object of its class, which is the
    right answer for "can this model vary Material.Thickness" and the wrong one
    for "how thick is this insulant". A layer needs its own number: suggesting an
    interval around the mean of thirty-five materials would bracket the wrong
    thing entirely.
    """
    class_name = class_name or _proper_class_name([obj], getattr(obj, 'key', ''))

    out = []
    for field in obj.fieldnames:
        if field in _NON_DESIGN or field.lower() in _NON_DESIGN:
            continue
        meta = _field_meta(obj, field)
        kind = _varyable(obj, field, meta)
        if kind != 'number':
            continue

        raw = getattr(obj, field, '')
        if raw in ('', None):
            continue
        value = _num(raw)
        if value is None:
            continue

        reason = _inert_reason(obj, class_name, field, meta)
        if reason:
            continue

        lo, hi = _bounds(meta)
        s_lo, s_hi = _suggest([value], lo, hi)
        out.append({
            'className': class_name,
            'field': field,
            'label': field.replace('_', ' '),
            'unit': _first(meta.get('units')) or '',
            'current': value,
            'min': lo,
            'max': hi,
            'suggestedMin': s_lo,
            'suggestedMax': s_hi,
            'familiar': (class_name.casefold(), field.casefold()) in _FAMILIAR_CF,
        })

    out.sort(key=lambda f: (not f['familiar'], f['field']))
    return out


def structure(idf=None):
    """The model as EnergyPlus itself organises it: group, class, object, field.

    This is the generic backbone, and it is generic because nothing in it was
    anticipated. EnergyPlus declares a \group for every class in the IDD -- 59 of
    them -- and its Input Output Reference is chaptered by exactly those groups
    ("Group - Surface Construction Elements", "Group - Internal Gains"). So the
    IDD, the documentation and the file all agree on one taxonomy, and reading it
    off the model means any IDF organises itself, including one using classes
    nobody here has ever seen.

    An unfamiliar building simply shows different groups: a residential model
    lands in twelve, a real HVAC model in twenty-seven, and neither needed a rule
    written for it.
    """
    idf = idf or idf_session.get()

    groups = {}
    for entry in catalogue(idf):
        objects = idf.idfobjects[entry['className'].upper()]
        try:
            group = objects[0].objidd[0].get('group') or 'Altro'
        except Exception:
            group = 'Altro'

        bucket = groups.setdefault(group, {'name': group, 'classes': {}})
        cls = bucket['classes'].setdefault(entry['className'], {
            'className': entry['className'],
            'objectCount': len(objects),
            'fields': [],
        })
        cls['fields'].append(entry)

    out = []
    for group in groups.values():
        classes = sorted(group['classes'].values(), key=lambda c: -len(c['fields']))
        out.append({
            'name': group['name'],
            # Which design question the group answers; None for groups that are
            # not a design decision and are reached only through the search.
            'section': design_sections.GROUP_SECTION.get(group['name']),
            'classes': classes,
            'fieldCount': sum(len(c['fields']) for c in classes),
            'objectCount': sum(c['objectCount'] for c in classes),
        })
    return sorted(out, key=lambda g: -g['fieldCount'])


def _targets(idf, v):
    """The objects a variable writes to, named one by one.

    A construction swap goes to the surfaces of its element and nowhere else; a
    layer goes to the material it names; a field from the group browser goes to
    every object of its class. Resolved here, at definition time, so the notebook
    reads a list rather than re-deriving what "the windows" meant.
    """
    if v.get('kind') == 'construction' and v.get('element'):
        import envelope  # envelope imports this module
        return envelope.surfaces_of(idf, v['element'])
    objects = [o for o in (v.get('objects') or []) if o]
    return objects or [ALL_OBJECTS]


def _construction(idf, v):
    """A construction swap on the surfaces of one element, of whatever class.

    The surfaces may be detailed or simplified (FenestrationSurface:Detailed
    and Window, BuildingSurface:Detailed and Wall:Exterior), so every target
    carries its own class. Chosen surfaces narrow the element and must belong
    to it. Every option must be a construction EnergyPlus accepts on every
    target, and a glazing swap under a shading control that names a shaded
    construction comes with the rewrite that keeps the device valid.
    """
    import envelope  # envelope imports this module
    element = v['element']
    members = {s.Name.upper(): s for s in envelope.surface_objects(idf, element)}
    if not members:
        return None, f'this model has no {element.replace("_", " ")}s.'
    picked = [o for o in (v.get('objects') or []) if o]
    outside = [o for o in picked if o.upper() not in members]
    if outside:
        return None, f'{outside[0]!r} is not one of the {element.replace("_", " ")}s.'
    hosts = [members[o.upper()] for o in picked] if picked else list(members.values())

    options = list(dict.fromkeys(str(o) for o in (v.get('options') or [])))
    if len(options) < 2:
        return None, 'at least two options are needed; with one it is a constant.'
    # Hosts of the same class and kind accept the same constructions.
    seen = {}
    for o in hosts:
        sig = (o.key.upper(), envelope.fenestration_kind(o))
        if sig not in seen:
            seen[sig] = set(_referenceable(idf, _field_meta(o, 'Construction_Name'), o,
                                           'Construction_Name'))
        bad = [p for p in options if p not in seen[sig]]
        if bad:
            return None, f'EnergyPlus does not accept {bad[0]!r} on {o.Name}.'

    classes = {o.Name: _proper_class_name([o], o.key) for o in hosts}
    item = {'name': v['name'].strip(), 'type': 'category', 'options': options,
            'className': next(iter(classes.values())) if len(set(classes.values())) == 1 else None,
            'field': 'Construction_Name',
            'targets': [{'object': o.Name, 'field': 'Construction_Name', 'className': classes[o.Name]}
                        for o in hosts],
            'label': v.get('label'), 'unit': '',
            'source': {k: v[k] for k in ('kind', 'element', 'elementLabel', 'perWindow', 'baseName')
                       if v.get(k)}}
    if element in ('window', 'skylight'):
        rewrites, blocked = envelope.shading_rewrites(idf, [o.Name for o in hosts])
        if blocked:
            return None, blocked[0]
        if rewrites:
            item['shading'] = rewrites
    return item, None


def _setpoint(idf, v):
    """A setpoint variable: one number written into fields of several schedules.

    Its targets are (schedule, field) pairs, not objects, because the value
    sits in a different field of each schedule. Each is checked to exist and to
    hold a number now -- a target that has moved since the panel read it would
    otherwise be overwritten wherever it now points.
    """
    targets = v.get('targets') or []
    if not targets:
        return None, 'no schedule to write it to.'
    resolved = []
    for t in targets:
        obj = next((idf.getobject(c, t.get('object', ''))
                    for c in ('SCHEDULE:COMPACT', 'SCHEDULE:CONSTANT')
                    if idf.getobject(c, t.get('object', '')) is not None), None)
        if obj is None:
            return None, f'schedule {t.get("object")!r} is not in the model.'
        if t.get('field') not in obj.fieldnames:
            return None, f'{t.get("object")} has no field {t.get("field")}.'
        now = getattr(obj, t['field'], None)
        if v.get('kind') == 'schedule_time':
            # A date or an hour of the schedule: the field must still hold one.
            if not str(now).strip().lower().startswith(('through', 'until')):
                return None, f'{t.get("object")}.{t.get("field")} no longer holds a date or a time.'
        elif _num(now) is None:
            return None, f'{t.get("object")}.{t.get("field")} does not hold a number.'
        # The class travels with each target: a setpoint can sit in a
        # Schedule:Compact in one zone and a Schedule:Constant in another.
        resolved.append({'object': obj.Name, 'field': t['field'], 'className': obj.key})
    if v.get('kind') == 'schedule_time':
        options = list(dict.fromkeys(str(o) for o in (v.get('options') or [])))
        now = str(getattr(obj, resolved[-1]['field'], '')).strip().lower()
        prefix = 'through' if now.startswith('through') else 'until'
        if len(options) < 2:
            return None, 'at least two options are needed.'
        if any(not o.lower().startswith(prefix) for o in options):
            return None, f'every option must be of the form "{prefix.title()}:".'
        return {'name': v['name'], 'type': 'category', 'options': options,
                'className': None, 'field': None, 'targets': resolved,
                'label': v.get('label'), 'unit': '',
                'source': {'kind': 'schedule_time', 'current': v.get('current'),
                           'choices': v.get('choices'), 'labels': v.get('display')}}, None

    lo, hi = v.get('min'), v.get('max')
    if lo is None or hi is None:
        return None, 'the range is missing.'
    lo, hi = float(lo), float(hi)
    if hi <= lo:
        return None, f'the range {lo}-{hi} is empty.'
    return {'name': v['name'], 'type': 'range', 'min': lo, 'max': hi,
            'className': None, 'field': None, 'targets': resolved,
            'label': v.get('label'), 'unit': '°C',
            'source': {'kind': 'setpoint', 'setpoint': v.get('setpoint'),
                       'current': v.get('current')}}, None


_SCHEDULE_FIELD_CLASSES = ('SCHEDULE:COMPACT', 'SCHEDULE:CONSTANT', 'SCHEDULE:DAY:HOURLY',
                           'SCHEDULE:DAY:INTERVAL', 'SCHEDULE:DAY:LIST')


def _schedule_box(idf, v):
    """A box of a schedule made a variable: its value (range) or the time it ends (options).

    Targets are {className, object, field}: the same box in several schedules,
    one per zone, is still one column. Any schedule kind schedule_model reads
    can hold the box -- a Compact field, a Day:Hourly hour, a Day:Interval pair.
    A schedule an EMS program always overwrites is refused: the variable would
    change nothing EnergyPlus uses.
    """
    import schedule_model  # imports nothing from here, but keep the panel's modules light
    targets = v.get('targets') or []
    if not targets:
        return None, 'no schedule to write it to.'
    by_class = {c: {str(o.obj[1]).strip().upper(): o for o in idf.idfobjects.get(c, [])}
                for c in _SCHEDULE_FIELD_CLASSES}
    over = schedule_model.overrides(idf)
    resolved, styles = [], set()
    for t in targets:
        cls = (t.get('className') or '').upper()
        obj = by_class.get(cls, {}).get((t.get('object') or '').upper())
        if obj is None:
            return None, f'schedule {t.get("object")!r} is not in the model.'
        if t.get('field') not in obj.fieldnames:
            return None, f'{t.get("object")} has no field {t.get("field")}.'
        full = [o for o in over.get(str(obj.obj[1]).strip().upper(), []) if o['active'] and not o['releases']]
        if full:
            return None, (f'{t.get("object")} is overwritten at every timestep by the EMS actuator '
                          f'{full[0]["name"]}; varying it would change nothing.')
        now = str(obj.obj[obj.fieldnames.index(t['field'])]).strip()
        if v.get('kind') == 'schedule_time':
            if schedule_model.parse_time(re.sub(r'^\s*until\s*:?\s*', '', now, flags=re.I)) is None:
                return None, f'{t.get("object")}.{t.get("field")} no longer holds a time.'
            styles.add('until' if now.lower().startswith('until') else 'bare')
        elif _num(now) is None:
            return None, f'{t.get("object")}.{t.get("field")} does not hold a number.'
        resolved.append({'object': str(obj.obj[1]).strip(), 'field': t['field'], 'className': obj.key})

    source = {k: v[k] for k in ('kind', 'role', 'when', 'zones', 'current') if v.get(k) is not None}
    if v.get('kind') == 'schedule_time':
        if len(styles) > 1:
            return None, 'the boxes mix "Until: hh:mm" and "hh:mm" fields; split them into two parameters.'
        times = []
        for o in v.get('options') or []:
            m = schedule_model.parse_time(re.sub(r'^\s*until\s*:?\s*', '', str(o), flags=re.I))
            if m is None:
                return None, f'{o!r} is not a time of day.'
            times.append(m)
        times = sorted(set(times))
        if len(times) < 2:
            return None, 'at least two options are needed.'
        lo, hi = v.get('minMinute'), v.get('maxMinute')
        if lo is not None and hi is not None and (times[0] < lo or times[-1] > hi):
            return None, 'an option falls outside the neighbouring slots and would put the times out of order.'
        fmt = (lambda m: f'Until: {m // 60:02d}:{m % 60:02d}') if styles == {'until'} \
            else (lambda m: f'{m // 60:02d}:{m % 60:02d}')
        return {'name': v['name'], 'type': 'category', 'options': [fmt(m) for m in times],
                'className': None, 'field': None, 'targets': resolved,
                'label': v.get('label'), 'unit': '', 'source': source}, None

    lo, hi = v.get('min'), v.get('max')
    if lo is None or hi is None:
        return None, 'the range is missing.'
    lo, hi = float(lo), float(hi)
    if hi <= lo:
        return None, f'the range {lo}-{hi} is empty.'
    return {'name': v['name'], 'type': 'range', 'min': lo, 'max': hi,
            'className': None, 'field': None, 'targets': resolved,
            'label': v.get('label'), 'unit': v.get('unit') or '', 'source': source}, None


_IDD_FIELD_LINE = re.compile(r'^\s*([AN]\d+)\s*[,;]\s*(?:\\field\s+(.*))?$')
_IDD_FIELD_START = re.compile(r'^\s*[AN]\d+\s*[,;]')
_IDD_FIELD_NAME_ONLY = re.compile(r'^\s+\\field\s+(.*)$')
_IDD_TEXT = {}


def _norm(name):
    return re.sub(r'\s+', ' ', str(name).strip()).lower()


def _idd_text_names():
    """The fields the IDD file itself names, class by class (class in upper case, names folded).

    eppy extends a class whose last fields repeat (a Schedule:Day:List holds 1444
    named values, the file lists five) by counting on from the last name it
    reads, so eppy can name a position the file never does. A reader that looks
    names up in the file -- bdopt -- cannot find those. Read the same way bdopt
    reads it, so that the two can be compared.
    """
    if 'names' not in _IDD_TEXT:
        names = {}
        try:
            with open(idf_session.IDD_PATH, encoding='latin-1') as handle:
                current, pending = None, False
                for raw in handle:
                    line = raw.rstrip()
                    if not line or line.startswith('!'):
                        continue
                    if line[0] not in ' \t\\' and not _IDD_FIELD_START.match(line):
                        cls = re.split(r'[,;]', line, maxsplit=1)[0].strip()
                        if cls:
                            current, pending = names.setdefault(cls.upper(), []), False
                        continue
                    if current is None:
                        continue
                    m = _IDD_FIELD_LINE.match(line)
                    if m:
                        current.append(_norm(m.group(2) or ''))
                        pending = not (m.group(2) or '').strip()
                        continue
                    if pending:
                        m = _IDD_FIELD_NAME_ONLY.match(line)
                        if m:
                            current[-1], pending = _norm(m.group(1)), False
        except OSError:
            names = {}  # no IDD file here: eppy's names are taken as they are
        _IDD_TEXT['names'] = names
    return _IDD_TEXT['names']


def _idd_names_position(obj, index, name):
    """True when the IDD file gives this name to this position, and to no earlier one."""
    listed = _idd_text_names().get(str(getattr(obj, 'key', '')).upper())
    if not listed:
        return True
    want = _norm(name)
    return want in listed and listed.index(want) == index


def _position(obj, field):
    """Where an eppy field sits in its IDF object, and what the IDD calls it.

    eppy's field names start with 'key', so the position in the IDF object (the
    name is 0, as bdopt counts) is the eppy index minus one. The IDD name is the
    exact text of the field's \\field line: 'Construction Name', where eppy says
    Construction_Name. It is None when the object cannot say, and when the IDD
    does not name that position itself (the Value 10 of a Schedule:Day:List:
    eppy counts on from Value 1, the file lists no more) or names an earlier one
    the same: a name that would lead a reader to another field is no name.
    """
    try:
        index = list(obj.fieldnames).index(field) - 1
    except (AttributeError, ValueError):
        return None, None
    if index < 0:
        return None, None
    name = _first(_field_meta(obj, field).get('field'))
    name = name.strip() if isinstance(name, str) else None
    if name and not _idd_names_position(obj, index, name):
        name = None
    return index, (name or None)


def add_positions(idf, variables):
    """Schema 2 of problem.json: the position and the IDD name of every field written.

    Returns copies of the variables where each carries fieldIndex and iddField
    (None when it has no single field: a setpoint spread over several schedule
    fields) and each dict target carries its own. eppy's name stays in 'field'.
    A target whose class is spelled differently in the file than in the IDD
    (SCHEDULE:COMPACT) also gets iddClass. The same call upgrades a definition
    of schema 1 against the model it was written for.
    """
    cache = {}

    def objects_of(class_name):
        key = str(class_name or '').upper()
        if key not in cache:
            objs = list(idf.idfobjects.get(key) or [])
            cache[key] = ({str(getattr(o, 'Name', '') or '').strip().upper(): o for o in objs},
                          objs[0] if objs else None)
        return cache[key]

    def locate(class_name, object_name, field):
        by_name, first = objects_of(class_name)
        obj = None
        if object_name not in (None, '', ALL_OBJECTS):
            obj = by_name.get(str(object_name).strip().upper())
        obj = obj or first
        if obj is None or not field:
            return None, None, None
        index, idd = _position(obj, field)
        return index, idd, _proper_class_name([obj], getattr(obj, 'key', class_name))

    out = []
    for v in variables:
        v = dict(v)
        targets = []
        for t in v.get('targets') or []:
            if isinstance(t, dict):
                t = dict(t)
                index, idd, proper = locate(t.get('className'), t.get('object'), t.get('field'))
                t['fieldIndex'], t['iddField'] = index, idd
                if proper and proper != t.get('className'):
                    t['iddClass'] = proper
            targets.append(t)
        if targets:
            v['targets'] = targets
        index = idd = None
        if v.get('className') and v.get('field'):
            first = targets[0] if targets else ALL_OBJECTS
            index, idd, _ = locate(v['className'], first.get('object') if isinstance(first, dict) else first,
                                   v['field'])
        v['fieldIndex'], v['iddField'] = index, idd
        if v.get('shading'):
            # The blind rewrite writes two fields of the shading control; where they are depends on the
            # IDD, so the cell is told rather than left to assume.
            rewrites = []
            for r in v['shading']:
                r = dict(r)
                control = (idf.getobject('WINDOWSHADINGCONTROL', r.get('control', ''))
                           if hasattr(idf, 'getobject') else None)
                if control is not None:
                    r['constructionIndex'], r['constructionField'] = _position(control, 'Construction_with_Shading_Name')
                    r['materialIndex'], r['materialField'] = _position(control, 'Shading_Device_Material_Name')
                rewrites.append(r)
            v['shading'] = rewrites
        out.append(v)
    return out


def _py(s):
    return repr(s)


def _num_text(x):
    return ('%.6g' % x) if isinstance(x, float) else str(x)


def notebook_cell(variables, objectives):
    """The problem as the student's "Define the problem" cell writes it.

    The library the cell is written for follows the image that serves the
    students' Jupyter: engine.surrogate_engine() is "besos" (the Laboratory's
    cell, below, unchanged) or "bdopt" (bdopt_cell.py, which reads the field
    positions and IDD names that problem.json carries from schema 2).
    """
    if engine.surrogate_engine() == 'bdopt':
        return bdopt_cell.notebook_cell(variables, objectives)
    return _notebook_cell_besos(variables, objectives)


def _notebook_cell_besos(variables, objectives):
    """The problem as the Laboratory's "Define The Problem" cell writes it.

    One FieldSelector and one Parameter per object; a parameter that writes
    several objects shares one descriptor and one name across them, as the
    Laboratory does for the windows, so it stays one column of the samples.
    Field names are the ones eppy reads (spaces as underscores), which
    FieldSelector accepts.
    """
    lines = ['from besos import sampling',
             'from besos.parameters import FieldSelector, Parameter, RangeParameter, CategoryParameter',
             'from besos.problem import EPProblem', '']
    # A blind given as a shaded construction only fits the glazing it was built
    # with; given as a material it fits whichever glazing a sample picks.
    rewrites = list({r['control']: r for v in variables for r in v.get('shading') or []}.values())
    if rewrites:
        lines.append('# The blinds over the windows whose construction changes: given as a material,')
        lines.append('# they fit any window construction a sample picks')
        lines.append('for control, blind in [{}]:'.format(', '.join(
            f'({_py(r["control"])}, {_py(r["material"])})' for r in rewrites)))
        lines.append("    wsc = building.getobject('WINDOWSHADINGCONTROL', control)")
        lines.append('    wsc.Shading_Device_Material_Name = blind')
        lines.append("    wsc.Construction_with_Shading_Name = ''")
        lines.append('')
    lines += ['parameters = []', '']
    used = set()
    for i, v in enumerate(variables):
        var = re.sub(r'[^a-z0-9]+', '_', v['name'].lower()).strip('_')[:28] or f'p{i}'
        if var[0].isdigit():
            var = 'p_' + var
        while var in used:
            var += '_'
        used.add(var)
        if v['type'] == 'range':
            descriptor = f'RangeParameter(min_val={_num_text(v["min"])}, max_val={_num_text(v["max"])})'
        else:
            descriptor = 'CategoryParameter(options=[{}])'.format(', '.join(_py(o) for o in v['options']))
        targets = [t if isinstance(t, dict) else {'object': t, 'field': v['field'], 'className': v['className']}
                   for t in v['targets']]
        lines.append(f'# {v["name"]}')
        if v['type'] == 'category':
            # A surrogate needs numbers: the same coding as in problem.json.
            lines.append('#   as numbers: ' + ', '.join(f'{i} = {o}' for i, o in enumerate(v['options'], 1)))
        if len(targets) == 1:
            t = targets[0]
            lines.append(f'{var}_sel = FieldSelector(class_name={_py(t["className"])}, '
                         f'object_name={_py(t["object"])}, field_name={_py(t["field"])})')
            lines.append(f'parameters.append(Parameter(selector={var}_sel, value_descriptors={descriptor}, '
                         f'name={_py(v["name"])}))')
        else:
            lines.append(f'{var} = {descriptor}')
            same = all(t['className'] == targets[0]['className'] and t['field'] == targets[0]['field'] for t in targets)
            if same:
                lines.append('for obj in [{}]:'.format(', '.join(_py(t['object']) for t in targets)))
                lines.append(f'    sel = FieldSelector(class_name={_py(targets[0]["className"])}, '
                             f'object_name=obj, field_name={_py(targets[0]["field"])})')
            else:
                lines.append('for cls, obj, field in [{}]:'.format(', '.join(
                    f'({_py(t["className"])}, {_py(t["object"])}, {_py(t["field"])})' for t in targets)))
                lines.append('    sel = FieldSelector(class_name=cls, object_name=obj, field_name=field)')
            lines.append(f'    parameters.append(Parameter(selector=sel, value_descriptors={var}, name={_py(v["name"])}))')
        lines.append('')
    lines.append('objectives = [{}]'.format(', '.join(_py(o['name'] if isinstance(o, dict) else o)
                                                     for o in objectives)))
    lines.append('problem = EPProblem(parameters, objectives)')
    lines.append('samples = sampling.dist_sampler(sampling.lhs, problem, num_samples=20)')
    return '\n'.join(lines)


_KNOWN = {'key': None, 'value': None}


def _known_fields(idf):
    """discover() indexed by (class, field), cached until the live model changes.

    Validating a problem, and every preview of it, needs the whole catalogue;
    rebuilding it takes 15-20 s on a 17-zone model. The cache key is the model
    object and idf_session's generation, bumped on every load or edit.
    """
    key = (id(idf), idf_session.generation())
    if _KNOWN['key'] != key:
        _KNOWN['value'] = {(e['className'], e['field']): e for e in discover(idf)}
        _KNOWN['key'] = key
    return _KNOWN['value']


def validate_problem(idf, variables, objectives):
    """Refuse a problem that cannot mean what it says, and write it out in full.

    Two kinds of variable, the two BESOS knows: a range, sampled between two
    numbers, and a category, chosen among named options -- a window build-up, a
    calculation method, a schedule. Each fails silently in its own way, and each
    is caught here rather than four hours later in a flat optimisation:

        either      a field EnergyPlus overwrites or another field switches off;
                    a target the model does not contain; a name already taken,
                    since the name is the column the samples are read back by
        a range     outside what the IDD accepts, or with both ends equal -- a
                    constant wearing the costume of a variable
        a category  with fewer than two options, or with an option EnergyPlus
                    would refuse on one of the objects it is written to
    """
    known = _known_fields(idf)
    problems, clean, names = [], [], set()

    for v in variables:
        if v.get('kind') == 'construction' and v.get('element'):
            name = (v.get('name') or '').strip()
            if not name or name in names:
                problems.append(f'{name or "construction"}: the name is missing or already used.')
                continue
            names.add(name)
            item, why = _construction(idf, v)
            if why:
                problems.append(f'{name}: {why}')
            else:
                clean.append(item)
            continue
        if v.get('kind') in ('setpoint', 'schedule_time', 'schedule_value'):
            name = (v.get('name') or '').strip()
            if not name or name in names:
                problems.append(f'{name or "setpoint"}: the name is missing or already used.')
                continue
            names.add(name)
            item, why = _setpoint(idf, v) if v.get('kind') == 'setpoint' else _schedule_box(idf, v)
            if why:
                problems.append(f'{name}: {why}')
            else:
                clean.append(item)
            continue

        class_name, field = v.get('className'), v.get('field')
        label = v.get('name') or f'{class_name}.{field}'
        entry = known.get((class_name, field))
        if entry is None:
            problems.append(f'{class_name}.{field} is not a variable of this model.')
            continue
        if entry['inert']:
            problems.append(f'{label}: {entry["inertReason"]}')
            continue

        name = (v.get('name') or '').strip()
        if not name:
            problems.append(f'{class_name}.{field}: the name is missing.')
            continue
        if name in names:
            problems.append(f'{name}: another parameter has this name; '
                            'in the notebook they would be the same column.')
            continue
        names.add(name)

        objects = idf.idfobjects.get(class_name.upper()) or []
        targets = _targets(idf, v)
        if targets == [ALL_OBJECTS]:
            hosts = list(objects)
        else:
            by_name = {(getattr(o, 'Name', '') or '').upper(): o for o in objects}
            missing = [t for t in targets if t.upper() not in by_name]
            if missing:
                problems.append(f'{name}: {class_name} {missing[0]!r} is not in the model.')
                continue
            hosts = [by_name[t.upper()] for t in targets]
        if not hosts:
            problems.append(f'{name}: no object to write it to.')
            continue

        meta = _field_meta(hosts[0], field)
        off = next(((getattr(o, 'Name', '?'), r) for o in hosts
                    for r in [_inert_reason(o, class_name, field)] if r), None)
        if off:
            problems.append(f'{name}: it would have no effect on {off[0]} -- {off[1]}')
            continue

        out = {'name': name, 'className': class_name, 'field': field,
               'targets': targets, 'label': v.get('label') or entry.get('label'),
               'unit': entry.get('unit') or '', 'source': {
                   k: v[k] for k in ('kind', 'element', 'elementLabel', 'layer', 'group', 'perWindow', 'baseName')
                   if v.get(k)}}

        if v.get('type') == 'category':
            if entry['kind'] == 'number':
                problems.append(f'{name}: this is a numeric field; give it as a range.')
                continue
            options = list(dict.fromkeys(str(o) for o in (v.get('options') or [])))
            if len(options) < 2:
                problems.append(f'{name}: at least two options are needed; '
                                'with one it is a constant.')
                continue
            if entry['kind'] == 'choice':
                allowed = {k.casefold() for k in (meta.get('key') or [])}
                bad = [o for o in options if o.casefold() not in allowed]
            else:
                # What a reference may point at depends on its host -- glazing on
                # a window, an opaque build-up on a wall -- so every host is asked.
                # Hosts of the same surface type get the same answer.
                bad, seen = [], {}
                for o in hosts:
                    kind = (getattr(o, 'Surface_Type', '') or '').lower()                         if field == 'Construction_Name' else ''
                    if kind not in seen:
                        seen[kind] = set(_referenceable(idf, meta, o, field))
                    bad += [p for p in options if p not in seen[kind] and p not in bad]
            if bad:
                problems.append(f'{name}: EnergyPlus does not accept {bad[0]!r} here.')
                continue
            clean.append({**out, 'type': 'category', 'options': options})
            continue

        if entry['kind'] != 'number':
            problems.append(f'{name}: this is not numeric; give it as a choice of options.')
            continue
        lo, hi = v.get('min'), v.get('max')
        if lo is None or hi is None:
            problems.append(f'{name}: the range is missing.')
            continue
        lo, hi = float(lo), float(hi)
        if hi <= lo:
            problems.append(f'{name}: the range {lo}-{hi} is empty.')
            continue

        bound_lo, bound_hi = entry.get('min'), entry.get('max')
        if bound_lo is not None and lo < bound_lo:
            problems.append(f'{name}: {lo} is below the minimum {bound_lo} '
                            'EnergyPlus accepts.')
            continue
        if bound_hi is not None and hi > bound_hi:
            problems.append(f'{name}: {hi} is above the maximum {bound_hi} '
                            'EnergyPlus accepts.')
            continue

        clean.append({**out, 'type': 'range', 'min': lo, 'max': hi})

    # A surrogate needs numbers: each option gets one, 1-based as in the
    # Laboratory (single/double/triple glazing -> 1/2/3).
    for item in clean:
        if item.get('type') == 'category':
            item['encoding'] = {o: i for i, o in enumerate(item['options'], 1)}

    if not variables:
        problems.append('At least one parameter is needed.')
    if not objectives:
        problems.append('At least one objective is needed.')

    return add_positions(idf, clean), problems


def catalogue(idf=None):
    """The variables an interface should offer: live, and about the building.

    discover() reports everything it found, including fields another field has
    switched off and references that move geometry rather than change it. Both
    belong in the full picture and neither belongs in a list of things to vary,
    so this is the filtered view the panel consumes.
    """
    idf = idf or idf_session.get()
    return [e for e in discover(idf) if not e['inert'] and not e.get('topology')]


def options(idf=None):
    """Everything this model can be asked to optimise, in one uniform list.

    Field-level variables and whole-geometry capabilities answer the same
    question -- can this building do it, and if not why -- so they are reported
    the same way rather than as two separate kinds of thing.
    """
    idf = idf or idf_session.get()

    out = []
    for entry in discover(idf):
        out.append({
            'id': '{}.{}'.format(entry['className'], entry['field']),
            'label': '{} - {}'.format(entry['className'], entry['label']),
            'group': 'topology' if entry.get('topology') else 'field',
            'available': not entry['inert'],
            'reason': entry.get('inertReason'),
            'detail': entry,
        })

    for cap in capabilities(idf):
        out.append({
            'id': cap['id'],
            'label': cap['label'],
            'group': 'geometry',
            'available': cap['available'],
            'reason': None if cap['available'] else cap['detail'],
            'detail': cap,
        })

    return out


def apply(idf, design):
    """Write a chosen design point into the model.

    Handles plain field writes only. Anything flagged `viaBesos` in
    capabilities() must be applied with its own BESOS selector inside the
    simulation container, so the saved model matches what was actually
    evaluated -- this refuses it rather than writing something different.

    Returns what each entry changed, so a silent no-match cannot pass for a
    successful optimisation.
    """
    applied = []
    for entry in design:
        class_name = entry['className']
        field = entry['field']
        raw = entry['value']

        objects = idf.idfobjects.get(class_name) or idf.idfobjects.get(class_name.upper())
        if not objects:
            raise ValueError(f'This model has no {class_name}.')

        meta = _field_meta(objects[0], field)
        kind = _varyable(objects[0], field, meta)
        if not kind:
            raise ValueError(f'{class_name}.{field} is not a field that can be varied.')

        # Resolved before the value is checked: what a reference may point at
        # depends on the object it is written to.
        wanted = (entry.get('objectName') or ALL_OBJECTS).strip()
        if wanted == ALL_OBJECTS:
            targets = list(objects)
        else:
            targets = [o for o in objects
                       if (getattr(o, 'Name', '') or '').strip().upper() == wanted.upper()]
        if not targets:
            raise ValueError(f'No {class_name} named {wanted!r} in this model.')

        if kind == 'number':
            value = float(raw)
            lo, hi = _bounds(meta)
            if lo is not None and value < lo:
                raise ValueError(f'{field}: {value} is below the EnergyPlus minimum {lo}.')
            if hi is not None and value > hi:
                raise ValueError(f'{field}: {value} is above the EnergyPlus maximum {hi}.')
        elif kind == 'choice':
            value = str(raw)
            allowed = meta.get('key', [])
            if allowed and value not in allowed:
                raise ValueError(f'{field}: {value!r} is not one of {allowed}.')
        else:
            value = str(raw)
            allowed = _referenceable(idf, meta, targets[0] if targets else None, field)
            if value not in allowed:
                raise ValueError(
                    f'{field}: this model has no object named {value!r} to point at.')

        ignored = [(getattr(o, 'Name', '?'), _inert_reason(o, class_name, field))
                   for o in targets]
        ignored = [(n, r) for n, r in ignored if r]
        if ignored:
            names = ', '.join(n for n, _ in ignored[:3])
            raise ValueError(f'{field} would do nothing on {names}: {ignored[0][1]}')

        for obj in targets:
            setattr(obj, field, value)

        applied.append({'className': class_name, 'field': field,
                        'objectName': wanted, 'value': value,
                        'objectsChanged': len(targets)})

    return applied
