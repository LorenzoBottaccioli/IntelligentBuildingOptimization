// Parameter selection and problem definition -- and deliberately nothing more.
//
// This page is the "Define the problem" step of the course lab: the student
// chooses which parameters vary, where each one acts and how much it varies,
// and picks the objectives. Sampling, the surrogate and the optimisation are
// their own code, in the notebook; this page saves the problem (problem.json)
// and shows the notebook cell that defines the same problem in code, to copy.
//
// The cell is written by the backend for one library, BESOS or bdopt, and the
// design space says which (`engine`). What the page tells the student about the
// cell follows it; everything else on the page is the same for both.
//
// Left, what this model lets you vary, by design decision: envelope (by
// building element), control (thermostat schedules, box by box), occupancy and
// loads, ventilation, HVAC. Right, the chosen parameters: each one is one
// column of the samples, however many objects it writes.

import { Fragment, useState, useEffect, useContext, useMemo, useRef } from 'react';
import './DesignProblem.css';
import { AppContext } from './AppContext';
import { api } from './api';

const round = (v) =>
  v === null || v === undefined || v === ''
    ? '—'
    : Math.abs(v) < 0.01 && v !== 0
    ? Number(v).toExponential(2)
    : String(Math.round(v * 1000) / 1000);

// Two significant digits: a suggested bound of 3.4375 reads as 3.4.
const nice = (v) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return null;
  const x = Number(v);
  if (x === 0) return 0;
  const e = 10 ** (Math.floor(Math.log10(Math.abs(x))) - 1);
  return Number((Math.round(x / e) * e).toPrecision(6));
};

// The library the notebook cell is written for. The design space carries it
// ("besos" or "bdopt"); a backend that does not say is the BESOS one.
const engineOf = (space) => (space?.engine === 'bdopt' ? 'bdopt' : 'besos');

// The few sentences whose truth depends on the library.
const WORDS = {
  besos: {
    sameName: 'another parameter has the same name: in the notebook they would be one column',
    course: 'The Laboratory uses about seven parameters and 10–40 Latin hypercube samples.',
  },
  bdopt: {
    // bdopt's Problem refuses two parameters with the same name.
    sameName: 'another parameter has the same name: every column of the samples needs its own name',
    course: 'The course lab uses about seven parameters and 10–40 Latin hypercube samples.',
  },
};

// Windows and doors are not thickened, they are chosen.
const CHOICE_ELEMENTS = new Set(['window', 'skylight', 'door']);
const WINDOW_ELEMENTS = new Set(['window', 'skylight']);
// The envelope a design decides on: what separates inside from outside.
const ENVELOPE_SHOWN = ['external_wall', 'roof', 'window', 'skylight'];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY_TYPES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
  'Holiday', 'SummerDesignDay', 'WinterDesignDay', 'CustomDay1', 'CustomDay2'];
const DAY_SHORT = { Sunday: 'Sun', Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed', Thursday: 'Thu',
  Friday: 'Fri', Saturday: 'Sat', Holiday: 'holidays', SummerDesignDay: 'summer design day',
  WinterDesignDay: 'winter design day', CustomDay1: 'custom day 1', CustomDay2: 'custom day 2' };
const ROLE = { heating: 'Heating', cooling: 'Cooling', 'heating or cooling': 'Heating or cooling' };
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const dayLabel = ([m, d]) => `${d} ${MONTHS[m - 1]}`;

function daysLabel(days) {
  const set = new Set(days);
  if (DAY_TYPES.every((d) => set.has(d))) return 'every day';
  const parts = [];
  const week = DAY_TYPES.slice(0, 7);
  const wk = week.slice(1, 6);
  if (week.every((d) => set.has(d))) {
    parts.push('Mon–Sun');
    week.forEach((d) => set.delete(d));
  } else if (wk.every((d) => set.has(d))) {
    parts.push('Mon–Fri');
    wk.forEach((d) => set.delete(d));
  }
  DAY_TYPES.forEach((d) => set.has(d) && parts.push(DAY_SHORT[d]));
  return parts.join(', ');
}

// The key is fixed when a parameter is chosen, so editing where it acts does
// not turn it into a different parameter.
const baseKey = (v) =>
  v.kind === 'construction'
    ? `construction:${v.element}`
    : v.kind === 'layer'
    ? `layer:${v.element}:${v.layer}:${v.field}`
    : v.kind === 'schedule_value' || v.kind === 'schedule_time'
    ? `${v.kind}:${v.box}`
    : `field:${v.className}.${v.field}`;

// problem.json (schemaVersion 2) carries, on every variable and every target,
// `fieldIndex` and `iddField`: where the field sits in the IDF object and its
// exact IDD name. The backend derives both from the model it has loaded, so a
// restored parameter is sent back without them, as a freshly chosen one is. A
// version 1 file has neither and is read the same way.
const withoutDerived = (t) => {
  if (!t || typeof t !== 'object' || Array.isArray(t)) return t;
  const { fieldIndex, iddField, ...rest } = t; // eslint-disable-line no-unused-vars
  return rest;
};

// problem.json is written for the notebook; reading it back puts the panel's
// own handles on again, as far as the saved file says.
function restoreVariable(v, elements) {
  const source = v.source ?? {};
  const back = { ...v, ...source, kind: source.kind ?? 'field' };
  if (back.kind === 'construction') {
    const element = elements.find((e) => e.id === source.element);
    back.choices = element?.alternatives ?? v.options;
    back.use = element?.alternativeUse ?? {};
    back.objects = (v.targets ?? []).map((t) => t.object ?? t);
    back.windows = (element?.members ?? []).filter((w) => back.objects.includes(w.name));
    back.surfaces = back.objects.length;
    if (source.perWindow) back.name = source.baseName ?? v.name;
  } else if (back.kind === 'layer') {
    back.objects = v.targets;
  } else if (back.kind === 'field') {
    back.all = (v.targets ?? []).includes('*');
    back.picked = back.all ? [] : v.targets;
  } else if (back.kind === 'schedule_value' || back.kind === 'schedule_time') {
    // The zones are restored as saved; the table is re-read from the model.
    back.members = (v.targets ?? []).map(withoutDerived).map((t) => ({ zones: [t.object], targets: [t] }));
    back.picked = back.members.map((m) => m.zones.join(', '));
    back.box = `restored:${v.name}`;
    if (back.kind === 'schedule_time') {
      back.chosen = (v.options ?? []).map((o) => o.replace(/^Until:\s*/i, ''));
    }
  }
  back.key = baseKey(back);
  return back;
}

// What a chosen parameter sends to the backend: the targets resolved from the
// zones or objects the student picked.
function payload(v) {
  const common = { name: v.name, label: v.label, kind: v.kind };
  if (v.kind === 'schedule_value' || v.kind === 'schedule_time') {
    const members = v.members.filter((m) => v.picked.includes(m.zones.join(', ')));
    const base = { ...common, targets: members.flatMap((m) => m.targets ?? [m.target]), role: v.role, when: v.when,
      zones: members.flatMap((m) => m.zones), current: v.current, unit: v.unit };
    if (v.kind === 'schedule_value') return { ...base, type: 'range', min: v.min, max: v.max };
    return { ...base, type: 'category', options: timeOptions(v).map(hhmm),
      minMinute: v.minMinute, maxMinute: v.maxMinute };
  }
  if (v.kind === 'field') {
    return { ...common, type: v.type, className: v.className, field: v.field, group: v.group,
      objects: v.all ? [] : v.picked, min: v.min, max: v.max, options: v.options };
  }
  const one = { ...common, type: v.type, className: v.className, field: v.field, element: v.element,
    elementLabel: v.elementLabel, layer: v.layer, objects: v.objects, min: v.min, max: v.max,
    options: v.options };
  // Windows one by one: a parameter, and so a column, per window.
  if (v.kind === 'construction' && v.perWindow && (v.objects ?? []).length > 1) {
    return v.objects.map((w) => ({ ...one, name: `${v.name} ${w}`, objects: [w], perWindow: true, baseName: v.name }));
  }
  return one;
}

function timeOptions(v) {
  const out = new Set([v.currentMinute]);
  for (let t = Number(v.from); t <= Number(v.to); t += Number(v.step) || 30) out.add(t);
  return [...out].filter((t) => t >= v.minMinute && t <= v.maxMinute).sort((a, b) => a - b);
}

function cardProblems(v, all, engine = 'besos') {
  const out = [];
  if (!String(v.name ?? '').trim()) out.push('the name is missing');
  if (all.filter((x) => x.name.trim() === String(v.name).trim()).length > 1) {
    out.push(WORDS[engine].sameName);
  }
  if (v.kind === 'field' && !v.all && !(v.picked ?? []).length) out.push('pick at least one object');
  if ((v.kind === 'schedule_value' || v.kind === 'schedule_time') && !(v.picked ?? []).length) {
    out.push('pick at least one zone');
  }
  if (v.type === 'range') {
    const lo = Number(v.min);
    const hi = Number(v.max);
    if (v.min === null || v.max === null || Number.isNaN(lo) || Number.isNaN(hi)) out.push('give both bounds');
    else {
      if (hi <= lo) out.push('"from" must be lower than "to"');
      if (v.bound?.min != null && lo < v.bound.min) out.push(`EnergyPlus accepts nothing below ${round(v.bound.min)}`);
      if (v.bound?.max != null && hi > v.bound.max) out.push(`EnergyPlus accepts nothing above ${round(v.bound.max)}`);
    }
  } else if (v.kind === 'schedule_time') {
    if (timeOptions(v).length < 2) out.push('at least two times are needed');
  } else if ((v.options ?? []).length < 2) out.push('at least two options are needed');
  return out;
}

export default function DesignProblem() {
  const { filesUploaded, modelId } = useContext(AppContext);

  const [envelope, setEnvelope] = useState([]);
  const [structure, setStructure] = useState([]);
  const [sections, setSections] = useState([]);
  const [tstats, setTstats] = useState({ thermostats: [], schedules: [] });
  const [objectives, setObjectives] = useState([]);
  const [model, setModel] = useState(null);
  const [engine, setEngine] = useState('besos');
  const [chosen, setChosen] = useState({});
  const [wanted, setWanted] = useState(new Set());
  const [openElement, setOpenElement] = useState(null);
  const [openGroup, setOpenGroup] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [query, setQuery] = useState('');
  const [familiarOnly, setFamiliarOnly] = useState(true);
  const [allObjectives, setAllObjectives] = useState(false);
  const [objectiveQuery, setObjectiveQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [problems, setProblems] = useState([]);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState({ cell: '', problems: [], columns: 0 });

  useEffect(() => {
    // A new model, or none: nothing chosen on the previous one survives. Its
    // objects (materials, windows, constructions) need not exist in this one.
    setChosen({});
    setWanted(new Set());
    setEnvelope([]);
    setStructure([]);
    setSections([]);
    setTstats({ thermostats: [], schedules: [] });
    setObjectives([]);
    setModel(null);
    setStatus(null);
    setProblems([]);
    setPreview({ cell: '', problems: [], columns: 0 });
    setOpenElement(null);
    setOpenGroup(null);
    setQuery('');
    if (!filesUploaded) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      fetch(api('/surrogate_modeling/envelope')).then((r) => r.json()),
      fetch(api('/surrogate_modeling/design_space')).then((r) => r.json()),
      fetch(api('/surrogate_modeling/problem')).then((r) => r.json()),
    ])
      .then(([env, space, saved]) => {
        setEnvelope(env.elements ?? []);
        setStructure(withoutThermostats(space.structure ?? []));
        setSections(space.sections ?? []);
        setTstats(space.thermostatSchedules ?? { thermostats: [], schedules: [] });
        setObjectives(space.objectives ?? []);
        setModel(space.model ?? null);
        setEngine(engineOf(space));
        if (saved?.defined) {
          const restored = {};
          (saved.variables ?? []).forEach((v) => {
            const back = restoreVariable(v, env.elements ?? []);
            const before = restored[back.key];
            // Windows saved one by one come back as one parameter again.
            if (before && back.perWindow) {
              before.objects = [...before.objects, ...back.objects];
              before.windows = [...before.windows, ...back.windows];
              before.surfaces = before.objects.length;
            } else restored[back.key] = back;
          });
          setChosen(restored);
          setWanted(new Set((saved.objectives ?? []).map((o) => o.name)));
        } else {
          const preferred = (space.objectives ?? []).filter((o) => o.preferred);
          setWanted(new Set(preferred.slice(0, 1).map((o) => o.name)));
        }
      })
      .catch(() => setStatus({ kind: 'error', text: 'The backend cannot be reached.' }))
      .finally(() => setLoading(false));
  }, [filesUploaded, modelId]);

  const picked = Object.values(chosen);

  // The notebook cell is written by the backend from the validated problem, so
  // what is shown is exactly what problem.json will hold.
  const timer = useRef(null);
  useEffect(() => {
    if (!filesUploaded || loading) return undefined;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const ready = picked.filter((v) => !cardProblems(v, picked, engine).length);
      if (!ready.length) {
        setPreview({ cell: '', problems: [], columns: 0 });
        return;
      }
      fetch(api('/surrogate_modeling/problem_preview'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          variables: ready.flatMap(payload),
          objectives: [...wanted].map((name) => ({ name, direction: 'minimize' })),
        }),
      })
        .then((r) => r.json())
        .then((p) => setPreview({ cell: p.cell ?? '', problems: p.problems ?? [], columns: p.columns ?? 0 }))
        .catch(() => {});
    }, 450);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosen, wanted, loading, filesUploaded]);

  const add = (variable) => {
    const key = baseKey(variable);
    setStatus(null);
    setProblems([]);
    setChosen((current) => {
      const next = { ...current };
      if (next[key]) delete next[key];
      else next[key] = { ...variable, key };
      return next;
    });
  };
  const setVariable = (variable) => {
    const key = baseKey(variable);
    setChosen((current) => ({ ...current, [key]: { ...current[key], ...variable, key } }));
  };
  const removeVariable = (key) =>
    setChosen((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  const update = (key, patch) =>
    setChosen((current) => ({ ...current, [key]: { ...current[key], ...patch } }));

  const onLibraryImport = (added) =>
    fetch(api('/surrogate_modeling/envelope'))
      .then((r) => r.json())
      .then((env) => {
        const elements = env.elements ?? [];
        setEnvelope(elements);
        setChosen((current) => {
          const next = { ...current };
          Object.entries(next).forEach(([key, v]) => {
            if (v.kind !== 'construction' || !WINDOW_ELEMENTS.has(v.element)) return;
            const el = elements.find((e) => e.id === v.element);
            next[key] = {
              ...v,
              choices: el?.alternatives ?? v.choices,
              use: el?.alternativeUse ?? v.use,
              options: [...new Set([...(v.options ?? []), ...added])],
            };
          });
          return next;
        });
      });

  const matches = (text) => !query || String(text).toLowerCase().includes(query.toLowerCase());

  const save = () => {
    if (saving) return;
    setStatus(null);
    setProblems([]);
    const bad = picked.find((v) => cardProblems(v, picked, engine).length);
    if (!picked.length) {
      setStatus({ kind: 'error', text: 'Choose at least one parameter.' });
      return;
    }
    if (bad) {
      setStatus({ kind: 'error', text: `${bad.name}: ${cardProblems(bad, picked, engine)[0]}.` });
      return;
    }
    setSaving(true);
    fetch(api('/surrogate_modeling/problem'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        variables: picked.flatMap(payload),
        objectives: [...wanted].map((name) => ({ name, direction: 'minimize' })),
      }),
    })
      .then(async (r) => ({ ok: r.ok, body: await r.json() }))
      .then(({ ok, body }) => {
        if (ok) {
          setStatus({
            kind: 'ok',
            text: `Saved to ${body.path}: ${body.problem.variables.length} parameters, ${body.problem.objectives.length} objectives.`,
          });
        } else {
          setStatus({ kind: 'error', text: body.error ?? 'The problem was refused.' });
          setProblems(body.problems ?? []);
        }
      })
      .catch(() => setStatus({ kind: 'error', text: 'Saving failed.' }))
      .finally(() => setSaving(false));
  };

  const mainObjectives = useMemo(
    () => objectives.filter((o) => o.preferred || wanted.has(o.name)),
    [objectives, wanted]
  );
  const otherObjectives = useMemo(
    () => objectives.filter((o) => !o.preferred && !wanted.has(o.name)),
    [objectives, wanted]
  );
  const shownObjectives = useMemo(() => {
    if (!allObjectives) return mainObjectives;
    const filtered = objectiveQuery
      ? otherObjectives.filter((o) => o.name.toLowerCase().includes(objectiveQuery.toLowerCase()))
      : otherObjectives;
    return [...mainObjectives, ...filtered.slice(0, 60)];
  }, [allObjectives, mainObjectives, otherObjectives, objectiveQuery]);

  if (!filesUploaded) return <p className="dp-empty">Upload an IDF and an EPW file to start.</p>;
  if (loading) return <p className="dp-empty">Reading the model…</p>;
  if (status?.kind === 'error' && !envelope.length && !structure.length) {
    return <p className="dp-error">{status.text}</p>;
  }

  // ---- the catalogue ------------------------------------------------------

  const elementMatches = (el) =>
    matches(el.label) ||
    el.constructions.some((b) => matches(b.construction) || b.layers.some((l) => matches(l.name)));
  const groupMatches = (g) =>
    matches(g.name) || g.classes.some((c) => matches(c.className) || c.fields.some((f) => matches(f.label)));

  const renderElement = (el) => {
    const open = openElement === el.id || Boolean(query);
    const inside = picked.filter((v) => v.element === el.id).length;
    const isChoice = CHOICE_ELEMENTS.has(el.id);
    return (
      <li key={el.id} className="dp-card">
        <button type="button" className="dp-row-head" onClick={() => setOpenElement(open ? null : el.id)}>
          <span className="dp-title">{el.label}</span>
          <span className="dp-meta">
            {inside > 0 && <b className="dp-picked">{inside} chosen · </b>}
            {el.surfaces} surfaces ·{' '}
            {isChoice ? `${el.constructions.length} in use` : `${el.constructions.length} build-ups`}
          </span>
        </button>
        {open && (
          <div className="dp-body">
            {WINDOW_ELEMENTS.has(el.id) ? (
              <GlazingChoice element={el} chosen={chosen} setVariable={setVariable} removeVariable={removeVariable}
                shadingVariable={shadingVariable} onToggle={add} />
            ) : isChoice ? (
              <ChoiceRow element={el} chosen={chosen} onToggle={add} />
            ) : (
              <>
                {el.constructions.map((build) => (
                  <Build key={build.construction} element={el} build={build} chosen={chosen} onToggle={add}
                    expanded={expanded} setExpanded={setExpanded} matches={matches} />
                ))}
                <ChoiceRow element={el} chosen={chosen} onToggle={add} />
              </>
            )}
          </div>
        )}
      </li>
    );
  };

  const fieldVariable = (group, f) => {
    const numeric = f.kind === 'number';
    const spelled = (value) => (f.choices ?? []).find((c) => c.toLowerCase() === String(value).toLowerCase());
    const inUse = [...new Set((f.objects ?? []).map((o) => spelled(o.value) ?? o.value))].filter(Boolean);
    return {
      kind: 'field',
      type: numeric ? 'range' : 'category',
      group: group.name,
      className: f.className,
      field: f.field,
      label: `${f.className} · ${f.label}`,
      name: `${f.className} ${f.label}`,
      unit: f.unit,
      min: numeric ? nice(f.suggestedMin) : null,
      max: numeric ? nice(f.suggestedMax) : null,
      bound: numeric ? { min: f.min, max: f.max } : null,
      current: valuesSummary(f.objects ?? [], f.unit),
      objectList: (f.objects ?? []).map((o) => o.name),
      all: true,
      picked: [],
      choices: numeric ? undefined : [...new Set([...inUse, ...(f.choices ?? [])])],
      options: numeric ? undefined : inUse,
    };
  };

  // A WindowShadingControl setpoint as the group browser would make it, narrowed
  // to the given controls ('*' when they are all of them).
  const shadingVariable = (fieldLabel, controls, unit, values) => {
    for (const group of structure) {
      for (const cls of group.classes) {
        if (cls.className !== 'WindowShadingControl') continue;
        const f = cls.fields.find((x) => x.label === fieldLabel);
        if (!f) return null;
        const v = fieldVariable(group, f);
        const names = controls.map((c) => c.name);
        const all = names.length === (f.objects ?? []).length;
        return { ...v, unit: unit ?? v.unit, all, picked: all ? [] : names,
          label: `Shading control · ${fieldLabel}`,
          current: values ? `${values.join(', ')}${unit ? ` ${unit}` : ''}` : v.current };
      }
    }
    return null;
  };

  const renderGroup = (group) => {
    const open = openGroup === group.name || Boolean(query);
    const inside = picked.filter((v) => v.group === group.name).length;
    return (
      <li key={group.name} className="dp-card">
        <button type="button" className="dp-row-head" onClick={() => setOpenGroup(open ? null : group.name)}>
          <span className="dp-title">{group.display ?? group.name}</span>
          <span className="dp-meta">
            {inside > 0 && <b className="dp-picked">{inside} chosen · </b>}
            {group.classes.length} classes · {group.objectCount} objects
          </span>
        </button>
        {open && (
          <div className="dp-body">
            {group.classes.map((cls) => {
              const found = cls.fields.filter((f) => matches(f.label) || matches(cls.className));
              // "Common fields only" puts the common ones first; it never empties
              // a class -- one with no common field shows all of them -- and the
              // rest stay one click away.
              const moreKey = `${group.name}:${cls.className}`;
              const common = found.filter((f) => f.familiar);
              const fields = !familiarOnly || query || expanded[moreKey] || !common.length ? found : common;
              const hidden = found.length - fields.length;
              if (!found.length) return null;
              return (
                <div key={cls.className} className="dp-class">
                  <code className="dp-class-name">{cls.className}</code>
                  <span className="dp-muted"> · {cls.objectCount} objects</span>
                  {fields.map((f) => {
                    const variable = fieldVariable(group, f);
                    const key = baseKey(variable);
                    return (
                      <label key={key} className="dp-field">
                        <input type="checkbox" checked={Boolean(chosen[key])} onChange={() => add(variable)} />
                        <span className="dp-field-name">
                          {f.label}
                          {f.unit && <span className="dp-muted"> [{f.unit}]</span>}
                          {f.familiar && <span className="dp-tag">common</span>}
                        </span>
                        <span className="dp-field-range" dangerouslySetInnerHTML={{ __html: variable.current }} />
                      </label>
                    );
                  })}
                  {hidden > 0 && (
                    <button type="button" className="dp-more" onClick={() => setExpanded({ ...expanded, [moreKey]: true })}>
                      {hidden} more fields of {cls.className}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </li>
    );
  };

  const groupsOf = (sectionId) => structure.filter((g) => g.section === sectionId && groupMatches(g));

  const renderSection = (section) => {
    if (section.id === 'envelope') {
      const els = ENVELOPE_SHOWN.map((id) => envelope.find((el) => el.id === id)).filter(
        (el) => el && elementMatches(el)
      );
      if (!els.length) return null;
      return (
        <>
          <ul className="dp-list">{els.map(renderElement)}</ul>
          {envelope.some((el) => WINDOW_ELEMENTS.has(el.id)) && <WindowLibrary onImported={onLibraryImport} />}
        </>
      );
    }
    const groups = groupsOf(section.id);
    const tables =
      section.id === 'control' ? <ScheduleTables data={tstats} chosen={chosen} onToggle={add} /> : null;
    if (!groups.length && !tables) return null;
    return (
      <>
        {tables}
        {groups.length > 0 && <ul className="dp-list">{groups.map(renderGroup)}</ul>}
      </>
    );
  };

  const searchOnly = structure.filter((g) => !g.section && groupMatches(g));
  // Windows chosen one by one are a column each.
  const columns = picked.reduce((n, v) => n + (v.kind === 'construction' && v.perWindow ? (v.objects ?? []).length || 1 : 1), 0);

  return (
    <div className="dp dp-wide">
      <header className="dp-head">
        <div className="dp-model">
          <span className="dp-model-name">{model?.name ?? 'model'}</span>
          <span className="dp-muted">{model?.zones} zones</span>
        </div>
        {model?.version &&
          (model.version.ok ? (
            <span className="dp-ok-inline">version {model.version.declared}, matches the simulator</span>
          ) : (
            <span className="dp-error">{model.version.message}</span>
          ))}
      </header>
      <ol className="dp-steps">
        <li>1 · Choose the parameters this model offers</li>
        <li>2 · Decide where each acts and how much it varies</li>
        <li>3 · Pick the objectives and save: the notebook cell is ready</li>
      </ol>

      <div className="dp-grid" key={modelId}>
        <div className="dp-catalogue">
          <input type="search" className="dp-search" placeholder="search the whole model — insulation, setpoint, ventilation…"
            value={query} onChange={(e) => setQuery(e.target.value)} />
          <label className="dp-inline dp-familiar">
            <input type="checkbox" checked={familiarOnly} onChange={(e) => setFamiliarOnly(e.target.checked)} />
            common fields only
          </label>

          {sections.map((section) => {
            const body = renderSection(section);
            if (!body) return null;
            return (
              <section key={section.id}>
                <h3>{section.label}</h3>
                <p className="dp-muted">{section.description}</p>
                {body}
              </section>
            );
          })}

          {query && searchOnly.length > 0 && (
            <section>
              <h3>Other EnergyPlus groups</h3>
              <p className="dp-muted">Found by the search: not a design decision, but still reachable.</p>
              <ul className="dp-list">{searchOnly.map(renderGroup)}</ul>
            </section>
          )}
        </div>

        <aside className="dp-chosen">
          <div className="dp-row-head dp-static">
            <span className="dp-title">Your parameters</span>
            <span className="dp-meta"><b className="dp-count">{columns}</b> {columns === 1 ? 'column' : 'columns'}</span>
          </div>
          <p className="dp-muted">
            Each parameter is one column of the sampling, even when it writes many objects. {WORDS[engine].course}
          </p>
          {columns === 0 ? (
            <p className="dp-muted">Tick a parameter on the left.</p>
          ) : (
            picked.map((v) => (
              <ParamCard key={v.key} v={v} all={picked} engine={engine} update={(patch) => update(v.key, patch)}
                remove={() => removeVariable(v.key)} />
            ))
          )}

          <p className="dp-muted dp-objectives-label">Objectives to minimise</p>
          <div className="dp-objectives">
            {shownObjectives.map((o) => (
              <label key={o.name} className={wanted.has(o.name) ? 'dp-obj dp-obj-on' : 'dp-obj'}>
                <input type="checkbox" checked={wanted.has(o.name)}
                  onChange={() => setWanted((current) => {
                    const next = new Set(current);
                    if (next.has(o.name)) next.delete(o.name);
                    else next.add(o.name);
                    return next;
                  })} />
                {o.name}
              </label>
            ))}
          </div>
          {otherObjectives.length > 0 && (
            <div className="dp-objectives-more">
              {allObjectives ? (
                <input type="search" className="dp-objective-search" placeholder={`filter ${otherObjectives.length} other meters…`}
                  value={objectiveQuery} onChange={(e) => setObjectiveQuery(e.target.value)} />
              ) : (
                <button type="button" className="dp-more" onClick={() => setAllObjectives(true)}>
                  {otherObjectives.length} more meters by zone and end use
                </button>
              )}
            </div>
          )}

          <div className="dp-actions">
            <button type="button" className="dp-save" onClick={save} aria-busy={saving}>
              {saving ? 'Checking the problem…' : 'Save problem'}
            </button>
            {status && <span className={status.kind === 'ok' ? 'dp-ok' : 'dp-error'}>{status.text}</span>}
          </div>
          {problems.length > 0 && (
            <ul className="dp-problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}
        </aside>
      </div>

      <NotebookCell preview={preview} engine={engine} scheduledOutputs={model?.scheduledOutputs ?? 0} />
    </div>
  );
}

function valuesSummary(objs, unit) {
  const count = {};
  objs.forEach((o) => {
    const k = typeof o.value === 'number' ? round(o.value) : String(o.value ?? '');
    count[k] = (count[k] || 0) + 1;
  });
  const e = Object.entries(count).sort((a, b) => b[1] - a[1]);
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  return (
    e.slice(0, 2).map(([v, n]) => `${esc(v)}${unit ? ` ${esc(unit)}` : ''}${objs.length > 1 ? ` (${n})` : ''}`).join(', ') +
    (e.length > 2 ? ` +${e.length - 2}` : '')
  );
}

// ---- one chosen parameter: name, what, where, how much ---------------------

function ParamCard({ v, all, engine, update, remove }) {
  const errors = cardProblems(v, all, engine);
  const isSchedule = v.kind === 'schedule_value' || v.kind === 'schedule_time';
  let where;
  if (v.kind === 'construction' && v.windows) {
    const facings = [...new Set(v.windows.map(facingWord).filter(Boolean))];
    where = (
      <span>
        {v.windows.length} window{v.windows.length > 1 ? 's' : ''}
        {facings.length > 0 && ` facing ${facings.join(', ')}`}
        {v.windows.length > 1 && (v.perWindow ? ', one by one' : ', together')}
        <span className="dp-muted"> · change it under Windows, on the left</span>
      </span>
    );
  } else if (v.kind === 'construction') where = <span>all {v.surfaces ?? ''} surfaces of the {String(v.elementLabel).toLowerCase()}</span>;
  else if (v.kind === 'layer') where = <code>{v.layer}</code>;
  else {
    const list = isSchedule ? v.members.map((m) => m.zones.join(', ')) : v.objectList ?? [];
    const allOn = isSchedule ? v.picked.length === list.length : v.all;
    where = list.length <= 1 ? (
      <code>{list[0] ?? '*'}</code>
    ) : (
      <>
        <div className="dp-where">
          <label><input type="radio" checked={allOn}
            onChange={() => update(isSchedule ? { picked: list } : { all: true, picked: [] })} />
            {isSchedule ? ` all ${list.length} zones` : ` all ${list.length} objects (object_name='*')`}</label>
          <label><input type="radio" checked={!allOn}
            onChange={() => update(isSchedule ? { picked: v.picked.length === list.length ? [] : v.picked } : { all: false, picked: v.picked?.length ? v.picked : list })} />
            {isSchedule ? ' only some zones' : ' only some objects'}</label>
        </div>
        {!allOn && (
          <div className="dp-objlist">
            {list.map((o) => (
              <label key={o}>
                <input type="checkbox" checked={(v.picked ?? []).includes(o)}
                  onChange={(e) => update({ picked: e.target.checked ? [...new Set([...(v.picked ?? []), o])] : v.picked.filter((x) => x !== o) })} />
                {' '}{(v.memberLabels && v.memberLabels[o]) || o}
              </label>
            ))}
          </div>
        )}
      </>
    );
  }

  let how;
  if (v.type === 'range') {
    how = (
      <div className="dp-range">
        <span className="dp-muted">from</span>
        <input type="number" step="any" value={v.min ?? ''} onChange={(e) => update({ min: e.target.value === '' ? null : Number(e.target.value) })} />
        <span className="dp-muted">to</span>
        <input type="number" step="any" value={v.max ?? ''} onChange={(e) => update({ max: e.target.value === '' ? null : Number(e.target.value) })} />
        {v.unit && <span className="dp-muted">{v.unit}</span>}
      </div>
    );
  } else if (v.kind === 'schedule_time') {
    const opts = timeOptions(v);
    how = (
      <>
        <div className="dp-range">
          <span className="dp-muted">times from</span>
          <input type="text" value={hhmm(v.from)} onChange={(e) => {
            const m = parseTime(e.target.value); if (m !== null) update({ from: m });
          }} />
          <span className="dp-muted">to</span>
          <input type="text" value={hhmm(v.to)} onChange={(e) => {
            const m = parseTime(e.target.value); if (m !== null) update({ to: m });
          }} />
          <span className="dp-muted">every</span>
          <input type="number" min="5" step="5" value={v.step} onChange={(e) => update({ step: Number(e.target.value) || 30 })} />
          <span className="dp-muted">min</span>
        </div>
        <div className="dp-muted">
          {opts.length} options: {opts.map(hhmm).join(', ')} · only between {hhmm(v.minMinute)} and {hhmm(v.maxMinute)}, so the slots stay in order
        </div>
      </>
    );
  } else {
    how = <Options variable={v} onToggle={(o) => update({ options: (v.options ?? []).includes(o) ? v.options.filter((x) => x !== o) : [...(v.options ?? []), o] })} />;
  }

  return (
    <div className="dp-pcard">
      <div className="dp-prow">
        <span className="dp-plabel">Name</span>
        <input className="dp-pname" type="text" value={v.name} onChange={(e) => update({ name: e.target.value })} />
        <button type="button" className="dp-x" onClick={remove} title="Remove">✕</button>
      </div>
      <div className="dp-prow"><span className="dp-plabel">What</span><span>{v.label}</span></div>
      <div className="dp-prow dp-top"><span className="dp-plabel">Where</span><div>{where}</div></div>
      <div className="dp-prow dp-top">
        <span className="dp-plabel">How much</span>
        <div>
          {how}
          {v.current && <div className="dp-muted">in the model: <span dangerouslySetInnerHTML={{ __html: v.current }} /></div>}
          {v.note && <div className="dp-muted">{v.note}</div>}
          {v.alsoIn?.length > 0 && (
            <div className="dp-warn">This material is also in: {v.alsoIn.join(', ')}. Varying it by name changes those too.</div>
          )}
        </div>
      </div>
      {errors.map((e) => <div key={e} className="dp-error">✕ {e}</div>)}
    </div>
  );
}

function parseTime(t) {
  const m = String(t).trim().match(/^(\d{1,2})(?::(\d{2}))?$/);
  if (!m) return null;
  const v = Number(m[1]) * 60 + Number(m[2] || 0);
  return v > 0 && v <= 1440 ? v : null;
}

// ---- thermostat schedules, box by box ---------------------------------------

// Zones whose schedules have the same structure (periods, day types, slot
// times) share one table, so "the same box in every zone" is one choice. The
// schedules come from schedule_model, so any schedule kind is read.
function ScheduleTables({ data, chosen, onToggle }) {
  const byName = useMemo(() => {
    const m = {};
    (data.schedules ?? []).forEach((s) => { m[s.name.toUpperCase()] = s; });
    return m;
  }, [data]);
  const groups = useMemo(() => {
    const out = {};
    (data.thermostats ?? []).forEach((t) =>
      t.controls.forEach((c) =>
        Object.entries(c.schedules).forEach(([role, name]) => {
          const s = byName[String(name).toUpperCase()];
          if (!s || !s.periods || !s.periods.length || s.problems?.length) return;
          const sig = JSON.stringify(s.periods.map((p) => [p.start, p.end, p.groups.map((g) => [[...g.days].sort(), g.slots.map((x) => x[0])])]));
          // A schedule an EMS program always overwrites is never in the same table as one it does not.
          const full = (s.overrides ?? []).some((o) => o.active && !o.releases);
          const k = `${role}|${sig}|${full}`;
          if (!out[k]) out[k] = { role, members: [] };
          if (!out[k].members.some((m) => m.sched.name === s.name && m.zones.join() === t.zones.join())) {
            out[k].members.push({ sched: s, zones: t.zones });
          }
        })
      )
    );
    return Object.values(out);
  }, [data, byName]);

  if (!(data.thermostats ?? []).length) {
    return <p className="dp-muted">This model has no ZoneControl:Thermostat.</p>;
  }

  return (
    <div className="dp-list">
      <p className="dp-muted">
        Thermostat temperatures, read from the setpoint schedules. Zones with the same schedule structure share a
        table; the number in brackets is how many zones hold that value. Slots at −50 / 100 °C mean the system is
        off and are not offered.
      </p>
      {groups.map((g, gi) => {
        const s0 = g.members[0].sched;
        const zones = g.members.flatMap((m) => m.zones);
        const overridden = g.members.flatMap((m) => m.sched.overrides ?? []);
        const full = overridden.find((o) => o.active && !o.releases);
        return (
          <div key={gi} className="dp-card dp-sched">
            <div className="dp-row-head dp-static">
              <span className="dp-title">{ROLE[g.role] ?? g.role}</span>
              <span className="dp-meta">{zones.length} {zones.length === 1 ? 'zone' : 'zones'}: {zones.slice(0, 4).join(', ')}{zones.length > 4 ? '…' : ''}</span>
            </div>
            {full && (
              <p className="dp-warn">
                The EMS actuator {full.name} overwrites this schedule at every timestep
                {full.programs?.length ? ` (program ${full.programs.join(', ')})` : ''}: the numbers below are not what
                EnergyPlus uses, so they cannot be design parameters.
              </p>
            )}
            {!full && overridden.some((o) => o.active) && (
              <p className="dp-muted">An EMS program overwrites this schedule at some times and releases it at others.</p>
            )}
            <table className="dp-table dp-sched-table">
              <thead><tr><th>Period</th><th>Days</th><th>Slot</th><th>Value</th><th /></tr></thead>
              <tbody>
                {s0.periods.map((p, pi) =>
                  p.groups.map((gr, gri) =>
                    gr.slots.map((sl, si) => {
                      const values = g.members.map((m) => m.sched.periods[pi].groups[gri].slots[si][1]);
                      const off = values.every((x) => x <= -40 || x >= 60);
                      const count = {};
                      values.forEach((x) => { count[x] = (count[x] || 0) + 1; });
                      const box = `${gi}|${pi}|${gri}|${si}`;
                      const from = si ? gr.slots[si - 1][0] : 0;
                      const when = `${dayLabel(p.start)}–${dayLabel(p.end)}, ${daysLabel(gr.days)}`;
                      const members = g.members.map((m) => ({
                        zones: m.zones,
                        value: m.sched.periods[pi].groups[gri].slots[si][1],
                        src: m.sched.periods[pi].groups[gri].src?.[si],
                        prev: si ? m.sched.periods[pi].groups[gri].slots[si - 1][0] : 0,
                        next: m.sched.periods[pi].groups[gri].slots[si + 1]?.[0],
                      }));
                      const top = Number(Object.entries(count).sort((a, b) => b[1] - a[1])[0][0]);
                      const valueVar = {
                        kind: 'schedule_value', type: 'range', box, role: g.role, when,
                        name: `${ROLE[g.role] ?? g.role} setpoint ${when}, ${hhmm(from)}–${hhmm(sl[0])}`,
                        label: `${(ROLE[g.role] ?? g.role).toLowerCase()} setpoint, ${when}, ${hhmm(from)}–${hhmm(sl[0])}`,
                        members: members.map((m) => ({ zones: m.zones, targets: m.src?.value ?? [], value: m.value })),
                        picked: members.filter((m) => m.value === top).map((m) => m.zones.join(', ')),
                        memberLabels: Object.fromEntries(members.map((m) => [m.zones.join(', '), `${m.zones.join(', ')} — ${round(m.value)} °C`])),
                        min: top - 2, max: top + 2, unit: '°C',
                        current: Object.entries(count).map(([x, n]) => `${round(Number(x))} °C (${n})`).join(', '),
                        note: members.some((m) => m.value !== top) ? `Only the zones at ${round(top)} °C are selected by default.` : '',
                      };
                      const hasTime = si < gr.slots.length - 1 && members.every((m) => m.src?.time?.length);
                      const lo = Math.max(...members.map((m) => m.prev)) + 30;
                      const hi = Math.min(...members.map((m) => m.next ?? 1440)) - 30;
                      const timeVar = hasTime ? {
                        kind: 'schedule_time', type: 'category', box: `${box}|t`, role: g.role, when,
                        name: `${ROLE[g.role] ?? g.role} ${when}: end of the ${hhmm(sl[0])} slot`,
                        label: `time the slot ending at ${hhmm(sl[0])} ends (${(ROLE[g.role] ?? g.role).toLowerCase()}, ${when})`,
                        members: members.map((m) => ({ zones: m.zones, targets: m.src.time })),
                        picked: members.map((m) => m.zones.join(', ')),
                        currentMinute: sl[0], minMinute: lo, maxMinute: hi,
                        from: Math.max(lo, sl[0] - 120), to: Math.min(hi, sl[0] + 120), step: 30,
                        current: hhmm(sl[0]),
                      } : null;
                      const onV = Boolean(chosen[`schedule_value:${box}`]);
                      const onT = Boolean(chosen[`schedule_time:${box}|t`]);
                      return (
                        <tr key={box}>
                          <td>{dayLabel(p.start)} – {dayLabel(p.end)}</td>
                          <td>{daysLabel(gr.days)}</td>
                          <td className="dp-num">{hhmm(from)}–{hhmm(sl[0])}</td>
                          <td className="dp-num">
                            {off ? <span className="dp-muted">off</span>
                              : Object.entries(count).map(([x, n]) => `${round(Number(x))}${g.members.length > 1 ? ` (${n})` : ''}`).join(', ') + ' °C'}
                          </td>
                          <td className="dp-nowrap">
                            {!off && !full && (
                              <button type="button" className={onV ? 'dp-vary dp-vary-on' : 'dp-vary'} onClick={() => onToggle(valueVar)}>
                                {onV ? 'value ✓' : 'vary value'}
                              </button>
                            )}
                            {timeVar && !full && (
                              <button type="button" className={onT ? 'dp-vary dp-vary-on' : 'dp-vary'} onClick={() => onToggle(timeVar)}>
                                {onT ? 'time ✓' : 'vary time'}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )
                )}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

// ---- envelope ----------------------------------------------------------------

// One construction of an element: its layers, and a tickable row per variable
// field of each layer. Every layer looks the same: which one insulates is for
// the student to find out from its material, not for the page to point at.
function Build({ element, build, chosen, onToggle, expanded, setExpanded, matches }) {
  return (
    <div className="dp-build">
      <div className="dp-build-head">
        <code>{build.construction}</code>
        <span className="dp-muted"> · {build.surfaces} surfaces</span>
      </div>
      <div className="dp-layers">
        {build.layers.map((layer, i) => (
          <span key={`${layer.name}-${i}`} className="dp-layer" title={layer.name}>
            {layer.name}
          </span>
        ))}
      </div>
      {build.layers.map((layer, i) => {
        const fields = (layer.fields ?? []).filter((f) => matches(f.label) || matches(layer.name));
        if (!fields.length) return null;
        const openKey = `${build.construction}:${layer.name}:${i}`;
        const showAll = expanded[openKey];
        const familiar = fields.filter((f) => f.familiar);
        const rest = fields.filter((f) => !f.familiar);
        const visible = showAll ? fields : familiar.length ? familiar : fields.slice(0, 2);
        return (
          <div key={openKey} className="dp-layer-fields">
            <div className="dp-layer-name">
              {layer.name}
              {layer.shared && <span className="dp-muted"> · also in: {layer.inElements.join(', ')}</span>}
            </div>
            {visible.map((f) => {
              const variable = {
                kind: 'layer', type: 'range', element: element.id, elementLabel: element.label,
                layer: layer.name, alsoIn: layer.shared ? layer.inElements : [],
                className: f.className, field: f.field,
                label: `${f.label} of ${layer.name} (${element.label.toLowerCase()})`,
                name: `${element.label} ${f.label.toLowerCase()} ${layer.name}`,
                unit: f.unit, objects: [layer.name],
                // Thickness: no suggested range, the student writes the design range
                // (the course examples use 0.1-0.8 m whatever the model holds).
                min: f.field === 'Thickness' ? null : nice(f.suggestedMin),
                max: f.field === 'Thickness' ? null : nice(f.suggestedMax),
                bound: { min: f.min, max: f.max },
                current: `${round(f.current)} ${f.unit ?? ''}`,
              };
              const key = baseKey(variable);
              return (
                <label key={key} className="dp-field">
                  <input type="checkbox" checked={Boolean(chosen[key])} onChange={() => onToggle(variable)} />
                  <span className="dp-field-name">
                    {f.label}
                    {f.unit && <span className="dp-muted"> [{f.unit}]</span>}
                  </span>
                  <span className="dp-field-range">now {round(f.current)}</span>
                </label>
              );
            })}
            {!showAll && rest.length > 0 && familiar.length > 0 && (
              <button type="button" className="dp-more" onClick={() => setExpanded({ ...expanded, [openKey]: true })}>
                {rest.length} more fields of this layer
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// The other lever: swap the whole build-up among the ones the model defines.
function ChoiceRow({ element, chosen, onToggle }) {
  const alternatives = element.alternatives ?? [];
  const inUse = element.constructions.map((b) => b.construction);
  const variable = {
    kind: 'construction', type: 'category', element: element.id, elementLabel: element.label,
    className: element.className, field: 'Construction_Name',
    label: `${element.label} · whole build-up`, name: `${element.label} build-up`,
    choices: alternatives, use: element.alternativeUse ?? {}, surfaces: element.surfaces,
    options: inUse.filter((c) => alternatives.includes(c)),
    current: inUse.join(', '),
    note: inUse.length > 1 ? `Today the ${element.label.toLowerCase()} use ${inUse.length} different build-ups; each sample puts one on all ${element.surfaces} surfaces.` : '',
  };
  const key = baseKey(variable);
  if (alternatives.length < 2) return null;
  return (
    <label className="dp-field dp-field-choice">
      <input type="checkbox" checked={Boolean(chosen[key])} onChange={() => onToggle(variable)} />
      <span className="dp-field-name">
        Swap the whole build-up
        <div className="dp-source">
          In every simulation all surfaces of the {element.label.toLowerCase()} take one of the build-ups you choose.
          {' '}{inUse.length} in use · {alternatives.length} available in the model.
        </div>
      </span>
    </label>
  );
}

// Windows: a window is changed by its whole construction, chosen among the
// window constructions the IDF defines (and those brought in from the
// EnergyPlus library). Never its glass or frame materials. Three questions,
// asked in order: which windows, which window constructions, together or one by one;
// then the shading controls over those windows, whose setpoints the examples vary.
const FACING = { N: 'north', NE: 'north-east', E: 'east', SE: 'south-east', S: 'south', SW: 'south-west', W: 'west', NW: 'north-west' };
const facingWord = (w) => FACING[w.facing] ?? (w.facing || '');
// A window may sit under several shading controls, deployed in sequence.
const shadingOf = (w) => w.shading ?? [];
const blindLabel = (w) =>
  shadingOf(w).length
    ? [...new Set(shadingOf(w).map((s) => s.type.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()))].join(' + ')
    : 'none';
const blockedReason = (w) => shadingOf(w).find((s) => s.blocked)?.blocked;

function GlazingChoice({ element, chosen, setVariable, removeVariable, shadingVariable, onToggle }) {
  const members = element.members ?? [];
  const controls = element.controls ?? [];
  const key = `construction:${element.id}`;
  const current = chosen[key];
  const [selected, setSelected] = useState(() => new Set(current?.objects ?? members.map((w) => w.name)));
  const [perWindow, setPerWindow] = useState(Boolean(current?.perWindow));
  const [tries, setTries] = useState(() => new Set(current?.options ?? []));

  const chosenWindows = members.filter((w) => selected.has(w.name));
  const inUse = [...new Set(chosenWindows.map((w) => w.construction))];
  const allInUse = element.constructions.map((b) => b.construction);
  const layersOf = (name) =>
    element.alternativeLayerLabels?.[name] ?? element.alternativeLayers?.[name] ??
    element.constructions.find((b) => b.construction === name)?.layers.map((l) => l.name) ?? [];
  const candidates = (element.alternatives ?? []).filter((c) => !inUse.includes(c));
  // What is tried survives a change of windows, even through "none": the
  // ticks, minus the constructions already on the chosen windows.
  const trying = new Set([...tries].filter((o) => !inUse.includes(o) && candidates.includes(o)));

  const push = (nextSelected, nextTrying, nextPer) => {
    const wins = members.filter((w) => nextSelected.has(w.name));
    const used = [...new Set(wins.map((w) => w.construction))];
    const extra = [...nextTrying].filter((o) => !used.includes(o));
    if (!wins.length || !extra.length) {
      removeVariable(key);
      return;
    }
    setVariable({
      kind: 'construction', type: 'category', element: element.id, elementLabel: element.label,
      className: element.className, field: 'Construction_Name',
      label: `${element.label} · window construction`, name: current?.name ?? `${element.label} construction`,
      choices: element.alternatives ?? [], use: element.alternativeUse ?? {},
      objects: wins.map((w) => w.name), windows: wins, perWindow: nextPer,
      surfaces: wins.length, options: [...used, ...extra], current: used.join(', '),
    });
  };

  const setWindows = (names, on, from = selected) => {
    const next = new Set(from);
    names.forEach((n) => (on ? next.add(n) : next.delete(n)));
    setSelected(next);
    push(next, tries, perWindow);
  };
  const toggleTry = (name) => {
    const next = new Set(tries);
    if (trying.has(name)) next.delete(name);
    else next.add(name);
    setTries(next);
    push(selected, next, perWindow);
  };
  const setMode = (per) => {
    setPerWindow(per);
    push(selected, tries, per);
  };

  if (!members.length) return <p className="dp-note">No windows found on this element.</p>;

  // Groups a designer picks by: the windows under a blind and those without.
  const groups = [
    ['With a blind or shade', members.filter((w) => shadingOf(w).length)],
    ['Without shading', members.filter((w) => !shadingOf(w).length)],
  ].filter(([, list]) => list.length);
  const facings = [...new Set(members.map((w) => w.facing).filter(Boolean))];
  const blinds = chosenWindows.filter((w) => shadingOf(w).length);
  const blocked = chosenWindows.filter((w) => blockedReason(w));
  const columns = perWindow ? chosenWindows.length : 1;
  return (
    <div className="gl">
      <div className="gl-step">
        <div className="gl-step-title">1 · Which windows change</div>
        <div className="gl-quick">
          <button type="button" className="gl-chip" onClick={() => setWindows(members.map((w) => w.name), true)}>all {members.length}</button>
          <button type="button" className="gl-chip" onClick={() => setWindows(members.map((w) => w.name), false)}>none</button>
          {groups.length > 1 && groups.map(([title, list]) => (
            <button key={title} type="button" className="gl-chip"
              onClick={() => setWindows(list.map((w) => w.name), true, new Set())}>
              only {title.toLowerCase()}
            </button>
          ))}
          {facings.length > 1 && facings.map((f) => {
            const list = members.filter((w) => w.facing === f).map((w) => w.name);
            const on = list.every((n) => selected.has(n));
            return (
              <button key={f} type="button" className={on ? 'gl-chip gl-chip-on' : 'gl-chip'}
                onClick={() => setWindows(list, !on)} title={`${plural(list.length, 'window')} facing ${FACING[f] ?? f}`}>
                {FACING[f] ?? f} ({list.length})
              </button>
            );
          })}
        </div>
        <table className="gl-table gl-windows">
          <thead>
            <tr><th /><th>Facing</th><th>Zone · window</th><th>Construction now</th><th>Shading</th></tr>
          </thead>
          <tbody>
            {groups.map(([title, list]) => {
              const allOn = list.every((w) => selected.has(w.name));
              return (
                <Fragment key={title}>
                  <tr className="gl-section">
                    <td className="gl-check">
                      <input type="checkbox" checked={allOn} onChange={() => setWindows(list.map((w) => w.name), !allOn)} />
                    </td>
                    <td colSpan={4}>{title} · {list.length}</td>
                  </tr>
                  {list.map((w) => (
                    <tr key={w.name} className={selected.has(w.name) ? 'gl-on' : ''}>
                      <td className="gl-check">
                        <input type="checkbox" checked={selected.has(w.name)} onChange={() => setWindows([w.name], !selected.has(w.name))} />
                      </td>
                      <td>{facingWord(w) || '—'}</td>
                      <td>
                        <div>{w.zone}</div>
                        <div className="gl-layers" title={w.name}>{w.name}</div>
                      </td>
                      <td className="gl-small">{w.construction}</td>
                      <td className="gl-small">{blindLabel(w)}</td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="gl-step">
        <div className="gl-step-title">2 · Which window constructions to try on them</div>
        <table className="gl-table">
          <tbody>
            {inUse.map((name) => (
              <tr key={name} className="gl-current">
                <td className="gl-check"><span className="gl-tag">now</span></td>
                <td><div className="gl-name">{name}</div><div className="gl-layers">{layersOf(name).join(' · ')}</div></td>
                <td className="gl-count">{plural(chosenWindows.filter((w) => w.construction === name).length, 'window')}</td>
              </tr>
            ))}
            {candidates.length === 0 && (
              <tr><td colSpan={3} className="dp-muted">No other window construction in the IDF: add some from the library below.</td></tr>
            )}
            {candidates.map((name) => (
              <tr key={name} className={trying.has(name) ? 'gl-on' : ''}>
                <td className="gl-check">
                  <label className="gl-try"><input type="checkbox" checked={trying.has(name)} disabled={!chosenWindows.length}
                    onChange={() => toggleTry(name)} /> try</label>
                </td>
                <td><div className="gl-name">{name}</div><div className="gl-layers">{layersOf(name).join(' · ')}</div></td>
                <td className="gl-count">{allInUse.includes(name) ? 'on other windows' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {chosenWindows.length > 1 && (
        <div className="gl-step">
          <div className="gl-step-title">3 · Together or one by one</div>
          <label className="gl-mode">
            <input type="radio" checked={!perWindow} onChange={() => setMode(false)} />
            <span><b>Together</b>: every sample puts the same construction on all {chosenWindows.length} windows · 1 column</span>
          </label>
          <label className="gl-mode">
            <input type="radio" checked={perWindow} onChange={() => setMode(true)} />
            <span><b>One by one</b>: each window gets its own construction · {chosenWindows.length} columns</span>
          </label>
        </div>
      )}

      <p className="gl-summary">
        {!chosenWindows.length
          ? 'No window chosen: the windows stay as they are.'
          : !trying.size
          ? `${plural(chosenWindows.length, 'window')} chosen. Tick at least one construction to try.`
          : `Sampling chooses among ${inUse.length + trying.size} window constructions for ${plural(chosenWindows.length, 'window')} · ${plural(columns, 'column')}.`}
      </p>
      {blinds.length > 0 && trying.size > 0 && !blocked.length && (
        <p className="gl-note">
          {blinds.length} of these windows have {/^[aeiou]/.test(blindLabel(blinds[0])) ? 'an' : 'a'} {blindLabel(blinds[0])}. It stays: the notebook cell gives it to
          EnergyPlus as a material (<code>Shading Device Material Name</code>), so it fits whichever window construction
          a sample picks. Given as a shaded construction, as in the model, it only fits the one it was built with.
        </p>
      )}
      {blocked.length > 0 && (
        <p className="dp-error">
          {plural(blocked.length, 'chosen window')}: the shading device is part of the glazed construction
          ({blockedReason(blocked[0])}) so the construction cannot be swapped. Untick them.
        </p>
      )}

      <ShadingSetpoints controls={controls} chosenWindows={chosenWindows} chosen={chosen}
        shadingVariable={shadingVariable} onToggle={onToggle} />
    </div>
  );
}

const UNIT_WORD = { C: '°C', W: 'W', 'W/m2': 'W/m²' };

// The setpoints of the shading controls over the chosen windows: when the blind
// comes down. Every course example varies these two. Which quantity each one is
// depends on the Shading Control Type (IDD notes), so it is said per control.
function ShadingSetpoints({ controls, chosenWindows, chosen, shadingVariable, onToggle }) {
  const names = new Set(chosenWindows.map((w) => w.name.toUpperCase()));
  const over = controls.filter((c) => c.windows.some((w) => names.has(w.toUpperCase())));
  if (!controls.length) return null;
  const rows = [
    ['Setpoint', 'setpoint', 'setpointUnit'],
    ['Setpoint 2', 'setpoint2', 'setpoint2Unit'],
  ].map(([label, value, unit]) => {
    const live = over.filter((c) => c[unit]);
    const units = [...new Set(live.map((c) => c[unit]))];
    return { label, value, unit, live, units };
  }).filter((r) => r.live.length);
  return (
    <div className="gl-step">
      <div className="gl-step-title">Shading control · when the blinds come down</div>
      {!over.length ? (
        <p className="dp-muted">No shading control over the chosen windows.</p>
      ) : (
        <>
          <p className="dp-muted">
            {plural(over.length, 'control')} over the chosen windows:{' '}
            {[...new Set(over.map((c) => c.controlType))].join(', ')}.
          </p>
          {rows.length === 0 && <p className="dp-muted">Their control type uses no setpoint.</p>}
          {rows.map((r) => {
            const values = [...new Set(r.live.map((c) => c[r.value]))];
            const variable = shadingVariable(r.label, r.live, r.units.length === 1 ? UNIT_WORD[r.units[0]] : null,
              values.map((x) => round(x)));
            if (!variable) return null;
            const key = baseKey(variable);
            return (
              <label key={r.label} className="dp-field">
                <input type="checkbox" checked={Boolean(chosen[key])} onChange={() => onToggle(variable)} />
                <span className="dp-field-name">
                  {r.label}
                  <span className="dp-muted"> [{r.units.map((u) => UNIT_WORD[u]).join(' / ')}]</span>
                  {r.units.length > 1 && <div className="dp-warn">These controls compare it with different quantities.</div>}
                </span>
                <span className="dp-field-range">now {values.map((x) => round(x)).join(', ')}</span>
              </label>
            );
          })}
        </>
      )}
    </div>
  );
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

// The options of a category, to narrow or widen, grouped by where each is
// already used: admissible and sensible are not the same list.
function Options({ variable, onToggle }) {
  const [more, setMore] = useState(false);
  const selected = new Set(variable.options ?? []);
  const choices = variable.choices ?? [];
  const use = variable.use;
  const usedBy = (c) => use?.[c] ?? [];
  const here = variable.element;
  const groups = use && variable.kind === 'construction'
    ? [
        ['used here', choices.filter((c) => usedBy(c).includes(here))],
        ['defined but unused', choices.filter((c) => !usedBy(c).length)],
        ['used by other elements', choices.filter((c) => usedBy(c).length && !usedBy(c).includes(here))],
      ]
    : [['', choices]];
  const LIMIT = 12;
  return (
    <div className="dp-options">
      <span className={selected.size < 2 ? 'dp-error' : 'dp-muted'}>
        {selected.size} of {choices.length} selected{selected.size < 2 ? ' — at least two are needed' : ''}
      </span>
      {groups.map(([title, items], i) => {
        if (!items.length) return null;
        const hidden = groups.length > 1 && i === 2 && !more && !items.some((c) => selected.has(c));
        if (hidden) {
          return (
            <button key={title} type="button" className="dp-more" onClick={() => setMore(true)}>
              {items.length} more {title}
            </button>
          );
        }
        const shown = more || items.length <= LIMIT ? items : items.slice(0, LIMIT);
        return (
          <div key={title || 'all'} className="dp-option-group">
            {title && <span className="dp-muted">{title}</span>}
            <div className="dp-objectives">
              {shown.map((c) => (
                <label key={c} className={selected.has(c) ? 'dp-obj dp-obj-on' : 'dp-obj'}>
                  <input type="checkbox" checked={selected.has(c)} onChange={() => onToggle(c)} />
                  {c}
                </label>
              ))}
              {shown.length < items.length && (
                <button type="button" className="dp-more" onClick={() => setMore(true)}>
                  {items.length - shown.length} more
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// The thermostat classes are covered by the schedule tables, so they are not
// listed again as raw fields.
const THERMOSTAT_CLASSES = /^(ZoneControl:Thermostat|ThermostatSetpoint:)/i;

function withoutThermostats(structure) {
  return structure
    .map((g) => {
      const classes = g.classes.filter((c) => !THERMOSTAT_CLASSES.test(c.className));
      const trimmed = classes.length < g.classes.length;
      return {
        ...g,
        display: trimmed ? `Other zone controls: ${classes.map((c) => c.className).join(', ')}` : undefined,
        classes,
        fieldCount: classes.reduce((n, c) => n + c.fields.length, 0),
        objectCount: classes.reduce((n, c) => n + c.objectCount, 0),
      };
    })
    .filter((g) => g.classes.length);
}

const PANES = { 1: 'single', 2: 'double', 3: 'triple', 4: 'quadruple' };

// New window types come in as whole constructions from EnergyPlus' own library.
// Importing adds them, with their layers, to the model; no window changes until
// a design point assigns one.
function WindowLibrary({ onImported }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState(null);
  const [panes, setPanes] = useState(2);
  const [q, setQ] = useState('');
  const [picked, setPicked] = useState(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (!open || items) return;
    fetch(api('/surrogate_modeling/window_library'))
      .then((r) => r.json())
      .then((d) => setItems(d.constructions ?? []))
      .catch(() => setMessage({ kind: 'error', text: 'The library cannot be reached.' }));
  }, [open, items]);

  const shown = (items ?? []).filter((c) => c.panes === panes && (!q || c.name.toLowerCase().includes(q.toLowerCase())));

  const bring = () => {
    setBusy(true);
    setMessage(null);
    fetch(api('/surrogate_modeling/window_library'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ names: [...picked] }),
    })
      .then(async (r) => ({ ok: r.ok, body: await r.json() }))
      .then(({ ok, body }) => {
        if (!ok) {
          setMessage({ kind: 'error', text: body.error ?? 'Import failed.' });
          return undefined;
        }
        setMessage({
          kind: 'ok',
          text: body.added.length ? `Added to the model: ${body.added.join(', ')}. They are now among the options.` : 'They were already in the model.',
        });
        setPicked(new Set());
        return onImported(body.added);
      })
      .finally(() => setBusy(false));
  };

  if (!open) {
    return (
      <button type="button" className="dp-more" onClick={() => setOpen(true)}>
        + more window constructions from the EnergyPlus library
      </button>
    );
  }
  return (
    <div className="dp-card dp-library">
      <div className="dp-row-head dp-static">
        <span className="dp-title">EnergyPlus window library</span>
        <span className="dp-meta">{items ? `${items.length} constructions` : 'reading…'}</span>
      </div>
      <p className="dp-muted">The construction and its layers are added to the model; the windows stay as they are until a design point chooses.</p>
      <div className="dp-library-bar">
        {Object.entries(PANES).map(([n, label]) => (
          <button key={n} type="button" className={Number(n) === panes ? 'dp-tab dp-tab-on' : 'dp-tab'} onClick={() => setPanes(Number(n))}>
            {label} ({(items ?? []).filter((c) => c.panes === Number(n)).length})
          </button>
        ))}
        <input type="search" className="dp-objective-search" placeholder="filter: LoE, Arg, 6mm…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="dp-library-list">
        {shown.map((c) => (
          <label key={c.name} className="dp-field">
            <input type="checkbox" checked={picked.has(c.name)}
              onChange={() => setPicked((cur) => {
                const next = new Set(cur);
                if (next.has(c.name)) next.delete(c.name);
                else next.add(c.name);
                return next;
              })} />
            <span className="dp-field-name">{c.name}<div className="dp-source">{c.layers.join(' · ')}</div></span>
          </label>
        ))}
      </div>
      <div className="dp-actions">
        <button type="button" className="dp-save" disabled={!picked.size || busy} onClick={bring}>
          {busy ? 'Adding…' : `Add to the model (${picked.size})`}
        </button>
        {message && <span className={message.kind === 'ok' ? 'dp-ok' : 'dp-error'}>{message.text}</span>}
      </div>
    </div>
  );
}

// ---- the notebook cell ------------------------------------------------------

// Only shown when the cell is written for BESOS. The problem is in the BESOS
// reader of the .eso file; bdopt reads the SQL output and has no such problem.
const SCHEDULE_FIX = `# after building = ef.get_building(...), before EvaluatorEP.
# BESOS 2.1.3 cannot read the .eso lines of Output:Variable objects that carry a
# schedule (they end in ",ON"): EnergyPlus finishes, then EvaluatorEP stops with
# "could not match". Remove the schedule on the in-memory copy:
for out in building.idfobjects["OUTPUT:VARIABLE"]:
    out.Schedule_Name = ""`;

// What the cell is, said for the library it is written in.
function CellExplanation({ engine }) {
  if (engine === 'bdopt') {
    return (
      <>
        <p className="dp-muted">
          This is the &quot;Define the problem&quot; cell for your notebook, with the parameters chosen above. It
          defines <code>parameters</code> (one bdopt <code>Parameter</code> per column), <code>objectives</code>,{' '}
          <code>problem</code>, <code>evaluator</code> and <code>samples</code>: 20 Latin hypercube rows, a row per
          design and a column per parameter. A parameter that writes several objects is still one{' '}
          <code>Parameter</code> with one selector (<code>FieldSelector</code> with <code>&quot;*&quot;</code>, or{' '}
          <code>MultiSelector</code> for a list of objects), so it stays one column.
        </p>
        <p className="dp-muted">
          The cell needs <code>idf</code> and <code>epw_file</code>, the model and the weather file: the platform
          defines them in a cell it adds to the notebook when you upload the files. The objectives are meters, which
          the evaluator requests by itself, so it is built on <code>sim_idf</code>, a copy of <code>idf</code> without
          its Output:Variable objects; <code>idf</code> itself stays the model to save. Creating the evaluator checks
          every selector against the model and simulates nothing: EnergyPlus runs when you evaluate the samples. The
          saved problem.json holds the same choices; the cell does not read it.
        </p>
      </>
    );
  }
  return (
    <p className="dp-muted">
      This is the Laboratory's &quot;Define The Problem&quot; cell with the parameters chosen above. A parameter that
      writes several objects becomes a loop with one shared descriptor and one name, as for the windows in the
      Laboratory, so it stays one column. The saved problem.json holds the same information.
    </p>
  );
}

function NotebookCell({ preview, engine = 'besos', scheduledOutputs }) {
  const [copied, setCopied] = useState(false);
  const pre = useRef(null);
  const copy = () => {
    navigator.clipboard.writeText(preview.cell).then(() => setCopied(true)).catch(() => {
      const r = document.createRange();
      r.selectNodeContents(pre.current);
      const s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
    });
  };
  return (
    <section className="dp-cell">
      <div className="dp-row-head dp-static">
        <span className="dp-title">The notebook cell</span>
        {preview.cell && (
          <button type="button" className="dp-more" onClick={copy}>{copied ? 'Copied' : 'Copy the cell'}</button>
        )}
      </div>
      <CellExplanation engine={engine} />
      {preview.problems.length > 0 && (
        <ul className="dp-problems">{preview.problems.map((p) => <li key={p}>{p}</li>)}</ul>
      )}
      {preview.cell ? (
        <pre ref={pre} className="dp-code"><code>{preview.cell}</code></pre>
      ) : (
        <p className="dp-muted">It appears as soon as one parameter is complete.</p>
      )}
      {engine === 'besos' && scheduledOutputs > 0 && preview.cell && (
        <>
          <p className="dp-warn">This model has {scheduledOutputs} Output:Variable objects with a schedule.</p>
          <pre className="dp-code"><code>{SCHEDULE_FIX}</code></pre>
        </>
      )}
    </section>
  );
}
