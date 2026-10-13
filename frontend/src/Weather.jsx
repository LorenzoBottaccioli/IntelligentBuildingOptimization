// Weather.jsx
// The two pages of the Weather section of the blue sidebar:
//   WeatherEditorPage   look inside an EPW file (header, statistics, daily curves) and change it
//   WeatherLibraryPage  build annual EPW files from Open-Meteo for the years the student chooses,
//                       and keep them in a library that both pages share
// The files themselves are read and written by the backend (pyepw); a file is named by its `source`:
// 'session' (the EPW the model runs with) or 'lib:<name>' (the library).
import React, { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Download, Pencil, Plus, Search, Trash2, Upload, X } from 'lucide-react';
import { api } from './api';
import { AppContext } from './AppContext';
import './Weather.css';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const num = (x, d = 1) => (x == null || Number.isNaN(x) ? '–' : Number(x).toFixed(d));
const errText = (err, fallback) => err?.response?.data?.error || err?.message || fallback;
const sourceUrl = (path, source) => api(`/weather/${path}?source=${encodeURIComponent(source)}`);

// ---------------------------------------------------------------------------- the shared library
const CHANGED = 'weather-library-changed';
const notifyLibrary = () => window.dispatchEvent(new Event(CHANGED));

function useLibrary() {
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);
  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(api('/weather/files'));
      setFiles(data.files || []);
      setError(null);
    } catch (err) {
      setError(errText(err, 'The backend is not reachable.'));
    }
  }, []);
  useEffect(() => {
    load();
    window.addEventListener(CHANGED, load);
    return () => window.removeEventListener(CHANGED, load);
  }, [load]);
  return { files, error, reload: load };
}

function useFlash() {
  const [msg, setMsg] = useState(null);
  const timer = useRef(null);
  const flash = useCallback((text, error = false) => {
    clearTimeout(timer.current);
    setMsg({ text, error });
    timer.current = setTimeout(() => setMsg(null), error ? 12000 : 7000);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);
  return [msg, flash];
}

/** Make a library file the session's weather (uploads/, exported FMUs, the problem notebook). */
async function adoptAsSessionWeather(source, name, updateWeatherFile) {
  if (!window.confirm(
    `Use ${name} as the weather of this session?\n\nIt replaces the EPW the model runs with, the weather inside the `
    + 'exported FMUs, the weather file named in your surrogate-problem notebook and the one in the tutorial notebooks '
    + '(their results then no longer match the text). The building model is not touched.'
  )) return null;
  const { data } = await axios.post(api('/weather/use'), { source, tutorials: true });
  updateWeatherFile(data.used.epw);
  notifyLibrary();
  const bits = [`${name} is now the session weather.`];
  if (data.used.kept) bits.push(`The previous session weather, ${data.used.kept}, is in the library.`);
  if (data.used.fmus) bits.push(`${data.used.fmus} exported FMU${data.used.fmus === 1 ? '' : 's'} updated.`);
  if (data.used.fmu_errors?.length) bits.push(`FMU errors: ${data.used.fmu_errors.join('; ')}`);
  if (data.used.notebook) bits.push('The surrogate-problem notebook was updated.');
  if (data.used.tutorials?.length) bits.push(`${data.used.tutorials.length} tutorial notebook(s) updated.`);
  if (data.used.notebook || data.used.tutorials?.length) bits.push('Restart a notebook that is already open.');
  return bits.join(' ');
}

// ---------------------------------------------------------------------------- charts
function niceTicks(lo, hi, count = 5) {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

/**
 * Daily curves over the year. `series` are [{values, color, label, width}]; `band` is an optional
 * {lo, hi, color} area (daily min to max). Hover shows the day's values.
 */
function YearChart({ title, unit, months, days, series, band, digits = 1 }) {
  const W = 760, H = 220, L = 46, R = 12, T = 12, B = 26;
  const [hover, setHover] = useState(null);
  const n = months.length;
  const all = [
    ...series.flatMap((s) => s.values),
    ...(band ? [...band.lo, ...band.hi] : []),
  ].filter((v) => v != null);
  if (!n || !all.length) return null;
  let lo = Math.min(...all), hi = Math.max(...all);
  if (lo > 0 && lo < (hi - lo) * 0.3) lo = 0;     // radiation: start the axis at zero
  const pad = (hi - lo) * 0.06 || 1;
  lo -= lo === 0 ? 0 : pad; hi += pad;
  const ticks = niceTicks(lo, hi);
  const x = (i) => L + (i / (n - 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const path = (vals) => vals.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`))
    .filter(Boolean).map((p, i) => `${i ? 'L' : 'M'}${p}`).join('');
  const starts = months.map((m, i) => (i === 0 || m !== months[i - 1] ? i : -1)).filter((i) => i >= 0);
  const area = band && `${band.hi.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')}`
    + `${band.lo.map((v, i) => `L${x(n - 1 - i).toFixed(1)},${y(band.lo[n - 1 - i]).toFixed(1)}`).join('')}Z`;
  const move = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.max(0, Math.min(n - 1, Math.round(((px - L) / (W - L - R)) * (n - 1)))));
  };
  return (
    <figure className="wx-chart">
      <figcaption>
        <strong>{title}</strong> <span className="wx-unit">{unit}</span>
        <span className="wx-readout">
          {hover != null && (
            <>
              {days[hover]} {MONTHS[months[hover] - 1]}
              {series.map((s) => (
                <span key={s.label} style={{ color: s.color }}> · {s.label} {num(s.values[hover], digits)}</span>
              ))}
              {band && <span> · range {num(band.lo[hover], digits)} to {num(band.hi[hover], digits)}</span>}
            </>
          )}
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}, daily values over the year`}
        onMouseMove={move} onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="wx-grid" />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" className="wx-tick">{t}</text>
          </g>
        ))}
        {starts.map((i) => (
          <text key={i} x={x(i)} y={H - 8} className="wx-tick">{MONTHS[months[i] - 1]}</text>
        ))}
        {band && <path d={area} fill={band.color} opacity="0.35" />}
        {series.map((s) => (
          <path key={s.label} d={path(s.values)} fill="none" stroke={s.color} strokeWidth={s.width || 1.6} />
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} className="wx-cursor" />}
      </svg>
    </figure>
  );
}

const GREY = '#8a93a0';
const BRAND = 'rgb(238, 81, 8)';
const NAVY = '#003366';

function Charts({ base, edited }) {
  const d = base.daily;
  const e = edited?.daily;
  return (
    <div className="wx-charts">
      <YearChart title="Outdoor temperature" unit="°C (daily mean, band = daily min to max)"
        months={d.month} days={d.day}
        band={{ lo: d.temp_min, hi: d.temp_max, color: e ? '#cfd5dc' : '#b9cde3' }}
        series={[
          { values: d.temp_mean, color: e ? GREY : NAVY, label: e ? 'file' : 'mean' },
          ...(e ? [{ values: e.temp_mean, color: BRAND, label: 'edited' }] : []),
        ]} />
      <YearChart title="Global horizontal radiation" unit="kWh/m² per day" digits={2}
        months={d.month} days={d.day}
        series={[
          { values: d.ghi_kwh_m2, color: e ? GREY : NAVY, label: e ? 'file' : 'daily' },
          ...(e ? [{ values: e.ghi_kwh_m2, color: BRAND, label: 'edited' }] : []),
        ]} />
    </div>
  );
}

// ---------------------------------------------------------------------------- hourly view
const HOURLY_COLORS = ['#003366', '#2a9d8f', '#8e44ad', '#c0392b', '#b8860b', '#1e7e4f', '#d35400', '#5d6d7e'];
const DEFAULT_VARS = ['dry_bulb_temperature'];
const MIN_SPAN = 24;                       // the closest zoom: one day of hours

function stamp(h, i, long) {
  const d = `${h.day[i]} ${MONTHS[h.month[i] - 1]}`;
  return long ? `${d}, hour ${h.hour[i]}` : d;
}

/** One panel: a variable over the visible hours, min-max band when there are more hours than pixels. */
function HourlyPanel({ label, unit, values, edited, range, color, hover, W, onHover }) {
  const H = 104, L = 44, R = 8, T = 8, B = 6;
  const [a, b] = range;
  const cols = Math.min(b - a, W - L - R);
  const bucket = (vals) => {
    const out = [];
    for (let c = 0; c < cols; c += 1) {
      const from = a + Math.floor(((b - a) * c) / cols);
      const to = Math.max(from + 1, a + Math.floor(((b - a) * (c + 1)) / cols));
      let lo = Infinity, hi = -Infinity, sum = 0, n = 0;
      for (let i = from; i < to; i += 1) {
        const v = vals[i];
        if (v != null) { lo = Math.min(lo, v); hi = Math.max(hi, v); sum += v; n += 1; }
      }
      out.push(n ? { lo, hi, mean: sum / n } : null);
    }
    return out;
  };
  const base = bucket(values);
  const ed = edited ? bucket(edited) : null;
  const all = [...base, ...(ed || [])].filter(Boolean);
  if (!all.length) return <div className="wx-panel wx-panel--empty">{label}: no data in this range</div>;
  let lo = Math.min(...all.map((p) => p.lo)), hi = Math.max(...all.map((p) => p.hi));
  if (lo >= 0 && lo < (hi - lo) * 0.3) lo = 0;
  if (hi === lo) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.05;
  hi += pad; if (lo !== 0) lo -= pad;
  const ticks = niceTicks(lo, hi, 3);
  const x = (c) => L + (c / Math.max(1, cols - 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const line = (pts) => pts.map((p, c) => (p ? `${x(c).toFixed(1)},${y(p.mean).toFixed(1)}` : null))
    .filter(Boolean).map((s, i) => `${i ? 'L' : 'M'}${s}`).join('');
  const bandPath = (pts) => {
    const up = pts.map((p, c) => (p ? [c, p] : null)).filter(Boolean);
    return up.map(([c, p], i) => `${i ? 'L' : 'M'}${x(c).toFixed(1)},${y(p.hi).toFixed(1)}`).join('')
      + [...up].reverse().map(([c, p]) => `L${x(c).toFixed(1)},${y(p.lo).toFixed(1)}`).join('') + 'Z';
  };
  const decimated = b - a > cols;
  const hc = hover != null && hover >= a && hover < b ? Math.round(((hover - a) / (b - a)) * (cols - 1)) : null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="wx-panel" role="img" aria-label={`${label}, hourly values`}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        const px = ((e.clientX - r.left) / r.width) * W;
        onHover(Math.max(a, Math.min(b - 1, a + Math.round(((px - L) / (W - L - R)) * (b - a - 1)))));
      }}>
      <text x={L} y={T + 2} className="wx-panel__title" fill={color}>{label} <tspan className="wx-unit">{unit}</tspan></text>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="wx-grid" />
          <text x={L - 5} y={y(t) + 4} textAnchor="end" className="wx-tick">{t}</text>
        </g>
      ))}
      {decimated && <path d={bandPath(base)} fill={color} opacity="0.18" />}
      <path d={line(base)} fill="none" stroke={ed ? GREY : color} strokeWidth="1.3" />
      {ed && <path d={line(ed)} fill="none" stroke={BRAND} strokeWidth="1.3" />}
      {hc != null && <line x1={x(hc)} x2={x(hc)} y1={T} y2={H - B} className="wx-cursor" />}
    </svg>
  );
}

/**
 * The file hour by hour: pick the variables, zoom with the wheel or the presets, drag to move,
 * or scroll with the bar. With a preview shown (`edits`), the edited values are drawn over the file's.
 */
function HourlyView({ source, edits }) {
  const [data, setData] = useState(null);          // {month, day, hour, vars}
  const [edited, setEdited] = useState(null);
  const [error, setError] = useState(null);
  const [chosen, setChosen] = useState(DEFAULT_VARS);
  const [range, setRange] = useState([0, 8760]);
  const [hover, setHover] = useState(null);
  const box = useRef(null);
  const drag = useRef(null);
  const [W, setW] = useState(640);

  useEffect(() => {
    let alive = true;
    setData(null); setEdited(null); setError(null);
    axios.get(api('/weather/series'), { params: { source } })
      .then(({ data: d }) => {
        if (!alive) return;
        setData(d.base);
        setRange([0, d.base.month.length]);
      })
      .catch((err) => { if (alive) setError(errText(err, 'The hourly values could not be read.')); });
    return () => { alive = false; };
  }, [source]);

  const editsKey = edits ? JSON.stringify(edits) : '';
  useEffect(() => {
    if (!edits) { setEdited(null); return undefined; }
    let alive = true;
    axios.post(api('/weather/series'), { source, ...edits })
      .then(({ data: d }) => { if (alive) setEdited(d.edited || null); })
      .catch(() => { if (alive) setEdited(null); });
    return () => { alive = false; };
  }, [editsKey, source]); // eslint-disable-line

  useEffect(() => {
    if (!box.current || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.round(e.contentRect.width))));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, [data]);

  const n = data?.month.length || 0;
  const clamp = (a, b) => {
    const span = Math.max(MIN_SPAN, Math.min(n, b - a));
    const start = Math.max(0, Math.min(n - span, a));
    return [Math.round(start), Math.round(start + span)];
  };
  const zoomAt = (frac, factor) => setRange(([a, b]) => {
    const span = (b - a) * factor;
    const focus = a + (b - a) * frac;
    return clamp(focus - span * frac, focus + span * (1 - frac));
  });

  // The wheel needs a non-passive listener to keep the page from scrolling while zooming.
  useEffect(() => {
    const el = box.current;
    if (!el || !n) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const frac = Math.max(0, Math.min(1, ((e.clientX - r.left) / r.width * W - 44) / (W - 52)));
      zoomAt(frac, e.deltaY < 0 ? 0.8 : 1.25);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }); // eslint-disable-line

  const down = (e) => { drag.current = { x: e.clientX, range }; };
  const move = (e) => {
    if (!drag.current) return;
    const r = box.current.getBoundingClientRect();
    const [a, b] = drag.current.range;
    const dh = ((drag.current.x - e.clientX) / r.width) * (W / (W - 52)) * (b - a);
    setRange(clamp(a + dh, b + dh));
  };
  const up = () => { drag.current = null; };

  const toggle = (id) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  const span = range[1] - range[0];
  const preset = (hours) => setRange(([a, b]) => {
    const mid = (a + b) / 2;
    return clamp(mid - hours / 2, mid + hours / 2);
  });
  const ticks = useMemo(() => {
    if (!n) return [];
    const count = 6;
    return Array.from({ length: count }, (_, k) => range[0] + Math.round(((range[1] - range[0] - 1) * k) / (count - 1)));
  }, [range, n]);

  if (error) return <p className="wx-error" role="alert">{error}</p>;
  if (!data) return <p className="muted">Reading the hourly values…</p>;
  const ids = data.order;
  return (
    <div className="wx-hourly">
      <div className="wx-vars" role="group" aria-label="Variables to show">
        {ids.map((id, k) => (
          <button key={id} type="button" className={chosen.includes(id) ? 'is-on' : ''} aria-pressed={chosen.includes(id)}
            onClick={() => toggle(id)} title={`${data.vars[id].label} (${data.vars[id].unit})`}>
            <i style={{ background: HOURLY_COLORS[k % HOURLY_COLORS.length] }} aria-hidden="true" />
            {data.vars[id].label}
          </button>
        ))}
      </div>
      <div className="wx-zoom">
        <button type="button" onClick={() => setRange([0, n])}>Year</button>
        <button type="button" onClick={() => preset(24 * 30)}>Month</button>
        <button type="button" onClick={() => preset(24 * 7)}>Week</button>
        <button type="button" onClick={() => preset(24)}>Day</button>
        <button type="button" onClick={() => zoomAt(0.5, 0.5)} aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" onClick={() => zoomAt(0.5, 2)} aria-label="Zoom out" title="Zoom out">−</button>
        <span className="wx-unit">
          {stamp(data, range[0])} to {stamp(data, range[1] - 1)} · {span} h
        </span>
      </div>
      <div ref={box} className="wx-panels" onMouseDown={down} onMouseMove={move} onMouseUp={up}
        onMouseLeave={() => { up(); setHover(null); }}>
        {chosen.length === 0 && <p className="muted">Choose at least one variable.</p>}
        {ids.filter((id) => chosen.includes(id)).map((id) => (
          <HourlyPanel key={id} label={data.vars[id].label} unit={data.vars[id].unit} values={data.vars[id].values}
            edited={edited?.[id]} range={range} W={W} hover={hover} onHover={setHover}
            color={HOURLY_COLORS[ids.indexOf(id) % HOURLY_COLORS.length]} />
        ))}
        {chosen.length > 0 && (
          <svg viewBox={`0 0 ${W} 22`} className="wx-axis" aria-hidden="true">
            {ticks.map((i, k) => (
              <text key={i} x={44 + (k / 5) * (W - 52)} y="14" className="wx-tick"
                textAnchor={k === 0 ? 'start' : k === 5 ? 'end' : 'middle'}>{stamp(data, i, span <= 24 * 4)}</text>
            ))}
          </svg>
        )}
      </div>
      <div className="wx-readout wx-readout--hourly" aria-live="polite">
        {hover != null ? (
          <>
            <strong>{stamp(data, hover, true)}</strong>
            {ids.filter((id) => chosen.includes(id)).map((id) => (
              <span key={id}> · {data.vars[id].label} {num(data.vars[id].values[hover], 1)} {data.vars[id].unit}
                {edited?.[id] && edited[id][hover] !== data.vars[id].values[hover] && (
                  <b className="wx-edit-value"> → {num(edited[id][hover], 1)}</b>
                )}
              </span>
            ))}
          </>
        ) : 'Wheel to zoom, drag to move; move over a panel to read the hour.'}
      </div>
      <input type="range" className="wx-scroll-bar" min={0} max={Math.max(0, n - span)} value={range[0]}
        disabled={span >= n} aria-label="Scroll through the year"
        onChange={(e) => setRange(clamp(Number(e.target.value), Number(e.target.value) + span))} />
    </div>
  );
}

// ---------------------------------------------------------------------------- statistics
const TILES = [
  { key: 'temp_mean', label: 'Mean temperature', unit: '°C', d: 1 },
  { key: 'temp_min', label: 'Coldest hour', unit: '°C', d: 1 },
  { key: 'temp_max', label: 'Hottest hour', unit: '°C', d: 1 },
  { key: 'hdd18', label: 'Heating degree-days (base 18 °C)', unit: 'K·day', d: 0 },
  { key: 'cdd24', label: 'Cooling degree-days (base 24 °C)', unit: 'K·day', d: 0 },
  { key: 'ghi_kwh_m2', label: 'Global horizontal radiation', unit: 'kWh/m²', d: 0 },
  { key: 'dni_kwh_m2', label: 'Direct normal radiation', unit: 'kWh/m²', d: 0 },
  { key: 'rh_mean', label: 'Mean relative humidity', unit: '%', d: 0 },
  { key: 'wind_mean', label: 'Mean wind speed', unit: 'm/s', d: 1 },
  { key: 'rain_mm', label: 'Precipitation', unit: 'mm', d: 0 },
];

function Tiles({ base, edited }) {
  return (
    <div className="wx-tiles">
      {TILES.map((t) => {
        const b = base.annual[t.key];
        if (b == null && edited?.annual[t.key] == null) return null;
        const e = edited?.annual[t.key];
        const delta = e != null && b != null ? e - b : null;
        const changed = delta != null && Math.abs(delta) >= 0.5 * 10 ** -t.d;
        return (
          <div key={t.key} className="wx-tile">
            <span className="wx-tile__label">{t.label}</span>
            <span className="wx-tile__value">
              {num(changed ? e : b, t.d)} <small>{t.unit}</small>
            </span>
            {changed && (
              <span className="wx-tile__delta">file {num(b, t.d)} ({delta > 0 ? '+' : ''}{num(delta, t.d)})</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function MonthTable({ base, edited }) {
  const cell = (b, e, d) => (
    <td>
      {num(e != null ? e : b, d)}
      {e != null && b != null && Math.abs(e - b) >= 0.5 * 10 ** -d && <small className="wx-was"> {num(b, d)}</small>}
    </td>
  );
  return (
    <div className="wx-scroll">
      <table className="wx-table">
        <thead>
          <tr>
            <th>Month</th><th>Mean °C</th><th>Min °C</th><th>Max °C</th><th>Radiation kWh/m²</th><th>RH %</th><th>Wind m/s</th>
          </tr>
        </thead>
        <tbody>
          {base.monthly.map((m, i) => {
            const e = edited?.monthly[i];
            return (
              <tr key={m.month}>
                <td>{MONTHS[m.month - 1]}</td>
                {cell(m.temp_mean, e?.temp_mean, 1)}
                {cell(m.temp_min, e?.temp_min, 1)}
                {cell(m.temp_max, e?.temp_max, 1)}
                {cell(m.ghi_kwh_m2, e?.ghi_kwh_m2, 0)}
                {cell(m.rh_mean, e?.rh_mean, 0)}
                {cell(m.wind_mean, e?.wind_mean, 1)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------- the editor page
const LOCATION_LABELS = [
  ['city', 'City'], ['state_province_region', 'State / region'], ['country', 'Country'], ['wmo', 'WMO'],
  ['latitude', 'Latitude (°N)'], ['longitude', 'Longitude (°E)'], ['timezone', 'Time zone (h from UTC)'],
  ['elevation', 'Elevation (m)'],
];
const OPS = [['add', 'Add'], ['scale', 'Multiply by'], ['set', 'Set to']];
const emptyAdjustment = () => ({ variable: 'dry_bulb_temperature', op: 'add', value: '', months: [], keep: 'rh' });

function AdjustmentRow({ adj, variables, onChange, onRemove }) {
  const v = variables.find((x) => x.id === adj.variable);
  const toggle = (m) => onChange({
    months: adj.months.includes(m) ? adj.months.filter((x) => x !== m) : [...adj.months, m].sort((a, b) => a - b),
  });
  return (
    <div className="wx-adj">
      <div className="wx-adj__main">
        <select value={adj.variable} onChange={(e) => onChange({ variable: e.target.value })} aria-label="Variable">
          {variables.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
        </select>
        <select value={adj.op} onChange={(e) => onChange({ op: e.target.value })} aria-label="Operation">
          {OPS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <input type="number" step="any" value={adj.value} placeholder="value" aria-label="Value"
          onChange={(e) => onChange({ value: e.target.value })} />
        <span className="wx-unit">{adj.op === 'scale' ? '×' : v?.unit}</span>
        {adj.variable === 'dry_bulb_temperature' && (
          <select value={adj.keep} onChange={(e) => onChange({ keep: e.target.value })} aria-label="Humidity">
            <option value="rh">Keep relative humidity</option>
            <option value="dew">Keep dew point</option>
          </select>
        )}
        <button type="button" className="wx-icon" onClick={onRemove} title="Remove this adjustment" aria-label="Remove">
          <X size={16} />
        </button>
      </div>
      <div className="wx-months" role="group" aria-label="Months">
        <span className="wx-unit">{adj.months.length ? 'Only in' : 'Whole year; or only in'}</span>
        {MONTHS.map((name, i) => (
          <button key={name} type="button" className={adj.months.includes(i + 1) ? 'is-on' : ''}
            aria-pressed={adj.months.includes(i + 1)} onClick={() => toggle(i + 1)}>{name}</button>
        ))}
      </div>
    </div>
  );
}

export function WeatherEditorPage() {
  const { pathname, state, key } = useLocation();
  const { updateWeatherFile } = useContext(AppContext);
  const lib = useLibrary();
  const [config, setConfig] = useState(null);
  const [source, setSource] = useState('');
  const [data, setData] = useState(null);           // {base, edited, done}
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loc, setLoc] = useState({});
  const [adjs, setAdjs] = useState([]);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(null);           // 'preview' | 'save'
  const [msg, flash] = useFlash();

  useEffect(() => {
    axios.get(api('/weather/config')).then(({ data: c }) => setConfig(c)).catch(() => {});
  }, []);
  useEffect(() => { if (pathname === '/weather_editor') lib.reload(); }, [pathname]); // eslint-disable-line

  // Arrived from the library with a file to open.
  useEffect(() => {
    if (pathname === '/weather_editor' && state?.source) setSource(state.source);
  }, [key]); // eslint-disable-line

  // Without a choice, the session file; without that, the first library file.
  useEffect(() => {
    if (!lib.files.length) { if (source) setSource(''); return; }
    if (!lib.files.some((f) => f.id === source)) setSource(lib.files[0].id);
  }, [lib.files, source]);

  const file = lib.files.find((f) => f.id === source);

  useEffect(() => {
    if (!source) { setData(null); return undefined; }
    let alive = true;
    setLoading(true);
    setError(null);
    setAdjs([]);
    axios.get(api('/weather/inspect'), { params: { source } })
      .then(({ data: d }) => {
        if (!alive) return;
        setData(d);
        setLoc(Object.fromEntries(LOCATION_LABELS.map(([k]) => [k, d.base.location[k] ?? ''])));
        setName(`${d.name.replace(/\.epw$/i, '')}_edited`);
      })
      .catch((err) => { if (alive) { setData(null); setError(errText(err, 'The file could not be read.')); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [source]);

  const edits = useMemo(() => {
    if (!data) return { location: {}, adjustments: [] };
    const location = {};
    LOCATION_LABELS.forEach(([k]) => {
      if (String(loc[k] ?? '') !== String(data.base.location[k] ?? '')) location[k] = loc[k];
    });
    const adjustments = adjs.filter((a) => a.value !== '').map((a) => ({ ...a, value: Number(a.value) }));
    return { location, adjustments };
  }, [data, loc, adjs]);
  const dirty = Object.keys(edits.location).length > 0 || edits.adjustments.length > 0;
  const incomplete = adjs.some((a) => a.value === '');

  // Any change invalidates the preview shown.
  useEffect(() => { setData((d) => (d?.edited ? { ...d, edited: null, done: null } : d)); }, [loc, adjs]); // eslint-disable-line

  const preview = async () => {
    setBusy('preview');
    try {
      const { data: d } = await axios.post(api('/weather/inspect'), { source, ...edits });
      setData((cur) => ({ ...cur, edited: d.edited, done: d.done }));
    } catch (err) {
      flash(errText(err, 'The preview failed.'), true);
    } finally {
      setBusy(null);
    }
  };

  const save = async (use) => {
    if (use && !window.confirm(`Save ${name} and use it as the session weather? The exported FMUs and the notebooks (problem and tutorials) switch to it.`)) return;
    setBusy('save');
    try {
      const { data: r } = await axios.post(api('/weather/save'), { source, name, ...edits, use, tutorials: use });
      notifyLibrary();
      if (use) updateWeatherFile(r.used.epw);
      flash(`${r.file.name} saved in the weather library.${use ? ' It is now the session weather.' : ''}`
        + `${use && r.used.fmus ? ` ${r.used.fmus} exported FMU(s) updated.` : ''}`);
      setSource(r.file.id);
    } catch (err) {
      flash(errText(err, 'Saving failed.'), true);
    } finally {
      setBusy(null);
    }
  };

  const use = async () => {
    try {
      const text = await adoptAsSessionWeather(source, file.name, updateWeatherFile);
      if (text) flash(text);
    } catch (err) {
      flash(errText(err, 'The weather could not be changed.'), true);
    }
  };

  const base = data?.base;
  const years = base?.period.years || [];
  return (
    <div className="wx wx--wide">
      <header className="wx-bar">
        <div>
          <h1>Edit weather file</h1>
          <p className="muted">
            Look inside an EPW file and change it: the place, and the temperature, humidity, wind, solar radiation
            or pressure, for the whole year or for some months. The file you open is never overwritten: an edit is
            saved as a new file in the weather library.
          </p>
        </div>
      </header>

      <section className="wx-card">
        <div className="wx-row">
          <label className="wx-field wx-field--wide">File
            <select value={source} onChange={(e) => setSource(e.target.value)} disabled={!lib.files.length}>
              {!lib.files.length && <option value="">No weather file yet</option>}
              {lib.files.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.kind === 'session' ? `Session weather: ${f.name}` : f.name}
                </option>
              ))}
            </select>
          </label>
          {file && (
            <div className="wx-actions">
              <a className="wx-btn" href={sourceUrl('download', source)}><Download size={15} /> Download</a>
              {file.kind === 'library' && <button type="button" className="wx-btn" onClick={use}>Use in session</button>}
            </div>
          )}
        </div>
        {lib.error && <p className="wx-error" role="alert">{lib.error}</p>}
        {!lib.files.length && !lib.error && (
          <p className="muted">
            There is no weather file in this session. Upload a model and its EPW from the sidebar, or build annual
            files from Open-Meteo in <strong>Weather files from Open-Meteo</strong>.
          </p>
        )}
        {loading && <p className="muted">Reading the file…</p>}
        {error && <p className="wx-error" role="alert">{error}</p>}
      </section>

      <details className="wx-card wx-builder">
        <summary>Find or build a weather file (Open-Meteo real years, EnergyPlus stations, PVGIS)</summary>
        <SourcesPanel onEdit={(f) => setSource(f.id)} />
      </details>

      {base && (
        <div className="wx-split">
          <div className="wx-main">
          <section className="wx-card">
            <h2>What the file contains</h2>
            <p className="wx-meta">
              {base.location.city}{base.location.country ? `, ${base.location.country}` : ''} ·{' '}
              {num(base.location.latitude, 2)}°N {num(base.location.longitude, 2)}°E, {num(base.location.elevation, 0)} m ·{' '}
              UTC{base.location.timezone >= 0 ? '+' : ''}{base.location.timezone} · source: {base.location.source} ·{' '}
              {base.period.rows} hours, {years.length === 1 ? `year ${years[0]}` : `${years.length} different years (a typical-year file)`}
            </p>
            {Object.keys(base.missing).length > 0 && (
              <p className="wx-warn">
                Missing values (hours): {Object.entries(base.missing).map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`).join(', ')}.
              </p>
            )}
            <Tiles base={base} edited={data.edited} />
            <Charts base={base} edited={data.edited} />
            <details className="wx-details">
              <summary>Month by month{data.edited ? ' (the file’s value in grey after the edited one)' : ''}</summary>
              <MonthTable base={base} edited={data.edited} />
            </details>
            {base.comments.some(Boolean) && (
              <details className="wx-details">
                <summary>Comments in the file</summary>
                {base.comments.filter(Boolean).map((c) => <p key={c} className="wx-comment">{c}</p>)}
              </details>
            )}
          </section>

          <section className="wx-card">
            <h2>Edit</h2>
            <h3>Place</h3>
            <div className="wx-row wx-loc">
              {LOCATION_LABELS.map(([k, label]) => (
                <label key={k} className="wx-field">{label}
                  <input value={loc[k] ?? ''} onChange={(e) => setLoc({ ...loc, [k]: e.target.value })}
                    className={String(loc[k] ?? '') !== String(base.location[k] ?? '') ? 'is-changed' : ''} />
                </label>
              ))}
            </div>
            <p className="muted wx-note">
              The latitude, longitude, elevation and time zone set the sun’s position and the pressure of the
              location; change them together with the radiation only if you know what you are doing.
            </p>

            <h3>Variables</h3>
            {adjs.map((a, i) => (
              <AdjustmentRow key={i} adj={a} variables={config?.variables || []}
                onChange={(patch) => setAdjs(adjs.map((x, j) => (j === i ? { ...x, ...patch } : x)))}
                onRemove={() => setAdjs(adjs.filter((_, j) => j !== i))} />
            ))}
            <button type="button" className="wx-btn" onClick={() => setAdjs([...adjs, emptyAdjustment()])}
              disabled={!config}>
              <Plus size={15} /> Add an adjustment
            </button>
            <p className="muted wx-note">
              Adjustments apply in the order listed. A temperature change moves the dew point so the relative
              humidity stays the same (or keeps the dew point and recomputes the humidity); a humidity change moves
              the dew point. Solar radiation scales the global, direct and diffuse columns together. Results are kept
              inside physical limits.
            </p>

            <div className="wx-row wx-save">
              <button type="button" className="wx-btn" onClick={preview} disabled={!dirty || incomplete || busy}>
                {busy === 'preview' ? 'Computing…' : 'Preview the changes'}
              </button>
              <label className="wx-field wx-field--wide">Save as
                <input value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <button type="button" className="wx-btn wx-btn--primary" onClick={() => save(false)}
                disabled={!dirty || incomplete || !name.trim() || busy}>
                {busy === 'save' ? 'Saving…' : 'Save to library'}
              </button>
              <button type="button" className="wx-btn wx-btn--primary wx-btn--alt" onClick={() => save(true)}
                disabled={!dirty || incomplete || !name.trim() || busy}>
                Save and use in session
              </button>
            </div>
            {incomplete && <p className="muted wx-note">Fill in the value of every adjustment, or remove it.</p>}
            {data.done?.length > 0 && (
              <ul className="wx-done">{data.done.map((d) => <li key={d}>{d}</li>)}</ul>
            )}
          </section>
          </div>
          <aside className="wx-side">
            <section className="wx-card">
              <h2>Hour by hour</h2>
              <HourlyView source={source}
                edits={data.edited ? { location: edits.location, adjustments: edits.adjustments } : null} />
            </section>
          </aside>
        </div>
      )}
      {msg && <p className={msg.error ? 'wx-error wx-toast' : 'wx-ok wx-toast'} role="status">{msg.text}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------- years
/** "2018-2020, 2023" -> [2018, 2019, 2020, 2023]; anything else is reported in `bad`. */
export function parseYears(text) {
  const years = new Set();
  const bad = [];
  text.split(/[\s,;]+/).filter(Boolean).forEach((tok) => {
    const m = tok.match(/^(\d{4})(?:\s*[-–:]\s*(\d{4}))?$/);
    if (!m) { bad.push(tok); return; }
    const a = Number(m[1]);
    const b = m[2] ? Number(m[2]) : a;
    if (b < a || b - a > 80) { bad.push(tok); return; }
    for (let y = a; y <= b; y += 1) years.add(y);
  });
  return { years: [...years].sort((a, b) => a - b), bad };
}

function yearProblem(year, model, config) {
  if (!config) return null;
  if (year > config.last_year) return `${year} is not complete yet (latest: ${config.last_year})`;
  const m = config.models.find((x) => x.id === model);
  if (m && year < m.first) return `${model} starts in ${m.first}`;
  if (m?.last && year > m.last) return `${model} ends in ${m.last}`;
  return null;
}

// ---------------------------------------------------------------------------- the library page
const STORE = 'weather.openmeteo.form';
const emptyForm = { latitude: '', longitude: '', elevation: '', city: '', state: '', country: '', timezone: '' };

function LibraryTable({ files, onEdit, onUse, onDelete }) {
  if (!files.length) return <p className="muted">The library is empty.</p>;
  return (
    <div className="wx-scroll">
      <table className="wx-table wx-table--files">
        <thead>
          <tr><th>File</th><th>Place</th><th>Size</th><th>Saved</th><th /></tr>
        </thead>
        <tbody>
          {files.map((f) => (
            <tr key={f.id}>
              <td>
                {f.name}{f.kind === 'session' && <span className="wx-badge">session weather</span>}
              </td>
              <td>{f.city}{f.country ? `, ${f.country}` : ''}{f.latitude != null && ` (${num(f.latitude, 2)}, ${num(f.longitude, 2)})`}</td>
              <td>{num(f.size / 1048576, 1)} MB</td>
              <td>{f.modified.replace('T', ' ')}</td>
              <td className="wx-rowactions">
                <button type="button" className="wx-icon" title="Open in the editor" aria-label={`Edit ${f.name}`}
                  onClick={() => onEdit(f)}><Pencil size={15} /></button>
                {f.kind === 'library' && (
                  <button type="button" className="wx-btn wx-btn--small" onClick={() => onUse(f)}>Use in session</button>
                )}
                <a className="wx-icon" href={sourceUrl('download', f.id)} title="Download" aria-label={`Download ${f.name}`}>
                  <Download size={15} />
                </a>
                {f.kind === 'library' && (
                  <button type="button" className="wx-icon wx-icon--danger" title="Delete from the library"
                    aria-label={`Delete ${f.name}`} onClick={() => onDelete(f)}><Trash2 size={15} /></button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------- place, shared by the sources
function PlacePicker({ form, set }) {
  const [query, setQuery] = useState('');
  const [places, setPlaces] = useState(null);
  const [searching, setSearching] = useState(false);
  const [msg, flash] = useFlash();
  const latOk = form.latitude !== '' && Math.abs(Number(form.latitude)) <= 90;
  const lonOk = form.longitude !== '' && Math.abs(Number(form.longitude)) <= 180;

  const search = async (e) => {
    e?.preventDefault();
    if (query.trim().length < 2) return;
    setSearching(true);
    try {
      const { data } = await axios.get(api('/weather/geocode'), { params: { q: query.trim() } });
      setPlaces(data.places);
    } catch (err) {
      flash(errText(err, 'The place search failed.'), true);
    } finally {
      setSearching(false);
    }
  };
  const pick = (p) => {
    set({
      latitude: String(p.latitude), longitude: String(p.longitude), city: p.name || '', state: p.admin1 || '',
      country: p.country_code || p.country || '', timezone: p.timezone || '', elevation: '',
    });
    setPlaces(null);
  };
  return (
    <section className="wx-card">
      <h2>Place</h2>
      <form className="wx-row wx-search" onSubmit={search}>
        <label className="wx-field wx-field--wide">Search a place
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Turin, Madrid, Nairobi…" />
        </label>
        <button type="submit" className="wx-btn" disabled={searching || query.trim().length < 2}>
          <Search size={15} /> {searching ? 'Searching…' : 'Search'}
        </button>
      </form>
      {msg && <p className={msg.error ? 'wx-error' : 'wx-ok'} role="status">{msg.text}</p>}
      {places && (
        <ul className="wx-places">
          {places.length === 0 && <li className="muted">No place found.</li>}
          {places.map((p, i) => (
            <li key={`${p.latitude}-${p.longitude}-${i}`}>
              <button type="button" onClick={() => pick(p)}>
                <strong>{p.name}</strong> {[p.admin1, p.country].filter(Boolean).join(', ')}
                <span className="muted"> · {num(p.latitude, 3)}, {num(p.longitude, 3)} · {num(p.elevation, 0)} m</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="wx-row wx-loc">
        <label className="wx-field">Latitude (°N)
          <input value={form.latitude} onChange={(e) => set({ latitude: e.target.value })} inputMode="decimal"
            aria-invalid={form.latitude !== '' && !latOk} />
        </label>
        <label className="wx-field">Longitude (°E)
          <input value={form.longitude} onChange={(e) => set({ longitude: e.target.value })} inputMode="decimal"
            aria-invalid={form.longitude !== '' && !lonOk} />
        </label>
        <label className="wx-field">Elevation (m)
          <input value={form.elevation} placeholder="Open-Meteo’s" onChange={(e) => set({ elevation: e.target.value })}
            inputMode="decimal" />
        </label>
        <label className="wx-field">Name in the file
          <input value={form.city} onChange={(e) => set({ city: e.target.value })} />
        </label>
        <label className="wx-field">Country
          <input value={form.country} onChange={(e) => set({ country: e.target.value })} />
        </label>
        <label className="wx-field">Time zone (IANA)
          <input value={form.timezone} placeholder="from the longitude" onChange={(e) => set({ timezone: e.target.value })} />
        </label>
      </div>
      <p className="muted wx-note">
        The place is used by the sources below. Elevation and time zone matter to Open-Meteo only: it gives the
        weather of a grid cell (5 to 25 km) corrected to that elevation, and the time zone is used to express the hours
        in local standard time, without daylight saving, as EnergyPlus expects.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------- typical years
/** The EnergyPlus weather list (3000+ locations): by name, or the stations nearest to the place above. */
function StationFinder({ form, onEdit }) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);       // {total, results, catalog_size, got}
  const [busy, setBusy] = useState(false);
  const [getting, setGetting] = useState(null);
  const [msg, flash] = useFlash();
  const hasPlace = form.latitude !== '' && form.longitude !== ''
    && Math.abs(Number(form.latitude)) <= 90 && Math.abs(Number(form.longitude)) <= 180;

  const search = async (nearest) => {
    setBusy(true);
    try {
      const params = { q: query.trim(), limit: 25 };
      if (nearest && hasPlace) { params.lat = form.latitude; params.lon = form.longitude; }
      const { data } = await axios.get(api('/weather/catalog/search'), { params });
      setResult(data);
    } catch (err) {
      flash(errText(err, 'The search failed.'), true);
    } finally {
      setBusy(false);
    }
  };
  const get = async (s) => {
    setGetting(s.id);
    try {
      const { data } = await axios.post(api('/weather/catalog/download'), { id: s.id });
      notifyLibrary();
      flash(`${data.file.name} is in the weather library (mean ${num(data.annual.temp_mean, 1)} °C, `
        + `${num(data.annual.ghi_kwh_m2, 0)} kWh/m² of radiation).`);
      setResult((r) => r && { ...r, got: { ...(r.got || {}), [s.id]: data.file } });
    } catch (err) {
      flash(errText(err, 'The download failed.'), true);
    } finally {
      setGetting(null);
    }
  };
  return (
    <section className="wx-card">
      <h2>Typical year from an EnergyPlus station</h2>
      <p className="muted wx-note">
        The weather files published by EnergyPlus (TMY, IWEC, CWEC… typical years built from many years of
        observations). Search by name, or list the stations nearest to the place above.
      </p>
      <p className="muted wx-note">
        Each file keeps the copyright line of its source in its header (COMMENTS 1). IWEC files are © ASHRAE and are licensed to
        you for your own use: do not pass them on to third parties without ASHRAE’s permission. The licence terms are per
        source: see <a href="https://energyplus.net/weather/sources" target="_blank" rel="noreferrer">EnergyPlus weather data sources</a>.
      </p>
      <form className="wx-row" onSubmit={(e) => { e.preventDefault(); search(false); }}>
        <label className="wx-field wx-field--wide">Station, city or country
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Torino, ESP, IWEC…" />
        </label>
        <button type="submit" className="wx-btn" disabled={busy}><Search size={15} /> Search</button>
        <button type="button" className="wx-btn" disabled={busy || !hasPlace} onClick={() => search(true)}
          title={hasPlace ? 'Stations closest to the latitude and longitude above' : 'Choose a place first'}>
          Nearest to the place
        </button>
      </form>
      {msg && <p className={msg.error ? 'wx-error' : 'wx-ok'} role="status">{msg.text}</p>}
      {result && (
        <>
          <p className="muted wx-note">
            {result.total} of {result.catalog_size} locations{result.total > result.results.length ? ', first 25 shown' : ''}.
          </p>
          <div className="wx-scroll">
            <table className="wx-table wx-table--files">
              <thead><tr><th>Station</th><th>Country</th><th>Type</th><th>Distance</th><th /></tr></thead>
              <tbody>
                {result.results.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name.replace(/_/g, ' ')}</td>
                    <td>{s.country}</td>
                    <td>{s.kind}</td>
                    <td>{s.distance_km != null ? `${s.distance_km} km` : ''}</td>
                    <td className="wx-rowactions">
                      {result.got?.[s.id] && (
                        <button type="button" className="wx-icon" onClick={() => onEdit(result.got[s.id])}
                          aria-label={`Open ${s.id} in the editor`} title="Open in the editor"><Pencil size={15} /></button>
                      )}
                      <button type="button" className="wx-btn wx-btn--small" disabled={getting != null}
                        onClick={() => get(s)}>
                        {getting === s.id ? 'Downloading…' : result.got?.[s.id] ? 'Download again' : 'Add to library'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

/** PVGIS (European Commission JRC): a typical meteorological year for any point, as EPW. */
function PvgisPanel({ form, onEdit }) {
  const [years, setYears] = useState({ start: '', end: '' });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [msg, flash] = useFlash();
  const ok = form.latitude !== '' && form.longitude !== ''
    && Math.abs(Number(form.latitude)) <= 90 && Math.abs(Number(form.longitude)) <= 180;
  const build = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(api('/weather/pvgis'), {
        latitude: Number(form.latitude), longitude: Number(form.longitude), city: form.city, country: form.country,
        startyear: years.start, endyear: years.end,
      });
      notifyLibrary();
      setDone(data);
      flash(`${data.file.name} is in the weather library.`);
    } catch (err) {
      flash(errText(err, 'PVGIS failed.'), true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="wx-card">
      <h2>Typical year from PVGIS</h2>
      <p className="muted wx-note">
        The Photovoltaic Geographical Information System of the European Commission builds a typical meteorological
        year for the exact point (ERA5 reanalysis). Without years it uses all the data PVGIS has; give a first and a
        last year to build it from a period (its web page uses ten years).
      </p>
      <div className="wx-row">
        <label className="wx-field">First year
          <input value={years.start} inputMode="numeric" placeholder="all" onChange={(e) => setYears({ ...years, start: e.target.value })} />
        </label>
        <label className="wx-field">Last year
          <input value={years.end} inputMode="numeric" placeholder="all" onChange={(e) => setYears({ ...years, end: e.target.value })} />
        </label>
        <button type="button" className="wx-btn wx-btn--primary" disabled={!ok || busy} onClick={build}>
          {busy ? 'Asking PVGIS…' : 'Build the typical year'}
        </button>
        {done && (
          <button type="button" className="wx-btn" onClick={() => onEdit(done.file)}><Pencil size={15} /> Open in the editor</button>
        )}
      </div>
      {!ok && <p className="muted wx-note">Choose a place first.</p>}
      {msg && <p className={msg.error ? 'wx-error' : 'wx-ok'} role="status">{msg.text}</p>}
      <p className="wx-attribution">
        Data: PVGIS © European Communities, 2001-{new Date().getFullYear()}, from the{' '}
        <a href="https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en"
          target="_blank" rel="noreferrer">Photovoltaic Geographical Information System</a> of the European Commission.
        Solar radiation comes from the database PVGIS uses for the place and the other variables from ERA5: contains modified
        Copernicus Climate Change Service information {new Date().getFullYear()}. Neither the European Commission nor ECMWF
        is responsible for any use that may be made of the Copernicus information or data it contains.
      </p>
    </section>
  );
}

function OtherSources() {
  const links = [
    ['EnergyPlus weather data', 'https://energyplus.net/weather', 'the official list, and the map the station search is built on'],
    ['Climate.OneBuilding.org', 'https://climate.onebuilding.org/', 'more locations and recent TMYx files, one map per WMO region'],
    ['PVGIS typical year', 'https://re.jrc.ec.europa.eu/pvg_tools/en/#TMY', 'the web page of the tool used above'],
    ['Open-Meteo', 'https://open-meteo.com/en/docs/historical-weather-api', 'the archive the real years are built from'],
  ];
  return (
    <section className="wx-card">
      <h2>Other sources</h2>
      <p className="muted wx-note">
        If a place is missing, download an EPW from one of these sites and add it to the library with “Add an EPW”
        at the bottom of the Files from Open-Meteo page. Each site has its own terms: Climate.OneBuilding.org asks to cite
        “Lawrie, Linda K, Drury B Crawley. 2026. Development of Global Typical Meteorological Years (TMYx).
        https://climate.onebuilding.org” and states no licence for redistributing the files.
      </p>
      <ul className="wx-links">
        {links.map(([name, url, why]) => (
          <li key={url}><a href={url} target="_blank" rel="noreferrer">{name}</a> <span className="muted">— {why}</span></li>
        ))}
      </ul>
    </section>
  );
}

const SOURCE_TABS = [
  ['real', 'Real years (Open-Meteo)'],
  ['stations', 'Typical year: EnergyPlus stations'],
  ['pvgis', 'Typical year: PVGIS'],
  ['other', 'Other sources'],
];

/** Everything that puts a weather file in the library, on one place chosen once. */
function SourcesPanel({ onEdit }) {
  const [form, setForm] = useState(() => {
    try { return { ...emptyForm, ...JSON.parse(localStorage.getItem(STORE) || '{}') }; } catch (e) { return emptyForm; }
  });
  const [tab, setTab] = useState('real');
  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify(form)); } catch (e) { /* private mode */ }
  }, [form]);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  return (
    <div className="wx-sources">
      <PlacePicker form={form} set={set} />
      <div className="wx-tabs" role="tablist">
        {SOURCE_TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'is-active' : ''}
            onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      <div hidden={tab !== 'real'}><OpenMeteoBuilder form={form} onEdit={onEdit} /></div>
      <div hidden={tab !== 'stations'}><StationFinder form={form} onEdit={onEdit} /></div>
      <div hidden={tab !== 'pvgis'}><PvgisPanel form={form} onEdit={onEdit} /></div>
      <div hidden={tab !== 'other'}><OtherSources /></div>
    </div>
  );
}

// ---------------------------------------------------------------------------- Open-Meteo builder (both pages)
function OpenMeteoBuilder({ form, onEdit }) {
  const [config, setConfig] = useState(null);
  const [model, setModel] = useState('best_match');
  const [yearsText, setYearsText] = useState('');
  const [runs, setRuns] = useState([]);           // [{year, state, file, annual, report, error}]
  const [running, setRunning] = useState(false);
  const stop = useRef(false);

  useEffect(() => {
    axios.get(api('/weather/config')).then(({ data: c }) => {
      setConfig(c);
      setYearsText((t) => t || String(c.last_year));
    }).catch(() => {});
  }, []);
  const { years, bad } = useMemo(() => parseYears(yearsText), [yearsText]);
  const problems = useMemo(
    () => years.map((y) => [y, yearProblem(y, model, config)]).filter(([, p]) => p), [years, model, config]);
  const latOk = form.latitude !== '' && Math.abs(Number(form.latitude)) <= 90;
  const lonOk = form.longitude !== '' && Math.abs(Number(form.longitude)) <= 180;
  const ready = latOk && lonOk && years.length > 0 && !bad.length && !problems.length && !running;

  const lastYears = (k) => {
    if (!config) return;
    setYearsText(`${config.last_year - k + 1}-${config.last_year}`.replace(/^(\d+)-\1$/, '$1'));
  };

  const generate = async () => {
    stop.current = false;
    setRunning(true);
    setRuns(years.map((year) => ({ year, state: 'wait' })));
    for (let i = 0; i < years.length; i += 1) {
      if (stop.current) {
        setRuns((r) => r.map((x, j) => (j >= i ? { ...x, state: 'skipped' } : x)));
        break;
      }
      setRuns((r) => r.map((x, j) => (j === i ? { ...x, state: 'run' } : x)));
      try {
        const { data } = await axios.post(api('/weather/openmeteo'), {
          latitude: Number(form.latitude), longitude: Number(form.longitude), year: years[i], model,
          elevation: form.elevation, city: form.city, state: form.state, country: form.country,
          timezone: form.timezone,
        });
        setRuns((r) => r.map((x, j) => (j === i ? { ...x, state: 'ok', file: data.file, annual: data.annual, report: data.report } : x)));
        notifyLibrary();
      } catch (err) {
        const text = errText(err, 'The request failed.');
        setRuns((r) => r.map((x, j) => (j === i ? { ...x, state: 'error', error: text } : x)));
        if (/rate limit|not reachable/i.test(text)) {      // the next years would fail the same way
          setRuns((r) => r.map((x, j) => (j > i ? { ...x, state: 'skipped' } : x)));
          break;
        }
      }
    }
    setRunning(false);
  };

  const model_ = config?.models.find((m) => m.id === model);
  return (
    <>
      <section className="wx-card">
        <h2>Real years from Open-Meteo</h2>
        <div className="wx-row">
          <label className="wx-field wx-field--wide">Years
            <input value={yearsText} onChange={(e) => setYearsText(e.target.value)} placeholder="2019, 2021-2023"
              aria-invalid={bad.length > 0 || problems.length > 0} />
          </label>
          <div className="wx-quick">
            <span className="wx-unit">Quick:</span>
            {[1, 3, 5, 10].map((k) => (
              <button key={k} type="button" onClick={() => lastYears(k)} disabled={!config}>
                last {k === 1 ? 'year' : `${k} years`}
              </button>
            ))}
          </div>
        </div>
        <p className="muted wx-note">
          Separate years with commas, and write a range with a dash: <code>2018-2020, 2023</code>. Only complete
          years can be chosen{config ? ` (the latest is ${config.last_year})` : ''}. Each year is one file of 8760 hours;
          29 February is left out of a leap year.
        </p>
        {years.length > 0 && (
          <div className="wx-chips" aria-label="Chosen years">
            {years.map((y) => {
              const p = yearProblem(y, model, config);
              return <span key={y} className={`wx-chip${p ? ' is-bad' : ''}`} title={p || ''}>{y}</span>;
            })}
          </div>
        )}
        {bad.length > 0 && <p className="wx-error">Not a year or a range: {bad.join(', ')}</p>}
        {problems.length > 0 && <p className="wx-error">{problems.map(([, p]) => p).join('; ')}.</p>}

        <div className="wx-row">
          <label className="wx-field wx-field--wide">Data set
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {(config?.models || []).map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>
        </div>
        {model_ && (
          <p className="muted wx-note">
            {model === 'best_match' && 'Open-Meteo picks the best model for the place and the year. '}
            All of them are reanalyses (a weather model fitted to observations), not measurements of a station;
            solar radiation in particular is modelled.
          </p>
        )}

        <div className="wx-row">
          <button type="button" className="wx-btn wx-btn--primary" onClick={generate} disabled={!ready}>
            {running ? 'Building…' : `Build ${years.length || ''} weather file${years.length === 1 ? '' : 's'}`}
          </button>
          {running && <button type="button" className="wx-btn" onClick={() => { stop.current = true; }}>Stop after this year</button>}
        </div>

        {runs.length > 0 && (
          <div className="wx-scroll">
            <table className="wx-table">
              <thead>
                <tr><th>Year</th><th>State</th><th>Mean °C</th><th>Radiation kWh/m²</th><th>Heating DD</th><th>Rain mm</th><th /></tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.year}>
                    <td>{r.year}</td>
                    <td className={r.state === 'error' ? 'wx-error' : ''}>
                      {{ wait: 'waiting', run: 'building…', ok: 'saved', skipped: 'not done' }[r.state] || r.error}
                      {r.report?.warnings?.length > 0 && <small className="wx-warn-inline"> · {r.report.warnings.join(' ')}</small>}
                    </td>
                    <td>{r.annual ? num(r.annual.temp_mean, 1) : ''}</td>
                    <td>{r.annual ? num(r.annual.ghi_kwh_m2, 0) : ''}</td>
                    <td>{r.annual ? num(r.annual.hdd18, 0) : ''}</td>
                    <td>{r.annual ? num(r.annual.rain_mm, 0) : ''}</td>
                    <td>{r.file && (
                      <button type="button" className="wx-icon" onClick={() => onEdit(r.file)} aria-label={`Open ${r.file.name} in the editor`}
                        title="Open in the editor"><Pencil size={15} /></button>
                    )}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="wx-attribution">
          <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Weather data by Open-Meteo.com</a>,
          licensed <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>;
          converted to the EPW format here (changes made). Based on ECMWF ERA5, ERA5-Land, IFS and CERRA: contains modified
          Copernicus Climate Change Service information {new Date().getFullYear()}. Neither the European Commission nor
          ECMWF is responsible for any use that may be made of the Copernicus information or data it contains. The free
          service is for non-commercial use and has request limits. See <Link to="/credits">Credits &amp; licences</Link>.
        </p>
      </section>
    </>
  );
}

export function WeatherLibraryPage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { updateWeatherFile } = useContext(AppContext);
  const lib = useLibrary();
  const fileRef = useRef(null);
  const [msg, flash] = useFlash();

  useEffect(() => { if (pathname === '/weather_library') lib.reload(); }, [pathname]); // eslint-disable-line

  const edit = (f) => navigate('/weather_editor', { state: { source: f.id } });
  const use = async (f) => {
    try {
      const text = await adoptAsSessionWeather(f.id, f.name, updateWeatherFile);
      if (text) flash(text);
    } catch (err) {
      flash(errText(err, 'The weather could not be changed.'), true);
    }
  };
  const remove = async (f) => {
    if (!window.confirm(`Delete ${f.name} from the weather library?`)) return;
    try {
      await axios.delete(api(`/weather/files/${encodeURIComponent(f.name)}`));
      notifyLibrary();
    } catch (err) {
      flash(errText(err, 'Deleting failed.'), true);
    }
  };
  const upload = async (file) => {
    if (!file) return;
    const body = new FormData();
    body.append('epw', file);
    try {
      await axios.post(api('/weather/upload'), body);
      notifyLibrary();
      flash(`${file.name} added to the library.`);
    } catch (err) {
      flash(errText(err, 'Upload failed.'), true);
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="wx">
      <header className="wx-bar">
        <div>
          <h1>Weather files from Open-Meteo</h1>
          <p className="muted">
            Find a weather file for any place: real years built from the Open-Meteo archive, typical years from the EnergyPlus
            stations or from PVGIS. The files go to the weather library below; open one in the editor, or use it as the
            weather of the session to simulate that real year.
          </p>
        </div>
      </header>

      <SourcesPanel onEdit={edit} />

      <section className="wx-card">
        <div className="wx-head">
          <h2>Weather library</h2>
          <div className="wx-actions">
            <input ref={fileRef} type="file" accept=".epw" hidden onChange={(e) => upload(e.target.files[0])} />
            <button type="button" className="wx-btn" onClick={() => fileRef.current?.click()}>
              <Upload size={15} /> Add an EPW
            </button>
          </div>
        </div>
        {lib.error && <p className="wx-error" role="alert">{lib.error}</p>}
        <LibraryTable files={lib.files} onEdit={edit} onUse={use} onDelete={remove} />
        <p className="muted wx-note">
          The library belongs to the session: it is saved with it and emptied by Reset session.
        </p>
      </section>
      {msg && <p className={msg.error ? 'wx-error wx-toast' : 'wx-ok wx-toast'} role="status">{msg.text}</p>}
    </div>
  );
}
