// EmsPrograms.jsx
// Programs, the calling managers that run them, and the variables they use.
//
// A program is Erl code; a calling manager says at which calling point of the
// timestep it runs and in which order. Both are edited here, side by side. Whatever
// the uploaded model already had is tagged "model", whatever was added since is
// "yours"; only the platform's own objects are read-only.
import React, { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppContext } from './AppContext';
import RoleSwitch from './FmuRole';
import './ModelEditor.css';

const VARIABLE_GROUPS = [
  ['builtIns', 'Built-in', 'Time, date and constants. Null releases an actuator.'],
  ['sensors', 'Sensors', 'What the model reports, read into a variable.'],
  ['actuators', 'Actuators', 'What the program sets.'],
  ['fmuInputs', 'FMU inputs', 'Values the controller writes.'],
  ['globals', 'Globals', 'Variables shared between programs.'],
  ['trends', 'Trends', 'The history of another variable.'],
];

const ORIGIN_LABEL = { student: 'yours', model: 'model', platform: 'platform' };

function toIdentifier(raw) {
  const cleaned = (raw || '').trim().replace(/[^0-9a-zA-Z_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
  if (!cleaned) return '';
  return /^\d/.test(cleaned) ? `v_${cleaned}` : cleaned;
}

const NEW_MANAGER = '__new__';
const blankDraft = (callingPoint) => ({ name: '', kind: 'program', callingPoint, manager: NEW_MANAGER, text: '', editing: false });

const RUNTIME_REASON = {
  outputs: 'a meter or a program variable is sent to the controller through an EMS output variable, and that stays silent unless some program runs',
  inputs: 'a controller input is applied by an EMS program',
  idle: 'the model has EMS objects but no calling manager calls anything, and EnergyPlus runs the EMS only when a program is called',
};

export default function EmsPrograms() {
  const {
    idfObjects, filesUploaded, fetchEmsPrograms, checkEmsProgram, saveEmsProgram, removeEmsProgram,
    saveEmsManager, removeEmsManager, setModelEms, addEmsVariable, removeEmsVariable, monitorQuantity, setFmuRole,
  } = useContext(AppContext);
  const [cat, setCat] = useState({
    programs: [], managers: [], variables: {}, callingPoints: [], defaultCallingPoint: '',
    modelEms: { present: false, off: [] }, runtime: { present: false, reason: null },
  });
  const [draft, setDraft] = useState(blankDraft(''));
  const [check, setCheck] = useState({ errors: [], warnings: [] });
  const [viewing, setViewing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const area = useRef(null);

  // The catalogue is read from the model again after every change to it.
  useEffect(() => {
    if (!filesUploaded) return undefined;
    let live = true;
    fetchEmsPrograms().then((c) => {
      if (!live) return;
      setCat(c);
      setDraft((d) => (d.callingPoint ? d : { ...d, callingPoint: c.defaultCallingPoint }));
    }).catch(() => {});
    return () => { live = false; };
  }, [idfObjects, filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live check of the text: errors block saving, warnings do not.
  useEffect(() => {
    const lines = draft.text.split('\n').filter((l) => l.trim());
    if (!lines.length) { setCheck({ errors: [], warnings: [] }); return undefined; }
    let live = true;
    const t = setTimeout(() => {
      checkEmsProgram(lines).then((c) => live && setCheck(c)).catch(() => {});
    }, 350);
    return () => { live = false; clearTimeout(t); };
  }, [draft.text, cat.variables]); // eslint-disable-line react-hooks/exhaustive-deps

  const pointOf = (name) => cat.callingPoints.find((c) => c.name === name);
  const point = pointOf(draft.callingPoint);
  const managersToJoin = cat.managers.filter((m) => m.editable);
  const chosenManager = cat.managers.find((m) => m.name === draft.manager);
  const reset = () => setDraft(blankDraft(cat.defaultCallingPoint));

  const run = async (fn, done) => {
    setBusy(true); setError(''); setNotice('');
    try { const r = await fn(); if (done) setNotice(typeof done === 'function' ? done(r) : done); } catch (e) {
      setError(e?.response?.data?.details || e?.response?.data?.error || e.message);
    } finally { setBusy(false); }
  };

  const insert = (name) => {
    const el = area.current;
    const at = el ? el.selectionStart : draft.text.length;
    const end = el ? el.selectionEnd : at;
    const text = draft.text.slice(0, at) + name + draft.text.slice(end);
    setDraft({ ...draft, text });
    requestAnimationFrame(() => { if (el) { el.focus(); el.selectionStart = el.selectionEnd = at + name.length; } });
  };

  const save = () => run(async () => {
    const payload = { name: draft.name, kind: draft.kind, lines: draft.text.split('\n').filter((l) => l.trim()) };
    if (!draft.editing && draft.kind === 'program') {
      if (draft.manager === NEW_MANAGER) payload.callingPoint = draft.callingPoint;
      else if (draft.manager) payload.manager = draft.manager;
    }
    const r = await saveEmsProgram(payload);
    reset();
    return r;
  }, (r) => (r.warnings?.length ? `Saved. ${r.warnings.join(' ')}` : 'Program saved.'));

  const removeProgram = (p) => {
    if (p.origin === 'model' && !window.confirm(`"${p.name}" comes with the model. Remove it anyway? "Restore original" brings it back.`)) return;
    run(() => removeEmsProgram(p.name), (r) => (r.removedManagers?.length ? `Program removed, and the calling manager ${r.removedManagers.join(', ')} with it: it had nothing else to run.` : 'Program removed.'));
  };

  // The model's own EMS, all of it or one calling manager.
  const switchModel = (enabled, name) => run(() => setModelEms(enabled, name), (r) => {
    const shading = r.shading?.length ? ` Shading controls ${enabled ? 'set to AlwaysOn, as the EMS drives them' : 'back to their own logic'}: ${r.shading.join(', ')}.` : '';
    return `${name ? `"${name}"` : "The model's EMS"} is ${enabled ? 'on' : 'off'}.${shading}`;
  });

  if (!filesUploaded) return <p className="me-empty">Upload an IDF and an EPW file to start.</p>;

  const programs = cat.programs.filter((p) => p.origin === 'student').concat(cat.programs.filter((p) => p.origin !== 'student'));
  return (
    <div className="me ep">
      {error && <div className="me-error">{error}</div>}
      {notice && <div className="me-note">{notice}</div>}

      <div className="ep-grid">
        <div className="ep-col">
        <section className="me-card ep-section">
          <h3>Programs <span className="me-count">{cat.programs.length}</span></h3>
          <p className="me-muted">
            Erl code. A calling manager runs a program; a subroutine runs when a program says RUN. The platform&apos;s own are read-only.
          </p>
          <ul className="me-list">
            {programs.map((p) => {
              const isOpen = viewing === p.name;
              return (
                <li key={`${p.kind}:${p.name}`} className={isOpen ? 'me-row me-row-open' : 'me-row'}>
                  <div className="me-row-head">
                    <span className="me-name">{p.name}</span>
                    <span className={p.origin === 'student' ? 'me-tag-on' : 'me-tag-muted'}>{ORIGIN_LABEL[p.origin]}</span>
                    <span className="me-meta">
                      {p.kind === 'subroutine' ? 'subroutine' : p.managers.length ? `${p.callingPoint}` : 'not called'} · {p.lines.length} {p.lines.length === 1 ? 'line' : 'lines'}
                    </span>
                    <button type="button" className="me-btn" onClick={() => setViewing(isOpen ? null : p.name)}>{isOpen ? 'Hide' : 'Show'}</button>
                    {p.editable && (
                      <>
                        <button type="button" className="me-btn" disabled={busy}
                          onClick={() => setDraft({ name: p.name, kind: p.kind, callingPoint: p.callingPoint || cat.defaultCallingPoint, manager: '', text: p.lines.join('\n'), editing: true })}>Edit</button>
                        <button type="button" className="me-btn" disabled={busy} onClick={() => removeProgram(p)}>Remove</button>
                      </>
                    )}
                  </div>
                  {isOpen && <pre className="ep-code">{p.lines.join('\n')}</pre>}
                </li>
              );
            })}
            {cat.programs.length === 0 && <li className="me-muted">No programs yet.</li>}
          </ul>
        </section>

        <section className="me-card ep-section">
          <h3>{draft.editing ? `Edit ${draft.name}` : 'New program'}</h3>
          <div className="ep-form">
            <label>Name
              <input value={draft.name} disabled={draft.editing} placeholder="MyControl"
                onChange={(e) => setDraft({ ...draft, name: toIdentifier(e.target.value) })} />
            </label>
            {!draft.editing && (
              <label>Kind
                <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
                  <option value="program">Program: a calling manager runs it</option>
                  <option value="subroutine">Subroutine: programs call it with RUN</option>
                </select>
              </label>
            )}
            {!draft.editing && draft.kind === 'program' && (
              <label>Calling manager
                <select value={draft.manager} onChange={(e) => setDraft({ ...draft, manager: e.target.value })}>
                  <option value={NEW_MANAGER}>A new manager, only for this program</option>
                  {managersToJoin.map((m) => <option key={m.name} value={m.name}>Add to {m.name}</option>)}
                  <option value="">None yet</option>
                </select>
              </label>
            )}
            {!draft.editing && draft.kind === 'program' && draft.manager === NEW_MANAGER && (
              <label>Runs at
                <select value={draft.callingPoint} onChange={(e) => setDraft({ ...draft, callingPoint: e.target.value })}>
                  {cat.callingPoints.map((c) => <option key={c.name} value={c.name}>{c.name}{c.control ? '' : '  (not for control)'}</option>)}
                </select>
              </label>
            )}
          </div>
          {!draft.editing && draft.kind === 'program' && draft.manager === NEW_MANAGER && point && <p className="me-muted ep-hint">{point.hint}</p>}
          {!draft.editing && draft.kind === 'program' && chosenManager && (
            <p className="me-muted ep-hint">It will run at {chosenManager.callingPoint}, after {chosenManager.programs.join(', ')}. {pointOf(chosenManager.callingPoint)?.hint}</p>
          )}
          {draft.editing && <p className="me-muted ep-hint">The managers that call this program are edited under When things run.</p>}

          <textarea ref={area} className="ep-text" rows={10} spellCheck={false} value={draft.text}
            placeholder={'IF WarmupFlag == 0\n  SET my_actuator = my_input\nENDIF'}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })} />
          <p className="me-muted ep-hint">
            One statement per line, starting with RUN, SET, IF, ELSEIF, ELSE, ENDIF, WHILE, ENDWHILE or RETURN. The commas
            are added for you. A line is cut at 100 characters. Set an actuator to Null to give control back to the model.
          </p>
          {check.errors.map((m) => <p key={m} className="me-error ep-msg">{m}</p>)}
          {check.warnings.map((m) => <p key={m} className="me-warn ep-msg">{m}</p>)}

          <div className="ep-actions">
            <button type="button" className="me-btn me-btn-primary" disabled={busy || !draft.name || !draft.text.trim() || check.errors.length > 0} onClick={save}>
              {busy ? 'Saving…' : draft.editing ? 'Save changes' : 'Save program'}
            </button>
            {(draft.editing || draft.text) && <button type="button" className="me-btn" onClick={reset}>Clear</button>}
          </div>

          <div className="ep-palette">
            <h4>Names you can use <span className="me-muted">(click to insert)</span></h4>
            {VARIABLE_GROUPS.map(([key, title, hint]) => {
              const items = (cat.variables[key] || []).map((v) => (typeof v === 'string' ? { name: v } : v));
              if (!items.length) return null;
              return (
                <details key={key} className="me-details" open={key === 'actuators' || key === 'fmuInputs' || undefined}>
                  <summary>{title} <span className="me-count">{items.length}</span> <span className="me-muted">{hint}</span></summary>
                  <ul className="me-chips">
                    {items.map((v) => (
                      <li key={v.name} className="me-chip" title={v.source || ''}>
                        <button type="button" className="ep-insert" onClick={() => insert(v.name)}><code>{v.name}</code></button>
                      </li>
                    ))}
                  </ul>
                </details>
              );
            })}
          </div>
        </section>

      <details className="me-card ep-section ep-vars">
        <summary><h3>Variables <span className="me-count">{Object.values(cat.variables).reduce((n, l) => n + (l?.length || 0), 0) - (cat.variables.builtIns || []).length}</span></h3></summary>
        <Variables cat={cat} data={idfObjects || {}} busy={busy} run={run}
          addEmsVariable={addEmsVariable} removeEmsVariable={removeEmsVariable} monitorQuantity={monitorQuantity} setFmuRole={setFmuRole} />
      </details>
        </div>

        <div className="ep-col">
          <Timeline cat={cat} busy={busy} run={run} pointOf={pointOf} switchModel={switchModel}
            saveEmsManager={saveEmsManager} removeEmsManager={removeEmsManager} />
        </div>
      </div>
    </div>
  );
}

// ---- when things run: the calling points, in the order the guide lists them -------

function Timeline({ cat, busy, run, pointOf, switchModel, saveEmsManager, removeEmsManager }) {
  const [fresh, setFresh] = useState({ name: '', callingPoint: '', program: '' });
  const callable = cat.programs.filter((p) => p.kind === 'program' && p.origin !== 'platform');
  const freshPoint = pointOf(fresh.callingPoint || cat.defaultCallingPoint);

  // Managers by calling point; the model's switched-off ones stay in place, dimmed.
  const off = (cat.modelEms.off || []).map((o) => ({ ...o, origin: 'model', off: true, editable: false, missing: [] }));
  const all = [...cat.managers.map((m) => ({ ...m, off: false })), ...off];
  const used = cat.callingPoints.filter((c) => all.some((m) => m.callingPoint === c.name));

  const write = (m, patch) => run(() => saveEmsManager({
    name: m.name, callingPoint: patch.callingPoint || m.callingPoint, programs: patch.programs || m.programs,
  }));
  const move = (m, i, d) => {
    const next = [...m.programs];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    write(m, { programs: next });
  };
  const drop = (m, i) => {
    if (m.programs.length === 1) {
      if (!window.confirm(`"${m.name}" would have nothing to run. Remove the calling manager?`)) return;
      run(() => removeEmsManager(m.name), 'Calling manager removed.');
    } else write(m, { programs: m.programs.filter((_, k) => k !== i) });
  };
  const create = () => run(async () => {
    await saveEmsManager({ name: fresh.name, callingPoint: fresh.callingPoint || cat.defaultCallingPoint, programs: [fresh.program] });
    setFresh({ name: '', callingPoint: '', program: '' });
  }, 'Calling manager created.');

  return (
    <section className="me-card ep-section">
      <h3>
        Calling managers <span className="me-count">{all.length}</span>
        {cat.modelEms.present && (
          <button type="button" className="me-btn ep-all" disabled={busy}
            title={cat.modelEms.running > 0 ? 'Stop every calling manager of the model from running' : 'Run the model’s calling managers again'}
            onClick={() => switchModel(cat.modelEms.running === 0)}>
            {cat.modelEms.running > 0 ? 'Switch the model’s off' : 'Switch the model’s on'}
          </button>
        )}
      </h3>
      <p className="me-muted">
        A calling manager runs its programs at one calling point of every timestep, in the order listed (first runs first).
        Points are listed in the order of the EMS guide; only the ones in use are shown.
      </p>

      {used.length === 0 && <p className="me-muted">Nothing runs yet.</p>}
      {used.map((c) => (
        <div key={c.name} className="ep-point-block">
          <h4 title={c.hint}>{c.name}{!c.control && <span className="me-muted"> · not for control</span>}</h4>
          <p className="me-muted ep-hint">{c.hint}</p>
          <ul className="me-list">
            {all.filter((m) => m.callingPoint === c.name).map((m) => (
              <li key={m.name} className={m.off ? 'me-row ep-off' : 'me-row'}>
                <div className="me-row-head">
                  <span className="me-name">{m.name}</span>
                  <span className={m.origin === 'student' ? 'me-tag-on' : 'me-tag-muted'}>{ORIGIN_LABEL[m.origin]}</span>
                  {m.off && <span className="me-tag-warn">switched off</span>}
                  {m.origin === 'platform' && <span className="me-meta">added automatically</span>}
                  {m.origin === 'model' && (
                    <button type="button" className="me-btn" disabled={busy} onClick={() => switchModel(m.off, m.name)}>{m.off ? 'Switch on' : 'Switch off'}</button>
                  )}
                  {m.origin === 'student' && (
                    <>
                      <select className="ep-point" value={m.callingPoint} disabled={busy} title="Move to another calling point"
                        onChange={(e) => write(m, { callingPoint: e.target.value })}>
                        {cat.callingPoints.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
                      </select>
                      <button type="button" className="me-btn" disabled={busy}
                        onClick={() => run(() => removeEmsManager(m.name), 'Calling manager removed.')}>Remove</button>
                    </>
                  )}
                </div>
                <ol className="ep-order">
                  {m.programs.map((name, i) => (
                    <li key={name} className={m.missing.includes(name) ? 'ep-missing' : undefined}>
                      <code>{name}</code>
                      {m.missing.includes(name) && <span className="me-tag-warn"> not in the model</span>}
                      {m.origin === 'student' && (
                        <span className="ep-order-btns">
                          <button type="button" disabled={busy || i === 0} title="Run earlier" onClick={() => move(m, i, -1)}>↑</button>
                          <button type="button" disabled={busy || i === m.programs.length - 1} title="Run later" onClick={() => move(m, i, 1)}>↓</button>
                          <button type="button" disabled={busy} title="Stop calling it" onClick={() => drop(m, i)}>×</button>
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
                {m.origin === 'student' && callable.some((p) => !m.programs.includes(p.name)) && (
                  <select className="ep-add" value="" disabled={busy}
                    onChange={(e) => e.target.value && write(m, { programs: [...m.programs, e.target.value] })}>
                    <option value="">Add a program…</option>
                    {callable.filter((p) => !m.programs.includes(p.name)).map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
                  </select>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      <h4 className="ep-sub">New calling manager</h4>
      <div className="ep-form">
        <label>Name
          <input value={fresh.name} placeholder="Morning control" onChange={(e) => setFresh({ ...fresh, name: e.target.value })} />
        </label>
        <label>Runs at
          <select value={fresh.callingPoint || cat.defaultCallingPoint} onChange={(e) => setFresh({ ...fresh, callingPoint: e.target.value })}>
            {cat.callingPoints.map((c) => <option key={c.name} value={c.name}>{c.name}{c.control ? '' : '  (not for control)'}</option>)}
          </select>
        </label>
        <label>First program
          <select value={fresh.program} onChange={(e) => setFresh({ ...fresh, program: e.target.value })}>
            <option value="">choose…</option>
            {callable.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        </label>
        <button type="button" className="me-btn me-btn-primary" disabled={busy || !fresh.name.trim() || !fresh.program} onClick={create}>Create</button>
      </div>
      {freshPoint && <p className="me-muted ep-hint">{freshPoint.hint}</p>}
      {cat.runtime.reason && (
        <p className="me-muted ep-hint">
          A do-nothing program (<code>{cat.runtime.program}</code>, manager <code>{cat.runtime.manager}</code>) was added
          automatically: {RUNTIME_REASON[cat.runtime.reason]}.
        </p>
      )}
    </section>
  );
}

// ---- declaring variables --------------------------------------------------------

function Variables({ cat, data, busy, run, addEmsVariable, removeEmsVariable, monitorQuantity, setFmuRole }) {
  const [kind, setKind] = useState('actuator');
  const [f, setF] = useState({});
  const set = (patch) => setF((x) => ({ ...x, ...patch }));

  const variables = data.rdd_variables || [];
  const kinds = useMemo(() => {
    const k = {};
    (data.edd_actuators || []).forEach((a) => {
      const id = `${a.componentType}|${a.controlType}`;
      (k[id] ||= { type: a.componentType, control: a.controlType, components: [] }).components.push(a.componentUniqueName);
    });
    return Object.values(k).sort((a, b) => `${a.type}${a.control}`.localeCompare(`${b.type}${b.control}`));
  }, [data.edd_actuators]);
  const sensorVar = variables.find((v) => v.variableName === f.variableName);
  const actKind = kinds.find((k) => `${k.type}|${k.control}` === f.kindId);
  const everyName = ['sensors', 'actuators', 'fmuInputs', 'globals', 'trends'].flatMap((g) => (cat.variables[g] || []).map((v) => v.name));

  const KINDS = [
    ['actuator', 'Actuator', 'A handle on a component that the program sets.'],
    ['sensor', 'Sensor', 'A report variable read into a variable.'],
    ['fmuInput', 'FMU input', 'A value the controller writes; the program reads it.'],
    ['global', 'Global', 'A variable shared between programs.'],
    ['trend', 'Trend', 'The history of another variable.'],
    ['output', 'Output to the controller', 'Send a program variable to the controller.'],
  ];

  const submit = () => run(async () => {
    if (kind === 'actuator') {
      await addEmsVariable({ kind, name: f.name, component: f.component || actKind.components[0], componentType: actKind.type, controlType: actKind.control });
    } else if (kind === 'sensor') {
      await addEmsVariable({ kind, name: f.name, variableName: f.variableName, key: f.key ?? (sensorVar?.keys || [''])[0] });
    } else if (kind === 'fmuInput') {
      // What crosses to the controller gets its range when it is added.
      const r = await addEmsVariable({ kind, name: f.name, initialValue: Number(f.initial) || 0 });
      await setFmuRole({ fmuVariableName: r.fmuVariableName, min: Number(f.min), max: Number(f.max) });
    } else if (kind === 'global') {
      await addEmsVariable({ kind, name: f.name });
    } else if (kind === 'trend') {
      await addEmsVariable({ kind, name: f.name, variable: f.variable, steps: Number(f.steps) || 12 });
    } else {
      const r = await monitorQuantity({ sourceType: 'actuator', sourceName: f.variable, name: f.name });
      await setFmuRole({ fmuVariableName: r.fmuVariableName, role: f.role || 'observation' });
    }
    setF({});
  }, 'Added.');

  const num = (x) => x !== '' && x != null && Number.isFinite(Number(x));
  const rangeOk = num(f.min) && num(f.max) && Number(f.min) <= Number(f.max);
  const ready = f.name && (
    (kind === 'actuator' && actKind) || (kind === 'sensor' && f.variableName) || (kind === 'fmuInput' && rangeOk)
    || kind === 'global' || ((kind === 'trend' || kind === 'output') && f.variable));

  const declared = [
    ['actuator', 'actuators'], ['sensor', 'sensors'], ['fmuInput', 'fmuInputs'], ['global', 'globals'], ['trend', 'trends'],
  ].flatMap(([k, g]) => (cat.variables[g] || []).map((v) => ({ ...v, kind: k })));

  return (
    <div className="ep-vars-body">
      <p className="me-muted">
        A program can only use a name that has been declared: it reads a sensor, sets an actuator, reads an FMU input.
        Declare here what your programs need; the lists in the editor above come from this. This is separate from the
        Sensors &amp; actuators page: that decides what crosses to the controller, these live inside the model. To send one of
        them to the controller, use &quot;Output to the controller&quot;.
      </p>
      <div className="ep-form">
        <label>Kind
          <select value={kind} onChange={(e) => { setKind(e.target.value); setF({}); }}>
            {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
        <label>Name
          <input value={f.name || ''} onChange={(e) => set({ name: toIdentifier(e.target.value) })} placeholder="my_variable" />
        </label>

        {kind === 'actuator' && (
          <>
            <label>Acts on
              <select value={f.kindId || ''} onChange={(e) => set({ kindId: e.target.value, component: '' })}>
                <option value="">choose…</option>
                {kinds.map((k) => <option key={`${k.type}|${k.control}`} value={`${k.type}|${k.control}`}>{k.type} — {k.control}</option>)}
              </select>
            </label>
            {actKind && (
              <label>Component
                <select value={f.component || actKind.components[0]} onChange={(e) => set({ component: e.target.value })}>
                  {actKind.components.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            )}
          </>
        )}
        {kind === 'sensor' && (
          <>
            <label>Variable
              <select value={f.variableName || ''} onChange={(e) => set({ variableName: e.target.value, key: undefined })}>
                <option value="">choose…</option>
                {variables.map((v) => <option key={v.variableName} value={v.variableName}>{v.variableName}</option>)}
              </select>
            </label>
            {f.variableName && (
              <label>Measured at
                {sensorVar?.keys?.length ? (
                  <select value={f.key ?? sensorVar.keys[0]} onChange={(e) => set({ key: e.target.value })}>
                    {sensorVar.keys.map((k) => <option key={k} value={k}>{k}</option>)}
                  </select>
                ) : <input value={f.key || ''} onChange={(e) => set({ key: e.target.value })} placeholder="key (zone, surface, node…)" />}
              </label>
            )}
          </>
        )}
        {kind === 'fmuInput' && (
          <>
            <label>Initial value
              <input type="number" step="any" value={f.initial ?? 0} onChange={(e) => set({ initial: e.target.value })} />
            </label>
            <label>Min
              <input type="number" step="any" value={f.min ?? ''} onChange={(e) => set({ min: e.target.value })} />
            </label>
            <label>Max
              <input type="number" step="any" value={f.max ?? ''} onChange={(e) => set({ max: e.target.value })} />
            </label>
          </>
        )}
        {kind === 'trend' && (
          <>
            <label>Of variable
              <select value={f.variable || ''} onChange={(e) => set({ variable: e.target.value })}>
                <option value="">choose…</option>
                {everyName.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label>Steps kept
              <input type="number" min="1" value={f.steps ?? 12} onChange={(e) => set({ steps: e.target.value })} />
            </label>
          </>
        )}
        {kind === 'output' && (
          <>
            <label>Variable to send
              <select value={f.variable || ''} onChange={(e) => set({ variable: e.target.value })}>
                <option value="">choose…</option>
                {[...(cat.variables.actuators || []), ...(cat.variables.globals || [])].map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
              </select>
            </label>
            <div className="me-field">
              <span>Role in the controller</span>
              <RoleSwitch value={f.role || 'observation'} onChange={(role) => set({ role })} />
            </div>
          </>
        )}
        <button type="button" className="me-btn me-btn-primary" disabled={busy || !ready} onClick={submit}>{busy ? 'Adding…' : 'Add'}</button>
      </div>
      <p className="me-muted ep-hint">{KINDS.find((k) => k[0] === kind)[2]}
        {kind === 'fmuInput' && ' Measured on EnergyPlus 9.6: the first warm-up step can run with 0 for it, whatever the initial value; skip writing during warm-up with IF WarmupFlag == 0.'}
      </p>

      {declared.length > 0 && (
        <details className="me-details">
          <summary>Declared variables</summary>
          <ul className="me-plain">
            {declared.map((v) => (
              <li key={`${v.kind}:${v.name}`}>
                <code>{v.name}</code> <span className="me-muted">· {v.kind} · {v.source}</span>{' '}
                <button type="button" className="me-btn" disabled={busy} onClick={() => run(() => removeEmsVariable(v.kind, v.name), 'Removed.')}>Remove</button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
