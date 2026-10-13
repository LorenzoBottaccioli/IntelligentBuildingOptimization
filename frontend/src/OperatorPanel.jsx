import React, { useContext, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { SERVICES } from './api';
import { AppContext } from './AppContext';

/**
 * The operator panel of the building: the screen of the person who runs it (live values, setpoints).
 * Two tools, one tab each, like the file tabs of the code pages. A tool that has been opened stays mounted
 * (hidden), so switching never reloads it. `?tool=homeassistant` selects a tab.
 */
const TOOLS = [
  {
    id: 'openhab',
    label: 'openHAB',
    src: SERVICES.openhab,
    blurb: 'Pages are made in the page designer (sign in as administrator, bottom of the sidebar); things and items come from your devices.',
  },
  {
    id: 'homeassistant',
    label: 'Home Assistant',
    src: SERVICES.homeassistant,
    blurb: 'Dashboards are edited with the pencil at the top right; MQTT entities in Settings > Devices & services > MQTT.',
  },
];

const NONE = new Set();

const toolFromSearch = (search) => {
  const id = new URLSearchParams(search).get('tool');
  return TOOLS.some((t) => t.id === id) ? id : TOOLS[0].id;
};

export default function OperatorPanel() {
  const { sessionKey } = useContext(AppContext);
  const { pathname, search } = useLocation();
  const [current, setCurrent] = useState(() => toolFromSearch(search));
  // Nothing is loaded until the page is shown: openHAB's Main UI, loaded inside a display:none
  // (zero-size) iframe, spins the browser's main thread and freezes every page of the platform.
  // The same goes after a new / open / reset session: the iframes are keyed on sessionKey and would be
  // created again while this page is hidden. So what is open belongs to the sessionKey it was opened under;
  // under a newer key nothing is open until the page is shown again (derived while rendering, not in an
  // effect, because an effect runs after the hidden iframe has already been created and started loading).
  const [openState, setOpenState] = useState(() => ({ key: sessionKey, ids: new Set() }));
  const opened = openState.key === sessionKey ? openState.ids : NONE;

  const open = (id) => {
    setCurrent(id);
    setOpenState((s) => {
      const ids = s.key === sessionKey ? s.ids : NONE;
      return ids.has(id) ? s : { key: sessionKey, ids: new Set(ids).add(id) };
    });
  };

  useEffect(() => {
    if (pathname === '/operator_panel') open(search ? toolFromSearch(search) : current);
  }, [pathname, search, sessionKey]);

  const active = TOOLS.find((t) => t.id === current);

  return (
    <div className="controller">
      <div className="controller__tabs" role="tablist">
        {TOOLS.map((t) => (
          <button key={t.id} role="tab" type="button" aria-selected={t.id === current}
            className={t.id === current ? 'is-active' : undefined} onClick={() => open(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <p className="controller__blurb">{active.blurb}</p>

      <div className="controller__body">
        <div className="controller__pane">
          {TOOLS.filter((t) => opened.has(t.id)).map((t) => (
            <iframe key={`${t.id}-${sessionKey}`} title={t.label} src={t.src} className="controller__frame"
              style={{ display: t.id === current ? 'block' : 'none' }} />
          ))}
        </div>
      </div>
    </div>
  );
}
