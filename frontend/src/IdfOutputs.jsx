import React, { useContext, useEffect, useMemo, useState } from 'react';
import { AppContext } from './AppContext';
import { METER_GROUPS, meterGroup, SENSOR_GROUPS, sensorGroup } from './outputGroups';

// The Outputs tab of the Model editor: what EnergyPlus writes to the results.
//
// The unit here is the variable (or meter), not the Output:Variable object: a student thinks
// "I want the zone air temperature, hourly and monthly", and the model holds one object per
// frequency (and per key). So each variable is one row, its reporting frequencies are switches,
// and rows sit in the same groups as the sensor lists of Sensors & actuators. The server
// (output_requests.py) still works per request and says what each one is read by; the lists of
// what the model can report come from its last Check model run (AppContext.idfObjects).

// The frequencies offered as switches; others the model already uses are added, the rest sit in a menu.
// What switching a variable on does: report at every time step; the other frequencies are one click away.
const DEFAULT_FREQUENCY = 'Timestep';
const MAIN = ['Timestep', 'Hourly', 'Daily', 'Monthly', 'RunPeriod'];
const READER = { 'platform-sensor': 'sensor', 'fmu-output': 'FMU output', 'model-sensor': 'model EMS sensor' };

const blank = (key) => !key || key === '*';
const lc = (s) => String(s).toLowerCase();
const ref = (row) => (row.kind === 'variable'
  ? { class: row.class, index: row.index, name: row.name, key: row.key }
  : { class: row.class, index: row.index, name: row.name });

export function cascadeMessage(body) {
  const lines = body.dependants.map((d) => (d.kind === 'platform-sensor'
    ? `• sensor "${d.name}"${d.fmu.length ? ` and its FMU output ${d.fmu.join(', ')}` : ''}`
    : `• FMU output "${d.name}"`));
  return `Something reads ${body.dependants.length === 1 ? 'this output' : 'these outputs'} and goes with `
    + `${body.dependants.length === 1 ? 'it' : 'them'}:\n\n${lines.join('\n')}\n\nRemove anyway?`;
}

/** One entry per variable or meter: the catalogue of the model, plus whatever is requested. */
function buildEntries(rows, catalogue, groupOf) {
  const byName = new Map();
  const entry = (name, info) => {
    const id = lc(name);
    // With no catalogue at all nothing can be called unlisted.
    if (!byName.has(id)) byName.set(id, { name, info, listed: Boolean(info) || catalogue.size === 0, requests: [], group: groupOf(name, info) });
    return byName.get(id);
  };
  catalogue.forEach((info, name) => entry(name, info));
  rows.forEach((r) => entry(r.name, undefined).requests.push(r));
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function readers(entry) {
  const seen = new Map();
  entry.requests.forEach((r) => r.usedBy.forEach((u) => seen.set(`${u.kind}|${u.name}`, u)));
  return [...seen.values()];
}

// ----------------------------------------------------------------------- entry

function Entry({ kind, entry, frequencies, busy, run, ed, newMeter }) {
  const isVariable = kind === 'variable';
  const base = isVariable ? entry.requests.filter((r) => blank(r.key)) : entry.requests;
  const keyed = isVariable ? entry.requests.filter((r) => !blank(r.key)) : [];
  const chips = [...MAIN.filter((f) => frequencies.includes(f))];
  entry.requests.forEach((r) => { if (!chips.includes(r.frequency)) chips.push(r.frequency); });
  const rest = frequencies.filter((f) => !chips.includes(f));
  const keys = (entry.info && entry.info.keys) || [];
  const [adding, setAdding] = useState({ key: '', frequency: DEFAULT_FREQUENCY });
  const reading = readers(entry);
  const listId = `ie-keys-${entry.name.replace(/\W/g, '_')}`;

  const remove = (list) => ed.write('delete', '/outputs/request', { requests: list.map(ref) },
    (body) => (window.confirm(cascadeMessage(body)) ? { cascade: true } : null));
  const add = (frequency, key = '*') => (isVariable
    ? ed.write('post', '/outputs/variable', { key, name: entry.name, frequency })
    : ed.write('post', '/outputs/meter', {
      name: entry.name, frequency, cumulative: newMeter.cumulative, fileOnly: !newMeter.inResults }));
  const toggle = (frequency) => run(() => {
    const on = base.filter((r) => r.frequency === frequency);
    return on.length ? remove(on) : add(frequency);
  });
  const toResults = (r) => run(() => ed.write('patch', '/outputs/request', {
    requests: [ref(r)], changes: { fileOnly: false } }));

  const on = (f) => base.some((r) => r.frequency === f);
  const locked = (f) => base.some((r) => r.frequency === f && r.locked);
  const units = entry.info && entry.info.units;
  const scope = isVariable
    ? (keyed.length && !base.length ? 'only specific keys' : (keys.length ? `${keys.length} key${keys.length === 1 ? '' : 's'}` : ''))
    : '';

  return (
    <li className={`ie-oe ${entry.requests.length ? 'is-reported' : ''}`}>
      <div className="ie-oe__head">
        <div className="ie-oe__name">
          <span>{entry.name}</span>
          {units ? <em className="ie-unit"> [{units}]</em> : null}
          {!entry.listed && <span className="ie-tag ie-tag--warn" title="EnergyPlus does not list it for this model: press Check model, or it will report nothing.">not listed</span>}
          {scope ? <span className="ie-oe__scope">{scope}</span> : null}
        </div>
        <div className="ie-oe__chips" role="group" aria-label={`Reporting frequency of ${entry.name}`}>
          {!entry.requests.length && (
            <button type="button" className="ie-chip ie-chip--report" disabled={busy}
              title="Report it at every time step (Timestep). Change the frequency afterwards if you want."
              onClick={() => toggle(DEFAULT_FREQUENCY)}>Report</button>
          )}
          {chips.map((f) => (
            <button
              key={f} type="button" disabled={busy}
              className={`ie-chip ${on(f) ? 'is-on' : ''} ${locked(f) ? 'is-locked' : ''}`}
              aria-pressed={on(f)}
              title={on(f) ? `Reported ${f}. Click to stop.` : `Click to report ${f}.`}
              onClick={() => toggle(f)}
            >{f}</button>
          ))}
          {rest.length > 0 && (
            <select className="ie-chip ie-chip--more" value="" disabled={busy} aria-label="Another frequency"
              onChange={(e) => e.target.value && run(() => add(e.target.value))}>
              <option value="">+</option>
              {rest.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          )}
        </div>
      </div>

      {reading.length > 0 && (
        <p className="ie-oe__note">
          <span className="ie-tag ie-tag--warn">read by</span>{' '}
          {reading.map((u) => `${READER[u.kind]} ${u.name}`).join(', ')}
          {base.some((r) => r.locked) ? ' — the frequency that feeds it stays until you remove it.' : '.'}
        </p>
      )}

      {!isVariable && base.filter((r) => r.fileOnly || r.cumulative).map((r) => (
        <p key={`${r.class}#${r.index}`} className="ie-oe__note">
          {r.frequency}: {r.cumulative ? 'cumulative' : ''}{r.cumulative && r.fileOnly ? ', ' : ''}{r.fileOnly ? 'meter file (.mtr) only' : ''}
          {r.fileOnly && !r.locked ? (
            <> — <button type="button" className="ie-link" disabled={busy} onClick={() => toResults(r)}>also write it to the results file</button></>
          ) : null}
        </p>
      ))}

      {keyed.length > 0 && (
        <ul className="ie-oe__keyed">
          {keyed.map((r) => (
            <li key={`${r.class}#${r.index}`}>
              <code>{r.key}</code> <span className="muted">{r.frequency}</span>
              {r.schedule ? <span className="ie-tag"> schedule {r.schedule}</span> : null}
              <button type="button" className="ie-link" disabled={busy} aria-label={`Stop reporting ${entry.name} for ${r.key}`}
                onClick={() => run(() => remove([r]))}>remove</button>
            </li>
          ))}
        </ul>
      )}

      {isVariable && (
        <details className="ie-oe__more">
          <summary>Report for one zone or surface only</summary>
          <div className="ie-inline">
            <label>Key
              <input value={adding.key} list={listId} placeholder="e.g. a zone name"
                onChange={(e) => setAdding({ ...adding, key: e.target.value })} />
              <datalist id={listId}>{keys.map((k) => <option key={k} value={k} />)}</datalist>
            </label>
            <label>Frequency
              <select value={adding.frequency} onChange={(e) => setAdding({ ...adding, frequency: e.target.value })}>
                {frequencies.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <button type="button" disabled={busy || !adding.key.trim()}
              onClick={() => run(() => add(adding.frequency, adding.key.trim()).then(() => setAdding({ ...adding, key: '' })))}>
              Add
            </button>
          </div>
        </details>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------- browser

function Browser({ kind, ed, rows, catalogue, frequencies, groups, groupOf }) {
  const [scope, setScope] = useState('reported');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [newMeter, setNewMeter] = useState({ inResults: true, cumulative: false });
  const entries = useMemo(() => buildEntries(rows, catalogue, groupOf), [rows, catalogue, groupOf]);
  const q = lc(query.trim());
  const shown = entries.filter((e) => (scope === 'all' || e.requests.length)
    && (!q || lc(e.name).includes(q) || e.requests.some((r) => lc(r.key || '').includes(q))));
  const reported = entries.filter((e) => e.requests.length).length;
  const listed = catalogue.size;

  const run = async (fn) => {
    setBusy(true);
    try { await fn(); } finally { setBusy(false); }
  };

  const byGroup = {};
  shown.forEach((e) => (byGroup[e.group] ||= []).push(e));
  const noun = kind === 'variable' ? 'variables' : 'meters';

  return (
    <section className="ie-card">
      <div className="ie-ob__tools">
        <nav className="ie-seg" role="tablist">
          {[['reported', `Reported (${reported})`], ['all', `All available (${Math.max(listed, entries.length)})`]].map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={scope === id}
              className={scope === id ? 'is-active' : ''} onClick={() => setScope(id)}>{label}</button>
          ))}
        </nav>
        <input type="search" value={query} placeholder={`Search ${noun}`} onChange={(e) => setQuery(e.target.value)} />
      </div>

      {kind === 'meter' && (
        <div className="ie-inline ie-ob__options">
          <span>When I switch a frequency on:</span>
          <label className="ie-check">
            <input type="checkbox" checked={newMeter.inResults}
              onChange={(e) => setNewMeter({ ...newMeter, inResults: e.target.checked })} />
            also write it to the results file (.eso), next to the variables
          </label>
          <label className="ie-check">
            <input type="checkbox" checked={newMeter.cumulative}
              onChange={(e) => setNewMeter({ ...newMeter, cumulative: e.target.checked })} />
            cumulative
          </label>
        </div>
      )}

      {listed === 0 && (
        <p className="ie-note">
          EnergyPlus has not listed what this model can report yet (it does that during Check model). Only what the model
          already requests is shown; you can still switch frequencies on and off.
        </p>
      )}
      {shown.length === 0 && (
        <p className="muted">
          {q ? `No ${noun} match “${query}”.` : `No ${noun} are reported. Choose “All available” to pick some.`}
        </p>
      )}

      {groups.map(([id, title, help]) => {
        const items = byGroup[id];
        if (!items) return null;
        const count = items.filter((e) => e.requests.length).length;
        return (
          <details key={`${id}-${scope}-${q ? 1 : 0}`} className="ie-og" open={scope === 'reported' || Boolean(q)}>
            <summary>
              <strong>{title}</strong>
              <span className="muted"> {count} reported{scope === 'all' ? ` of ${items.length}` : ''}</span>
            </summary>
            <p className="ie-memo">{help}</p>
            <ul className="ie-oe-list">
              {items.map((e) => (
                <Entry key={lc(e.name)} kind={kind} entry={e} frequencies={frequencies} busy={busy} run={run}
                  ed={ed} newMeter={newMeter} />
              ))}
            </ul>
          </details>
        );
      })}
    </section>
  );
}

// ----------------------------------------------------------------------- page

export default function OutputsView({ ed }) {
  const { idfObjects, fetchIdfObjects } = useContext(AppContext);
  const [data, setData] = useState(null);
  const [section, setSection] = useState('variables');

  useEffect(() => {
    if (!ed.active || !ed.filesUploaded) return;
    ed.call('get', '/outputs').then((d) => { setData(d); ed.seen(d.generation); })
      .catch((e) => ed.setNotice({ kind: 'error', lines: [e.message] }));
  }, [ed.rev, ed.active, ed.filesUploaded]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (ed.active && ed.filesUploaded && !idfObjects) fetchIdfObjects(); },
    [ed.active, ed.filesUploaded, idfObjects, fetchIdfObjects]);

  const catalogue = useMemo(() => {
    const variables = new Map();
    ((idfObjects && idfObjects.rdd_variables) || []).forEach((v) => variables.set(v.variableName, v));
    const meters = new Map();
    ((idfObjects && idfObjects.mdd_meters) || []).forEach((m) => meters.set(m.meterName, { units: m.units }));
    return { variables, meters };
  }, [idfObjects]);

  if (!data) return <p className="muted">Loading…</p>;

  const variableGroup = (name, info) => sensorGroup({ variableName: name, varType: info && info.varType });
  const reportedVariables = new Set(data.variables.map((r) => lc(r.name))).size;
  const reportedMeters = new Set(data.meters.map((r) => lc(r.name))).size;

  return (
    <div className="ie-outputs">
      <p className="ie-lead">
        Choose what EnergyPlus writes to the results: <strong>report variables</strong> (values over time: a zone temperature,
        a surface heat flow) and <strong>meters</strong> (energy and water totals). One row per variable; switch on the
        frequencies you want.
      </p>
      <details className="ie-explain">
        <summary>What changes where</summary>
        <p>
          These choices set the Output:Variable and Output:Meter objects of the working model, so they apply to the simulation
          you run from this platform and to the exported building. A sensor you export to the controller (Sensors &amp; actuators,
          comfort, CO2) builds on one of them: it shows as &quot;read by&quot;, and switching off the frequency that feeds it
          removes the sensor too, after asking.
        </p>
        <p>
          Every meter goes to the meter file (.mtr); it also goes to the results file (.eso), where the variables are, unless it
          is set to meter file only. Cumulative reports the running total instead of the value of each interval.
        </p>
        <p>
          The bdopt design notebook simulates a copy without the report variables and requests by itself the meters it optimises,
          so what you choose here does not change its results.
        </p>
      </details>
      <nav className="ie-seg" role="tablist">
        {[['variables', `Report variables (${reportedVariables})`], ['meters', `Meters (${reportedMeters})`]].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={section === id}
            className={section === id ? 'is-active' : ''} onClick={() => setSection(id)}>{label}</button>
        ))}
      </nav>
      {section === 'variables'
        ? <Browser key="v" kind="variable" ed={ed} rows={data.variables} catalogue={catalogue.variables}
          frequencies={data.frequencies.variable} groups={SENSOR_GROUPS} groupOf={variableGroup} />
        : <Browser key="m" kind="meter" ed={ed} rows={data.meters} catalogue={catalogue.meters}
          frequencies={data.frequencies.meter} groups={METER_GROUPS} groupOf={meterGroup} />}
    </div>
  );
}
