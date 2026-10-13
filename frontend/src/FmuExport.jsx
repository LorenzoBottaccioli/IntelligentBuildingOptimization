// FmuExport.jsx
// The FMU in the Control room: whether it is up to date with the choices made in Sensors &
// actuators, the parameters.py the notebooks import (editable), and the export itself. The
// simulated period is the one of the Control room. Everything the export sends is derived from
// idfObjects (roles and ranges live in idfObjects.fmu_roles), by ONE function used for the
// text and for the request, so the two cannot disagree.
import React, { useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { api } from './api';
import { AppContext } from './AppContext';
import { Download } from 'lucide-react';
import { dayLabel, periodOf } from './PeriodCard';
import './FmuExport.css';

const DEFAULT_MIN = -1000;
const DEFAULT_MAX = 1000;

const finite = (x) => typeof x === 'number' && Number.isFinite(x);

/** What goes into parameters.py: names, roles, ranges, and what is still missing. */
export function deriveExportSpec(idfObjects, scheduleTypeLimits) {
  const data = idfObjects || {};
  const roles = data.fmu_roles || {};
  const fromVars = data.current_fmu_from_variables || [];
  const schedules = data.current_fmu_schedules || [];
  const actuators = [
    ...(data.current_fmu_actuators || []),
    ...(data.current_fmu_to_variables || []),
    ...schedules,
  ];
  const scheduleNames = new Set(schedules.map((s) => s.fmuVariableName));
  const limitsOf = (a) => {
    if (!scheduleNames.has(a.fmuVariableName)) return null;
    const l = (scheduleTypeLimits || {})[a.scheduleTypeLimitsNames];
    return l && finite(l.min) && finite(l.max) ? l : null;
  };

  const observations = fromVars.filter((v) => roles[v.fmuVariableName]?.role === 'observation').map((v) => v.fmuVariableName);
  const rewards = fromVars.filter((v) => roles[v.fmuVariableName]?.role === 'reward').map((v) => v.fmuVariableName);
  const noRole = fromVars.filter((v) => !roles[v.fmuVariableName]?.role).map((v) => v.fmuVariableName);

  const actions = actuators.map((a) => a.fmuVariableName);
  const noRange = [];
  const actionMin = [];
  const actionMax = [];
  actuators.forEach((a) => {
    const r = roles[a.fmuVariableName] || {};
    const explicit = finite(r.min) && finite(r.max);
    const lim = limitsOf(a);
    if (!explicit && !lim) noRange.push(a.fmuVariableName);
    actionMin.push(explicit ? r.min : lim ? lim.min : DEFAULT_MIN);
    actionMax.push(explicit ? r.max : lim ? lim.max : DEFAULT_MAX);
  });
  return { observations, rewards, actions, actionMin, actionMax, noRole, noRange };
}

function buildParameters(spec, p, uploadedIdf) {
  const dtype = 'np.float64';
  const per = periodOf(p);
  // EnergyPlusToFMU sanitises the model name -- a dot is not valid in an FMU
  // identifier -- so 'Res_flat1_9.6EMS.idf' becomes 'Res_flat1_9_6EMS.fmu'.
  const fmuPath = (uploadedIdf || '').replace(/\.idf$/i, '').replace(/[^0-9a-zA-Z_]/g, '_') + '.fmu';
  // fmi_gym reads fmu_warmup_time as an absolute time, the moment the
  // controller starts acting -- not as a duration.
  const warmup = per.warm > 0
    ? `${per.control} * 60 * 60 * 24  # absolute: controller acts from day ${per.control} (${dayLabel(per.control)}); days ${per.start}-${per.control} run with every action = 0`
    : 'None  # no fmi_gym warm-up: the controller acts from the start';
  return `
import numpy as np

parameter = {}
# fmi_gym parameter
parameter['seed'] = 1
parameter['store_data'] = True

# fmu parameter
dtype = ${dtype}
parameter['fmu_step_size'] = ${3600 / p.timestep}  # s, = 3600 / ${p.timestep} timesteps per hour of the model
parameter['fmu_path'] = '${fmuPath}'
parameter['fmu_start_time'] = ${per.start} * 60 * 60 * 24  # day ${per.start}, ${dayLabel(per.start)} 00:00
parameter['fmu_warmup_time'] = ${warmup}
parameter['fmu_final_time'] = ${per.end} * 60 * 60 * 24  # day ${per.end}, ${dayLabel(per.end)} 00:00

# data exchange parameter
parameter['action_names'] = ${JSON.stringify(spec.actions)}
parameter['action_min'] = np.array(${JSON.stringify(spec.actionMin)}, dtype=${dtype})
parameter['action_max'] = np.array(${JSON.stringify(spec.actionMax)}, dtype=${dtype})
parameter['observation_names'] = ${JSON.stringify(spec.observations)}
parameter['reward_names'] = ${JSON.stringify(spec.rewards)}
`.trim();
}

/** The blob of a failed download holds the JSON error; show its message. */
async function errorMessage(error) {
  const d = error?.response?.data;
  try {
    const raw = d instanceof Blob ? await d.text() : d;
    const j = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (j && (j.details || j.error)) return [j.error, j.details].filter(Boolean).join(': ');
  } catch (e) { /* not JSON: fall through */ }
  return error?.message || 'Export failed.';
}

/**
 * The export, with the simulated period of the Control room (`period`).
 * Lives in the page that shows it, so the edited parameters.py survives while the page stays mounted.
 */
export function useFmuExport(period) {
  const { idfObjects, scheduleTypeLimits, uploadedFiles, filesUploaded, modelId } = useContext(AppContext);
  const modelTimestep = idfObjects?.timesteps_per_hour || 6;
  const [edited, setEdited] = useState(null); // text typed by the student, or null
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState(null); // { kind: 'ok' | 'error', text }
  const [exportedAt, setExportedAt] = useState(0); // bumped after each export: the state of the FMU is read again

  // A new model: the typed text described another one.
  useEffect(() => {
    setEdited(null);
    setStatus(null);
  }, [modelId]);

  // Until the Control room has the period, or while it holds none, the model's own timestep.
  const p = { startDay: 0, warmupDays: 0, endDay: 7, ...(period || {}) };
  p.timestep = p.timestep ?? modelTimestep;
  const spec = useMemo(() => deriveExportSpec(idfObjects, scheduleTypeLimits), [idfObjects, scheduleTypeLimits]);
  const generated = filesUploaded ? buildParameters(spec, p, uploadedFiles.idf) : '';
  const text = edited ?? generated;
  const per = periodOf(p);

  const doExport = useCallback(async () => {
    setProgress(10);
    setStatus(null);
    try {
      const { data } = await axios.post(api('/model_converter/export_model'), {
        timestep: p.timestep,
        startTime: per.start,
        warmupTime: per.warm > 0 ? per.control : per.start,
        finalTime: per.end,
        observations: spec.observations,
        rewards: spec.rewards,
        actions: spec.actions,
        actionMin: spec.actionMin,
        actionMax: spec.actionMax,
        configText: text,
        download: false,
      });
      setProgress(100);
      setExportedAt((n) => n + 1);
      setStatus({
        kind: 'ok',
        text: `Exported ${data.fmu}${data.baselineFmu ? ` and ${data.baselineFmu}` : ''} to Field/, with parameters.py.`
          + (data.baselineWarning ? ` ${data.baselineWarning}` : ''),
      });
    } catch (error) {
      console.error('Error exporting model:', error);
      setStatus({ kind: 'error', text: await errorMessage(error) });
    } finally {
      setTimeout(() => setProgress(0), 1000);
    }
  }, [p.timestep, per.start, per.warm, per.control, per.end, spec, text]);

  const downloadBundle = useCallback(async () => {
    try {
      const response = await axios.get(api('/model_converter/download_bundle'), { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/zip' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'conversion_bundle.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setStatus({ kind: 'error', text: await errorMessage(error) });
    }
  }, []);

  return {
    period: p, modelTimestep, per, spec, text, generated, edited, setEdited,
    progress, status, doExport, downloadBundle, exportedAt, filesUploaded,
  };
}

function copyText(text) {
  return navigator.clipboard.writeText(text).catch(() => {
    // Plain-http pages have no clipboard API: select and copy through the DOM.
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  });
}

/** One line on what the FMU is, from the state the backend computes. */
function fmuHeadline(state) {
  if (!state) return { tone: 'muted', text: 'Reading the state of the FMU…' };
  if (state.noModel) return { tone: 'muted', text: 'Upload a model first.' };
  if (state.busy) return { tone: 'muted', text: 'The model is being saved: asking again in a moment.' };
  if (state.error) return { tone: 'bad', text: `The state of the FMU could not be read: ${state.error}` };
  if (!state.exported) return { tone: 'warn', text: 'Not exported yet.' };
  if (state.tracked === false) return { tone: 'warn', text: 'Exported before changes were tracked: export again to start tracking.' };
  if (state.upToDate) return { tone: 'ok', text: 'FMU up to date with your choices.' };
  const n = state.changes;
  return { tone: 'warn', text: `${n} ${n === 1 ? 'change' : 'changes'} since the last export: export again.` };
}

/** The FMU in the Control room: state, parameters.py, the export and the zip. */
export function FmuCard({ ex, state }) {
  const { spec, text, generated, edited, setEdited, progress, status, doExport, downloadBundle, per, filesUploaded } = ex;
  const [copied, setCopied] = useState(false);
  const busy = progress > 0;
  const warn = [...spec.noRole.map((n) => `${n}: no role`), ...spec.noRange.map((n) => `${n}: no range`)];
  const head = fmuHeadline(state);
  const changes = state && state.tracked
    ? [...(state.added || []).map((n) => `+ ${n}`), ...(state.removed || []).map((n) => `− ${n}`),
      ...(state.changed || []).map((n) => `~ ${n} (role or range)`), ...(state.timestep ? ['~ timesteps per hour'] : [])]
    : [];

  if (!filesUploaded) {
    return (
      <section className="gw-card fx-fmu">
        <h2>FMU</h2>
        <p className="muted">Upload an IDF and an EPW file, and choose what the controller reads and writes in Sensors &amp; actuators.</p>
      </section>
    );
  }

  return (
    <section className="gw-card fx-fmu">
      <h2>FMU</h2>
      <p className={`fx-state fx-state--${head.tone}`} role="status">
        {head.text}
        {state?.exportedAt && <span className="muted"> Last export: {state.exportedAt.replace('T', ' ')}.</span>}
      </p>
      {changes.length > 0 && (
        <details className="fx-changes" open={changes.length <= 6 || undefined}>
          <summary>What changed</summary>
          <ul>{changes.map((c) => <li key={c}><code>{c}</code></li>)}</ul>
        </details>
      )}
      <p className="gw-note">
        Converts the model to an FMU, and to a baseline FMU without your inputs, and writes both with <code>parameters.py</code>{' '}
        to <code>Field/</code>. What goes in is chosen in <Link to="/sensors_actuators">Sensors &amp; actuators</Link>;
        the period is the one above.
      </p>
      {warn.length > 0 && <p className="me-warn fx-note">Not set: {warn.join(' · ')}</p>}
      <div className="fx-row fx-row-center">
        <button type="button" className="fx-export" onClick={doExport} disabled={busy || per.errors.length > 0}>
          <Download size={16} aria-hidden="true" /> {busy ? 'Exporting…' : 'Export FMU'}
        </button>
        <button type="button" className="me-btn" onClick={downloadBundle} disabled={busy || !state?.exported}
          title="The model, the weather file, the FMUs, parameters.py and points.yaml in one zip">
          Download zip
        </button>
        {busy && (
          <div className="fx-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>
      {status && <p className={status.kind === 'error' ? 'me-error fx-msg' : 'fx-msg fx-ok'}>{status.text}</p>}

      <details className="fx-params">
        <summary>parameters.py{edited !== null ? ' (edited)' : ''}</summary>
        <div className="fx-head-actions">
          {edited !== null && (
            <button type="button" className="fx-link" onClick={() => setEdited(null)}>edited · regenerate from selections</button>
          )}
          <button type="button" className="me-btn" onClick={() => copyText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <textarea className="fx-text" spellCheck={false} value={text}
          rows={Math.max(12, text.split('\n').length + 1)}
          onChange={(e) => setEdited(e.target.value === generated ? null : e.target.value)} />
        <p className="me-muted fx-msg">
          Saved exactly as written; only the <code>fmu_path</code> line is set to the FMU actually generated.
          The notebooks import it with <code>from parameters import parameter</code>.
        </p>
      </details>
    </section>
  );
}
