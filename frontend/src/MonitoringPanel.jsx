// MonitoringPanel.jsx
// What a controller can read from the building and what it can act on.
//
// Four tabs -- meters, sensors (report variables), schedules and actuators -- with ONE interface
// (InstrumentPicker): which type -> which one -> where. Types come from what EnergyPlus declares
// (units, resource tokens, control types), not from words of one building; "where" is a set of
// zones, components or keys, and one zone bar for the page says which zones a row starts with.
// A tick adds nothing by itself: "Add to the FMU" sends the whole selection in one request, and
// "Your FMU" at the right lists what the controller reads and writes, with roles and ranges.
// Sensor keys come from EnergyPlus itself (a one-day probe run lists every key of every
// variable), so a sensor can only be built on a key that exists.
import React, { useContext, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import RoleSwitch from './FmuRole';
import InstrumentPicker from './InstrumentPicker';
import KitBar from './KitBar';
import { AppContext } from './AppContext';
import { api } from './api';
import {
  ACTUATOR_KINDS, QUANTITIES, SCHEDULE_KINDS, actuatorKind, defaultSelection, meterFamily, meterParts, pairKey,
  scheduleKind, sensorRows, shortKey, toIdentifier, zonesOfOption,
} from './instrumentGroups';
import './ModelEditor.css';
import './InstrumentPicker.css';
import './FmuExport.css';

const EMS_KEY = 'EMS';
const APPLY_PREFIX = 'SBEP_Apply_';
const RESOURCE_ORDER = ['Electricity', 'NaturalGas', 'DistrictHeating', 'DistrictCooling', 'EnergyTransfer', 'Water', 'WaterUse'];

// ---- role and range of the FMU variables --------------------------------------
// Kept in the model session (idfObjects.fmu_roles); the export reads them from there.

const filled = (x) => x !== '' && x != null && Number.isFinite(Number(x));
const rangeOk = (o) => filled(o.min) && filled(o.max) && Number(o.min) <= Number(o.max);

/** Badge on an input row: the range, editable in place. */
function RangeBadge({ info, disabled, fallback, onSet }) {
  const [edit, setEdit] = useState(null);
  const has = info && Number.isFinite(info.min) && Number.isFinite(info.max);
  if (edit) {
    const save = () => onSet(Number(edit.min), Number(edit.max)).then(() => setEdit(null)).catch(() => {});
    return (
      <span className="fx-range-edit">
        <input type="number" step="any" value={edit.min} onChange={(e) => setEdit({ ...edit, min: e.target.value })} aria-label="Min" />
        <input type="number" step="any" value={edit.max} onChange={(e) => setEdit({ ...edit, max: e.target.value })} aria-label="Max" />
        <button type="button" title="Save" disabled={disabled || !rangeOk(edit)} onClick={save}>✓</button>
        <button type="button" title="Cancel" onClick={() => setEdit(null)}>↩</button>
      </span>
    );
  }
  const start = () => setEdit({ min: has ? info.min : fallback?.min ?? '', max: has ? info.max : fallback?.max ?? '' });
  if (has) {
    return <button type="button" className="fx-badge" disabled={disabled} title="Click to edit the range" onClick={start}>[{info.min}, {info.max}]</button>;
  }
  if (fallback) {
    return <button type="button" className="fx-badge" disabled={disabled} title="Range of the schedule type limits. Click to set your own." onClick={start}>[{fallback.min}, {fallback.max}]</button>;
  }
  return <button type="button" className="fx-badge fx-badge-warn" disabled={disabled} title="No range yet: the export would use -1000..1000. Click to set it." onClick={start}>no range</button>;
}

// ---- the zone bar -----------------------------------------------------------------

const zoneDetail = (z) => {
  const bits = [];
  if (z.level != null) bits.push(`level ${z.level}`);
  if (z.mainFacing) bits.push(z.mainFacing);
  if (z.floorArea != null) bits.push(`${Math.round(z.floorArea)} m²`);
  return bits.join(' · ');
};

/** The zones every row starts with, once for the page. Chips carry level, orientation and area. */
function ZoneBar({ zones, scope, setScope, geometry }) {
  if (zones.length === 0) return null;
  const all = scope.size === zones.length;
  const levels = [...new Set(zones.filter((z) => z.level != null).map((z) => z.level))].sort((a, b) => a - b);
  const facings = [...new Set(zones.map((z) => z.mainFacing).filter(Boolean))].sort();
  const pick = (test) => setScope(new Set(zones.filter(test).map((z) => z.name)));
  const toggle = (name) => {
    const next = new Set(scope);
    if (next.has(name)) next.delete(name); else next.add(name);
    setScope(next);
  };
  return (
    <section className="ins-card zb" aria-label="Zones">
      <div className="zb-head">
        <span className="zb-title">Zones</span>
        <span className="ip-muted">{scope.size} of {zones.length} · every row starts with these; a row can change them</span>
        <button type="button" className="ip-link" onClick={() => setScope(new Set(zones.map((z) => z.name)))} disabled={all}>all</button>
        <button type="button" className="ip-link" onClick={() => setScope(new Set())} disabled={scope.size === 0}>none</button>
        {levels.length > 1 && levels.map((l) => (
          <button key={`l${l}`} type="button" className="ip-link" onClick={() => pick((z) => z.level === l)}>level {l}</button>
        ))}
        {facings.length > 1 && facings.map((f) => (
          <button key={`f${f}`} type="button" className="ip-link" onClick={() => pick((z) => z.mainFacing === f)}>facing {f}</button>
        ))}
      </div>
      <div className="zb-chips">
        {zones.map((z) => (
          <button key={z.name} type="button" className={`zb-chip${scope.has(z.name) ? ' is-on' : ''}`} aria-pressed={scope.has(z.name)}
            title={zoneDetail(z) || z.name} onClick={() => toggle(z.name)}>
            {z.name}{geometry && zoneDetail(z) && <small>{zoneDetail(z)}</small>}
          </button>
        ))}
      </div>
      {!geometry && <p className="ip-muted">Level, orientation and area appear after the model has been analysed once (upload it again).</p>}
    </section>
  );
}

// ---- the panel -------------------------------------------------------------------

export default function MonitoringPanel() {
  const {
    idfObjects, filesUploaded, modelId, fetchIdfObjects, unmonitorQuantity, removeControlledActuator,
    removeDirectActuator, fetchScheduleCandidates, removeDirectSchedule, removeDirectVariable, setFmuRole,
    scheduleTypeLimits,
  } = useContext(AppContext);
  const [tab, setTab] = useState('sensors');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [cands, setCands] = useState({ schedules: [], thermostats: [] });
  const [zinfo, setZinfo] = useState({ zones: [], owners: {}, geometry: false });
  const [scope, setScope] = useState(new Set());
  const [sensorMode, setSensorMode] = useState('direct');
  const [actuatorMode, setActuatorMode] = useState('direct');
  const [bulk, setBulk] = useState({ min: '', max: '' });
  const [kits, setKits] = useState({ provided: [], saved: [] });
  const [kitBusy, setKitBusy] = useState(false);
  const [kitMessage, setKitMessage] = useState(null);

  // The kits of the platform and those saved in this session.
  useEffect(() => {
    if (!filesUploaded) return;
    axios.get(api('/model_editor/kits')).then(({ data: k }) => setKits(k)).catch(() => {});
  }, [filesUploaded, modelId]);

  // Schedules and thermostats are read from the model again after every change to it.
  useEffect(() => {
    if (!filesUploaded) return undefined;
    let live = true;
    fetchScheduleCandidates()
      .then((c) => live && setCands(c))
      .catch(() => live && setCands({ schedules: [], thermostats: [] }));
    return () => { live = false; };
  }, [idfObjects, filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // The zones with the geometry EnergyPlus resolved, and which zone owns each object: once per model.
  useEffect(() => {
    if (!filesUploaded) return undefined;
    let live = true;
    axios.get(api('/model_editor/zones'))
      .then(({ data }) => {
        if (!live) return;
        setZinfo({ zones: data.zones || [], owners: data.owners || {}, geometry: Boolean(data.geometry) });
        setScope(new Set((data.zones || []).map((z) => z.name)));
      })
      .catch(() => live && setZinfo({ zones: [], owners: {}, geometry: false }));
    return () => { live = false; };
  }, [filesUploaded, modelId]);

  const data = idfObjects || {};
  const roles = data.fmu_roles || {};
  const limitsFor = (name) => {
    const l = (scheduleTypeLimits || {})[name];
    return l && Number.isFinite(l.min) && Number.isFinite(l.max) ? l : null;
  };
  const meters = data.mdd_meters || [];
  const variables = data.rdd_variables || [];
  const available = data.edd_actuators || [];

  // What the platform added, told apart from what the model brought with it.
  const outputs = (data.current_fmu_from_variables || []).filter((v) => v.outputVariableIndexKeyName === EMS_KEY);
  const directReads = (data.current_fmu_from_variables || []).filter((v) => v.outputVariableIndexKeyName !== EMS_KEY);
  const nReads = outputs.length + directReads.length;
  const applyPrograms = new Set((data.current_ems_programs || []).filter((p) => p.name.startsWith(APPLY_PREFIX)).map((p) => p.name));
  const inputs = (data.current_fmu_to_variables || []).filter((v) => applyPrograms.has(`${APPLY_PREFIX}${v.name}`));
  const otherInputs = (data.current_fmu_to_variables || []).filter((v) => !applyPrograms.has(`${APPLY_PREFIX}${v.name}`));
  const directActuators = data.current_fmu_actuators || [];
  const directSchedules = data.current_fmu_schedules || [];
  const nInputs = inputs.length + otherInputs.length + directActuators.length + directSchedules.length;
  const platformActuators = new Set(inputs.map((v) => `${v.name}_act`.toUpperCase()));
  const modelPrograms = (data.current_ems_programs || []).filter((p) => !p.name.startsWith(APPLY_PREFIX) && !/^donothing$/i.test(p.name));
  const modelActuators = (data.current_ems_actuators || []).filter((a) => !platformActuators.has(a.name.toUpperCase()));
  const outputNames = new Set(outputs.map((o) => o.outputVariableName.toUpperCase()));
  const modelSensors = (data.current_ems_sensors || []).filter((s) => !outputNames.has(s.name.toUpperCase()));

  // Which of the model's programs writes each of its actuators.
  const writers = useMemo(() => {
    const out = {};
    modelActuators.forEach((a) => {
      const re = new RegExp(`^SET\\s+${a.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*=`, 'i');
      out[a.name] = modelPrograms.filter((p) => (p.programLines || []).some((l) => re.test(l.trim()))).map((p) => p.name);
    });
    return out;
  }, [modelActuators, modelPrograms]);

  // Components the model's own EMS already drives: making them FMU inputs too
  // would give the component two writers.
  const drivenByModel = useMemo(() => {
    const m = {};
    modelActuators.forEach((a) => {
      m[`${a.actuatedComponentUniqueName}|${a.actuatedComponentType}|${a.actuatedComponentControlType}`.toUpperCase()] = writers[a.name] || [];
    });
    return m;
  }, [modelActuators, writers]);

  // The initial value is what EnergyPlus uses in sizing and warm-up, so it should
  // be what the model itself would do: for a zone setpoint, its thermostat schedule.
  const scheduleByName = useMemo(() => {
    const m = {};
    cands.schedules.forEach((x) => { m[x.name.toUpperCase()] = x; });
    return m;
  }, [cands]);

  const suggestInitial = (type, control, component) => {
    const c = (control || '').toLowerCase();
    if (/^zone temperature control$/i.test(type) && /(heating|cooling) setpoint/.test(c)) {
      const role = c.startsWith('heating') ? 'heating' : 'cooling';
      for (const t of cands.thermostats) {
        if (!(t.zones || []).some((z) => z.toUpperCase() === component.toUpperCase())) continue;
        for (const ctl of t.controls || []) {
          const sched = scheduleByName[String((ctl.schedules || {})[role] || '').toUpperCase()];
          if (sched && sched.suggestedInitial != null) return sched.suggestedInitial;
        }
      }
    }
    return 0;
  };

  // ---- run an action of the table, one request each ----------------------------------

  const run = async (fn) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e?.response?.data?.details || e?.response?.data?.error || e.message);
    } finally {
      setBusy(false);
    }
  };
  const setRole = (fmuVariableName, role) => run(() => setFmuRole({ fmuVariableName, role }));
  const setRange = async (fmuVariableName, min, max) => {
    try {
      setError('');
      await setFmuRole({ fmuVariableName, min, max });
    } catch (e) {
      setError(e?.response?.data?.error || e?.response?.data?.details || e.message);
      throw e;
    }
  };

  // ---- writes in a block ---------------------------------------------------------------

  /** One request for the whole selection; the answer says which items failed and why. */
  const sendBatch = async (ops) => {
    if (ops.length === 0) return { added: 0, failed: 0, failures: [] };
    const { data: res } = await axios.post(api('/model_editor/instrument_batch'), { ops: ops.map(({ itemId, ...op }) => op) });
    await fetchIdfObjects();
    const failures = res.results.filter((r) => !r.ok).map((r) => ({ itemId: ops[r.index].itemId, error: r.error }));
    return { added: res.added, failed: res.failed, failures };
  };

  // ---- places ("where") -------------------------------------------------------------

  const zoneByUpper = useMemo(() => Object.fromEntries(zinfo.zones.map((z) => [z.name.toUpperCase(), z])), [zinfo]);
  const placeOptions = (labels, whatIs = (l) => l) => {
    const shorts = labels.map((l) => shortKey(whatIs(l)) || whatIs(l));
    const dup = new Set(shorts.filter((s, i) => shorts.indexOf(s) !== i));
    return labels.map((label, i) => {
      const z = zoneByUpper[label.toUpperCase()];
      const owner = zonesOfOption(label, zinfo.owners);
      return {
        id: label, label,
        short: dup.has(shorts[i]) ? label : shorts[i],
        detail: z ? zoneDetail(z) : owner.length && owner[0].toUpperCase() !== label.toUpperCase() ? `in ${owner.join(', ')}` : '',
      };
    });
  };

  // ---- the items of each tab ---------------------------------------------------------

  const sensorItems = useMemo(() => sensorRows(variables).map((r) => ({
    id: `s:${r.id}`, title: r.id, kind: r.quantity, whereLabel: 'Measured at',
    variants: r.variants, options: placeOptions(r.keys), freeText: r.keys.length === 0, meta: r.keys.length ? '' : 'keys not known yet',
  })), [variables, zinfo]); // eslint-disable-line react-hooks/exhaustive-deps

  const addedReads = useMemo(
    () => new Set(directReads.map((o) => `${o.outputVariableName}|${o.outputVariableIndexKeyName}`.toUpperCase())),
    [directReads],
  );
  const sensorAdded = (item, key) => item.variants.some((v) => addedReads.has(`${v.id}|${key}`.toUpperCase()));

  const addSensors = async (selection) => {
    const used = new Set();
    const ops = [];
    selection.forEach(({ item, optionIds, variantIds, role }) => {
      variantIds.forEach((variantName) => {
        optionIds.forEach((key) => {
          if (addedReads.has(`${variantName}|${key}`.toUpperCase())) return;
          let name = toIdentifier(`${variantName}_${shortKey(key)}`);
          while (used.has(name.toUpperCase())) name += '_';
          used.add(name.toUpperCase());
          ops.push({ op: 'variable', mode: sensorMode, indexKey: key, variableName: variantName, name, fmuVariableName: name, role, itemId: item.id });
        });
      });
    });
    return sendBatch(ops);
  };

  const meterItems = useMemo(() => {
    const rows = new Map();
    meters.forEach((m) => {
      const p = meterParts(m.meterName);
      let row = rows.get(p.row);
      if (!row) {
        row = { id: `m:${p.row}`, title: p.row, kind: meterFamily(p), whereLabel: 'Scope', meta: m.units ? `[${m.units}]` : '', metas: [] };
        rows.set(p.row, row);
      }
      row.metas.push({ meter: m.meterName, scope: p.scope });
    });
    return [...rows.values()].map((row) => {
      const zoneLabels = row.metas.filter((x) => x.scope.name).map((x) => x.scope.name);
      const opts = row.metas.map((x) => {
        const label = x.scope.name || x.scope.type || 'Facility';
        const z = zoneByUpper[label.toUpperCase()];
        return {
          id: x.meter, label,
          short: x.scope.name ? (zoneLabels.filter((l) => shortKey(l) === shortKey(label)).length > 1 ? label : shortKey(label) || label) : label,
          detail: x.scope.type === 'SpaceType' ? 'space type' : z ? zoneDetail(z) : '',
        };
      });
      const whole = row.metas.find((x) => x.scope.type === 'Facility') || row.metas.find((x) => x.scope.type === 'Building');
      return { ...row, options: opts, defaultOptions: whole ? [whole.meter] : undefined };
    });
  }, [meters, zoneByUpper]);

  const meterKinds = useMemo(() => {
    const present = [...new Set(meterItems.map((i) => i.kind))];
    const rank = (k) => (RESOURCE_ORDER.includes(k) ? RESOURCE_ORDER.indexOf(k) : k === 'Other' ? 99 : k === 'Plant loop demand' ? 90 : k === 'Emissions' ? 80 : 50);
    return present.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b)).map((k) => [k, k]);
  }, [meterItems]);

  const meterFmuName = (item, meterName) => {
    const p = meterParts(meterName);
    return toIdentifier(`${item.title.split(':').slice(-2).join('_')}_${shortKey(p.scope.name) || p.scope.type}`);
  };
  const meterAdded = (item, meterName) => outputNames.has(meterFmuName(item, meterName).toUpperCase());

  const addMeters = async (selection) => {
    const used = new Set();
    const ops = [];
    selection.forEach(({ item, optionIds, role }) => {
      optionIds.forEach((meterName) => {
        if (meterAdded(item, meterName)) return;
        let name = meterFmuName(item, meterName);
        while (used.has(name.toUpperCase())) name += '_';
        used.add(name.toUpperCase());
        ops.push({ op: 'meter', meterName, name, role, itemId: item.id });
      });
    });
    return sendBatch(ops);
  };

  const actuatorItems = useMemo(() => {
    const kinds = new Map();
    available.forEach((a) => {
      const id = `${a.componentType}|${a.controlType}`;
      if (!kinds.has(id)) kinds.set(id, { type: a.componentType, control: a.controlType, units: a.units || '', components: [] });
      kinds.get(id).components.push(a.componentUniqueName);
    });
    return [...kinds.entries()].map(([id, k]) => {
      const nDriven = k.components.filter((c) => drivenByModel[`${c}|${k.type}|${k.control}`.toUpperCase()]).length;
      return {
        id: `a:${id}`, title: k.control, meta: k.type, kind: actuatorKind(k.type, k.control, k.units), whereLabel: 'Component',
        options: placeOptions(k.components), type: k.type, control: k.control, units: k.units,
        tag: nDriven ? `${nDriven} driven by the model` : '', tagTitle: 'Already written by an EMS program of the model',
        note: /control$/i.test(k.type) && /setpoint/i.test(k.control)
          ? 'A setpoint of 0 in the first warm-up step stops zones with dual setpoints. To drive a thermostat, make its setpoint schedule controllable in the Schedules tab: there the initial value is honoured.'
          : '',
      };
    });
  }, [available, zinfo, drivenByModel]); // eslint-disable-line react-hooks/exhaustive-deps

  const addedActuators = useMemo(
    () => new Set(directActuators.map((a) => `${a.actuatedComponentUniqueName}|${a.actuatedComponentType}|${a.actuatedComponentControlType}`.toUpperCase())),
    [directActuators],
  );
  const actuatorAdded = (item, component) => addedActuators.has(`${component}|${item.type}|${item.control}`.toUpperCase());

  /** A proposed range for the chosen components, with where it comes from; one request for all of them. */
  const loadActuatorValues = async (item, components) => {
    if (components.length === 0) return { min: '', max: '', source: '', note: '' };
    const { data: res } = await axios.post(api('/model_editor/actuator_defaults'), {
      items: components.slice(0, 200).map((component) => ({ component, type: item.type, control: item.control, units: item.units })),
    });
    const known = res.ranges.filter((r) => r.min != null || r.max != null);
    if (known.length === 0) return { min: '', max: '', source: 'none', note: '' };
    const lo = Math.min(...known.map((r) => (r.min == null ? Infinity : r.min)));
    const hi = Math.max(...known.map((r) => (r.max == null ? -Infinity : r.max)));
    const distinct = new Set(known.map((r) => `${r.min}|${r.max}`)).size;
    return {
      min: Number.isFinite(lo) ? lo : '', max: Number.isFinite(hi) ? hi : '',
      source: known[0].source, note: distinct > 1 ? 'the widest of the ranges of the chosen components' : known[0].note,
    };
  };

  const addActuators = async (selection) => {
    const used = new Set();
    const ops = [];
    selection.forEach(({ item, optionIds, values }) => {
      optionIds.forEach((component) => {
        if (actuatorAdded(item, component)) return;
        let name = toIdentifier(`${shortKey(component) || component}_${item.control}`);
        while (used.has(name.toUpperCase())) name += '_';
        used.add(name.toUpperCase());
        ops.push({
          op: 'actuator', mode: actuatorMode, name, component, type: item.type, control: item.control,
          initial: filled(values.initial) ? Number(values.initial) : suggestInitial(item.type, item.control, component),
          min: Number(values.min), max: Number(values.max), itemId: item.id,
        });
      });
    });
    return sendBatch(ops);
  };

  const scheduleItems = useMemo(() => cands.schedules.map((sch) => {
    const over = (sch.overrides || []).filter((o) => o.by !== 'FMU');
    return {
      id: `c:${sch.name}`, title: sch.name, meta: `${sch.type} · ${sch.users.length} ${sch.users.length === 1 ? 'use' : 'uses'}`,
      kind: scheduleKind(sch), schedule: sch, disabled: sch.external || !sch.replaceable,
      tag: sch.external ? 'FMU input' : !sch.replaceable ? 'not replaceable' : over.length ? 'overridden by EMS' : '',
      tagTitle: over.map((o) => `${o.by}: ${o.name}`).join(', '),
      warn: over.length ? `An EMS actuator already writes this schedule (${over.map((o) => o.name).join(', ')}): remove it first.` : '',
      note: sch.users.length ? `Used by ${sch.users.slice(0, 4).map((u) => u.object).join(', ')}${sch.users.length > 4 ? ` and ${sch.users.length - 4} more` : ''}.` : '',
    };
  }), [cands]);

  const loadScheduleValues = async (item) => {
    const lim = limitsFor(item.schedule.limits);
    // The type limits of a temperature schedule are often -60..200: of no use as the range of a setpoint.
    if (lim && item.kind === 'setpoints' && /temperature/i.test(item.schedule.limits) && lim.max - lim.min > 60) {
      return {
        initial: item.schedule.suggestedInitial ?? '', min: 10, max: 30, source: 'default',
        note: `the type limits (${lim.min}..${lim.max}) are too wide for a setpoint: a usual range, check it`,
      };
    }
    return {
      initial: item.schedule.suggestedInitial ?? '',
      min: lim ? lim.min : '', max: lim ? lim.max : '', source: lim ? 'model' : 'none',
      note: lim ? `type limits "${item.schedule.limits}"` : '',
    };
  };

  const addSchedules = async (selection) => {
    const ops = selection.map(({ item, values }) => ({
      op: 'schedule', scheduleName: item.schedule.name, fmuVariableName: toIdentifier(`${item.schedule.name}_FMU`),
      initial: filled(values.initial) ? Number(values.initial) : (item.schedule.suggestedInitial ?? Number(values.min)),
      min: Number(values.min), max: Number(values.max), itemId: item.id,
    }));
    return sendBatch(ops);
  };


  // ---- kits ----------------------------------------------------------------------------

  const itemsOf = { sensors: sensorItems, meters: meterItems, actuators: actuatorItems, schedules: scheduleItems };
  const same = (a, b) => String(a).toLowerCase() === String(b).toLowerCase();

  const optionsFor = (item, e) => {
    if (!item.options) return [];
    const ids = item.options.map((o) => o.id);
    if (e.where === 'all') return ids;
    if (e.where === 'default') return item.defaultOptions || defaultSelection(item.options, scope, zinfo.owners);
    if (Array.isArray(e.where)) {
      return item.options.filter((o) => e.where.some((w) => same(w, o.label) || same(w, o.id) || same(shortKey(w), shortKey(o.label)))).map((o) => o.id);
    }
    return defaultSelection(item.options, scope, zinfo.owners);
  };

  /** Resolve a kit on the open model and add what it finds in one request per tab; say what it could not find. */
  const applyKit = async (kit) => {
    setKitBusy(true);
    setKitMessage(null);
    const missing = [];
    const byTab = { sensors: [], meters: [], actuators: [], schedules: [] };
    try {
      for (const e of kit.entries) {
        const item = itemsOf[e.tab].find((i) => same(i.title, e.title) && (!e.type || same(i.type || e.type, e.type)));
        if (!item || item.disabled) { missing.push(`${e.title}${item?.disabled ? ' (not available)' : ''}`); continue; }
        const optionIds = optionsFor(item, e);
        if (item.options && optionIds.length === 0) { missing.push(`${e.title} (nowhere to put it)`); continue; }
        const variantIds = item.variants
          ? (e.variants && e.variants.length ? item.variants.filter((v) => e.variants.includes(v.id)).map((v) => v.id) : [item.variants[0].id])
          : [];
        let values = {};
        if (e.tab === 'actuators' || e.tab === 'schedules') {
          const proposed = e.tab === 'actuators' ? await loadActuatorValues(item, optionIds) : await loadScheduleValues(item);
          values = { ...proposed, ...(e.min != null ? { min: e.min, max: e.max } : {}) };
          if (!rangeOk(values)) { missing.push(`${e.title} (no range: add it by hand)`); continue; }
        }
        byTab[e.tab].push({ item, optionIds, variantIds, values, role: e.role || 'observation' });
      }
      const sent = [
        byTab.sensors.length && addSensors(byTab.sensors),
        byTab.meters.length && addMeters(byTab.meters),
        byTab.actuators.length && addActuators(byTab.actuators),
        byTab.schedules.length && addSchedules(byTab.schedules),
      ].filter(Boolean);
      const results = [];
      for (const s of sent) results.push(await s);   // one after the other: each one saves the model
      const added = results.reduce((n, r) => n + r.added, 0);
      const failed = results.reduce((n, r) => n + r.failed, 0);
      const notes = [...missing.map((m) => `not in this model: ${m}`)];
      if (failed) notes.push(`${failed} could not be added: ${results.flatMap((r) => r.failures).slice(0, 2).map((f) => f.error).join('; ')}`);
      setKitMessage({
        kind: failed ? 'error' : 'ok',
        text: `${kit.name}: ${added} added${notes.length ? `. ${notes.join('. ')}` : ''}.`,
      });
    } catch (e) {
      setKitMessage({ kind: 'error', text: e?.response?.data?.details || e?.response?.data?.error || e.message });
    } finally {
      setKitBusy(false);
    }
  };

  /** What is in the FMU now, written by name so that it can be applied to another model. */
  const kitEntries = () => {
    const entries = [];
    const zoneNames = zinfo.zones.map((z) => z.name.toUpperCase());
    const coversZones = (labels) => zoneNames.length > 0 && labels.length === zoneNames.length
      && zoneNames.every((z) => labels.some((l) => l.toUpperCase() === z));
    const whereOf = (labels) => (coversZones(labels) ? 'scope' : labels);

    const groups = {};
    directReads.forEach((o) => {
      const v = variables.find((x) => x.variableName === o.outputVariableName);
      const role = roles[o.fmuVariableName]?.role || 'observation';
      const g = (groups[`${pairKey(o.outputVariableName, v?.units ?? '')}|${role}`] ||= { title: pairKey(o.outputVariableName, v?.units ?? ''), role, keys: [], variants: [] });
      if (!g.keys.includes(o.outputVariableIndexKeyName)) g.keys.push(o.outputVariableIndexKeyName);
      if (!g.variants.includes(o.outputVariableName)) g.variants.push(o.outputVariableName);
    });
    Object.values(groups).forEach((g) => entries.push({ tab: 'sensors', title: g.title, where: whereOf(g.keys), role: g.role, variants: g.variants }));

    const meterGroups = {};
    outputs.forEach((o) => {
      const sensor = (data.current_ems_sensors || []).find((s) => s.name.toUpperCase() === o.outputVariableName.toUpperCase());
      const source = sensor?.outputVariableOrOutputMeterName;
      if (!source) return;
      const role = roles[o.fmuVariableName]?.role || 'observation';
      if (meters.some((m) => m.meterName === source)) {
        const p = meterParts(source);
        const g = (meterGroups[`${p.row}|${role}`] ||= { title: p.row, role, scopes: [] });
        g.scopes.push(p.scope.name || p.scope.type);
      } else {
        entries.push({ tab: 'sensors', title: pairKey(source, variables.find((x) => x.variableName === source)?.units ?? ''), where: [sensor.outputVariableOrOutputMeterIndexKeyName], role });
      }
    });
    Object.values(meterGroups).forEach((g) => entries.push({
      tab: 'meters', title: g.title, role: g.role,
      where: g.scopes.length === 1 && /^(Facility|Building)$/.test(g.scopes[0]) ? 'default' : whereOf(g.scopes),
    }));

    const acts = {};
    directActuators.forEach((a) => {
      const k = `${a.actuatedComponentType}|${a.actuatedComponentControlType}`;
      const g = (acts[k] ||= { type: a.actuatedComponentType, title: a.actuatedComponentControlType, comps: [], range: roles[a.fmuVariableName] });
      g.comps.push(a.actuatedComponentUniqueName);
    });
    Object.values(acts).forEach((g) => {
      const e = { tab: 'actuators', title: g.title, type: g.type, where: whereOf(g.comps) };
      if (g.range && Number.isFinite(g.range.min) && Number.isFinite(g.range.max)) { e.min = g.range.min; e.max = g.range.max; }
      entries.push(e);
    });
    directSchedules.forEach((s) => {
      const r = roles[s.fmuVariableName];
      const e = { tab: 'schedules', title: s.scheduleName, where: 'default' };
      if (r && Number.isFinite(r.min) && Number.isFinite(r.max)) { e.min = r.min; e.max = r.max; }
      entries.push(e);
    });
    return entries;
  };

  const saveKit = async (name) => {
    setKitBusy(true);
    setKitMessage(null);
    try {
      const { data: res } = await axios.post(api('/model_editor/kits'), { name, entries: kitEntries() });
      setKits((k) => ({ ...k, saved: res.saved }));
      setKitMessage({ kind: 'ok', text: `Kit "${name}" saved in this session.` });
      return true;
    } catch (e) {
      setKitMessage({ kind: 'error', text: e?.response?.data?.error || e.message });
      return false;
    } finally {
      setKitBusy(false);
    }
  };

  const deleteKit = async (name) => {
    setKitBusy(true);
    try {
      const { data: res } = await axios.delete(api('/model_editor/kits'), { data: { name } });
      setKits((k) => ({ ...k, saved: res.saved }));
    } catch (e) {
      setKitMessage({ kind: 'error', text: e?.response?.data?.error || e.message });
    } finally {
      setKitBusy(false);
    }
  };

  if (!filesUploaded) return <p className="me-empty">Upload an IDF and an EPW file to start.</p>;

  const TABS = [
    ['sensors', 'Sensors', variables.length, 'Report variables: what the building measures.'],
    ['meters', 'Meters', meters.length, 'What the building consumes and produces, counted by meter: electricity, gas, heating, cooling.'],
    ['schedules', 'Schedules', cands.schedules.length, 'Schedules the controller can write, replacing their fixed profile.'],
    ['actuators', 'Actuators', available.length ? new Set(available.map((a) => `${a.componentType}|${a.controlType}`)).size : 0, 'What a controller can act on.'],
  ];

  const writeRows = [
    ...directSchedules.map((v) => ({
      key: `s:${v.fmuVariableName}`, name: v.fmuVariableName, what: `schedule ${v.scheduleName}`,
      fallback: limitsFor(v.scheduleTypeLimitsNames), remove: () => removeDirectSchedule(v.scheduleName), title: 'Remove and restore the schedule',
    })),
    ...directActuators.map((v) => ({
      key: `a:${v.fmuVariableName}`, name: v.fmuVariableName, what: `${v.actuatedComponentControlType} of ${v.actuatedComponentUniqueName}`,
      remove: () => removeDirectActuator(v.name), title: 'Remove',
    })),
    ...inputs.map((v) => ({
      key: `i:${v.name}`, name: v.fmuVariableName, what: 'via an EMS program', remove: () => removeControlledActuator(v.name), title: 'Remove',
    })),
    ...otherInputs.map((v) => ({
      key: `o:${v.fmuVariableName}`, name: v.fmuVariableName, what: 'declared in EMS programs (removed there)', remove: null, title: '',
    })),
  ];

  const setAllRanges = () => run(async () => {
    const lo = Number(bulk.min);
    const hi = Number(bulk.max);
    for (const r of writeRows) await setFmuRole({ fmuVariableName: r.name, min: lo, max: hi });
  });

  const pickerProps = {
    sensors: {
      items: sensorItems, kinds: QUANTITIES, onAdd: addSensors, needsRole: true, added: sensorAdded,
      placeholder: 'Search variables or keys: Mean Air Temperature, a zone, a window…', emptyText: 'This model reports no variables yet.',
    },
    meters: {
      items: meterItems, kinds: meterKinds, onAdd: addMeters, needsRole: true, added: meterAdded,
      placeholder: 'Search meters: Electricity, Heating, a zone name…', emptyText: 'This model has no meters yet.',
    },
    schedules: {
      items: scheduleItems, kinds: SCHEDULE_KINDS, onAdd: addSchedules, valuesMode: 'range', hasInitial: true,
      loadValues: loadScheduleValues, placeholder: 'Search schedules or the objects that use them: a setpoint, a zone, lights…',
      emptyText: 'This model has no schedules.',
    },
    actuators: {
      items: actuatorItems, kinds: ACTUATOR_KINDS, onAdd: addActuators, valuesMode: 'range', hasInitial: true,
      loadValues: loadActuatorValues, added: actuatorAdded, placeholder: 'Search actuators or components: Setpoint, Shading, a zone…',
      emptyText: 'This model offers no actuators.',
    },
  }[tab];

  return (
    <div className="me ins">
      {error && <div className="me-error">{error}</div>}

      <ZoneBar zones={zinfo.zones} scope={scope} setScope={setScope} geometry={zinfo.geometry} />

      <KitBar kits={kits} busy={kitBusy} message={kitMessage} canSave={nReads + nInputs > 0} onApply={applyKit} onSave={saveKit} onDelete={deleteKit} />

      <div className="ins-cols">
        <section className="ins-card">
          <nav className="me-tabs" role="tablist">
            {TABS.map(([id, label, n, hint]) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'me-tab me-tab-on' : 'me-tab'}
                title={hint} onClick={() => setTab(id)}>
                {label} <span className="me-count">{n}</span>
              </button>
            ))}
          </nav>
          <p className="me-muted me-tab-hint">{TABS.find((t) => t[0] === tab)[3]}</p>
          {tab === 'sensors' && (
            <>
              <label className="ip-muted">Mode{' '}
                <select value={sensorMode} onChange={(e) => setSensorMode(e.target.value)}>
                  <option value="direct">Direct: the FMU reads the variable, no EMS object</option>
                  <option value="ems">Via EMS: a sensor and an output variable relay it</option>
                </select>
              </label>
              {!data.variableKeysKnown && variables.length > 0 && (
                <p className="me-warn">The keys of the variables are not known yet: upload the model again to list where each can be measured.</p>
              )}
            </>
          )}
          {tab === 'actuators' && (
            <label className="ip-muted">Mode{' '}
              <select value={actuatorMode} onChange={(e) => setActuatorMode(e.target.value)}>
                <option value="direct">Direct: the FMU writes the actuator, no EMS program</option>
                <option value="program">Via program: an EMS program applies the FMU value</option>
              </select>
            </label>
          )}
          <InstrumentPicker key={tab} scope={scope} owners={zinfo.owners} {...pickerProps} />
        </section>

        <aside className="ins-side">
          <section className="ins-card">
            <h3>Your FMU <span className="me-count">{nReads} read · {nInputs} written</span></h3>
            {nReads + nInputs === 0 ? (
              <p className="me-muted">Nothing yet: tick sensors, meters, schedules or actuators and add them.</p>
            ) : (
              <div className="ft-scroll">
                {nReads > 0 && <h4 className="ft-section">The controller reads {nReads}</h4>}
                <ul className="ft">
                  {directReads.map((o) => (
                    <li key={`d:${o.fmuVariableName}`} className="ft-row">
                      <div className="ft-main"><code>{o.fmuVariableName}</code><span className="ft-what">{o.outputVariableName} at {o.outputVariableIndexKeyName}</span></div>
                      <RoleSwitch compact value={roles[o.fmuVariableName]?.role} disabled={busy} onChange={(r) => setRole(o.fmuVariableName, r)} />
                      <button type="button" title="Remove" disabled={busy} onClick={() => run(() => removeDirectVariable(o.fmuVariableName))}>×</button>
                    </li>
                  ))}
                  {outputs.map((o) => (
                    <li key={o.fmuVariableName} className="ft-row">
                      <div className="ft-main"><code>{o.fmuVariableName}</code><span className="ft-what">via EMS</span></div>
                      <RoleSwitch compact value={roles[o.fmuVariableName]?.role} disabled={busy} onChange={(r) => setRole(o.fmuVariableName, r)} />
                      <button type="button" title="Remove" disabled={busy} onClick={() => run(() => unmonitorQuantity(o.outputVariableName))}>×</button>
                    </li>
                  ))}
                </ul>
                {nInputs > 0 && <h4 className="ft-section">The controller writes {nInputs}</h4>}
                <ul className="ft">
                  {writeRows.map((r) => (
                    <li key={r.key} className="ft-row">
                      <div className="ft-main"><code>{r.name}</code><span className="ft-what">{r.what}</span></div>
                      <RangeBadge info={roles[r.name]} disabled={busy} fallback={r.fallback} onSet={(lo, hi) => setRange(r.name, lo, hi)} />
                      {r.remove ? <button type="button" title={r.title} disabled={busy} onClick={() => run(r.remove)}>×</button> : <span />}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {nInputs > 1 && (
              <div className="ip-values" style={{ marginTop: 'var(--space-3)' }}>
                <span className="ip-muted">Same range for every input</span>
                <label>Min <input type="number" step="any" value={bulk.min} onChange={(e) => setBulk({ ...bulk, min: e.target.value })} /></label>
                <label>Max <input type="number" step="any" value={bulk.max} onChange={(e) => setBulk({ ...bulk, max: e.target.value })} /></label>
                <button type="button" disabled={busy || !rangeOk(bulk)} onClick={setAllRanges}>Apply</button>
              </div>
            )}
            <p className="me-muted me-ems-note">
              {outputs.length > 0 || inputs.length > 0
                ? 'The platform added an EMS program and calling manager to the model.'
                : 'The platform added no EMS objects to the model.'}
              {' '}Export it from the <Link to="/control_room">Control room</Link>.
            </p>
          </section>

          <section className="ins-card">
            <h3>Already controlled by the model <span className="me-count">{modelActuators.length}</span></h3>
            <p className="me-muted">
              The model&apos;s own EMS: {modelPrograms.length} {modelPrograms.length === 1 ? 'program' : 'programs'}, {modelSensors.length} sensors, {modelActuators.length} actuators.
            </p>
            {modelActuators.length > 0 && (
              <details className="me-details">
                <summary>What the EMS drives</summary>
                <ul className="me-plain">
                  {modelActuators.map((a) => (
                    <li key={a.name}>
                      <b>{a.actuatedComponentControlType}</b> of <code>{a.actuatedComponentUniqueName}</code>
                      <span className="me-muted"> · {(writers[a.name] || []).length ? `by ${writers[a.name].join(', ')}` : 'declared, written by no program'}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
