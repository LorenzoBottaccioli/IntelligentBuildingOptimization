import React, { useContext } from 'react';
import { AppContext } from './AppContext';

/**
 * Full-bleed embedded service (Jupyter, Grafana, openHAB, Home Assistant).
 *
 * The `key` on the iframe forces a remount when a new model is uploaded, so the
 * embedded tool picks up the new files. Everything else relies on App.jsx keeping
 * this component mounted (hidden with display:none) so the iframe is never
 * reloaded just by navigating away and back.
 */
export default function IframePage({ title, src }) {
  const { filesUploaded, sessionKey } = useContext(AppContext);

  return (
    <div className="iframe-page">
      <iframe
        key={`${filesUploaded ? 'loaded' : 'empty'}-${sessionKey}`}
        title={title}
        src={src}
        className="iframe-page__frame"
      />
    </div>
  );
}
