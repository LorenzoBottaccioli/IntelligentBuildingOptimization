// KitBar.jsx
// Kits: lists of choices by name ("the mean air temperature of every zone"), applied to the open model in one
// click. The platform provides two; the student's own are saved in the session (backend/instrument_kits.py).
import React, { useState } from 'react';

export default function KitBar({ kits, busy, message, canSave, onApply, onSave, onDelete }) {
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState('');
  const all = [...(kits.provided || []), ...(kits.saved || [])];
  const save = async () => {
    if (!name.trim()) return;
    if (await onSave(name.trim())) { setNaming(false); setName(''); }
  };
  return (
    <section className="ins-card kb" aria-label="Kits">
      <div className="zb-head">
        <span className="zb-title">Kits</span>
        <span className="ip-muted">a kit adds a whole selection by name, on any model</span>
      </div>
      <div className="kb-list">
        {all.map((k) => (
          <span key={`${k.provided ? 'p' : 's'}:${k.name}`} className="kb-kit">
            <button type="button" className="kb-apply" disabled={busy} title={k.description || `${k.entries.length} choices`} onClick={() => onApply(k)}>
              <b>{k.name}</b>
              <small>{k.provided ? 'platform' : 'yours'} · {k.entries.length} {k.entries.length === 1 ? 'choice' : 'choices'}</small>
            </button>
            {!k.provided && <button type="button" className="kb-x" title="Delete this kit" disabled={busy} onClick={() => onDelete(k.name)}>×</button>}
          </span>
        ))}
        {!naming && (
          <button type="button" className="ip-link" disabled={busy || !canSave} onClick={() => setNaming(true)}
            title={canSave ? 'Keep what is in Your FMU as a kit' : 'Add something to the FMU first'}>
            Save what is in the FMU as a kit…
          </button>
        )}
        {naming && (
          <form className="kb-name" onSubmit={(e) => { e.preventDefault(); save(); }}>
            <input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="Name of the kit" aria-label="Name of the kit" autoFocus />
            <button type="submit" disabled={busy || !name.trim()}>Save</button>
            <button type="button" onClick={() => { setNaming(false); setName(''); }}>Cancel</button>
          </form>
        )}
      </div>
      {message && <p className={message.kind === 'error' ? 'ip-warn' : 'ip-ok'} role="status">{message.text}</p>}
    </section>
  );
}
