"""Check an uploaded IDF against the EnergyPlus the platform actually runs.

An IDF written for an older EnergyPlus is not rejected by eppy: it is parsed
against whatever IDD is loaded, and every field after one that a later version
added is read one position off. Nothing raises, so the model looks fine and is
quietly wrong.

This is not hypothetical. The exercise models on the course machine declare
version 9.4, while the platform ships EnergyPlus 9.6. Version 9.6 added a
"Space Name" field to BuildingSurface:Detailed, so on those files eppy reads the
outside-boundary object where the boundary condition should be: every surface
came back with no boundary condition of 'Outdoors', the window-to-wall ratio was
reported unavailable "because the model has no exterior walls", and that was an
artefact of the shift rather than anything about the buildings.

EnergyPlus ships IDFVersionUpdater for exactly this. Until the platform runs it,
the least it can do is say so instead of proceeding on a misread model.
"""

import os
import re

IDD_PATH = os.environ.get('IDD_PATH', '/app/EnergyPlus-9-6-0/Energy+.idd')

_IDD_VERSION = re.compile(r'!IDD_Version\s+([0-9.]+)')
_IDF_VERSION = re.compile(r'^\s*Version\s*,\s*([0-9.]+)\s*;', re.M | re.I)


def _major_minor(raw):
    """'9.4.0.001' and '9.4' both reduce to (9, 4): EnergyPlus breaks input
    compatibility on minor releases, not on patch numbers."""
    parts = [p for p in (raw or '').split('.') if p.isdigit()]
    if len(parts) < 2:
        return None
    return int(parts[0]), int(parts[1])


def idd_version(idd_path=None):
    path = idd_path or IDD_PATH
    try:
        with open(path, encoding='latin-1') as handle:
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                found = _IDD_VERSION.search(line)
                if found:
                    return found.group(1)
    except OSError:
        pass
    return None


def idf_version(idf_path):
    """The version the file declares, or None when it declares none."""
    try:
        with open(idf_path, encoding='latin-1') as handle:
            head = handle.read(200000)
    except OSError:
        return None
    found = _IDF_VERSION.search(head)
    return found.group(1) if found else None


def check(idf_path, idd_path=None):
    """Compare the file's version with the IDD the platform parses against.

    Returns a dict the interface can show. `ok` False means the model must not be
    trusted as parsed -- not that it is unusable, but that it needs converting
    first.
    """
    declared = idf_version(idf_path)
    expected = idd_version(idd_path)

    result = {'declared': declared, 'expected': expected, 'ok': True, 'message': None}

    if expected is None:
        result['message'] = ('Could not read the EnergyPlus version of the platform’s '
                             'IDD; the model was parsed without that check.')
        return result

    if declared is None:
        result['ok'] = False
        result['message'] = (
            'This IDF declares no Version object, so there is no way to tell which '
            f'EnergyPlus it was written for. The platform parses against {expected}.')
        return result

    a, b = _major_minor(declared), _major_minor(expected)
    if a is None or b is None or a == b:
        return result

    older = a < b
    result['ok'] = False
    result['message'] = (
        f'This model is written for EnergyPlus {declared}, and the platform runs '
        f'{expected}. Fields that {expected} added are missing from the file, so '
        'everything after them is read one position out — surfaces in particular '
        'come back with the wrong boundary conditions. '
        + ('Convert it with IDFVersionUpdater, which ships with EnergyPlus, before '
           'using it here.' if older else
           'It was written for a newer EnergyPlus than this platform runs.'))
    return result
