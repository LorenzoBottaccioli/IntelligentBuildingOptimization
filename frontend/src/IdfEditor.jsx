import React, { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import axios from 'axios';
import { api } from './api';
import { AppContext } from './AppContext';
import OutputsView, { cascadeMessage } from './IdfOutputs';
import './IdfEditor.css';

const PAGE = '/idf_editor';

/** One call to the editor API; the message of a failed call is the server's own. */
async function call(method, path, data, params) {
  try {
    const r = await axios({ method, url: api(`/idf_editor${path}`), data, params });
    return r.data;
  } catch (e) {
    const error = new Error(e?.response?.data?.error || e.message);
    error.status = e?.response?.status;
    error.body = e?.response?.data;
    throw error;
  }
}

/**
 * What every tab shares: the generation of the model this page last saw, the
 * banner, and `write`, which sends it with each change so an edit made
 * elsewhere in the meantime is refused instead of overwritten.
 */
function useEditor() {
  const { pathname } = useLocation();
  const { filesUploaded, modelId, sessionKey, fetchIdfObjects } = useContext(AppContext);
  const active = pathname === PAGE;
  const gen = useRef(null);
  const [rev, setRev] = useState(0);
  const [notice, setNotice] = useState(null);

  // Hidden pages stay mounted, so a model changed elsewhere is re-read on arrival.
  useEffect(() => {
    if (active && filesUploaded) setRev((n) => n + 1);
  }, [active, filesUploaded, modelId, sessionKey]);

  const seen = useCallback((g) => { if (typeof g === 'number') gen.current = g; }, []);

  // `onCascade(body)`: when a removal is refused because something reads what it removes, the
  // answer lists those readers; a truthy return (extra fields for the body) sends it again.
  const write = useCallback(async (method, path, body, onCascade) => {
    try {
      const data = await call(method, path, { ...body, generation: gen.current });
      seen(data.generation);
      setNotice(data.warnings && data.warnings.length ? { kind: 'warn', lines: data.warnings } : null);
      setRev((n) => n + 1);
      fetchIdfObjects();
      return data;
    } catch (e) {
      if (onCascade && e.status === 409 && e.body && e.body.needsCascade) {
        const more = onCascade(e.body);
        return more ? write(method, path, { ...body, ...more }) : null;
      }
      setNotice({ kind: 'error', lines: [e.message] });
      if (/Reload/i.test(e.message)) setRev((n) => n + 1);
      return null;
    }
  }, [fetchIdfObjects, seen]);

  return { active, filesUploaded, rev, setRev, seen, write, call, notice, setNotice };
}

// ------------------------------------------------------------------ fields

const BLANK = '';

/** A single field, drawn from the IDD's description of it. */
function FieldRow({ cls, field, value, onChange }) {
  const [options, setOptions] = useState(null);
  const [help, setHelp] = useState(false);
  const listId = `ie-list-${cls}-${field.index}`;
  const lists = !!(field.objectLists && field.objectLists.length) && !field.keys;

  const loadOptions = async () => {
    if (!lists || options) return;
    try {
      const d = await call('get', '/candidates', null, { class: cls, field: field.index });
      setOptions(d.values || []);
    } catch (e) {
      setOptions([]);
    }
  };

  let input;
  if (field.keys) {
    const known = field.keys.some((k) => k.toLowerCase() === value.toLowerCase());
    input = (
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value={BLANK}>{field.default ? `(default: ${field.default})` : '(blank)'}</option>
        {field.keys.map((k) => <option key={k} value={k}>{k}</option>)}
        {value && !known && <option value={value}>{value}</option>}
      </select>
    );
  } else {
    input = (
      <>
        <input
          type="text"
          value={value}
          list={lists ? listId : undefined}
          placeholder={field.default ? `default: ${field.default}` : ''}
          inputMode={field.numeric ? 'decimal' : undefined}
          onFocus={loadOptions}
          onChange={(e) => onChange(e.target.value)}
        />
        {lists && options && (
          <datalist id={listId}>{options.map((o) => <option key={o} value={o} />)}</datalist>
        )}
      </>
    );
  }
  const limits = [];
  if (field.minimum !== undefined) limits.push(`${field.minimumExclusive ? '>' : '≥'} ${field.minimum}`);
  if (field.maximum !== undefined) limits.push(`${field.maximumExclusive ? '<' : '≤'} ${field.maximum}`);
  const flags = [field.autosizable && 'autosize', field.autocalculatable && 'autocalculate'].filter(Boolean);

  return (
    <div className="ie-field">
      <label className="ie-field__label">
        {field.name}
        {field.required && <span className="ie-req" title="Required by the IDD"> *</span>}
      </label>
      <div className="ie-field__input">
        {input}
        {field.units && <span className="ie-unit">{field.units}</span>}
        {(field.notes || limits.length > 0 || flags.length > 0) && (
          <button type="button" className="ie-link" onClick={() => setHelp(!help)} aria-expanded={help}>
            {help ? 'hide' : 'help'}
          </button>
        )}
      </div>
      {help && (
        <div className="ie-field__help">
          {(field.notes || []).map((n, i) => <p key={i}>{n}</p>)}
          {limits.length > 0 && <p>Range: {limits.join(', ')}{field.units ? ` ${field.units}` : ''}</p>}
          {flags.length > 0 && <p>Accepts: {flags.join(', ')}</p>}
        </div>
      )}
    </div>
  );
}

/** A form for the fields of one object. Saves only what was changed. */
function ObjectForm({ spec, values, only, skip, saveLabel, onSave, onCancel, busy }) {
  const [draft, setDraft] = useState({});
  useEffect(() => setDraft({}), [values, spec.name]);

  const lead = useMemo(() => {
    const b = spec.fields.find((f) => f.beginExtensible);
    return b ? b.index : spec.fields.length;
  }, [spec]);
  const count = only ? spec.fields.length : (
    spec.extensible && spec.fields.length > 60
      ? Math.min(spec.fields.length, Math.max(values.length + spec.extensible, lead))
      : spec.fields.length);
  const fields = spec.fields.slice(0, count)
    .filter((f) => (!only || only.includes(f.index)) && !(skip && skip.includes(f.index)));
  const changed = Object.keys(draft).length;
  const current = (f) => (draft[f.index] !== undefined ? draft[f.index] : (values[f.index] || ''));

  return (
    <form className="ie-form" onSubmit={(e) => { e.preventDefault(); if (changed) onSave(draft); }}>
      {fields.map((f) => (
        <FieldRow
          key={f.index}
          cls={spec.name}
          field={f}
          value={current(f)}
          onChange={(v) => setDraft((d) => {
            const n = { ...d };
            if (v === (values[f.index] || '')) delete n[f.index]; else n[f.index] = v;
            return n;
          })}
        />
      ))}
      <div className="ie-form__actions">
        <button type="submit" className="ie-primary" disabled={!changed || busy}>
          {saveLabel || 'Save'}{changed ? ` (${changed} field${changed > 1 ? 's' : ''})` : ''}
        </button>
        {onCancel && <button type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

// ------------------------------------------------------- one class, objects

/** The objects of a class: list, form, add / duplicate / rename / delete. */
function ClassEditor({ ed, className }) {
  const [spec, setSpec] = useState(null);
  const [list, setList] = useState({ total: 0, objects: [] });
  const [query, setQuery] = useState('');
  const [sel, setSel] = useState(null); // an object entry, or 'new'
  const [action, setAction] = useState(null); // {kind:'delete'|'rename', ...}
  const [error, setError] = useState('');

  const loadSpec = useCallback(async (upto) => {
    try {
      setSpec(await call('get', '/class', null, { name: className, upto }));
    } catch (e) { setError(e.message); }
  }, [className]);

  useEffect(() => { setSel(null); setAction(null); setQuery(''); setSpec(null); loadSpec(); }, [className, loadSpec]);

  useEffect(() => {
    let live = true;
    if (!ed.active || !ed.filesUploaded) return undefined;
    call('get', '/objects', null, { class: className, q: query, limit: 300 })
      .then((d) => { if (live) { setList(d); ed.seen(d.generation); setError(''); } })
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [className, query, ed.rev, ed.active, ed.filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // An object longer than the fields sent: ask for the rest.
  useEffect(() => {
    if (spec && sel && sel !== 'new' && sel.values.length > spec.fields.length && spec.fieldCount > spec.fields.length) {
      loadSpec(sel.values.length + spec.extensible);
    }
  }, [sel]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the selection pointing at the refreshed copy of the same object.
  useEffect(() => {
    if (sel && sel !== 'new') {
      const fresh = list.objects.find((o) => o.index === sel.index && o.label === sel.label);
      if (fresh && fresh.values.join('|') !== sel.values.join('|')) setSel(fresh);
    }
  }, [list]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error && !spec) return <p className="ie-error">{error}</p>;
  if (!spec) return <p className="muted">Loading…</p>;

  const save = async (draft) => {
    if (sel === 'new') {
      const r = await ed.write('post', '/object', { class: className, values: draft });
      if (r) {
        setSel(null);
      }
    } else {
      await ed.write('patch', '/object', { class: className, index: sel.index, label: sel.label, values: draft });
    }
  };
  const startDelete = async () => {
    let referrers = [];
    try {
      referrers = (await call('get', '/referrers', null, { class: className, index: sel.index, label: sel.label })).referrers;
    } catch (e) { /* the delete itself will say */ }
    setAction({ kind: 'delete', referrers });
  };
  const doDelete = async () => {
    const r = await ed.write('delete', '/object', { class: className, index: sel.index, label: sel.label });
    if (r) { setSel(null); setAction(null); }
  };
  const doRename = async () => {
    const r = await ed.write('post', '/object/rename', {
      class: className, index: sel.index, label: sel.label, newName: action.value });
    if (r) { setSel(null); setAction(null); }
  };
  const duplicate = async () => {
    await ed.write('post', '/object/duplicate', { class: className, index: sel.index, label: sel.label });
  };
  const canAdd = !(spec.unique && list.total > 0);
  const namedByReference = spec.fields[0] && spec.fields[0].references;

  return (
    <div className="ie-class">
      <header className="ie-class__head">
        <h2>{spec.name}</h2>
        <p className="muted">{spec.group}{spec.unique ? ' · only one allowed' : ''}</p>
        {spec.memo.length > 0 && <p className="ie-memo">{spec.memo.join(' ')}</p>}
      </header>

      <div className="ie-class__body">
        <div className="ie-list">
          <div className="ie-list__tools">
            <input type="search" placeholder="Filter objects" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button type="button" disabled={!canAdd} onClick={() => { setSel('new'); setAction(null); }}>
              New {spec.unique ? '' : 'object'}
            </button>
          </div>
          {list.objects.length === 0 && <p className="muted">{query ? 'No match.' : 'No objects of this class in the model.'}</p>}
          <ul>
            {list.objects.map((o) => (
              <li key={o.index}>
                <button
                  type="button"
                  className={`ie-row ${sel && sel !== 'new' && sel.index === o.index ? 'is-active' : ''}`}
                  onClick={() => { setSel(o); setAction(null); }}
                >
                  <strong>{o.label || '(unnamed)'}</strong>
                  {o.managed && <span className="ie-tag" title="Written by the platform (FMU / EMS)">platform</span>}
                  <span className="ie-row__sub">{o.values.slice(1, 4).filter(Boolean).join(' · ')}</span>
                </button>
              </li>
            ))}
          </ul>
          {list.total > list.objects.length && <p className="muted">Showing {list.objects.length} of {list.total}; filter to narrow.</p>}
        </div>

        <div className="ie-detail">
          {!sel && <p className="muted">Choose an object, or create a new one.</p>}
          {sel && (
            <>
              {sel !== 'new' && (
                <div className="ie-detail__actions">
                  {!spec.unique && <button type="button" onClick={duplicate}>Duplicate</button>}
                  {namedByReference && (
                    <button type="button" onClick={() => setAction({ kind: 'rename', value: sel.label })}>Rename</button>
                  )}
                  <button type="button" className="ie-danger" onClick={startDelete}>Delete</button>
                </div>
              )}
              {action && action.kind === 'rename' && (
                <div className="ie-inline">
                  <span>New name (every reference follows):</span>
                  <input value={action.value} onChange={(e) => setAction({ ...action, value: e.target.value })} />
                  <button type="button" className="ie-primary" onClick={doRename}>Rename</button>
                  <button type="button" onClick={() => setAction(null)}>Cancel</button>
                </div>
              )}
              {action && action.kind === 'delete' && (
                <div className="ie-inline ie-inline--danger">
                  <span>
                    Delete {sel.label || spec.name}?
                    {action.referrers.length > 0 && (
                      <> {action.referrers.length} object(s) still refer to it:{' '}
                        {[...new Set(action.referrers.map((r) => `${r.class} / ${r.field}`))].join(', ')}.</>
                    )}
                  </span>
                  <button type="button" className="ie-danger" onClick={doDelete}>Delete</button>
                  <button type="button" onClick={() => setAction(null)}>Keep</button>
                </div>
              )}
              <ObjectForm
                spec={spec}
                values={sel === 'new' ? [] : sel.values}
                saveLabel={sel === 'new' ? 'Create' : 'Save'}
                onSave={save}
                onCancel={sel === 'new' ? () => setSel(null) : undefined}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------ all classes

function ClassBrowser({ ed }) {
  const [groups, setGroups] = useState(null);
  const [filter, setFilter] = useState('');
  const [onlyUsed, setOnlyUsed] = useState(true);
  const [current, setCurrent] = useState('');

  useEffect(() => {
    if (!ed.active || !ed.filesUploaded) return;
    call('get', '/overview').then((d) => { setGroups(d.groups); ed.seen(d.generation); }).catch(() => setGroups([]));
  }, [ed.rev, ed.active, ed.filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  const low = filter.trim().toLowerCase();
  const visible = (groups || []).map((g) => ({
    ...g,
    classes: g.classes.filter((c) => (!onlyUsed || c.count > 0 || c.name === current)
      && (!low || c.name.toLowerCase().includes(low))),
  })).filter((g) => g.classes.length);

  return (
    <div className="ie-browser">
      <aside className="ie-tree">
        <input type="search" placeholder="Find a class" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <label className="ie-check">
          <input type="checkbox" checked={onlyUsed} onChange={(e) => setOnlyUsed(e.target.checked)} />
          Only classes with objects
        </label>
        {visible.map((g) => (
          <details key={g.name} open={!!low || g.classes.some((c) => c.name === current)}>
            <summary>{g.name}</summary>
            <ul>
              {g.classes.map((c) => (
                <li key={c.name}>
                  <button
                    type="button"
                    title={c.memo}
                    className={`ie-class-link ${current === c.name ? 'is-active' : ''}`}
                    onClick={() => setCurrent(c.name)}
                  >
                    <span>{c.name}</span>
                    <em>{c.count || ''}</em>
                  </button>
                </li>
              ))}
            </ul>
          </details>
        ))}
        {groups === null && <p className="muted">Loading…</p>}
        {groups !== null && visible.length === 0 && <p className="muted">No class matches.</p>}
      </aside>
      <section className="ie-main">
        {current ? <ClassEditor ed={ed} className={current} /> : (
          <p className="muted">
            Every EnergyPlus class is here, grouped as in the Input Output Reference. Each field shows the units, range, keys and notes
            the IDD declares for it.
          </p>
        )}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ comfort

function OutputList({ ed, title, items, frequencies, frequency, setFrequency, reports, onAdd, chosenReports, setChosenReports, source }) {
  const absent = items.filter((v) => !v.present);
  const [busy, setBusy] = useState(false);

  // The dot switches one variable. Off: every Output:Variable of that name goes, whatever its key. An FMU
  // output that reads it as its only source goes with it, after asking (the Outputs tab does the same).
  const toggle = async (v) => {
    setBusy(true);
    try {
      if (!v.present) {
        await ed.write('post', '/outputs/add', { variables: [v.name], reports: [], frequency });
        return;
      }
      const d = await ed.call('get', '/outputs');
      ed.seen(d.generation);
      const mine = d.variables.filter((r) => r.name.toLowerCase() === v.name.toLowerCase());
      if (!mine.length) return;
      await ed.write('delete', '/outputs/request',
        { requests: mine.map((r) => ({ class: r.class, index: r.index, name: r.name, key: r.key })) },
        (body) => (window.confirm(cascadeMessage(body)) ? { cascade: true } : null));
    } catch (e) {
      ed.setNotice({ kind: 'error', lines: [e.message] });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="ie-card">
      <h3>{title}</h3>
      <ul className="ie-vars">
        {items.map((v) => (
          <li key={v.name}>
            <button type="button" className={`ie-dot ${v.present ? 'is-on' : ''}`} disabled={busy} aria-pressed={v.present}
              aria-label={`${v.present ? 'Stop reporting' : 'Report'} ${v.name}`}
              title={v.present
                ? 'Reported in the model. Click to stop reporting it (an FMU output that reads it goes too, after asking).'
                : 'Not reported yet. Click to report it.'}
              onClick={() => toggle(v)} />
            {v.name}{v.units ? <em> [{v.units}]</em> : null}
          </li>
        ))}
        {items.length === 0 && <li className="muted">Nothing to report yet.</li>}
      </ul>
      {items.length > 0 && <p className="ie-memo">Click a dot to switch that variable on or off in the model.</p>}
      {reports && reports.length > 0 && (
        <div className="ie-reports">
          <span>Summary reports (tabular output):</span>
          {reports.map((r) => (
            <label key={r.key} className="ie-check">
              <input
                type="checkbox"
                disabled={r.present}
                checked={r.present || chosenReports.includes(r.key)}
                onChange={(e) => setChosenReports(e.target.checked
                  ? [...chosenReports, r.key] : chosenReports.filter((k) => k !== r.key))}
              />
              {r.key}{r.present ? ' (in model)' : ''}
            </label>
          ))}
        </div>
      )}
      <div className="ie-inline">
        <label>Reporting frequency
          <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            {frequencies.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <button
          type="button"
          className="ie-primary"
          disabled={absent.length === 0 && chosenReports.length === 0}
          onClick={() => onAdd(absent.map((v) => v.name))}
        >
          Report {absent.length} variable{absent.length === 1 ? '' : 's'}
        </button>
      </div>
      <p className="ie-source">{source}</p>
    </section>
  );
}

function useFrequencies() {
  const [list, setList] = useState(['Timestep']);
  useEffect(() => {
    call('get', '/class', null, { name: 'Output:Variable' }).then((d) => {
      const f = d.fields.find((x) => x.name === 'Reporting Frequency');
      if (f && f.keys) setList(f.keys);
    }).catch(() => {});
  }, []);
  return list;
}

const COMFORT_PREFIX = 'Zone Thermal Comfort ';
const COMFORT_HELP = {
  'Zone Thermal Comfort Fanger Model PMV': 'Predicted Mean Vote: how the average occupant would rate the thermal sensation. 0 means the body loses exactly the heat it produces; positive is warmer, negative cooler (the variable ranges from −4 to 4).',
  'Zone Thermal Comfort Fanger Model PPD': 'Predicted Percentage of Dissatisfied: the share of occupants who would be uncomfortable, from 5 % (at PMV 0) to 100 %. It follows from the PMV, so both move together.',
};

/**
 * Step 3 of the comfort view: export what the comfort models compute as sensors for the
 * controller. A comfort variable is reported per People object, not per zone, and EnergyPlus
 * only lists it once the model is in the file and the model has been checked.
 */
function ComfortSensors({ ed, data }) {
  const { idfObjects, fetchIdfObjects, addDirectVariable, removeDirectVariable, setFmuRole } = useContext(AppContext);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (ed.active && ed.filesUploaded && !idfObjects) fetchIdfObjects(); },
    [ed.active, ed.filesUploaded, idfObjects, fetchIdfObjects]);

  const catalogue = {};
  ((idfObjects && idfObjects.rdd_variables) || []).forEach((v) => { catalogue[v.variableName] = v.keys || []; });
  const exported = {};
  ((idfObjects && idfObjects.current_fmu_from_variables) || []).forEach((v) => {
    exported[`${v.outputVariableName}|${String(v.outputVariableIndexKeyName).toUpperCase()}`] = v;
  });
  const active = new Set(data.people.flatMap((p) => p.models));
  const groups = data.models.filter((m) => active.has(m.key))
    .map((m) => ({ title: m.key, items: m.variables }));
  if (groups.length) groups.push({ title: 'Common to the models', items: data.common });

  const run = async (fn) => {
    setBusy(true);
    try { await fn(); } catch (e) {
      ed.setNotice({ kind: 'error', lines: [e?.response?.data?.details || e?.response?.data?.error || e.message] });
    } finally { setBusy(false); }
  };
  const fmuName = (variable, key) => toIdentifier(`${variable.replace(COMFORT_PREFIX, '')}_${key}`).toLowerCase();
  const add = (variable, key) => run(async () => {
    const name = fmuName(variable, key);
    const r = await addDirectVariable({ indexKey: key, variableName: variable, fmuVariableName: name });
    await setFmuRole({ fmuVariableName: r.fmuVariableName || name, role: 'observation' });
  });
  const remove = (variable, key) => run(() => removeDirectVariable(exported[`${variable}|${key.toUpperCase()}`].fmuVariableName));

  const row = (v) => {
    const keys = catalogue[v.name];
    return (
      <li key={v.name} className="ie-sensor">
        <div className="ie-sensor__head">
          <strong>{v.name.replace(COMFORT_PREFIX, '')}</strong>{v.units ? <em> [{v.units}]</em> : null}
        </div>
        {COMFORT_HELP[v.name] && <p className="ie-memo">{COMFORT_HELP[v.name]}</p>}
        {!keys ? <p className="muted">Not listed by EnergyPlus yet: press Check model.</p> : (
          <table className="ie-table">
            <tbody>
              {keys.map((k) => {
                const done = exported[`${v.name}|${k.toUpperCase()}`];
                return (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{done ? <code>{done.fmuVariableName}</code> : <span className="muted">not exported</span>}</td>
                    <td>
                      {done
                        ? <button type="button" disabled={busy} onClick={() => remove(v.name, k)}>Remove</button>
                        : <button type="button" className="ie-primary" disabled={busy} onClick={() => add(v.name, k)}>Export as sensor</button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </li>
    );
  };

  return (
    <section className="ie-card">
      <h3>3 · Comfort sensors for the controller</h3>
      <p className="ie-memo">
        A comfort index becomes an input of the exported building (an FMU output, role: observation), so your gateway can
        publish it as a sensor, for instance the PMV of an office. Each row is one People object: the key is its name
        (EnergyPlus writes it in capitals), and it covers the occupants of that zone. Exports also appear in Sensors &amp; actuators.
      </p>
      <details className="ie-explain">
        <summary>How to read PMV and PPD</summary>
        <p>
          The Fanger model compares the heat the occupants produce with the heat they lose to the room, using air and
          radiant temperature, humidity, air speed, clothing and activity (EnergyPlus Engineering Reference, p. 1501–1503).
        </p>
        <p>
          <strong>PMV</strong> turns that balance into a thermal sensation vote: 0 is neutral, positive is warm, negative is cool.
          <strong> PPD</strong> is the percentage of people expected to be dissatisfied at that PMV; it never goes below 5 %.
        </p>
        <p>
          These are averages for a typical occupant, computed at every time step from the schedules of the People object
          (activity, clothing, air velocity). They are only as realistic as those schedules.
        </p>
      </details>
      {groups.length === 0 ? (
        <p className="muted">Choose and apply at least one model above; its variables will be listed here.</p>
      ) : groups.map((g) => (
        <details key={g.title} open={g.title === 'Fanger'} className="ie-group">
          <summary>{g.title}</summary>
          <ul className="ie-sensors">{g.items.map(row)}</ul>
        </details>
      ))}
    </section>
  );
}

function ComfortView({ ed }) {
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState({}); // People index -> [model keys]
  const [open, setOpen] = useState(null);
  const [alsoOutputs, setAlsoOutputs] = useState(true);
  const [frequency, setFrequency] = useState('Timestep');
  const [chosenReports, setChosenReports] = useState([]);
  const frequencies = useFrequencies();

  useEffect(() => {
    if (!ed.active || !ed.filesUploaded) return;
    call('get', '/comfort').then((d) => { setData(d); ed.seen(d.generation); setDraft({}); })
      .catch((e) => ed.setNotice({ kind: 'error', lines: [e.message] }));
  }, [ed.rev, ed.active, ed.filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return <p className="muted">Loading…</p>;
  if (data.people.length === 0) {
    return (
      <p className="muted">
        This model has no People object, so no comfort model can be attached to it. Create one in All classes → People
        (it needs a zone, an occupancy schedule and an activity schedule).
      </p>
    );
  }
  const keys = data.models.map((m) => m.key);
  const modelsOf = (p) => (draft[p.index] || p.models);
  const toggle = (p, key, on) => {
    const set = new Set(modelsOf(p));
    if (on) set.add(key); else set.delete(key);
    const next = keys.filter((k) => set.has(k));
    setDraft((d) => {
      const n = { ...d };
      if (next.join('|') === p.models.join('|')) delete n[p.index]; else n[p.index] = next;
      return n;
    });
  };
  const column = (key, on) => data.people.forEach((p) => toggle(p, key, on));
  const dirty = Object.keys(draft);

  const apply = async () => {
    const groups = {};
    dirty.forEach((i) => { (groups[draft[i].join('|')] = groups[draft[i].join('|')] || []).push(Number(i)); });
    for (const [models, indexes] of Object.entries(groups)) {
      // eslint-disable-next-line no-await-in-loop
      const r = await ed.write('post', '/comfort/models', {
        indexes, models: models ? models.split('|') : [], addOutputs: alsoOutputs, frequency });
      if (!r) return;
    }
  };

  const shown = [...new Set(data.people.flatMap(modelsOf))];
  const outputs = [...shown.flatMap((k) => (data.models.find((m) => m.key === k) || { variables: [] }).variables), ...data.common];
  const uniqueOutputs = outputs.filter((v, i) => outputs.findIndex((w) => w.name === v.name) === i);
  const addOutputs = (names) => ed.write('post', '/outputs/add', { variables: names, reports: chosenReports, frequency })
    .then(() => setChosenReports([]));
  const detail = data.people.find((p) => p.index === open);
  const slotSet = new Set(data.slots);
  const comfortFields = data.class.fields.map((f) => f.index).filter((i) => i >= data.fieldsFrom && !slotSet.has(i));

  return (
    <div className="ie-comfort">
      <p className="ie-lead">
        A People object attaches up to {data.slots.length} comfort models to a zone&apos;s occupants; each model reports its
        own variables. Tick the models you want per People object.
      </p>

      <div className="ie-matrix-wrap">
        <table className="ie-matrix">
          <thead>
            <tr>
              <th>People object</th>
              {keys.map((k) => (
                <th key={k}>
                  <span>{k}</span>
                  <span className="ie-col-tools">
                    <button type="button" className="ie-link" onClick={() => column(k, true)}>all</button>
                    <button type="button" className="ie-link" onClick={() => column(k, false)}>none</button>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.people.map((p) => (
              <tr key={p.index} className={draft[p.index] ? 'is-dirty' : ''}>
                <th scope="row">
                  <button type="button" className="ie-link ie-link--strong" onClick={() => setOpen(open === p.index ? null : p.index)}>
                    {p.name || '(unnamed)'}
                  </button>
                  <span className="ie-row__sub">{p.zone}</span>
                  {p.missing.length > 0 && <span className="ie-tag ie-tag--warn" title="Inputs the chosen models need are blank">needs input</span>}
                  {p.duplicates.length > 0 && <span className="ie-tag ie-tag--warn">duplicate model</span>}
                  {p.unknownModels.length > 0 && <span className="ie-tag ie-tag--warn" title={p.unknownModels.join(', ')}>unknown model</span>}
                </th>
                {keys.map((k) => (
                  <td key={k}>
                    <input
                      type="checkbox"
                      aria-label={`${k} for ${p.name}`}
                      checked={modelsOf(p).includes(k)}
                      onChange={(e) => toggle(p, k, e.target.checked)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="ie-inline">
        <label className="ie-check">
          <input type="checkbox" checked={alsoOutputs} onChange={(e) => setAlsoOutputs(e.target.checked)} />
          Also request the variables of the chosen models
        </label>
        <button type="button" className="ie-primary" disabled={dirty.length === 0} onClick={apply}>
          Apply to {dirty.length} People object{dirty.length === 1 ? '' : 's'}
        </button>
        <button type="button" disabled={dirty.length === 0} onClick={() => setDraft({})}>Discard</button>
      </div>

      {data.controlObjects.length > 0 && (
        <p className="ie-note">
          Control objects built on thermal comfort exist in this model ({data.controlObjects.map((c) => `${c.class} ×${c.count}`).join(', ')});
          removing a model they use will break them.
        </p>
      )}

      {detail && (
        <section className="ie-card">
          <h3>Comfort inputs of {detail.name}</h3>
          {detail.missing.map((m) => (
            <p key={m.field} className="ie-note">
              {m.name} is blank, and {m.neededBy.join(', ')} {m.neededBy.length > 1 ? 'need' : 'needs'} it
              (IDD note of that field).
            </p>
          ))}
          <ObjectForm
            spec={data.class}
            values={detail.values}
            only={comfortFields}
            saveLabel="Save comfort inputs"
            onSave={(d) => ed.write('patch', '/object', { class: 'People', index: detail.index, label: detail.name, values: d })}
          />
        </section>
      )}

      <ComfortSensors ed={ed} data={data} />

      <OutputList
        ed={ed}
        title="4 · Report the variables in the model"
        items={uniqueOutputs}
        frequencies={frequencies}
        frequency={frequency}
        setFrequency={setFrequency}
        reports={data.reports}
        chosenReports={chosenReports}
        setChosenReports={setChosenReports}
        onAdd={addOutputs}
        source={data.source}
      />
    </div>
  );
}

// ---------------------------------------------------------------------- CO2

const CO2_VARIABLE = 'Zone Air CO2 Concentration';
const toIdentifier = (raw) => {
  const cleaned = (raw || '').trim().replace(/[^0-9a-zA-Z_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
  if (!cleaned) return '';
  return /^\d/.test(cleaned) ? `v_${cleaned}` : cleaned;
};

/**
 * Step 3 of the CO2 view: export the zone CO2 concentration to the controller as a
 * sensor. It is the platform's own "direct" export (no EMS objects), the same one the
 * Sensors & actuators page makes, so the zones listed are the keys EnergyPlus reported
 * at the last Check model, and what is exported shows up there too.
 */
function Co2Sensor({ ed, enabled }) {
  const { idfObjects, fetchIdfObjects, addDirectVariable, removeDirectVariable, setFmuRole } = useContext(AppContext);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (ed.active && ed.filesUploaded && !idfObjects) fetchIdfObjects(); },
    [ed.active, ed.filesUploaded, idfObjects, fetchIdfObjects]);

  const entry = ((idfObjects && idfObjects.rdd_variables) || []).find((v) => v.variableName === CO2_VARIABLE);
  const zones = (entry && entry.keys) || [];
  const exported = ((idfObjects && idfObjects.current_fmu_from_variables) || [])
    .filter((v) => v.outputVariableName === CO2_VARIABLE);
  const byZone = {};
  exported.forEach((v) => { byZone[String(v.outputVariableIndexKeyName).toUpperCase()] = v; });

  const run = async (fn) => {
    setBusy(true);
    try { await fn(); } catch (e) {
      ed.setNotice({ kind: 'error', lines: [e?.response?.data?.details || e?.response?.data?.error || e.message] });
    } finally { setBusy(false); }
  };
  const add = (zone) => run(async () => {
    const name = toIdentifier(`co2_${zone}`).toLowerCase();
    const r = await addDirectVariable({ indexKey: zone, variableName: CO2_VARIABLE, fmuVariableName: name });
    await setFmuRole({ fmuVariableName: r.fmuVariableName || name, role: 'observation' });
  });
  const remove = (zone) => run(() => removeDirectVariable(byZone[zone.toUpperCase()].fmuVariableName));
  const addAll = () => run(async () => {
    for (const z of zones) {
      if (byZone[z.toUpperCase()]) continue;
      const name = toIdentifier(`co2_${z}`).toLowerCase();
      // eslint-disable-next-line no-await-in-loop
      const r = await addDirectVariable({ indexKey: z, variableName: CO2_VARIABLE, fmuVariableName: name });
      // eslint-disable-next-line no-await-in-loop
      await setFmuRole({ fmuVariableName: r.fmuVariableName || name, role: 'observation' });
    }
  });

  let body;
  if (!enabled) {
    body = <p className="muted">Switch the CO2 balance on first: EnergyPlus lists no CO2 variable without it.</p>;
  } else if (!entry) {
    body = (
      <p className="ie-note">
        EnergyPlus has not listed {CO2_VARIABLE} yet: the variable list is made when the model is checked.
        Press <strong>Check model</strong> (top right) and this table fills in.
      </p>
    );
  } else {
    body = (
      <>
        <table className="ie-table">
          <thead><tr><th>Zone</th><th>Controller input</th><th /></tr></thead>
          <tbody>
            {zones.map((z) => {
              const done = byZone[z.toUpperCase()];
              return (
                <tr key={z}>
                  <td>{z}</td>
                  <td>{done ? <code>{done.fmuVariableName}</code> : <span className="muted">not exported</span>}</td>
                  <td>
                    {done
                      ? <button type="button" disabled={busy} onClick={() => remove(z)}>Remove</button>
                      : <button type="button" className="ie-primary" disabled={busy} onClick={() => add(z)}>Export as sensor</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="ie-inline">
          <button type="button" disabled={busy || zones.every((z) => byZone[z.toUpperCase()])} onClick={addAll}>Export every zone</button>
          <span className="muted">The sensor reads {CO2_VARIABLE} [ppm] directly; nothing is added to the model but the export.</span>
        </div>
      </>
    );
  }
  return (
    <section className="ie-card">
      <h3>3 · CO2 sensor for the controller</h3>
      <p className="ie-memo">
        The zone CO2 concentration becomes an input of the exported building (an FMU output, role: observation),
        so your gateway can publish it like a real CO2 sensor. It is listed in Sensors &amp; actuators too.
      </p>
      {body}
    </section>
  );
}

function Co2View({ ed }) {
  const [data, setData] = useState(null);
  const [schedule, setSchedule] = useState('');
  const [mode, setMode] = useState('existing');
  const [created, setCreated] = useState({ name: 'Outdoor CO2', value: '' });
  const [levelDraft, setLevelDraft] = useState(null);
  const [options, setOptions] = useState([]);
  const [frequency, setFrequency] = useState('Timestep');
  const [chosenReports, setChosenReports] = useState([]);
  const frequencies = useFrequencies();

  useEffect(() => {
    if (!ed.active || !ed.filesUploaded) return;
    call('get', '/co2').then((d) => {
      setData(d); ed.seen(d.generation);
      setSchedule(d.balance ? d.balance.schedule : '');
      setLevelDraft(null);
      return call('get', '/candidates', null, { class: 'ZoneAirContaminantBalance', field: d.scheduleIndex });
    }).then((d) => setOptions(d.values || []))
      .catch((e) => ed.setNotice({ kind: 'error', lines: [e.message] }));
  }, [ed.rev, ed.active, ed.filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return <p className="muted">Loading…</p>;
  const balanceNotes = data.balanceClass.fields.find((f) => f.name === 'Carbon Dioxide Concentration');
  const outdoorNotes = data.balanceClass.fields.find((f) => f.name.startsWith('Outdoor Carbon Dioxide'));
  const enabled = !!(data.balance && data.balance.enabled);
  const level = data.outdoorSchedule;

  const setBalance = (on) => {
    const body = { enabled: on };
    if (on && mode === 'new') {
      body.createSchedule = { name: created.name, value: created.value };
    } else if (schedule) {
      body.schedule = schedule;
    }
    return ed.write('post', '/co2/balance', body);
  };

  return (
    <div className="ie-co2">
      <p className="ie-lead">
        Indoor CO2 is a zone mass balance: occupants and other sources add CO2, outdoor-air exchange dilutes it. It is
        simulated only when the model contains ZoneAirContaminantBalance with Carbon Dioxide Concentration = Yes.
        Three things set the result: what produces CO2 (step 2), how much outdoor air comes in (the model&apos;s
        ventilation, infiltration or HVAC) and the CO2 that air carries (step 1, outdoor schedule).
      </p>

      <section className="ie-card">
        <h3>1 · CO2 balance</h3>
        <div className="ie-switch">
          <span className={`ie-pill ${enabled ? 'is-on' : ''}`}>{enabled ? 'On' : 'Off'}</span>
          <span>{data.balance ? 'ZoneAirContaminantBalance exists' : 'No ZoneAirContaminantBalance in this model'}</span>
        </div>
        {balanceNotes && (balanceNotes.notes || []).map((n, i) => <p key={i} className="ie-memo">{n}</p>)}
        <details className="ie-explain">
          <summary>What is the outdoor CO2 schedule?</summary>
          <p>
            The air that enters a zone (infiltration, ventilation, outdoor air from the HVAC) carries the CO2 of the
            outdoors. EnergyPlus needs that value at every time step, and it reads it from this schedule, in ppm.
          </p>
          <p>
            Think of it as the floor of the zone&apos;s CO2: people push the concentration up, fresh air pulls it back
            towards the outdoor value, and it can never fall below it. With no air exchange at all nothing pulls it down.
          </p>
          <p>
            <strong>Constant level</strong> means one fixed value all year (the editor creates a Schedule:Constant for
            it). <strong>Use a schedule</strong> picks an existing schedule, for example one that follows the traffic
            near the building. The course models use about 430 ppm.
          </p>
          <p>
            This is the outdoor CO2, not the setpoint to keep indoors. The field is optional in the IDD and the
            documentation does not say what EnergyPlus does when it is blank, so fill it in.
          </p>
        </details>
        <div className="ie-field">
          <span className="ie-field__label">{outdoorNotes.name}</span>
          <div className="ie-seg" role="group" aria-label="Outdoor CO2 schedule">
            <button type="button" className={mode === 'existing' ? 'is-active' : ''} onClick={() => setMode('existing')}>Use a schedule</button>
            <button type="button" className={mode === 'new' ? 'is-active' : ''} onClick={() => setMode('new')}>Constant level</button>
          </div>
          {mode === 'existing' ? (
            <>
              <input list="ie-co2-sched" value={schedule} onChange={(e) => setSchedule(e.target.value)} placeholder="schedule name" />
              <datalist id="ie-co2-sched">{options.map((o) => <option key={o} value={o} />)}</datalist>
            </>
          ) : (
            <div className="ie-inline">
              <input value={created.name} onChange={(e) => setCreated({ ...created, name: e.target.value })} aria-label="New schedule name" />
              <input value={created.value} inputMode="decimal" placeholder="level" onChange={(e) => setCreated({ ...created, value: e.target.value })} aria-label="Outdoor CO2 level" />
              <span className="ie-unit">ppm</span>
            </div>
          )}
          {(outdoorNotes.notes || []).map((n, i) => <p key={i} className="ie-memo">{n}</p>)}
        </div>
        {level && (
          <div className="ie-inline">
            <label>Level of {level.label} (ppm)
              <input value={levelDraft !== null ? levelDraft : level.value} inputMode="decimal"
                onChange={(e) => setLevelDraft(e.target.value)} />
            </label>
            <button type="button" disabled={levelDraft === null || levelDraft === level.value}
              onClick={async () => {
                const r = await ed.write('patch', '/object', {
                  class: 'Schedule:Constant', index: level.index, label: level.label,
                  values: { [level.valueIndex]: levelDraft } });
                if (r) setLevelDraft(null);
              }}>Save level</button>
            {level.sharedWith > 0 && (
              <span className="ie-note">This schedule is also used by {level.sharedWith} other object(s): changing it changes them too.</span>
            )}
          </div>
        )}
        {data.balance && data.balance.schedule && !level && (
          <p className="ie-note">
            {data.balance.schedule} is not a constant schedule: edit its values in All classes (Schedule:Compact and the other
            schedule types), or switch to Constant level above.
          </p>
        )}
        <div className="ie-inline">
          <button type="button" className="ie-primary" onClick={() => setBalance(true)}>
            {enabled ? 'Update the balance' : 'Switch CO2 on'}
          </button>
          {data.balance && <button type="button" disabled={!enabled} onClick={() => setBalance(false)}>Switch CO2 off</button>}
        </div>
      </section>

      <section className="ie-card">
        <h3>2 · What produces CO2 in each zone</h3>
        <p className="ie-memo">
          Per People object: {data.rateField.name} ({data.rateField.units}), the rate per unit of activity level.
          {data.rateField.default ? ` Blank means the IDD default, ${data.rateField.default}.` : ''}
          {data.rateField.maximum !== undefined ? ` The IDD maximum is ${data.rateField.maximum}.` : ''}
        </p>
        <table className="ie-table">
          <thead><tr><th>People object</th><th>Zone</th><th>{data.rateField.name}</th><th /></tr></thead>
          <tbody>
            {data.people.map((p) => <RateRow key={p.index} ed={ed} p={p} field={data.rateField} />)}
          </tbody>
        </table>
        {data.people.length === 0 && <p className="muted">No People object in the model.</p>}
        <p className="ie-note">
          Other sources and sinks: {data.sourceClass} ({data.sourceCount} in the model) — edit them in All classes.
          ZoneControl:ContaminantController: {data.controllerCount}; Controller:MechanicalVentilation: {data.ventilationCount}{' '}
          (demand-controlled ventilation is documented but not edited here).
        </p>
      </section>

      <Co2Sensor ed={ed} enabled={enabled} />

      <OutputList
        ed={ed}
        title="4 · Report the variables in the model"
        items={data.variables}
        frequencies={frequencies}
        frequency={frequency}
        setFrequency={setFrequency}
        reports={data.reports}
        chosenReports={chosenReports}
        setChosenReports={setChosenReports}
        onAdd={(names) => ed.write('post', '/outputs/add', { variables: names, reports: chosenReports, frequency })
          .then(() => setChosenReports([]))}
        source={data.source}
      />
    </div>
  );
}

function RateRow({ ed, p, field }) {
  const [value, setValue] = useState(p.rate);
  useEffect(() => setValue(p.rate), [p.rate]);
  const save = () => ed.write('patch', '/object', {
    class: 'People', index: p.index, label: p.name, values: { [field.index]: value } });
  return (
    <tr>
      <td>{p.name}</td>
      <td>{p.zone}</td>
      <td><input value={value} placeholder={field.default ? `default: ${field.default}` : ''} onChange={(e) => setValue(e.target.value)} /></td>
      <td><button type="button" disabled={value === p.rate} onClick={save}>Save</button></td>
    </tr>
  );
}

// ---------------------------------------------------------------- the check

function CheckModel({ ed }) {
  const [state, setState] = useState({ state: 'idle' });
  const timer = useRef(null);
  const { fetchIdfObjects } = useContext(AppContext);

  const poll = useCallback(async () => {
    try {
      const s = await call('get', '/check/status');
      setState(s);
      if (s.state === 'running') timer.current = setTimeout(poll, 3000);
      else { ed.setRev((n) => n + 1); fetchIdfObjects(); }
    } catch (e) {
      setState({ state: 'done', result: { ok: false, fatal: [e.message], severe: [], warnings: [] } });
    }
  }, [ed, fetchIdfObjects]);

  useEffect(() => () => clearTimeout(timer.current), []);

  const start = async () => {
    try {
      await call('post', '/check');
      setState({ state: 'running', elapsed: 0 });
      timer.current = setTimeout(poll, 3000);
    } catch (e) {
      ed.setNotice({ kind: 'error', lines: [e.message] });
    }
  };
  const r = state.result;
  return (
    <div className="ie-check-model">
      <button type="button" onClick={start} disabled={!ed.filesUploaded || state.state === 'running'}>
        {state.state === 'running' ? `Running the model… ${Math.round(state.elapsed || 0)} s` : 'Check model'}
      </button>
      {state.state === 'done' && r && (
        <div className={`ie-result ${r.ok && r.severe.length === 0 ? 'is-ok' : 'is-bad'}`}>
          <strong>
            {r.ok && r.severe.length === 0 && r.fatal.length === 0
              ? `EnergyPlus ran the model for one day without severe errors (${r.seconds} s).`
              : `EnergyPlus reported problems (${r.seconds} s).`}
          </strong>
          {r.fatal.map((t, i) => <p key={`f${i}`} className="ie-error">Fatal: {t}</p>)}
          {r.severe.map((t, i) => <p key={`s${i}`} className="ie-error">Severe: {t}</p>)}
          {r.warnings.length > 0 && (
            <details>
              <summary>{r.warnings.length} warning(s)</summary>
              {r.warnings.slice(0, 100).map((t, i) => <p key={i}>{t}</p>)}
            </details>
          )}
          <p className="ie-source">The variable list in Sensors &amp; actuators now reflects this run.</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- the page

const TABS = [
  { id: 'comfort', label: 'Thermal comfort' },
  { id: 'co2', label: 'Indoor CO2' },
  { id: 'outputs', label: 'Outputs' },
  { id: 'all', label: 'All classes' },
];

export default function IdfEditor() {
  const ed = useEditor();
  const { revertToOriginal } = useContext(AppContext);
  const [tab, setTab] = useState('comfort');

  const restore = async () => {
    if (!window.confirm('Discard every change and go back to the uploaded IDF?')) return;
    try {
      await revertToOriginal();
      ed.setNotice({ kind: 'ok', lines: ['Model restored to the uploaded original.'] });
      ed.setRev((n) => n + 1);
    } catch (e) {
      ed.setNotice({ kind: 'error', lines: [e?.response?.data?.details || e.message] });
    }
  };

  return (
    <div className="ie">
      <header className="ie-bar">
        <div>
          <h1>Model editor</h1>
          <p className="muted">
            Edit the model&apos;s IDF. Every form is built from the EnergyPlus 9.6 IDD. Changes go to the working copy
            (comments in the file are not kept); the uploaded original can always be restored.
          </p>
        </div>
        <div className="ie-bar__actions">
          <CheckModel ed={ed} />
          <button type="button" onClick={restore} disabled={!ed.filesUploaded}>Restore original</button>
        </div>
      </header>

      {!ed.filesUploaded ? (
        <p className="ie-empty">Upload an IDF and a weather file first (left menu, Model).</p>
      ) : (
        <>
          <nav className="ie-tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
                className={tab === t.id ? 'is-active' : ''} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>
          {ed.notice && (
            <div className={`ie-notice ie-notice--${ed.notice.kind}`} role="status">
              {ed.notice.lines.map((l, i) => <p key={i}>{l}</p>)}
              <button type="button" className="ie-link" onClick={() => ed.setNotice(null)}>dismiss</button>
            </div>
          )}
          <div className="ie-content">
            {tab === 'comfort' && <ComfortView ed={ed} />}
            {tab === 'co2' && <Co2View ed={ed} />}
            {tab === 'outputs' && <OutputsView ed={ed} />}
            {tab === 'all' && <ClassBrowser ed={ed} />}
          </div>
        </>
      )}
    </div>
  );
}
