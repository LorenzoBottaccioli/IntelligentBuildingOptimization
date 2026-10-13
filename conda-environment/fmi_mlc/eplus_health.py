"""Detect an EnergyPlus that died inside the FMU.

When EnergyPlus hits a fatal error mid-co-simulation, the FMU does NOT report it
to the master. `do_step` keeps returning success and the last computed values, so
the loop runs to completion and every observation silently freezes at whatever it
held when the simulation stopped. A student sees "288 steps completed" and a full
set of numbers that mean nothing.

Observed for real: commanding shading Control Status 6 (interior blind) on a
window whose WindowShadingControl declares ExteriorBlind drove the window
temperature solver to -39127 C, EnergyPlus terminated at 01/02 04:20, and the run
reported 263 further steps of frozen data without any error.

Call check_slave() after a run -- or watch_frozen() during one -- so the failure
surfaces instead of becoming plausible-looking output.
"""

import glob
import os

SLAVE_DIR = 'Output_EPExport_Slave'
FATAL_MARKER = 'Terminated--Fatal Error Detected'


class EnergyPlusFailed(RuntimeError):
    """EnergyPlus stopped inside the FMU; observations after that point are stale."""


def slave_error_files(work_dir='.'):
    return sorted(glob.glob(os.path.join(work_dir, SLAVE_DIR, '*.err')))


def check_slave(work_dir='.', raise_on_error=True):
    """Inspect the FMU's EnergyPlus log. Returns a dict describing what it found.

    Never assumes a missing log means success -- it reports that separately, so a
    caller can tell "ran clean" apart from "nothing to inspect".
    """
    files = slave_error_files(work_dir)
    if not files:
        return {'checked': False, 'reason': 'no EnergyPlus log found', 'fatal': False}

    report = {'checked': True, 'fatal': False, 'file': files[0], 'severe': [], 'fatal_line': None}
    with open(files[0], encoding='utf-8', errors='replace') as handle:
        for line in handle:
            if '** Severe' in line:
                report['severe'].append(line.strip())
            if FATAL_MARKER in line:
                report['fatal'] = True
                report['fatal_line'] = line.strip()

    if report['fatal'] and raise_on_error:
        detail = report['severe'][-1] if report['severe'] else report['fatal_line']
        raise EnergyPlusFailed(
            'EnergyPlus terminated inside the FMU, so every observation after that '
            'point is a stale repeat of the last valid timestep.\n'
            f'  log:   {report["file"]}\n'
            f'  cause: {detail}'
        )
    return report


def watch_frozen(series, window=12):
    """True when every tracked series has been constant for `window` steps.

    A cheap in-loop symptom of the same failure: real weather and real zone
    temperatures never hold exactly still, so a flat window means the model has
    stopped advancing.
    """
    if not series:
        return False
    for values in series.values():
        if len(values) < window:
            return False
        if len(set(values[-window:])) > 1:
            return False
    return True


# EnergyPlus WindowShadingControl "Control Status" actuator codes, from the EMS
# Application Guide (Thermal Envelope), EnergyPlus 9.6:
# https://bigladdersoftware.com/epx/docs/9-6/ems-application-guide/thermal-envelope.html
#
# The value that means "deployed" depends on the shading device the window
# actually declares. Commanding a code the window cannot honour is what kills the
# simulation: asking for an interior blind (6) on a window whose control declares
# ExteriorBlind drove the glass temperature to -39127 C and EnergyPlus terminated.
SHADING_NO_DEVICE = -1
SHADING_OFF = 0
SHADING_STATUS = {
    'INTERIORSHADE': 1,
    'SWITCHABLEGLAZING': 2,
    'EXTERIORSHADE': 3,
    'EXTERIORSCREEN': 4,
    'INTERIORBLIND': 6,
    'EXTERIORBLIND': 7,
    'BETWEENGLASSSHADE': 8,
    'BETWEENGLASSBLIND': 9,
}


def deployed_status_for(shading_type):
    """Map a WindowShadingControl Shading Type to the status code that deploys it."""
    key = (shading_type or '').replace(' ', '').replace('_', '').upper()
    if key not in SHADING_STATUS:
        raise ValueError(f'Unknown shading type {shading_type!r}; '
                         f'known: {sorted(SHADING_STATUS)}')
    return SHADING_STATUS[key]
