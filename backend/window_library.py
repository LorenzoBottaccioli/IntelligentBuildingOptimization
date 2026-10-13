"""The window constructions EnergyPlus ships, to be brought into a model.

A model usually defines one or two glazed build-ups, so "which window should
this building have" has nothing to choose from. A window is changed by swapping
its construction -- not by retuning a pane -- so new window types come in as
whole constructions, with their layers, from EnergyPlus' own library:

    datasets/WindowConstructs.idf       207 constructions (single to quadruple)
    datasets/WindowGlassMaterials.idf   the panes they are made of
    datasets/WindowGasMaterials.idf     the gas fills between them

Copied verbatim from EnergyPlus 9.6's DataSets folder, which the nrel/energyplus
image does not carry. Importing adds objects to the model and changes none: the
imported constructions become options of the window variable, and the windows
keep their construction until a design point says otherwise.
"""

import os
from io import StringIO

from eppy.modeleditor import IDF

import idf_session

DATASETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datasets')
_FILES = ('WindowConstructs.idf', 'WindowGlassMaterials.idf', 'WindowGasMaterials.idf')

# What a layer of a window construction can be, in the library files.
_LAYER_CLASSES = ('WINDOWMATERIAL:GLAZING', 'WINDOWMATERIAL:GAS',
                  'WINDOWMATERIAL:GASMIXTURE')

_library = None


def _load():
    """Parse the three files once, as one IDF against the loaded IDD."""
    global _library
    if _library is None:
        idf_session.get()  # makes sure the IDD is set
        text = ''.join(open(os.path.join(DATASETS, f), encoding='latin-1').read()
                       for f in _FILES)
        _library = IDF(StringIO(text))
    return _library


def _layers(construction):
    return [getattr(construction, f) for f in construction.fieldnames
            if (f == 'Outside_Layer' or f.startswith('Layer_'))
            and getattr(construction, f)]


def _find(idf, name):
    for cls in _LAYER_CLASSES:
        obj = idf.getobject(cls, name)
        if obj is not None:
            return obj
    return None


def catalogue():
    """Every library construction, described by what it is made of.

    The number of panes is counted from the layers rather than read off the
    name, and the gas from the gas layers -- the names are EnergyPlus'
    abbreviations and not every one follows the same pattern.
    """
    lib = _load()
    out = []
    for c in lib.idfobjects['CONSTRUCTION']:
        layers = _layers(c)
        objects = [_find(lib, l) for l in layers]
        if any(o is None for o in objects):
            continue  # a construction whose layers the library does not define
        panes = sum(1 for o in objects if o.key.upper() == 'WINDOWMATERIAL:GLAZING')
        gases = sorted({(getattr(o, 'Gas_Type', '') or 'Mix') for o in objects
                        if o.key.upper() != 'WINDOWMATERIAL:GLAZING'})
        out.append({'name': c.Name, 'panes': panes, 'gases': gases, 'layers': layers})
    return out


def import_into(idf, names):
    """Copy the named constructions, and any layer the model lacks, into idf.

    A layer already present under the same name is left as the model has it:
    the model's definition wins over the library's.
    """
    lib = _load()
    added = []
    for name in names:
        if idf.getobject('CONSTRUCTION', name) is not None:
            continue
        construction = lib.getobject('CONSTRUCTION', name)
        if construction is None:
            raise ValueError(f'{name!r} is not in the EnergyPlus library.')
        for layer in _layers(construction):
            if _find(idf, layer) is None:
                idf.copyidfobject(_find(lib, layer))
        idf.copyidfobject(construction)
        added.append(name)
    return added
