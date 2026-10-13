// SurrogateModeling.jsx
// The notebook, with the model at hand beside it: the problem saved in
// Problem definition, and the objects a FieldSelector names, searchable.
import React, { useState, useEffect, useContext, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { api, SERVICES } from './api';
import { ChevronDown, ChevronRight, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import SurrogateObjectGrid, { FIELDS } from './SurrogateObjectGrid';
import { AppContext } from './AppContext';
import './SurrogateModeling.css';

const surrogateTypes = [
  { key: 'materials', label: 'Materials', className: 'Material' },
  { key: 'constructions', label: 'Constructions', className: 'Construction' },
  { key: 'fenestration_surfaces', label: 'Windows', className: 'FenestrationSurface:Detailed' },
  { key: 'window_shading_controls', label: 'Window shading', className: 'WindowShadingControl' },
  { key: 'zone_ventilations', label: 'Ventilation', className: 'ZoneVentilation:DesignFlowRate' },
  { key: 'lights', label: 'Lights', className: 'Lights' },
];

export default function SurrogateModeling() {
  const { filesUploaded, uploadedFiles, sessionKey } = useContext(AppContext);
  const [data, setData] = useState({});
  const [problem, setProblem] = useState(null);
  const [open, setOpen] = useState({});
  const [query, setQuery] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    setOpen({});
    setQuery('');
    if (!filesUploaded) {
      setData({});
      setProblem(null);
      return;
    }
    fetch(api('/surrogate_modeling/get_surrogate_objects'))
      .then((res) => res.json())
      .then(setData)
      .catch((err) => console.error(err));
    fetch(api('/surrogate_modeling/problem'))
      .then((res) => res.json())
      .then(setProblem)
      .catch(() => setProblem(null));
  }, [filesUploaded, uploadedFiles.idf]);

  // A search looks in the names and in every field value, so "1001" finds the
  // glazing, the constructions using it and the windows it is on.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = {};
    surrogateTypes.forEach(({ key }) => {
      const objects = data[key] ?? [];
      out[key] = !q
        ? objects
        : objects.filter(
            (o) =>
              String(o.name).toLowerCase().includes(q) ||
              FIELDS[key](o).some(([, v]) => String(v ?? '').toLowerCase().includes(q))
          );
    });
    return out;
  }, [data, query]);

  const toggle = (key) => setOpen((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="sm">
      {sidebarOpen && (
        <aside className="sm-side">
          <div className="sm-side-head">
            <h2>Model reference</h2>
            <button type="button" className="sm-icon" onClick={() => setSidebarOpen(false)} title="Hide">
              <PanelLeftClose size={18} />
            </button>
          </div>

          {!filesUploaded ? (
            <p className="sm-muted">Upload an IDF and an EPW file to see the model here.</p>
          ) : (
            <>
              <div className="sm-problem">
                {problem?.defined ? (
                  <>
                    <div>
                      <b>{problem.variables.length}</b> parameters · <b>{problem.objectives.length}</b> objectives
                    </div>
                    <div className="sm-muted">saved in problem.json</div>
                  </>
                ) : (
                  <div className="sm-muted">No problem saved yet.</div>
                )}
                <Link to="/design_problem" className="sm-link">
                  {problem?.defined ? 'Edit in Problem definition' : 'Define it in Problem definition'}
                </Link>
              </div>

              <p className="sm-hint">
                The names and fields to write in <code>FieldSelector(class_name, object_name, field_name)</code>.
              </p>
              <input
                className="sm-search"
                type="search"
                placeholder="Search names and values"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />

              {surrogateTypes.map((t) => {
                const items = filtered[t.key] ?? [];
                const isOpen = open[t.key] || (query && items.length > 0);
                return (
                  <section key={t.key} className="sm-group">
                    <button type="button" className="sm-group-head" onClick={() => toggle(t.key)}>
                      {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      <span className="sm-group-label">{t.label}</span>
                      <code className="sm-class">{t.className}</code>
                      <span className="sm-count">{items.length}</span>
                    </button>
                    {isOpen && <SurrogateObjectGrid objects={items} type={t.key} />}
                  </section>
                );
              })}
            </>
          )}
        </aside>
      )}

      <main className="sm-main">
        {!sidebarOpen && (
          <button type="button" className="sm-icon sm-reopen" onClick={() => setSidebarOpen(true)} title="Show the model reference">
            <PanelLeftOpen size={18} />
          </button>
        )}
        {/* Remounted when the model changes, so the notebook reloads with it. */}
        <iframe
          key={`${uploadedFiles.idf || 'empty'}-${sessionKey}`}
          title="Surrogate Notebook"
          src={SERVICES.surrogateNotebook}
          className="sm-frame"
        />
      </main>
    </div>
  );
}
