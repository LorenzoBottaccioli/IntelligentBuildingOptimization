import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api } from './api';
import { PeriodFields, periodOf, periodBody, dayLabel } from './PeriodCard';
import { FmuCard, useFmuExport } from './FmuExport';
import './ControlRoom.css';

const POLL_MS = 1500;
const BUSY = ['starting', 'running'];

function fmtSimTime(t) {
  if (!t) return '–';
  const d = new Date(t);
  if (Number.isNaN(d.getTime())) return String(t);
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

// The page where a script is edited, from its folder.
function editPage(name) {
  if (name.startsWith('devices/')) return '/devices_code';
  if (name.startsWith('iot/')) return '/subscriber_code';
  if (name.startsWith('ai/')) return '/controller_code';
  return null;
}

const tailText = (tail) => (Array.isArray(tail) ? tail.slice(-20).join('\n') : String(tail || ''));

async function post(path, body) {
  const r = await fetch(api(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) {
    let msg = `Request failed (${r.status})`;
    try { const j = await r.json(); msg = j.error || j.message || msg; } catch { /* keep default */ }
    throw new Error(msg);
  }
}

function LogTail({ tail, label = 'Log' }) {
  const [show, setShow] = useState(false);
  return (
    <>
      <button type="button" className="gw-btn gw-btn--link" onClick={() => setShow((s) => !s)} aria-expanded={show}>
        {show ? '▾' : '▸'} {label}
      </button>
      {show && <pre className="gw-tail">{tailText(tail) || '(empty)'}</pre>}
    </>
  );
}

function BrokerCard({ broker }) {
  const b = broker || {};
  return (
    <section className="gw-card">
      <h2>Broker</h2>
      <p>
        <span className={`gw-badge gw-badge--${b.connected ? 'connected' : 'disconnected'}`}>
          {b.connected ? 'connected' : 'disconnected'}
        </span>
        {' '}<span className="muted">{b.clients ?? 0} clients connected</span>
      </p>
      <p className="gw-note">Use host <code>mosquitto</code>, port <code>1883</code> in your code.</p>
    </section>
  );
}

function ServicesCard({ services, busy, error, onAction }) {
  return (
    <section className="gw-card">
      <h2>Services</h2>
      {services.length === 0 ? (
        <p className="muted">No scripts yet: write them in IoT &amp; data and AI.</p>
      ) : (
        <table className="gw-table">
          <thead>
            <tr><th>Script</th><th>State</th><th className="gw-num">Restarts</th><th /></tr>
          </thead>
          <tbody>
            {services.map((s) => {
              const page = editPage(s.name);
              const running = s.state === 'running';
              return (
                <React.Fragment key={s.name}>
                  <tr>
                    <td className="gw-name">{page ? <Link to={page} title="Edit it">{s.name}</Link> : s.name}</td>
                    <td><span className={`gw-badge gw-badge--${s.state}`}>{s.state}</span></td>
                    <td className="gw-num">{s.restarts ?? 0}</td>
                    <td>
                      <div className="gw-actions">
                        <button type="button" className="gw-btn gw-btn--primary" disabled={busy || running}
                          onClick={() => onAction(s.name, 'start')}>Start</button>
                        <button type="button" className="gw-btn gw-btn--secondary" disabled={busy || !running}
                          onClick={() => onAction(s.name, 'stop')}>Stop</button>
                        <button type="button" className="gw-btn gw-btn--secondary" disabled={busy}
                          onClick={() => onAction(s.name, 'restart')}>Restart</button>
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={4}>
                      <LogTail tail={s.log_tail} />
                      {s.exit_code !== null && s.exit_code !== undefined && !running && (
                        <span className="muted"> exit code {s.exit_code}</span>
                      )}
                    </td>
                  </tr>
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}
      {error && <p className="gw-alert gw-alert--error">{error}</p>}
    </section>
  );
}


const yearsText = (w) => (w.years.length === 0 ? 'no year in the data'
  : w.kind === 'real' ? `real year ${w.years[0]}`
    : `typical year assembled from ${w.years[0]}-${w.years[w.years.length - 1]} (${w.years.length} source years)`);
const placeText = (w) => [w.city, w.country].filter((x) => x && x !== '-').join(', ');
const stampText = (from) => (from === 'weather' ? 'the weather file is one real year' : 'a typical year has no single year, so site.year of Field/points.yaml is used');

// The weather of the session: the one in use, where it is used, and the others waiting in the library.
function WeatherCard({ weather, stampYear, stampFrom, files, reloadFiles, locked, onChanged }) {
  const [busyFile, setBusyFile] = useState('');
  const [message, setMessage] = useState(null);

  const load = reloadFiles;

  const use = async (f) => {
    setBusyFile(f.id);
    setMessage(null);
    try {
      const r = await fetch(api('/weather/use'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source: f.id }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || `Request failed (${r.status})`);
      const used = j.used || {};
      setMessage({
        kind: used.fmu_errors && used.fmu_errors.length ? 'error' : 'ok',
        text: `${f.name} is now the weather of the session${used.fmus ? `; ${used.fmus} exported FMU${used.fmus === 1 ? '' : 's'} updated` : ''}.`
          + (used.kept ? ` ${used.kept} went to the library.` : '')
          + (used.fmu_errors && used.fmu_errors.length ? ` Not updated: ${used.fmu_errors.join('; ')}` : ''),
      });
      await Promise.all([load(), onChanged()]);
    } catch (e) {
      setMessage({ kind: 'error', text: e.message });
    } finally {
      setBusyFile('');
    }
  };

  const inUse = weather && weather.file ? weather : null;
  const real = inUse && inUse.kind === 'real' ? inUse.years[0] : null;
  const library = files.filter((f) => f.kind === 'library');
  return (
    <section className="gw-card">
      <h2>Weather</h2>
      {!inUse ? (
        <p className="gw-note">No weather file in this session yet: upload a model with its EPW.</p>
      ) : (
        <p>
          <b>In use:</b> <code>{inUse.file}</code>{placeText(inUse) ? `, ${placeText(inUse)}` : ''} · {yearsText(inUse)}.
        </p>
      )}
      <p className="gw-note">
        The session holds one weather file. The annual run reads it each time you press Run; an exported FMU carries a copy,
        replaced when you put another file in use. Dates stored in InfluxDB carry the year <b>{stampYear}</b>: {stampText(stampFrom)}.
        To simulate several years, run one after the other and keep what is stored (below).
      </p>
      {real && stampYear && real !== stampYear && (
        <p className="gw-alert gw-alert--warn">The weather is from {real} but the stored dates say {stampYear}.</p>
      )}
      <h3 className="gw-h3">In the library</h3>
      {library.length === 0 ? (
        <p className="muted">Nothing else yet. Make files from real years, stations or PVGIS in <Link to="/weather_edit">Weather</Link>; they wait here.</p>
      ) : (
        <table className="gw-table">
          <thead><tr><th>File</th><th>Place</th><th>Data</th><th /></tr></thead>
          <tbody>
            {library.map((f) => (
              <tr key={f.id}>
                <td className="gw-name"><code>{f.name}</code></td>
                <td>{placeText(f) || '–'}</td>
                <td>{f.years && f.years.length ? yearsText({ ...f, kind: f.yearKind }) : '–'}</td>
                <td>
                  {inUse && f.name === inUse.file ? <span className="gw-badge gw-badge--connected">in use</span> : (
                    <button type="button" className="gw-btn gw-btn--secondary" disabled={locked || Boolean(busyFile)}
                      title={locked ? 'The building or the annual run is running' : 'Make it the weather of the session'}
                      onClick={() => use(f)}>{busyFile === f.id ? 'Applying…' : 'Use'}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {locked && <p className="gw-note">Locked while the building or the annual run is running.</p>}
      {message && <p className={message.kind === 'error' ? 'gw-alert gw-alert--error' : 'gw-msg'}>{message.text}</p>}
      <p className="gw-note"><Link to="/weather_edit">Make more files</Link> · <Link to="/weather_edit" state={{ source: 'session' }}>Edit the one in use</Link></p>
    </section>
  );
}

// The period of the simulation, shared with the FMU export below: both read and overwrite the same
// lines of Field/parameters.py. The direct EnergyPlus run uses what is typed here.
function PeriodCard({ period, saved, disabled, message, onChange }) {
  if (!period) return null;
  const per = periodOf(period);
  const steps = (per.end - per.start) * 24 * period.timestep;
  return (
    <section className="gw-card">
      <h2>Simulated period</h2>
      <PeriodFields period={period} onChange={onChange} modelTimestep={saved?.timestep} disabled={disabled} />
      {per.errors.length === 0 && (
        <p className="gw-note">
          {dayLabel(per.start)} to {dayLabel(per.end - 1)}, both included: {per.end - per.start} days,{' '}
          {steps.toLocaleString()} steps of {60 / period.timestep} min.
        </p>
      )}
      {saved?.exists ? (
        <p className="gw-note">
          Saved in <code>Field/parameters.py</code> as soon as it is valid; the FMU export below uses the same period.
        </p>
      ) : (
        <p className="gw-note">
          Nothing exported yet, so there is no <code>Field/parameters.py</code> to overwrite: the EnergyPlus-only run
          below uses these values now; the FMU export will write them.
        </p>
      )}
      {saved?.needsExport && (
        <p className="gw-alert gw-alert--warn">
          The exported FMU was built with {saved.exportedTimestep} timesteps per hour, the period now says {saved.timestep}:
          {' '}export the FMU again (below) before starting the building. The EnergyPlus-only run is not affected.
        </p>
      )}
      {disabled && <p className="gw-note">Locked while a simulation is running.</p>}
      {message && <p className="gw-alert gw-alert--error">{message}</p>}
    </section>
  );
}

const DIRECT_BADGE = { building: 'running', running: 'running', writing: 'running', done: 'finished', error: 'crashed' };

// The model in EnergyPlus alone -- no FMU, no gateway, no students' code -- stored in InfluxDB.
function DirectCard({ direct, period, saved, files, buildingRunning, busy, error, onStart, onStop }) {
  const [keep, setKeep] = useState(false);
  const [picked, setPicked] = useState(null);   // ids of the weather files of this run; null = the one of the session
  const d = direct || {};
  const state = d.state || 'idle';
  const active = ['building', 'running', 'writing'].includes(state);
  const valid = !period || periodOf(period).errors.length === 0;
  const pct = state === 'writing' && d.rows_total
    ? Math.min(100, (d.rows / d.rows_total) * 100) : Number(d.progress) || 0;
  const points = d.points || [];
  const missing = d.not_observable || [];
  // The files that can be run: the session's and the library's (without the library copy of the session's own file).
  const sessionName = files.find((f) => f.kind === 'session')?.name || saved?.weather?.file;
  const options = files
    .filter((f) => f.kind === 'session' || f.name !== sessionName)
    .map((f) => ({ ...f, label: f.yearKind === 'real' && f.years?.length ? String(f.years[0]) : 'typical year' }))
    .sort((a, b) => (a.id === 'session' ? -1 : b.id === 'session' ? 1 : a.label.localeCompare(b.label)));
  const chosen = picked || new Set(['session']);
  const toggle = (id) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPicked(next);
  };
  const n = [...chosen].filter((id) => options.some((o) => o.id === id)).length;
  return (
    <section className="gw-card">
      <h2>Annual run, EnergyPlus only</h2>
      <p className="gw-note">
        Runs the model in EnergyPlus alone, with its own logic (thermostats, schedules and its EMS programs), over the
        period above: no FMU, no gateway, none of your code. Everything the FMU would carry is stored in InfluxDB, database{' '}
        <code>{d.database || 'direct_building'}</code>, measurement <code>points</code>: the outputs, and the inputs as the
        building itself computes them. It replaces what the previous run stored unless you keep it; the timestamps are the simulated dates, in the year below.
      </p>
      <h3 className="gw-h3">Which weather year?</h3>
      <p className="gw-note">
        Tick the weather files to simulate, one run each, oldest year first. The weather of the session is not changed:
        a file of the library is lent to EnergyPlus for the run only. Dates are stored with the year of each file.
      </p>
      <ul className="gw-years">
        {options.map((f) => (
          <li key={f.id}>
            <label>
              <input type="checkbox" checked={chosen.has(f.id)} disabled={busy || active} onChange={() => toggle(f.id)} />
              {' '}<b>{f.label}</b> <code>{f.name}</code>
              <span className="muted"> {placeText(f)}{f.id === 'session' ? ' · the weather of the session' : ''}</span>
            </label>
          </li>
        ))}
      </ul>
      {options.length < 2 && (
        <p className="gw-note">For more years, make them in <Link to="/weather_edit">Weather</Link> (Open-Meteo real years): they appear here.</p>
      )}
      <label className="gw-check">
        <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} disabled={busy || active} />
        {' '}Keep what is already stored: add to it instead of replacing it (the years after the first are always added)
      </label>
      <div className="gw-controls">
        <button type="button" className="gw-btn gw-btn--primary" onClick={() => onStart(keep, [...chosen].filter((id) => options.some((o) => o.id === id)))}
          disabled={busy || active || buildingRunning || !valid || !period || n === 0}>{n > 1 ? `Run ${n} years` : 'Run'}</button>
        <button type="button" className="gw-btn gw-btn--secondary" onClick={onStop} disabled={busy || !active}>Stop</button>
      </div>
      {buildingRunning && <p className="gw-note">The building is running through the FMU: stop it first.</p>}
      {error && <p className="gw-alert gw-alert--error">{error}</p>}

      <div className="gw-status" style={{ marginTop: 'var(--space-4)' }}>
        <span className={`gw-badge gw-badge--${DIRECT_BADGE[state] || state}`}>{state}</span>
        {d.sim_date && state === 'running' && <span><span className="muted">Simulating </span>{d.sim_date}</span>}
        {d.of > 1 && <span><span className="muted">Weather </span>{d.step} of {d.of}</span>}
        {d.year && <span><span className="muted">Year </span>{d.year}</span>}
        {d.rows_total > 0 && <span><span className="muted">Rows </span>{(d.rows || 0).toLocaleString()} / {d.rows_total.toLocaleString()}</span>}
        {d.severe > 0 && <span className="gw-bad">{d.severe} severe EnergyPlus message(s)</span>}
      </div>
      <div className="gw-bar" aria-hidden="true"><div className="gw-bar__fill" style={{ width: `${pct}%` }} /></div>
      {d.message && <p className={state === 'error' ? 'gw-alert gw-alert--error' : 'gw-msg'}>{d.message}</p>}

      {points.length > 0 && (
        <>
          <h3 className="gw-h3">Stored</h3>
          <div className="gw-bms__body">
            {points.map((p) => (
              <span key={p.id} className="gw-chip" title={p.fmu}>
                <code>{p.id}</code> {p.type}{p.unit ? ` · ${p.unit}` : ''}
              </span>
            ))}
          </div>
        </>
      )}
      {missing.length > 0 && (
        <>
          <h3 className="gw-h3">Not stored</h3>
          <ul className="gw-log">
            {missing.map((p) => <li key={p.id}><code>{p.id}</code> <span className="muted">{p.reason}</span></li>)}
          </ul>
        </>
      )}
      <p className="gw-note">Plot it in <Link to="/grafana">Dashboards</Link>: datasource &ldquo;InfluxDB Direct&rdquo;.</p>
    </section>
  );
}

function BuildingCard({ building, busy, error, blocked, onStart, onStop }) {
  const proc = building?.process || {};
  const status = building?.status || {};
  const state = status.state || proc.state || 'idle';
  const running = BUSY.includes(state) || proc.state === 'running';

  const [run, setRun] = useState('baseline');
  const [mode, setMode] = useState('fast');
  const [stepSeconds, setStepSeconds] = useState(1);

  const chooseRun = (r) => {
    setRun(r);
    if (r === 'baseline' && mode === 'sync') setMode('fast');
  };

  const total = Number(status.steps_total) || 0;
  const step = Number(status.step) || 0;
  const pct = total > 0 ? Math.min(100, (step / total) * 100) : 0;

  const start = () => onStart({
    run,
    mode,
    step_seconds: mode === 'scaled' ? Math.max(0.05, Number(stepSeconds) || 1) : 0,
  });

  return (
    <section className="gw-card">
      <h2>Building</h2>
      {building?.emergency && (
        <p className="gw-alert gw-alert--warn">
          Emergency gateway active (enabled by the teacher): the platform&apos;s gateway runs instead of your <code>devices/gateway.py</code>.
        </p>
      )}
      <div className="gw-radios">
        <div>
          <h3>Run</h3>
          <label>
            <input type="radio" name="cr-run" checked={run === 'baseline'} onChange={() => chooseRun('baseline')} disabled={running} />
            {' '}baseline (native EnergyPlus control)
          </label>
          <label>
            <input type="radio" name="cr-run" checked={run === 'controlled'} onChange={() => chooseRun('controlled')} disabled={running} />
            {' '}controlled (your controller drives the actuators)
          </label>
        </div>
        <div>
          <h3>Mode</h3>
          <label>
            <input type="radio" name="cr-mode" checked={mode === 'fast'} onChange={() => setMode('fast')} disabled={running} />
            {' '}fast
          </label>
          <label>
            <input type="radio" name="cr-mode" checked={mode === 'scaled'} onChange={() => setMode('scaled')} disabled={running} />
            {' '}scaled
            <input type="number" min="0.05" step="0.05" value={stepSeconds}
              onChange={(e) => setStepSeconds(e.target.value)} disabled={running || mode !== 'scaled'}
              style={{ width: '5rem', margin: '0 var(--space-2)' }} />
            seconds per step
          </label>
          <label>
            <input type="radio" name="cr-mode" checked={mode === 'sync'} onChange={() => setMode('sync')} disabled={running || run !== 'controlled'} />
            {' '}sync (waits for the controller each step)
          </label>
        </div>
      </div>
      <div className="gw-controls">
        <button type="button" className="gw-btn gw-btn--primary" onClick={start} disabled={busy || running || blocked}>Start</button>
        <button type="button" className="gw-btn gw-btn--secondary" onClick={onStop} disabled={busy || !running}>Stop</button>
      </div>
      {error && <p className="gw-alert gw-alert--error">{error}</p>}

      <div className="gw-status" style={{ marginTop: 'var(--space-4)' }}>
        <span className={`gw-badge gw-badge--${state}`}>{state}</span>
        <span><span className="muted">Simulated date </span>{fmtSimTime(status.sim_time)}</span>
        <span><span className="muted">Step </span>{step}{total ? ` / ${total}` : ''}</span>
        {status.run && <span><span className="muted">Run </span>{status.run}</span>}
      </div>
      <div className="gw-bar" aria-hidden="true"><div className="gw-bar__fill" style={{ width: `${pct}%` }} /></div>
      {status.message && <p className="gw-msg">{status.message}</p>}

      <h3 className="gw-h3">
        Output of <code>{proc.emergency ? 'emergency_gateway.py (platform)' : 'devices/gateway.py'}</code>
      </h3>
      <LogTail tail={proc.log_tail} />
    </section>
  );
}

function DataCard({ storage, studentTopics }) {
  return (
    <section className="gw-card">
      <h2>Data</h2>
      {['baseline', 'controlled', 'direct'].map((run) => {
        const s = storage?.[run];
        const ms = s?.measurements || [];
        return (
          <div key={run} className="gw-bms__row">
            <div className="gw-bms__head">
              <strong>{run === 'direct' ? 'EnergyPlus only' : run}</strong> {s?.db && <code>{s.db}</code>}
              {run === 'direct' && s?.from && <span className="muted"> {String(s.from).slice(0, 10)} to {String(s.to).slice(0, 10)}</span>}
            </div>
            <div className="gw-bms__body">
              {s?.error ? (
                <span className="gw-bad">not readable ({s.error})</span>
              ) : ms.length === 0 ? (
                <span className="muted">empty</span>
              ) : (
                ms.map((m) => (
                  <span key={m.name} className="gw-chip"><code>{m.name}</code> {m.series} series</span>
                ))
              )}
            </div>
          </div>
        );
      })}
      <h3 className="gw-h3">Your topics</h3>
      {studentTopics.length === 0 ? (
        <p className="muted">None published yet.</p>
      ) : (
        <ul className="gw-log gw-trace">
          {studentTopics.slice(0, 20).map((t) => (
            <li key={t.topic}>{t.topic} <span className="muted">{t.payload}</span></li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StepCard({ trace }) {
  return (
    <section className="gw-card">
      <h2>Step by step</h2>
      <p className="gw-note">
        Every message crossing the broker, newest first. The loop is yours: <code>devices/gateway.py</code> calls{' '}
        <code>building.step()</code> and publishes.
      </p>
      {trace.length === 0 ? (
        <p className="muted">Nothing yet. Start your services, then the building.</p>
      ) : (
        <ul className="gw-log gw-trace">
          {[...trace].reverse().slice(0, 40).map((m, i) => {
            const kind = m.topic.endsWith('/sim/tick') ? 'tick'
              : m.topic.endsWith('/sim/ack') ? 'ack'
                : m.topic.includes('/command/') ? 'cmd'
                  : m.topic.endsWith('/active') ? 'active' : 'value';
            return (
              <li key={i} className={`gw-trace--${kind}`}>
                <span className="gw-log__ts">{m.at}</span> {m.topic} <span className="muted">{m.payload}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default function ControlRoom() {
  const { pathname } = useLocation();
  const active = pathname === '/control_room';

  const [data, setData] = useState(null);
  const [unreachable, setUnreachable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [buildingError, setBuildingError] = useState('');
  const [serviceError, setServiceError] = useState('');
  const [directError, setDirectError] = useState('');

  // The period: typed here, saved to Field/parameters.py a moment after the last keystroke. What
  // the server holds replaces it only when it changed elsewhere (the export page) and nothing typed here is pending.
  const [period, setPeriod] = useState(null);
  const [periodError, setPeriodError] = useState('');
  const pending = useRef(false);
  const timer = useRef(null);
  const saved = data?.period || null;
  const savedKey = saved ? [saved.timestep, saved.startDay, saved.warmupDays, saved.endDay].join('/') : '';
  const buildingRunning = data?.building?.process?.state === 'running';
  const directActive = ['building', 'running', 'writing'].includes(data?.direct?.state);
  useEffect(() => {
    if (!saved || pending.current) return;
    setPeriod({ timestep: saved.timestep, startDay: saved.startDay, warmupDays: saved.warmupDays, endDay: saved.endDay });
  }, [savedKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const savePeriod = useCallback(async (next) => {
    try {
      const r = await fetch(api('/bms/period'), {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(periodBody(next)),
      });
      if (!r.ok) {
        let msg = `Request failed (${r.status})`;
        try { msg = (await r.json()).error || msg; } catch { /* keep default */ }
        throw new Error(msg);
      }
      pending.current = false;
      setPeriodError('');
      await refresh();
    } catch (e) {
      pending.current = false;
      setPeriodError(e.message);
      await refresh();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const changePeriod = (next) => {
    setPeriod(next);
    setPeriodError('');
    clearTimeout(timer.current);
    if (!saved?.exists || periodOf(next).errors.length > 0) { pending.current = false; return; }
    pending.current = true;
    timer.current = setTimeout(() => savePeriod(next), 700);
  };

  const refresh = useCallback(async () => {
    try {
      const r = await fetch(api('/bms/state'));
      if (!r.ok) throw new Error(String(r.status));
      setData(await r.json());
      setUnreachable(false);
    } catch {
      setUnreachable(true);
    }
  }, []);

  // Is the exported FMU what the model describes now? Read with the state; a model that is being
  // written answers "busy" and the last answer stays.
  const [fmu, setFmu] = useState(null);
  const refreshFmu = useCallback(async () => {
    try {
      const r = await fetch(api('/model_converter/fmu_state'));
      if (!r.ok) throw new Error(String(r.status));
      const s = await r.json();
      if (!s.busy) setFmu(s);
    } catch {
      setFmu((old) => old || { error: 'the backend did not answer' });
    }
  }, []);
  const [weatherFiles, setWeatherFiles] = useState([]);
  const reloadWeatherFiles = useCallback(async () => {
    try {
      const r = await fetch(api('/weather/files'));
      if (r.ok) setWeatherFiles((await r.json()).files || []);
    } catch { /* the list stays as it was */ }
  }, []);
  const ex = useFmuExport(period);
  useEffect(() => { if (active) refreshFmu(); }, [active, ex.exportedAt, refreshFmu]);
  useEffect(() => { if (active) reloadWeatherFiles(); }, [active, data?.period?.weather?.file, reloadWeatherFiles]);

  // The page stays mounted when hidden: poll only while it is the current one and the tab is visible.
  useEffect(() => {
    if (!active) return undefined;
    const tick = () => { if (document.visibilityState === 'visible') { refresh(); refreshFmu(); } };
    tick();
    const id = setInterval(tick, POLL_MS);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [active, refresh, refreshFmu]);

  const send = async (path, body, setErr) => {
    setBusy(true);
    setErr('');
    try {
      await post(path, body);
      await refresh();
    } catch (e) {
      setErr(e.message || 'BMS API not reachable');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="gw">
      <header className="gw-head">
        <h1>Control room</h1>
        <p className="muted">Your code runs here. Start your services, then the building.</p>
      </header>

      {unreachable && <p className="gw-alert gw-alert--error">BMS API not reachable</p>}

      <BrokerCard broker={data?.broker} />

      <ServicesCard services={data?.services || []} busy={busy} error={serviceError}
        onAction={(name, action) => send(`/bms/services/${name}/${action}`, null, setServiceError)} />

      <PeriodCard period={period} saved={saved} message={periodError} onChange={changePeriod}
        disabled={buildingRunning || directActive} />

      <WeatherCard weather={saved?.weather} stampYear={saved?.stampYear} stampFrom={saved?.stampFrom} files={weatherFiles} reloadFiles={reloadWeatherFiles}
        locked={buildingRunning || directActive} onChanged={refresh} />

      <FmuCard ex={ex} state={fmu} />

      <BuildingCard building={data?.building} busy={busy} error={buildingError}
        blocked={directActive || !!saved?.needsExport}
        onStart={(body) => send('/bms/building/start', body, setBuildingError)}
        onStop={() => send('/bms/building/stop', null, setBuildingError)} />

      <DirectCard direct={data?.direct} period={period} saved={saved} files={weatherFiles} buildingRunning={buildingRunning} busy={busy} error={directError}
        onStart={(keep, weathers) => send('/bms/direct/start', { ...periodBody(period), keep, weathers }, setDirectError)}
        onStop={() => send('/bms/direct/stop', null, setDirectError)} />

      <DataCard storage={data?.storage} studentTopics={data?.student_topics || []} />

      <StepCard trace={data?.trace || []} />
    </div>
  );
}
