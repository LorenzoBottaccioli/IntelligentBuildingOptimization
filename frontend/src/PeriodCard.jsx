// PeriodCard.jsx
// The simulated period, in ONE place: used by the Control room (the FMU export and the direct run),
// which read and overwrite the same four lines of Field/parameters.py (backend/run_period.py).
import React from 'react';
import './FmuExport.css';

const DAY = 86400;
// IDD 9.6, Timestep: "Must be evenly divisible into 60".
export const TIMESTEPS = [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60];

export const whole = (x) => Number.isInteger(x) && x >= 0;

/** FMU time 0 is midnight of 1 January; day d starts at d * 86400 s. */
export function dayLabel(d) {
  // 2021 is not a leap year; the weather file in the FMU decides the real one.
  return new Date(Date.UTC(2021, 0, 1) + d * DAY * 1000)
    .toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

/** The period as fmi_gym reads it, plus what is wrong with it. */
export function periodOf(p) {
  const start = Number(p.startDay);
  const warm = Number(p.warmupDays);
  const end = Number(p.endDay);
  const errors = [];
  // EnergyPlus starts and stops the FMU at midnight only.
  if (![start, warm, end].every(whole)) errors.push('Days must be whole numbers (the FMU starts and stops at midnight).');
  else {
    if (end > 365) errors.push('The end day must be at most 365.');
    if (start + warm >= end) errors.push('The controller must get at least one day: start + warm-up must be before the end.');
  }
  return { start, warm, end, control: start + warm, errors };
}

/** What the backend takes: the four numbers, nothing typed as text. */
export const periodBody = (p) => ({
  timestep: Number(p.timestep), startDay: Number(p.startDay),
  warmupDays: Number(p.warmupDays), endDay: Number(p.endDay),
});

/**
 * The four fields (timesteps per hour, start day, warm-up days, end day) with their dates and
 * the validation messages. `period` holds what is typed; `onChange(next)` gets the whole object.
 */
export function PeriodFields({ period, onChange, modelTimestep, disabled = false }) {
  const per = periodOf(period);
  const set = (key) => (e) => onChange({ ...period, [key]: key === 'timestep' ? Number(e.target.value) : e.target.value });
  return (
    <>
      <div className="fx-row">
        <label className="fx-field">Timesteps per hour
          <select value={period.timestep} onChange={set('timestep')} disabled={disabled}>
            {TIMESTEPS.map((n) => <option key={n} value={n}>{n}{n === modelTimestep ? ' (model)' : ''}</option>)}
          </select>
        </label>
        <label className="fx-field">Start day
          <input type="number" min="0" max="364" step="1" value={period.startDay} onChange={set('startDay')} disabled={disabled} />
          <small>{whole(per.start) ? dayLabel(per.start) : '–'}</small>
        </label>
        <label className="fx-field">Warm-up days
          <input type="number" min="0" step="1" value={period.warmupDays} onChange={set('warmupDays')} disabled={disabled} />
          <small>{per.warm > 0 ? `actions = 0 until ${dayLabel(per.control)}` : 'none'}</small>
        </label>
        <label className="fx-field">End day
          <input type="number" min="1" max="365" step="1" value={period.endDay} onChange={set('endDay')} disabled={disabled} />
          <small>{whole(per.end) ? dayLabel(per.end) : '–'}</small>
        </label>
      </div>
      {per.errors.map((e) => <p key={e} className="me-error fx-msg">{e}</p>)}
    </>
  );
}
