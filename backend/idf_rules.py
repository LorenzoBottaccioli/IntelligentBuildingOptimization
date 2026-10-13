"""When an IDF field actually matters, distilled from the EnergyPlus documentation.

The IDD says what a field *is* -- type, units, bounds, allowed keys. It does not
say when a field is *used*, and that is where a design tool goes wrong quietly:
offering a student a variable that another field has switched off produces an
optimisation that looks flat for no visible reason. Three traps were found the
hard way before this existed:

  * ZoneVentilation:DesignFlowRate keeps a computed Design Flow Rate even when
    its calculation method selects Air Changes per Hour, so "is it filled in"
    proves nothing.
  * Shading Control Status 6 (interior blind) on a window whose control declares
    ExteriorBlind drove EnergyPlus to a fatal convergence error mid-run, and the
    FMU reported success for another 263 timesteps.
  * People's per-area field is People_per_Floor_Area, not the
    People_per_Zone_Floor_Area that Lights' naming suggests. Transcribing by
    analogy left the inert field on offer.

The rules live in rules/*.py, one file per group of documentation sections, and
are merged here. Two properties of that arrangement are worth keeping:

  * Every name was checked against Energy+.idd before being written down. The
    prose and the IDD disagree in 31 recorded places -- the documentation says
    "GlazedDoor" where the key is GlassDoor, and describes capacity-method fields
    on baseboard objects that in 9.6 have moved to companion :Design objects.
    Where they differ, the IDD wins.
  * Where two files cover the same class from different sections they agree: 18
    overlaps, no conflicts. merge_conflicts() re-checks that on every load, so a
    future extraction that contradicts an existing rule surfaces instead of
    silently overwriting it.

SECTIONS_READ is the audit trail. A class absent from these rules has not been
checked, and callers must treat that as "unknown", never as "fine" -- see
is_covered().
"""

import glob
import os

RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')


def norm(field):
    """Documentation spells fields with spaces; eppy uses underscores.

    Parenthetical hints in the docs -- "...for Beam Irradiance (taub)" -- are not
    part of the field name eppy exposes, so they come off.
    """
    text = (field or '').strip().replace(' ', '_').replace('-', '_')
    if '(' in text:
        text = text.split('(', 1)[0]
    return text.strip('_')


def norm_selection(value):
    """A method key may select no field, one field, or several together.

    SizingPeriod:DesignDay's Solar Model Indicator picks the beam *and* diffuse
    schedules at once, and AvailabilityManager's StayOff picks none. Everything
    becomes a tuple so callers do not have to care which.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        return (norm(value),)
    return tuple(norm(v) for v in value if v)


def _load():
    gated, methods, autosized, constraints = {}, {}, set(), {}
    sections, disagreements, conflicts = [], [], []
    sources_g, sources_m = {}, {}

    for path in sorted(glob.glob(os.path.join(RULES_DIR, '*.py'))):
        name = os.path.basename(path)
        namespace = {}
        with open(path, encoding='utf-8') as handle:
            exec(compile(handle.read(), name, 'exec'), namespace)

        for key, rule in (namespace.get('GATED') or {}).items():
            key = (key[0], norm(key[1]))
            rule = dict(rule, by=norm(rule.get('by', '')))
            if key in gated and (gated[key]['by'] != rule['by']
                                 or tuple(gated[key]['when']) != tuple(rule['when'])):
                conflicts.append(('GATED', key, sources_g[key], name))
            gated[key] = rule
            sources_g[key] = name

        for key, table in (namespace.get('METHOD_GROUPS') or {}).items():
            key = (key[0], norm(key[1]))
            table = {k: norm_selection(v) for k, v in table.items()}
            if key in methods and methods[key] != table:
                conflicts.append(('METHOD_GROUPS', key, sources_m[key], name))
            methods[key] = table
            sources_m[key] = name

        for entry in (namespace.get('AUTOSIZABLE') or set()):
            autosized.add((entry[0], norm(entry[1])))

        for cls, lines in (namespace.get('CONSTRAINTS') or {}).items():
            constraints.setdefault(cls, []).extend(lines)

        sections.extend(namespace.get('SECTIONS_READ') or [])
        disagreements.extend(namespace.get('IDD_DISAGREEMENTS') or [])

    return gated, methods, autosized, constraints, sections, disagreements, conflicts


(GATED, METHOD_GROUPS, AUTOSIZABLE, CONSTRAINTS,
 SECTIONS_READ, IDD_DISAGREEMENTS, MERGE_CONFLICTS) = _load()

_COVERED_CLASSES = (
    {c for c, _ in GATED} | {c for c, _ in METHOD_GROUPS}
    | {c for c, _ in AUTOSIZABLE} | set(CONSTRAINTS)
)


def is_covered(class_name):
    """Whether any documentation section covering this class has been read.

    False means unknown, not safe: callers should say so rather than implying the
    field has been checked and found fine.
    """
    return class_name in _COVERED_CLASSES


def gating_for(class_name, field):
    """What switches this field off, if anything is recorded."""
    return GATED.get((class_name, norm(field)))


def method_groups_for(class_name):
    """Calculation-method groups recorded for this class: {method field: {key: field}}."""
    return {method: table for (cls, method), table in METHOD_GROUPS.items()
            if cls == class_name}


def governed_fields(class_name):
    """Every field that some calculation method on this class selects between."""
    out = set()
    for table in method_groups_for(class_name).values():
        for selection in table.values():
            out.update(selection)
    return out


def is_autosizable(class_name, field):
    return (class_name, norm(field)) in AUTOSIZABLE


def constraints_for(class_name):
    return CONSTRAINTS.get(class_name, [])


def why_inert(obj, class_name, field):
    """Why varying this field on this object would change nothing -- or None.

    Three reasons, in the order they bite:
      * the object holds autosize/autocalculate, so EnergyPlus overwrites it;
      * a calculation method on the object selects a different sibling field;
      * another field gates it to values this object does not have.
    """
    field = norm(field)
    value = str(getattr(obj, field, '') or '').strip().lower()

    if value in ('autosize', 'autocalculate') and is_autosizable(class_name, field):
        return 'EnergyPlus sizes this field itself; the entered value is replaced.'

    for method, table in method_groups_for(class_name).items():
        governed = {f for selection in table.values() for f in selection}
        if field in governed:
            # EnergyPlus reads choice keys case-insensitively: "Flow/zone" is Flow/Zone.
            value = str(getattr(obj, method, '') or '').strip().casefold()
            chosen = next((sel for key, sel in table.items() if key.casefold() == value), None)
            if chosen is not None and field not in chosen:
                what = (' and '.join(c.replace('_', ' ') for c in chosen)
                        if chosen else 'no field at all')
                return f'{method.replace("_", " ")} selects {what} instead of this one.'

    rule = gating_for(class_name, field)
    if rule and rule.get('when'):
        current = str(getattr(obj, rule['by'], '') or '').strip()
        if current and current.casefold() not in {w.casefold() for w in rule['when']}:
            return (f'{rule["by"].replace("_", " ")} is {current}; this field applies '
                    f'only when it is {" or ".join(rule["when"])}.')

    return None


def summary():
    return {
        'sections': len(set(SECTIONS_READ)),
        'gated': len(GATED),
        'methodGroups': len(METHOD_GROUPS),
        'autosizable': len(AUTOSIZABLE),
        'constraints': sum(len(v) for v in CONSTRAINTS.values()),
        'iddDisagreements': len(IDD_DISAGREEMENTS),
        'mergeConflicts': len(MERGE_CONFLICTS),
    }
