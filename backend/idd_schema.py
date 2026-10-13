"""The EnergyPlus IDD as data: groups, classes, fields and their reference graph.

The Model editor draws every form from this module, so nothing about a class is
transcribed by hand: the IDD declares the type, the keys, the units, the bounds,
the defaults, the reference lists and the help text of every field, and this is
the only place that reads it. Parsed once per IDD file (about a second), cached.

Why an own parser and not eppy's `idd_info`: eppy keeps the markers as raw
strings, keeps only the first `\\object-list` of a field, and its reference
index misses classes. Field order here is the order of appearance in the IDD,
which is also the position in an eppy object (`obj.obj[i]`, with the class at 0).
"""

import os
import re
import threading

_FIELD = re.compile(r'^\s*([AN])(\d+)\s*([,;])\s*(.*)$')
_MARKER = re.compile(r'^\s*\\([A-Za-z\-]+)(:\d+)?([<>]?)\s*(.*)$')


class FieldSpec(object):
    __slots__ = ('index', 'letter', 'name', 'type', 'keys', 'object_lists', 'external_list',
                 'references', 'units', 'ip_units', 'units_based_on', 'minimum', 'minimum_excl',
                 'maximum', 'maximum_excl', 'default', 'autosizable', 'autocalculatable',
                 'required', 'notes', 'begin_extensible', 'retaincase')

    def __init__(self, index, letter):
        self.index = index
        self.letter = letter
        self.name = ''
        self.type = 'alpha' if letter == 'A' else 'real'
        self.keys = []
        self.object_lists = []
        self.external_list = None
        self.references = []
        self.units = None
        self.ip_units = None
        self.units_based_on = None
        self.minimum = None
        self.minimum_excl = False
        self.maximum = None
        self.maximum_excl = False
        self.default = None
        self.autosizable = False
        self.autocalculatable = False
        self.required = False
        self.notes = []
        self.begin_extensible = False
        self.retaincase = False

    def to_json(self):
        out = {'index': self.index, 'name': self.name, 'type': self.type, 'numeric': self.letter == 'N'}
        if self.keys:
            out['keys'] = self.keys
        if self.object_lists:
            out['objectLists'] = self.object_lists
        if self.external_list:
            out['externalList'] = self.external_list
        if self.references:
            out['references'] = self.references
        for attr, label in (('units', 'units'), ('ip_units', 'ipUnits'), ('default', 'default')):
            if getattr(self, attr) is not None:
                out[label] = getattr(self, attr)
        if self.minimum is not None:
            out['minimum'] = self.minimum
            out['minimumExclusive'] = self.minimum_excl
        if self.maximum is not None:
            out['maximum'] = self.maximum
            out['maximumExclusive'] = self.maximum_excl
        for attr in ('autosizable', 'autocalculatable', 'required', 'begin_extensible'):
            if getattr(self, attr):
                out[attr[0] + attr.title().replace('_', '')[1:]] = True
        if self.notes:
            out['notes'] = self.notes
        return out


class ClassSpec(object):
    def __init__(self, name, group):
        self.name = name
        self.group = group
        self.memo = []
        self.unique = False
        self.required = False
        self.min_fields = 0
        self.extensible = 0
        self.fields = []

    @property
    def upper(self):
        return self.name.upper()

    def field_for_index(self, i):
        """FieldSpec for 0-based position i, following the extensible template past the end."""
        n = len(self.fields)
        if i < n:
            return self.fields[i]
        if self.extensible and n >= self.extensible:
            return self.fields[n - self.extensible + ((i - n) % self.extensible)]
        return None

    def to_json(self, upto=None, default_extensible_rows=3):
        total = len(self.fields)
        shown = total
        if self.extensible and total > 100:
            lead = total
            for f in self.fields:
                if f.begin_extensible:
                    lead = f.index
                    break
            shown = min(total, lead + self.extensible * default_extensible_rows)
        if upto is not None:
            shown = min(total, max(shown, upto))
        return {
            'name': self.name, 'group': self.group, 'memo': self.memo, 'unique': self.unique,
            'required': self.required, 'minFields': self.min_fields, 'extensible': self.extensible,
            'fieldCount': total, 'fields': [f.to_json() for f in self.fields[:shown]],
        }


class Schema(object):
    def __init__(self, path):
        self.path = path
        self.version = ''
        self.build = ''
        self.groups = []                # [(group, [ClassSpec])] in IDD order
        self.classes = {}               # UPPER name -> ClassSpec
        self.providers = {}             # reference group -> [(class UPPER, 0-based field index)]
        self.class_name_groups = {}     # \reference-class-name group -> [class UPPER]
        self._parse(path)
        self._index()

    def _parse(self, path):
        group = ''
        cls = None
        field = None
        by_group = {}
        with open(path, encoding='latin-1') as handle:
            for raw in handle:
                line = raw.rstrip('\r\n')
                if not line.strip():
                    continue
                if line.lstrip().startswith('!'):
                    if line.startswith('!IDD_Version'):
                        self.version = line.split(None, 1)[1].strip() if ' ' in line else ''
                    elif line.startswith('!IDD_BUILD'):
                        self.build = line.split(None, 1)[1].strip() if ' ' in line else ''
                    continue
                if line[0] == '\\':
                    m = _MARKER.match(line)
                    if m and m.group(1) == 'group':
                        group = m.group(4).strip()
                        continue
                if line[0] not in ' \t\\':
                    # A class line: "Name," (or "Name;" for a class without fields).
                    name = line.split('!')[0].strip().rstrip(',;').strip()
                    cls = ClassSpec(name, group)
                    field = None
                    self.classes[cls.upper] = cls
                    by_group.setdefault(group, []).append(cls)
                    continue
                if cls is None:
                    continue
                m = _FIELD.match(line)
                if m:
                    field = FieldSpec(len(cls.fields), m.group(1))
                    cls.fields.append(field)
                    rest = m.group(4)
                    if rest.startswith('\\'):
                        self._marker(cls, field, rest)
                    continue
                self._marker(cls, field, line)
        for g in by_group:
            self.groups.append((g, by_group[g]))

    @staticmethod
    def _marker(cls, field, line):
        m = _MARKER.match(line)
        if not m:
            return
        name, num, cmp_, text = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        if field is None:
            if name == 'memo':
                cls.memo.append(text)
            elif name == 'unique-object':
                cls.unique = True
            elif name == 'required-object':
                cls.required = True
            elif name == 'min-fields':
                cls.min_fields = int(text.split()[0])
            elif name == 'extensible':
                cls.extensible = int(num[1:]) if num else 0
            return
        if name == 'field':
            field.name = text
        elif name == 'type':
            field.type = text.lower()
        elif name == 'key':
            field.keys.append(text)
        elif name == 'object-list':
            field.object_lists.append(text)
        elif name == 'external-list':
            field.external_list = text
        elif name == 'reference':
            field.references.append(text)
        elif name == 'units':
            field.units = text
        elif name == 'ip-units':
            field.ip_units = text
        elif name == 'unitsBasedOnField':
            field.units_based_on = text
        elif name in ('minimum', 'maximum'):
            try:
                value = float(text)
            except ValueError:
                return
            setattr(field, name, value)
            setattr(field, name + '_excl', cmp_ in ('<', '>'))
        elif name == 'default':
            field.default = text
        elif name == 'autosizable':
            field.autosizable = True
        elif name == 'autocalculatable':
            field.autocalculatable = True
        elif name == 'required-field':
            field.required = True
        elif name == 'note':
            field.notes.append(text)
        elif name == 'begin-extensible':
            field.begin_extensible = True
        elif name == 'retaincase':
            field.retaincase = True

    def _index(self):
        for cls in self.classes.values():
            for f in cls.fields:
                for ref in f.references:
                    self.providers.setdefault(ref, []).append((cls.upper, f.index))

    def get(self, name):
        return self.classes.get(str(name).upper())


_cache = {}
_lock = threading.Lock()


def load(path):
    """The Schema of the IDD at `path`, parsed once per file version."""
    stamp = (path, os.path.getmtime(path))
    with _lock:
        entry = _cache.get(path)
        if entry is None or entry[0] != stamp:
            entry = (stamp, Schema(path))
            _cache[path] = entry
        return entry[1]
