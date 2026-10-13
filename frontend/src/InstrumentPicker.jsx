// InstrumentPicker.jsx
// One interface for the four tabs of Sensors & actuators: which type -> which one -> where.
//
//   which type  filters with a count (the quantity of a variable, the resource of a meter, what an
//               actuator writes, what a schedule drives);
//   which one   the list, divided into headers by common prefix only when it is longer than LIST_LIMIT;
//   where       the zones, components or keys the choice applies to: chips with search, "all in scope",
//               and the zone bar of the page decides what a row starts with.
//
// The picker holds only the choice; what an item is and how it becomes FMU variables is the parent's
// business (MonitoringPanel builds the items and the operations).
import React, { useEffect, useMemo, useRef, useState } from 'react';
import RoleSwitch from './FmuRole';
import { LIST_LIMIT, defaultSelection, splitByPrefix } from './instrumentGroups';
import './InstrumentPicker.css';

const CHIP_LIMIT = 60;

const filled = (x) => x !== '' && x != null && Number.isFinite(Number(x));
const rangeOk = (v) => filled(v.min) && filled(v.max) && Number(v.min) <= Number(v.max);

const SOURCE_TITLES = {
  model: 'From the model: the type limits of the schedule behind it',
  idd: 'From the field the actuator overrides, in the EnergyPlus IDD',
  unit: 'From the unit: a bound the quantity always has',
  default: 'A usual value for this quantity: check it',
  none: 'Nothing known: type the range',
};

function SourceBadge({ source, note }) {
  if (!source) return null;
  return <span className={`ip-source ip-source--${source}`} title={`${SOURCE_TITLES[source] || ''}${note ? ` (${note})` : ''}`}>{source}</span>;
}

/** The "where" of one row: chips, a search box when long, "in scope" and "none". */
function WherePicker({ item, chosen, onChange, scope, owners, added, onCustom }) {
  const [q, setQ] = useState('');
  const [typed, setTyped] = useState('');
  const options = item.options || [];
  const needle = q.trim().toLowerCase();
  const shown = options.filter((o) => !needle || o.label.toLowerCase().includes(needle));
  const visible = shown.slice(0, CHIP_LIMIT);
  const toggle = (id) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id); else next.add(id);
    onChange(next);
  };
  const inScope = () => new Set(defaultSelection(options, scope, owners));
  return (
    <div className="ip-where">
      <div className="ip-where-head">
        <span className="ip-where-title">{item.whereLabel || 'Where'}</span>
        <span className="ip-muted">{chosen.size} of {options.length}</span>
        <button type="button" className="ip-link" onClick={() => onChange(inScope())}>zones in scope</button>
        <button type="button" className="ip-link" onClick={() => onChange(new Set(shown.map((o) => o.id)))}>
          {needle ? 'all matching' : 'all'}
        </button>
        <button type="button" className="ip-link" onClick={() => onChange(new Set())}>none</button>
        {options.length > 12 && (
          <input type="search" className="ip-where-search" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Filter…" aria-label={`Filter the ${item.whereLabel || 'places'} of ${item.title}`} />
        )}
      </div>
      {options.length === 0 && onCustom && (
        <form className="ip-where-head" onSubmit={(e) => { e.preventDefault(); if (typed.trim()) { onCustom(typed.trim()); setTyped(''); } }}>
          <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Key name: a zone, surface, node…" aria-label="Key name" />
          <button type="button" onClick={() => { if (typed.trim()) { onCustom(typed.trim()); setTyped(''); } }}>Use this key</button>
        </form>
      )}
      <div className="ip-chips">
        {visible.map((o) => {
          const on = chosen.has(o.id);
          const done = added && added(item, o.id);
          return (
            <button key={o.id} type="button" className={`ip-chip${on ? ' is-on' : ''}${done ? ' is-added' : ''}`}
              aria-pressed={on} title={o.detail ? `${o.label} · ${o.detail}` : o.label} onClick={() => toggle(o.id)}>
              {o.short || o.label}{done ? ' ✓' : ''}
            </button>
          );
        })}
        {shown.length > visible.length && <span className="ip-muted">… {shown.length - visible.length} more: filter to see them</span>}
        {shown.length === 0 && <span className="ip-muted">No match.</span>}
      </div>
    </div>
  );
}

/** Initial value and range of an actuator or schedule row. */
function ValuesEditor({ row, onChange, hasInitial, busy }) {
  const v = row.values;
  const set = (patch) => onChange({ ...v, ...patch });
  const bad = filled(v.min) && filled(v.max) && !rangeOk(v);
  return (
    <div className="ip-values">
      {hasInitial && (
        <label>Initial
          <input type="number" step="any" value={v.initial ?? ''} placeholder="auto" title="Left empty, each component starts from what the model does: the thermostat schedule for a setpoint, 0 otherwise"
            onChange={(e) => set({ initial: e.target.value })} />
        </label>
      )}
      <label>Min
        <input type="number" step="any" value={v.min ?? ''} onChange={(e) => set({ min: e.target.value, source: 'you' })} />
      </label>
      <label>Max
        <input type="number" step="any" value={v.max ?? ''} onChange={(e) => set({ max: e.target.value, source: 'you' })} />
      </label>
      {busy ? <span className="ip-muted">proposing a range…</span> : <SourceBadge source={v.source === 'you' ? '' : v.source} note={v.note} />}
      {!busy && !rangeOk(v) && !bad && <span className="ip-warn">a range is needed</span>}
      {bad && <span className="ip-warn">Min must not exceed max.</span>}
    </div>
  );
}

export default function InstrumentPicker({
  items, kinds, scope, owners, valuesMode, hasInitial = false, loadValues, onAdd, addLabel = 'Add to the FMU',
  needsRole = false, placeholder = 'Search…', added, emptyText = 'Nothing here.', defaultKind,
}) {
  const [kind, setKind] = useState(defaultKind || 'all');
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState({});            // id -> { options:Set, variants:Set, values }
  const [role, setRole] = useState('observation');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState({});
  const [message, setMessage] = useState(null);    // { kind: 'ok'|'error', text }
  const [failures, setFailures] = useState({});    // id -> text
  const seq = useRef(0);

  // A new model or tab: nothing chosen yet.
  useEffect(() => { setRows({}); setMessage(null); setFailures({}); }, [items]);

  const byId = useMemo(() => {
    const m = new Map();
    items.forEach((it) => m.set(it.id, it));
    return m;
  }, [items]);

  const q = query.trim().toLowerCase();
  const matches = (it) => !q || it.title.toLowerCase().includes(q) || (it.meta || '').toLowerCase().includes(q)
    || (it.options || []).some((o) => o.label.toLowerCase().includes(q));
  const counts = useMemo(() => {
    const c = { all: 0 };
    items.filter(matches).forEach((it) => { c.all += 1; c[it.kind] = (c[it.kind] || 0) + 1; });
    return c;
  }, [items, q]); // eslint-disable-line react-hooks/exhaustive-deps
  const visible = useMemo(
    () => items.filter((it) => (kind === 'all' || it.kind === kind) && matches(it)),
    [items, kind, q], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const tree = useMemo(() => splitByPrefix(visible, (it) => it.title, LIST_LIMIT), [visible]);

  const startValues = async (item, optionIds, rowNow) => {
    if (!valuesMode || !loadValues) return;
    const mine = ++seq.current;
    setLoading((l) => ({ ...l, [item.id]: true }));
    try {
      const got = await loadValues(item, [...optionIds]);
      if (mine > seq.current) return;
      setRows((r) => (r[item.id] ? { ...r, [item.id]: { ...r[item.id], values: { ...r[item.id].values, ...got } } } : r));
    } catch (e) {
      setRows((r) => (r[item.id] ? { ...r, [item.id]: { ...r[item.id], values: { ...rowNow.values, source: 'none', note: String(e.message || e) } } } : r));
    } finally {
      setLoading((l) => ({ ...l, [item.id]: false }));
    }
  };

  const toggleRow = (item) => {
    if (rows[item.id]) {
      setRows((r) => { const n = { ...r }; delete n[item.id]; return n; });
      return;
    }
    const options = new Set(item.options ? (item.defaultOptions || defaultSelection(item.options, scope, owners)) : []);
    const variants = new Set((item.variants || []).slice(0, 1).map((v) => v.id));
    const row = { options, variants, values: { initial: '', min: '', max: '', source: '', note: '' } };
    setRows((r) => ({ ...r, [item.id]: row }));
    startValues(item, options, row);
  };

  const optionsOf = (item, row) => [...(item.options || []), ...(row.custom || []).map((k) => ({ id: k, label: k }))];
  const addCustom = (item, key) => setRows((r) => ({
    ...r, [item.id]: { ...r[item.id], custom: [...(r[item.id].custom || []), key], options: new Set([...r[item.id].options, key]) },
  }));
  const setOptions = (item, next) => {
    setRows((r) => ({ ...r, [item.id]: { ...r[item.id], options: next } }));
    startValues(item, next, rows[item.id]);
  };
  const toggleVariant = (item, id) => setRows((r) => {
    const cur = new Set(r[item.id].variants);
    if (cur.has(id)) cur.delete(id); else cur.add(id);
    return { ...r, [item.id]: { ...r[item.id], variants: cur } };
  });
  const setValues = (item, values) => setRows((r) => ({ ...r, [item.id]: { ...r[item.id], values } }));

  // What the add button would write, and what is missing.
  const chosen = Object.entries(rows).map(([id, row]) => ({ item: byId.get(id), row })).filter((x) => x.item);
  const problem = (item, row) => {
    if (item.options && row.options.size === 0) return 'choose where';
    if (item.variants && row.variants.size === 0) return 'choose a unit';
    if (valuesMode && !rangeOk(row.values)) return 'a range is needed';
    return '';
  };
  const count = (item, row) => (item.options ? row.options.size : 1) * (item.variants ? row.variants.size : 1);
  const ready = chosen.filter(({ item, row }) => !problem(item, row));
  const total = ready.reduce((n, { item, row }) => n + count(item, row), 0);

  const add = async () => {
    setBusy(true);
    setMessage(null);
    setFailures({});
    try {
      const res = await onAdd(ready.map(({ item, row }) => ({
        item, optionIds: [...row.options], variantIds: [...row.variants], values: row.values, role,
      })));
      const fails = {};
      (res.failures || []).forEach((f) => { fails[f.itemId] = f.error; });
      setFailures(fails);
      setMessage(res.failed
        ? { kind: 'error', text: `${res.added} added, ${res.failed} not added: see the rows marked below.` }
        : { kind: 'ok', text: `${res.added} added to the FMU.` });
    } catch (e) {
      setMessage({ kind: 'error', text: e?.response?.data?.details || e?.response?.data?.error || e.message });
    } finally {
      setBusy(false);
    }
  };

  const renderRow = (item) => {
    const row = rows[item.id];
    const on = Boolean(row);
    const issue = on ? problem(item, row) : '';
    return (
      <li key={item.id} className={`ip-row${on ? ' is-open' : ''}`}>
        <div className="ip-row-head">
          <label className="ip-check">
            <input type="checkbox" checked={on} disabled={item.disabled} onChange={() => toggleRow(item)}
              aria-label={`Select ${item.title}`} />
            <span className="ip-title">{item.title}</span>
          </label>
          {item.variants && item.variants.length > 0 && (
            <span className="ip-variants">
              {item.variants.map((v) => (
                <button key={v.id} type="button" className={`ip-pill${on && row.variants.has(v.id) ? ' is-on' : ''}`}
                  disabled={!on} aria-pressed={on && row.variants.has(v.id)} title={v.id} onClick={() => toggleVariant(item, v.id)}>
                  {v.units || '–'}
                </button>
              ))}
            </span>
          )}
          {item.meta && <span className="ip-meta">{item.meta}</span>}
          {item.tag && <span className="ip-tag" title={item.tagTitle}>{item.tag}</span>}
          {on && issue && <span className="ip-warn">{issue}</span>}
          {failures[item.id] && <span className="ip-warn" role="alert">{failures[item.id]}</span>}
        </div>
        {on && (
          <div className="ip-row-body">
            {item.options && (
              <WherePicker item={{ ...item, options: optionsOf(item, row) }} chosen={row.options} scope={scope} owners={owners}
                added={added} onChange={(next) => setOptions(item, next)} onCustom={item.freeText ? (k) => addCustom(item, k) : undefined} />
            )}
            {item.options && item.options.length === 0 && !item.freeText && <p className="ip-muted">No place to choose from.</p>}
            {valuesMode && (
              <ValuesEditor row={row} hasInitial={hasInitial} busy={Boolean(loading[item.id])} onChange={(v) => setValues(item, v)} />
            )}
            {item.warn && <p className="ip-warn">{item.warn}</p>}
            {item.note && <p className="ip-muted">{item.note}</p>}
          </div>
        )}
      </li>
    );
  };

  const renderNodes = (nodes, depth = 0) => nodes.map((n) => {
    if (n.children) {
      return (
        <details key={`${depth}:${n.title}`} className="ip-group" open={Boolean(q) || undefined}>
          <summary><span className="ip-group-title">{n.title}</span><span className="ip-count">{n.count}</span></summary>
          <div className="ip-group-body">{renderNodes(n.children, depth + 1)}</div>
        </details>
      );
    }
    if (tree.length === 1 && !n.title) return <ul key="all" className="ip-list">{n.items.map(renderRow)}</ul>;
    return (
      <details key={`${depth}:${n.title}`} className="ip-group" open={Boolean(q) || n.count <= 8 || undefined}>
        <summary><span className="ip-group-title">{n.title || 'Other'}</span><span className="ip-count">{n.count}</span></summary>
        <ul className="ip-list">{n.items.map(renderRow)}</ul>
      </details>
    );
  });

  return (
    <div className="ip">
      <div className="ip-facets" role="group" aria-label="Type">
        <button type="button" className={`ip-facet${kind === 'all' ? ' is-on' : ''}`} aria-pressed={kind === 'all'} onClick={() => setKind('all')}>
          All <b>{counts.all}</b>
        </button>
        {kinds.filter(([id]) => counts[id]).map(([id, label]) => (
          <button key={id} type="button" className={`ip-facet${kind === id ? ' is-on' : ''}`} aria-pressed={kind === id} onClick={() => setKind(id)}>
            {label} <b>{counts[id]}</b>
          </button>
        ))}
      </div>
      <input type="search" className="ip-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={placeholder}
        aria-label="Search" />

      {visible.length === 0 ? <p className="ip-muted">{q ? `Nothing matches “${query}”.` : emptyText}</p> : renderNodes(tree)}

      <div className="ip-bar" role="region" aria-label="Add the selection">
        <span className="ip-bar-text">
          {chosen.length === 0 ? 'Tick what you want, then add it.'
            : `${chosen.length} selected · ${total} to add${chosen.length > ready.length ? ` · ${chosen.length - ready.length} incomplete` : ''}`}
        </span>
        {needsRole && <RoleSwitch value={role} onChange={setRole} disabled={busy} />}
        <button type="button" className="ip-add" disabled={busy || total === 0} onClick={add}>{busy ? 'Adding…' : addLabel}</button>
        {message && <span className={message.kind === 'error' ? 'ip-warn' : 'ip-ok'} role="status">{message.text}</span>}
      </div>
    </div>
  );
}
