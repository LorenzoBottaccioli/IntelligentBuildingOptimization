import React, { useContext, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { SERVICES } from './api';
import { AppContext } from './AppContext';

/**
 * The students' Workspace/ in the embedded Jupyter (port 8892), one tab per file.
 * Tabs already opened stay mounted (hidden), so switching never drops unsaved edits.
 *
 * files: [{ id, label, path, file, blurb }] where path is a Jupyter path such as
 * `edit/devices/gateway.py`, `notebooks/iot/data_access.ipynb` or `tree/logs`.
 * route: the page's own address; `?file=<id>` on it selects a tab.
 */
export default function WorkspacePage({ files, route }) {
  const { sessionKey } = useContext(AppContext);
  const { pathname, search } = useLocation();

  const fileFromSearch = (s) => {
    const id = new URLSearchParams(s).get('file');
    return files.some((f) => f.id === id) ? id : files[0].id;
  };

  const [current, setCurrent] = useState(() => fileFromSearch(search));
  const [opened, setOpened] = useState(() => new Set([fileFromSearch(search)]));

  const open = (id) => {
    setCurrent(id);
    setOpened((o) => (o.has(id) ? o : new Set(o).add(id)));
  };

  useEffect(() => {
    if (pathname !== route || !search) return;
    const id = new URLSearchParams(search).get('file');
    if (files.some((f) => f.id === id)) {
      setCurrent(id);
      setOpened((o) => (o.has(id) ? o : new Set(o).add(id)));
    }
  }, [pathname, search, route, files]);

  const active = files.find((f) => f.id === current) || files[0];
  const isPy = active.path.endsWith('.py');
  const isNotebook = active.path.endsWith('.ipynb');

  return (
    <div className="controller">
      {files.length > 1 && (
        <div className="controller__tabs" role="tablist">
          {files.map((f) => (
            <button key={f.id} role="tab" type="button" aria-selected={f.id === current}
              className={f.id === current ? 'is-active' : undefined} onClick={() => open(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
      )}

      <p className="controller__blurb">
        <code>{active.file}</code> · {active.blurb}{' '}
        {isPy && (
          <>Save with Ctrl+S. Run it from <Link to="/control_room">BMS › Control room</Link>.</>
        )}
        {isNotebook && <>Run the cells here.</>}
      </p>

      <div className="controller__body">
        <div className="controller__pane">
          {files.filter((f) => opened.has(f.id)).map((f) => (
            <iframe
              key={`${f.id}-${sessionKey}`}
              title={f.file}
              src={`${SERVICES.workspaceJupyter}/${f.path}`}
              className="controller__frame"
              style={{ display: f.id === current ? 'block' : 'none' }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
