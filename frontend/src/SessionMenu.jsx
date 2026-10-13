import React, { useState, useEffect, useRef, useContext, useCallback } from 'react';
import axios from 'axios';
import { api } from './api';
import { AppContext } from './AppContext';
import { FolderOpen, RotateCcw, Trash2 } from 'lucide-react';
import './SessionMenu.css';

const errText = (err, fallback) => err?.response?.data?.error || err?.message || fallback;

const fmtDate = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const day = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  return `${day} ${time}`;
};

const fmtTime = (d) => d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

// Saved workspaces: model, notebooks and outputs of one piece of work.
export default function SessionMenu({ onError, collapsed, onExpand }) {
  const { reloadWorkspace, resetSession } = useContext(AppContext);
  const [open, setOpen] = useState(false);
  const [state, setState] = useState({ current: null, sessions: [] });
  // 'save' | 'new' | 'reset' | 'open:<id>' | 'delete:<id>' | 'rename:<id>'
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null); // { text, error }
  const [savedAt, setSavedAt] = useState(null);
  const [saveName, setSaveName] = useState('');
  const [newName, setNewName] = useState('');
  const [renaming, setRenaming] = useState(null); // { id, name }
  const rootRef = useRef(null);
  const buttonRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get(api('/sessions'));
      setState({ current: data.current ?? null, sessions: data.sessions || [] });
      return true;
    } catch (err) {
      console.error('Error reading the sessions:', err);
      return false;
    }
  }, []);

  // On load the backend may still be starting: retry until it answers.
  useEffect(() => {
    let timer = null;
    let tries = 0;
    const ask = async () => {
      if (!(await refresh()) && ++tries < 60) timer = setTimeout(ask, 2000);
    };
    ask();
    return () => clearTimeout(timer);
  }, [refresh]);
  useEffect(() => { if (open) refresh(); }, [open, refresh]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const currentSession = state.sessions.find((s) => s.id === state.current);
  const label = state.current == null ? 'Unsaved' : currentSession?.name || 'Session';
  const locked = busy != null;

  const call = async (key, fn) => {
    setBusy(key);
    setMsg(null);
    onError?.(null);
    try {
      return await fn();
    } catch (err) {
      setMsg({ text: errText(err, 'Request failed.'), error: true });
      return undefined;
    } finally {
      setBusy(null);
    }
  };

  const warn = (data) => {
    const w = data?.warnings;
    if (w && w.length) {
      setMsg({ text: `Done, with warnings: ${w.join(' ')}`, error: true });
      return true;
    }
    return false;
  };

  const apply = (data) => setState({ current: data.current ?? null, sessions: data.sessions || [] });

  const doSave = async (e) => {
    e?.preventDefault?.();
    const name = saveName.trim();
    if (state.current == null && !name) return;
    const data = await call('save', async () =>
      (await axios.post(api('/sessions/save'), name ? { name } : {})).data);
    if (data) {
      apply(data);
      setSaveName('');
      if (!warn(data)) setSavedAt(new Date());
    }
  };

  const doNew = async (e) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    const data = await call('new', async () => {
      const r = (await axios.post(api('/sessions/new'), { name })).data;
      await reloadWorkspace();
      return r;
    });
    if (data) {
      apply(data);
      setNewName('');
      setSavedAt(null);
      if (!warn(data)) setOpen(false);
    }
  };

  const doOpen = async (s) => {
    if (locked || s.id === state.current) return;
    const data = await call(`open:${s.id}`, async () => {
      const r = (await axios.post(api('/sessions/open'), { id: s.id })).data;
      await reloadWorkspace();
      return r;
    });
    if (data) {
      apply(data);
      setSavedAt(null);
      if (!warn(data)) setOpen(false);
    }
  };

  const doRename = async (e) => {
    e.preventDefault();
    const name = renaming.name.trim();
    if (!name) return;
    const data = await call(`rename:${renaming.id}`, async () =>
      (await axios.post(api('/sessions/rename'), { id: renaming.id, name })).data);
    if (data) {
      apply(data);
      setRenaming(null);
    }
  };

  const doDelete = async (s) => {
    if (!window.confirm(`Delete the session "${s.name}"? Its saved model, notebooks, outputs, InfluxDB data and Grafana dashboards are removed.`)) return;
    const data = await call(`delete:${s.id}`, async () =>
      (await axios.delete(api(`/sessions/${encodeURIComponent(s.id)}`))).data);
    if (data) apply(data);
  };

  // Folded sidebar: only the icon, which unfolds it.
  if (collapsed) {
    return (
      <button type="button" className="sidebar__icon" title={`Session: ${label}`} aria-label={`Session: ${label}`} onClick={onExpand}>
        <FolderOpen size={18} aria-hidden="true" />
      </button>
    );
  }

  return (
    <div className="sessionmenu" ref={rootRef}>
      <span className="sessionmenu__label">Session</span>
      <button
        ref={buttonRef}
        type="button"
        className={`sessionmenu__toggle${state.current == null ? ' is-unsaved' : ''}`}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <FolderOpen size={16} aria-hidden="true" />
        <span className="sessionmenu__name">{label}</span>
        <span className="sessionmenu__caret" aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="sessionmenu__panel" role="dialog" aria-label="Sessions">
          {busy && busy.startsWith('open:') && <div className="sessionmenu__busy">Opening…</div>}
          {busy === 'new' && <div className="sessionmenu__busy">Creating…</div>}
          {busy === 'reset' && <div className="sessionmenu__busy">Resetting…</div>}

          <section className="sessionmenu__section">
            {state.current == null ? (
              <form className="sessionmenu__row" onSubmit={doSave}>
                <input
                  className="sessionmenu__input"
                  placeholder="Name this session"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  disabled={locked}
                  aria-label="Session name"
                  autoFocus
                />
                <button type="submit" className="modelbar__btn modelbar__btn--primary" disabled={locked || !saveName.trim()}>
                  {busy === 'save' ? 'Saving…' : 'Save'}
                </button>
              </form>
            ) : (
              <div className="sessionmenu__row">
                <button type="button" className="modelbar__btn modelbar__btn--primary" onClick={doSave} disabled={locked}>
                  {busy === 'save' ? 'Saving…' : 'Save'}
                </button>
                {savedAt && <span className="sessionmenu__ok">Saved {fmtTime(savedAt)}</span>}
              </div>
            )}
          </section>

          <section className="sessionmenu__section">
            <form className="sessionmenu__row" onSubmit={doNew}>
              <input
                className="sessionmenu__input"
                placeholder="New session…"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                disabled={locked}
                aria-label="New session name"
              />
              <button type="submit" className="modelbar__btn" disabled={locked || !newName.trim()}>Create</button>
            </form>
            <p className="sessionmenu__hint">
              The current session, InfluxDB data and Grafana dashboards included, is saved first. The new session starts with an empty workspace, empty InfluxDB databases and no Grafana dashboards. The building must be stopped.
            </p>
          </section>

          <section className="sessionmenu__section sessionmenu__list" aria-label="Saved sessions">
            {state.sessions.length === 0 && <p className="sessionmenu__hint">No saved sessions yet.</p>}
            {state.sessions.map((s) => {
              const isCurrent = s.id === state.current;
              if (renaming?.id === s.id) {
                return (
                  <form key={s.id} className="sessionmenu__item sessionmenu__row" onSubmit={doRename}>
                    <input
                      className="sessionmenu__input"
                      value={renaming.name}
                      onChange={(e) => setRenaming({ id: s.id, name: e.target.value })}
                      aria-label="New name"
                      autoFocus
                      disabled={locked}
                    />
                    <button type="submit" className="modelbar__btn" disabled={locked || !renaming.name.trim()}>OK</button>
                    <button type="button" className="modelbar__btn" onClick={() => setRenaming(null)}>Cancel</button>
                  </form>
                );
              }
              return (
                <div key={s.id} className={`sessionmenu__item${isCurrent ? ' is-current' : ''}`}>
                  <button
                    type="button"
                    className="sessionmenu__open"
                    onClick={() => doOpen(s)}
                    disabled={locked && busy !== `open:${s.id}`}
                    aria-current={isCurrent ? 'true' : undefined}
                    title={isCurrent ? 'Current session' : 'Open this session'}
                  >
                    <span className="sessionmenu__itemname">
                      {s.name}
                      {isCurrent && <span className="sessionmenu__badge">current</span>}
                    </span>
                    <span className="sessionmenu__meta">
                      {busy === `open:${s.id}`
                        ? 'Opening…'
                        : `${s.idf || 'no model'}${s.saved ? ` · saved ${fmtDate(s.saved)}` : ''}`}
                    </span>
                  </button>
                  <button type="button" className="sessionmenu__mini" disabled={locked}
                    onClick={() => setRenaming({ id: s.id, name: s.name })}>Rename</button>
                  <button type="button" className="sessionmenu__mini sessionmenu__mini--danger"
                    disabled={locked || isCurrent} onClick={() => doDelete(s)}
                    title={isCurrent ? 'The current session cannot be deleted' : undefined}>Delete</button>
                </div>
              );
            })}
          </section>

          {msg && <p className={`sessionmenu__msg${msg.error ? ' is-error' : ''}`} role="alert">{msg.text}</p>}

        </div>
      )}
    </div>
  );
}

/** Under the session: clear the InfluxDB data, or start the session over. */
export function SessionTools({ collapsed, onExpand }) {
  const { resetSession } = useContext(AppContext);
  const [busy, setBusy] = useState(null); // 'influx' | 'reset'
  const [msg, setMsg] = useState(null);

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(null), 5000); };

  const reset = async () => {
    if (!window.confirm(
      'Reset the current session? The model, every edit, the notebooks, the simulation outputs and the InfluxDB data are emptied.'
    )) return;
    setBusy('reset');
    try {
      await resetSession();
      flash({ text: 'Session reset.' });
    } catch (err) {
      flash({ text: errText(err, 'Reset failed.'), error: true });
    } finally {
      setBusy(null);
    }
  };

  // The controlled and baseline runs write to InfluxDB; its content belongs to the current session.
  const clearInflux = async () => {
    if (!window.confirm('Clear InfluxDB? Every stored controlled and baseline run of the current session is deleted.')) return;
    setBusy('influx');
    try {
      const { data } = await axios.post(api('/model_converter/clear_influx'));
      if (!data.success) throw new Error(data.error || 'Unknown error');
      flash({ text: 'InfluxDB cleared.' });
    } catch (err) {
      flash({ text: errText(err, 'Clearing InfluxDB failed.'), error: true });
    } finally {
      setBusy(null);
    }
  };

  const tools = [
    { id: 'influx', Icon: Trash2, text: busy === 'influx' ? 'Clearing InfluxDB…' : 'Clear InfluxDB data', danger: true,
      title: 'Delete the stored controlled and baseline runs (of the current session)', onClick: clearInflux },
    { id: 'reset', Icon: RotateCcw, text: busy === 'reset' ? 'Resetting…' : 'Reset session', danger: true,
      title: 'Empty model, notebooks, outputs and InfluxDB', onClick: reset },
  ];

  return (
    <div className="sessiontools">
      {tools.map((t) => (
        <button key={t.id} type="button" title={t.title} disabled={busy != null}
          className={collapsed ? 'sidebar__icon' : `sessiontools__btn${t.danger ? ' is-danger' : ''}`}
          onClick={collapsed ? onExpand : t.onClick}>
          <t.Icon size={collapsed ? 18 : 15} aria-hidden="true" />
          {!collapsed && <span>{t.text}</span>}
        </button>
      ))}
      {msg && !collapsed && <p className={`sessiontools__msg${msg.error ? ' is-error' : ''}`} role="status">{msg.text}</p>}
    </div>
  );
}
