// Thermostats as their timetable, every number a box.
//
// One table per regime -- zones whose heating and cooling profiles are the
// same -- laid out the way the schedule works (Input Output Reference, Zone
// Controls - Thermostats; Schedules): for heating and for cooling, the season
// it is on, then each day type with its time slots and the temperature of each.
//
// Every number is a box that can be changed. Two different things can be done
// with it, and the panel keeps them apart:
//   change the value   edits the model itself. Changes wait until "Applica al
//                      modello", which writes them (backend: thermostats.edit,
//                      which refuses hours or dates out of order).
//   varia              makes it a design variable: "da" and "a" boxes appear,
//                      and it goes into the problem, not into the model.
//
// Hours and dates are typed plainly: "5" or "05:00"; a day and a month. Where
// heating and cooling change at the same hour or on the same date the box is
// shared, and writes to both.

import { useState } from 'react';
import { api } from './api';

const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS_IN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

const slug = (t) =>
  String(t).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
const pad = (n) => String(n).padStart(2, '0');
const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);
const zoneWord = (n) => (n === 1 ? 'zona' : 'zone');

const fromDoy = (doy) => {
  let m = 0;
  let d = doy;
  while (d > DAYS_IN[m]) {
    d -= DAYS_IN[m];
    m += 1;
  }
  return [m + 1, d];
};
const toDoy = (m, d) => DAYS_IN.slice(0, m - 1).reduce((a, b) => a + b, 0) + d;
const dateLabel = (doy) => {
  const [m, d] = fromDoy(doy);
  return `${d} ${MONTHS[m - 1]}`;
};
const through = (doy) => {
  const [m, d] = fromDoy(doy);
  return `Through: ${d} ${MONTHS_EN[m - 1]}`;
};
const doyOfThrough = (text) => {
  const [d, mon] = text.replace('Through:', '').trim().split(' ');
  return toDoy(MONTHS_EN.indexOf(mon) + 1, Number(d));
};
const hh = (h) => `${pad(Math.floor(h))}:${pad(Math.round((h % 1) * 60))}`;
const parseHour = (text) => {
  const t = String(text).trim();
  const m = t.match(/^(\d{1,2})(?::(\d{2}))?$/);
  if (!m) return null;
  const h = Number(m[1]) + (m[2] ? Number(m[2]) / 60 : 0);
  return h >= 0 && h <= 24 ? h : null;
};
const hourOfUntil = (text) => parseHour(text.replace('Until:', '').trim());

// ---- the boxes ------------------------------------------------------------------

function TempBox({ value, onChange, width = '4.5rem' }) {
  return (
    <span className="tt-unit">
      <input
        className="tt-box"
        style={{ width }}
        type="number"
        step="0.5"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
      />
      °C
    </span>
  );
}

// Typed as text: "5", "05", "5:30", "05:00". Kept as typed until it parses.
function HourBox({ value, onChange }) {
  const [text, setText] = useState(null);
  const shown = text ?? (value == null ? '' : hh(value));
  return (
    <input
      className="tt-box tt-hour"
      type="text"
      inputMode="numeric"
      placeholder="hh:mm"
      value={shown}
      onChange={(e) => {
        setText(e.target.value);
        onChange(parseHour(e.target.value));
      }}
      onBlur={() => setText(null)}
    />
  );
}

function DateBox({ value, onChange }) {
  const [m, d] = value == null ? [null, null] : fromDoy(value);
  const set = (month, day) => {
    if (!month || !day) return onChange(null);
    const clamped = Math.min(day, DAYS_IN[month - 1]);
    return onChange(toDoy(month, clamped));
  };
  return (
    <span className="tt-date">
      <input
        className="tt-box tt-day"
        type="number"
        min="1"
        max="31"
        value={d ?? ''}
        onChange={(e) => set(m, Number(e.target.value))}
      />
      <select className="tt-box tt-month" value={m ?? ''} onChange={(e) => set(Number(e.target.value), d)}>
        {MONTHS.map((name, i) => (
          <option key={name} value={i + 1}>
            {name}
          </option>
        ))}
      </select>
    </span>
  );
}

const BOX = { temp: TempBox, hour: HourBox, date: DateBox };

// A number of the timetable: its value (editable, staged for the model) and,
// on demand, the range it may take as a design variable.
function Num({ type, model, pending, onValue, variable, onVary, limits }) {
  const Box = BOX[type];
  const value = pending ?? model;
  const changed = pending != null && pending !== model;
  const fmt = (v) => (type === 'hour' ? hh(v) : type === 'date' ? dateLabel(v) : `${v} °C`);
  const out =
    (limits && value != null && (value < limits[0] || value > limits[1])) ||
    (type === 'temp' && value == null);
  const rangeBad =
    variable &&
    (variable.lo == null ||
      variable.hi == null ||
      variable.hi <= variable.lo ||
      (limits && (variable.lo < limits[0] || variable.hi > limits[1])));

  return (
    <span className={`tt-num ${changed ? 'tt-changed' : ''} ${variable ? 'tt-varied' : ''}`}>
      <Box value={value} onChange={(v) => onValue(v)} />
      <button
        type="button"
        className="tt-vary"
        onClick={() => onVary(variable ? null : 'on')}
        title={variable ? 'torna a un valore fisso' : 'fanne una variabile di progetto'}
      >
        {variable ? 'fisso' : 'varia'}
      </button>
      {variable && (
        <span className="tt-range">
          da <Box value={variable.lo} onChange={(v) => onVary({ ...variable, lo: v })} width="4rem" />
          a <Box value={variable.hi} onChange={(v) => onVary({ ...variable, hi: v })} width="4rem" />
        </span>
      )}
      {out && <span className="tt-error">fuori dai limiti {limits && `(${fmt(limits[0])}–${fmt(limits[1])})`}</span>}
      {rangeBad && (
        <span className="tt-error">
          intervallo non valido{limits ? ` (limiti ${fmt(limits[0])}–${fmt(limits[1])})` : ''}
        </span>
      )}
    </span>
  );
}

// ---- the variables --------------------------------------------------------------

const regimeId = (r) =>
  slug(r.zones.length === 1 ? r.zones[0] : `${r.zones[0]}_${r.zones.length}`);

function slotVariable(r, kind, group, block, targets, where, lo, hi) {
  const what = kind === 'heating' ? 'Riscaldamento' : 'Raffrescamento';
  return {
    kind: 'setpoint',
    type: 'range',
    setpoint: kind,
    current: block.value,
    name: `${kind}_${slug(group.days)}_${block.from}_${block.to}_${slug(where)}_${regimeId(r)}`,
    label: `${what} ${group.days} ${hh(block.from)}–${hh(block.to)} (${block.value} °C) · ${where}`,
    unit: '°C',
    min: lo,
    max: hi,
    targets,
  };
}

function hourVariable(r, h, lo, hi) {
  const options = [];
  for (let x = Math.ceil(lo); x <= Math.floor(hi); x += 1) options.push(`Until: ${pad(x)}:00`);
  return {
    kind: 'schedule_time',
    type: 'category',
    current: h.label,
    name: `hour_${slug(h.label)}_${slug(h.days)}_${regimeId(r)}`,
    label: `Cambio delle ${h.label} (${h.days}) · ${r.zones.length} ${zoneWord(r.zones.length)}`,
    choices: options,
    options,
    display: Object.fromEntries(options.map((o) => [o, o.replace('Until: ', '')])),
    targets: h.targets,
  };
}

function seasonVariable(r, s, lo, hi) {
  const options = [];
  for (let x = lo; x < hi; x += 7) options.push(through(x));
  options.push(through(hi));
  const uniq = [...new Set(options)];
  return {
    kind: 'schedule_time',
    type: 'category',
    current: s.label,
    name: `season_${slug(s.label)}_${regimeId(r)}`,
    label: `${cap(s.events.join(' / '))} (${s.label}) · ${r.zones.length} ${zoneWord(r.zones.length)}`,
    choices: uniq,
    options: uniq,
    display: Object.fromEntries(uniq.map((o) => [o, dateLabel(doyOfThrough(o))])),
    targets: s.targets,
  };
}

// ---- one regime --------------------------------------------------------------

function Regime({ regime, chosen, keyOf, setVariable, removeVariable, onIndependent, busyZone, onEdited }) {
  const [zone, setZone] = useState('');
  const [pending, setPending] = useState({});
  const [ranges, setRanges] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const z = zone || null;
  const zoneShared = z && !regime.own[z];
  const where = z ?? `${regime.zones.length} ${zoneWord(regime.zones.length)}`;
  const inZone = (kind, targets) =>
    z ? targets.filter((t) => t.object === regime.zoneSchedules[z]?.[kind]) : targets;

  const hourOf = (id) => regime.hours.find((h) => h.id === id);
  const seasonOf = (id) => regime.seasons.find((s) => s.id === id);

  // What each box stands for: how its value is written to the model, and the
  // design variable it becomes with a range.
  const spec = (box) => {
    if (box.type === 'hour') {
      const h = hourOf(box.id);
      return {
        pkey: `hour:${h.id}`,
        store: (v) => v,
        show: (v) => v,
        model: h.hour,
        limits: [h.min, h.max],
        write: (v) => ({ targets: h.targets, value: `Until: ${hh(v)}` }),
        make: (lo, hi) => hourVariable(regime, h, lo, hi),
        probe: hourVariable(regime, h, h.min, h.max),
        read: (v) => ({ lo: hourOfUntil(v.options[0]), hi: hourOfUntil(v.options[v.options.length - 1]) }),
      };
    }
    if (box.type === 'date') {
      const s = seasonOf(box.id);
      // A season's first day is the day after the Through date it moves.
      const shift = box.start ? 1 : 0;
      return {
        // One pending value per season date, kept as the Through day, so the
        // "from 15 ott" and "to 14 ott" boxes of the same date move together.
        pkey: `season:${s.id}`,
        store: (v) => v - shift,
        show: (v) => v + shift,
        model: s.end + shift,
        limits: [s.min + shift, s.max + shift],
        write: (v) => ({ targets: s.targets, value: through(v - shift) }),
        make: (lo, hi) => seasonVariable(regime, s, lo - shift, hi - shift),
        probe: seasonVariable(regime, s, s.min, s.max),
        read: (v) => ({
          lo: doyOfThrough(v.options[0]) + shift,
          hi: doyOfThrough(v.options[v.options.length - 1]) + shift,
        }),
      };
    }
    const targets = inZone(box.kind, box.block.targets);
    return {
      pkey: box.boxId,
      store: (v) => v,
      show: (v) => v,
      model: box.block.value,
      limits: null,
      write: (v) => ({ targets, value: String(v) }),
      make: (lo, hi) => slotVariable(regime, box.kind, box.group, box.block, targets, where, lo, hi),
      probe: slotVariable(regime, box.kind, box.group, box.block, targets, where, 0, 0),
      read: (v) => ({ lo: v.min, hi: v.max }),
    };
  };

  const num = (box) => {
    const s = spec(box);
    const key = keyOf(s.probe);
    const inProblem = chosen[key];
    const draft = ranges[key];
    const variable = draft ?? (inProblem ? s.read(inProblem) : null);
    return (
      <Num
        key={box.boxId}
        type={box.type}
        model={s.model}
        limits={s.limits}
        pending={pending[s.pkey] ? s.show(pending[s.pkey].v) : undefined}
        onValue={(v) => {
          setMessage(null);
          setPending((cur) => {
            const next = { ...cur };
            if (v == null || v === s.model) delete next[s.pkey];
            else next[s.pkey] = { v: s.store(v), change: s.write(v) };
            return next;
          });
        }}
        variable={variable}
        onVary={(r) => {
          if (r === null) {
            setRanges((cur) => ({ ...cur, [key]: undefined }));
            removeVariable(key);
            return;
          }
          const next =
            r === 'on'
              ? box.type === 'temp'
                ? { lo: s.model - 2, hi: s.model + 2 }
                : box.type === 'hour'
                ? { lo: Math.max(s.limits[0], s.model - 1), hi: Math.min(s.limits[1], s.model + 1) }
                : { lo: Math.max(s.limits[0], s.model - 14), hi: Math.min(s.limits[1], s.model + 14) }
              : r;
          setRanges((cur) => ({ ...cur, [key]: next }));
          const ok =
            next.lo != null &&
            next.hi != null &&
            next.hi > next.lo &&
            (!s.limits || (next.lo >= s.limits[0] && next.hi <= s.limits[1]));
          if (ok) setVariable(s.make(next.lo, next.hi));
          else removeVariable(key);
        }}
      />
    );
  };

  const apply = () => {
    setSaving(true);
    setMessage(null);
    fetch(api('/surrogate_modeling/thermostat_edit'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ changes: Object.values(pending).map((p) => p.change) }),
    })
      .then(async (r) => ({ ok: r.ok, body: await r.json() }))
      .then(({ ok, body }) => {
        if (!ok) {
          setMessage({ kind: 'error', text: body.error ?? 'Modifica rifiutata.' });
          return;
        }
        setPending({});
        setMessage({ kind: 'ok', text: `Modello aggiornato (${body.written} campi).` });
        return onEdited();
      })
      .catch(() => setMessage({ kind: 'error', text: 'Modifica non riuscita.' }))
      .finally(() => setSaving(false));
  };

  const nPending = Object.keys(pending).length;

  const section = (v) => {
    const what = v.kind === 'heating' ? 'Riscaldamento' : 'Raffrescamento';
    if (v.never) {
      return (
        <tbody key={v.kind}>
          <tr className="tt-season">
            <td colSpan={3}>
              <b>{what}</b> <span className="tt-muted">spento tutto l&apos;anno</span>
            </td>
          </tr>
        </tbody>
      );
    }
    return (
      <tbody key={v.kind + v.spans.map((s) => s.start).join()}>
        <tr className="tt-season">
          <td colSpan={3}>
            <b>{what}</b>{' '}
            {v.allYear ? (
              <span className="tt-muted">acceso tutto l&apos;anno</span>
            ) : (
              v.spans.map((sp, i) => (
                <span key={i} className="tt-span">
                  {i > 0 && ' e '}acceso dal{' '}
                  {sp.startSeason
                    ? num({ type: 'date', id: sp.startSeason, start: true, boxId: `${v.kind}:start:${sp.startSeason}` })
                    : <b>{dateLabel(sp.start)}</b>}{' '}
                  al{' '}
                  {sp.endSeason
                    ? num({ type: 'date', id: sp.endSeason, start: false, boxId: `${v.kind}:end:${sp.endSeason}` })
                    : <b>{dateLabel(sp.end)}</b>}
                </span>
              ))
            )}
          </td>
        </tr>
        {v.groups.map((g) =>
          g.blocks.map((b, j) => (
            <tr key={`${g.days}-${j}`} className={j === 0 ? 'tt-first' : ''}>
              <td className="tt-days">{j === 0 ? cap(g.days) : ''}</td>
              <td className="tt-slot">
                {b.from === 0 && b.to === 24 ? (
                  <span className="tt-muted">tutto il giorno</span>
                ) : (
                  <>
                    dalle{' '}
                    {b.fromHour ? num({ type: 'hour', id: b.fromHour, boxId: `hour:${b.fromHour}` }) : <b>{hh(b.from)}</b>}{' '}
                    alle{' '}
                    {b.toHour ? num({ type: 'hour', id: b.toHour, boxId: `hour:${b.toHour}` }) : <b>{hh(b.to)}</b>}
                  </>
                )}
              </td>
              <td className="tt-temp">
                {b.off ? (
                  <span className="tt-muted">spento</span>
                ) : zoneShared ? (
                  <b>{b.value} °C</b>
                ) : (
                  num({
                    type: 'temp',
                    kind: v.kind,
                    group: g,
                    block: b,
                    boxId: `${v.kind}:${g.days}:${j}:${z ?? ''}`,
                  })
                )}
              </td>
            </tr>
          ))
        )}
      </tbody>
    );
  };

  return (
    <section className="tt-regime">
      <header className="tt-head">
        <span className="tt-title">
          {regime.zones.length} {zoneWord(regime.zones.length)}
        </span>
        <span className="tt-zones">{regime.zones.join(' · ')}</span>
        {regime.zones.length > 1 && (
          <label className="tt-scope">
            temperature di
            <select value={zone} onChange={(e) => setZone(e.target.value)}>
              <option value="">tutte le {regime.zones.length} zone</option>
              {regime.zones.map((name) => (
                <option key={name} value={name}>
                  solo {name}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      {!regime.writable ? (
        <p className="tt-note">
          Setpoint in uno schedule che qui si legge ma non si modifica (Schedule:Year o
          Schedule:File).
        </p>
      ) : (
        <>
          {zoneShared && (
            <p className="tt-note">
              {z} legge gli stessi schedule di altre zone: per cambiarne le temperature da sola
              le serve una copia sua.{' '}
              <button
                type="button"
                className="tt-link"
                disabled={busyZone === z}
                onClick={() => onIndependent(z)}
              >
                {busyZone === z ? 'la rendo indipendente…' : 'Rendila indipendente'}
              </button>
            </p>
          )}
          <table className="tt-table">
            <thead>
              <tr>
                <th>Giorni</th>
                <th>Fascia oraria</th>
                <th>Temperatura</th>
              </tr>
            </thead>
            {regime.view.map(section)}
          </table>
          <div className="tt-actions">
            <button type="button" className="tt-apply" disabled={!nPending || saving} onClick={apply}>
              {saving ? 'Scrivo nel modello…' : `Applica al modello${nPending ? ` (${nPending})` : ''}`}
            </button>
            {nPending > 0 && (
              <button type="button" className="tt-link" onClick={() => setPending({})}>
                annulla modifiche
              </button>
            )}
            {message && <span className={message.kind === 'ok' ? 'dp-ok' : 'dp-error'}>{message.text}</span>}
          </div>
        </>
      )}
    </section>
  );
}

export default function ThermostatPanel({
  data,
  chosen,
  keyOf,
  setVariable,
  removeVariable,
  onIndependent,
  busyZone,
  onEdited,
}) {
  const regimes = data?.regimes ?? [];
  if (!regimes.length) return null;
  return (
    <li className="dp-card tt-panel">
      <div className="dp-row-head dp-static">
        <span className="dp-title">Termostati</span>
      </div>
      <p className="tt-intro">
        Cambia un numero e premi <b>Applica al modello</b> per modificare il modello. Premi{' '}
        <b>varia</b> per farne una variabile di progetto, con i valori da… a….
      </p>
      {regimes.map((r) => (
        <Regime
          key={r.zones.join('|')}
          regime={r}
          chosen={chosen}
          keyOf={keyOf}
          setVariable={setVariable}
          removeVariable={removeVariable}
          onIndependent={onIndependent}
          busyZone={busyZone}
          onEdited={onEdited}
        />
      ))}
    </li>
  );
}
