import React, { useContext, useState } from 'react';
import { AppContext } from './AppContext';
import { SERVICES } from './api';
import './Tutorials.css';

// The tutorial notebooks live in surrogate_notebooks/tutorials/ (the folder of the Jupyter on port 8889),
// so they are part of every saved session and the demo session brings them.
const NOTEBOOKS = [
  {
    id: 'overview',
    label: '1 · bdopt overview',
    path: 'notebooks/tutorials/1_bdopt_overview.ipynb',
    blurb: 'Read a model, define parameters and objectives, simulate a few designs and look at the results.',
  },
  {
    id: 'surrogate',
    label: '2 · Surrogate modelling',
    path: 'notebooks/tutorials/2_surrogate_modelling.ipynb',
    blurb: 'Train surrogate models on simulated samples and compare them on designs they have not seen.',
  },
  {
    id: 'optimization',
    label: '3 · Optimization',
    path: 'notebooks/tutorials/3_optimization.ipynb',
    blurb: 'Find the Pareto front with NSGA-II, on EnergyPlus and on the surrogate, and check the best design.',
  },
  {
    id: 'adaptive',
    label: '4 · Adaptive sampling',
    path: 'notebooks/tutorials/4_adaptive_sampling.ipynb',
    blurb: 'Let the sampler choose which simulations to run: one objective, then several, against a Latin hypercube.',
  },
  {
    id: 'folder',
    label: 'All files',
    path: 'tree/tutorials',
    blurb: 'The folder with the notebooks, the model (test.idf), the weather file and the stored results.',
  },
];

export default function Tutorials() {
  const { sessionKey } = useContext(AppContext);
  const [active, setActive] = useState(NOTEBOOKS[0].id);
  const current = NOTEBOOKS.find((n) => n.id === active);
  const base = SERVICES.surrogateJupyter;

  return (
    <div className="tutorials">
      <div className="tutorials__bar">
        <div className="tutorials__tabs" role="tablist">
          {NOTEBOOKS.map((n) => (
            <button
              key={n.id}
              type="button"
              role="tab"
              aria-selected={n.id === active}
              className={`tutorials__tab${n.id === active ? ' tutorials__tab--active' : ''}`}
              onClick={() => setActive(n.id)}
            >
              {n.label}
            </button>
          ))}
        </div>
        <p className="tutorials__blurb">{current.blurb}</p>
        <p className="tutorials__blurb">
          The tutorials are part of the session you are working in, so your changes are saved with it. If a notebook
          is not found, open the session <strong>Demo - bdopt tutorial</strong> from the Sessions menu.
        </p>
      </div>
      <iframe
        key={`${active}-${sessionKey}`}
        title={current.label}
        src={`${base}/${current.path}`}
        className="tutorials__frame"
      />
    </div>
  );
}
