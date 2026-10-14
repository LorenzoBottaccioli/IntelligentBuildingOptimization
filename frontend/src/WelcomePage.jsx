import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Brain, Cpu, CloudSun, Database, Gauge, Sparkles } from 'lucide-react';

// The live loop of an intelligent building. Orange = written by the student,
// blue = provided by the platform. Each node opens the page where it is built.
const COL = [20, 220, 420, 620, 820];
const ROW = [34, 214];
const W = 150;
const H = 92;

const NODES = [
  { id: 'building', col: 0, row: 0, kind: 'platform', title: 'Building', sub: 'EnergyPlus as an FMU', to: '/idf_editor' },
  { id: 'gateway', col: 1, row: 0, kind: 'student', title: 'Gateway', sub: 'devices/gateway.py', to: '/devices_code' },
  { id: 'broker', col: 2, row: 0, kind: 'platform', title: 'MQTT broker', sub: 'topics are yours', to: '/control_room' },
  { id: 'subscriber', col: 3, row: 0, kind: 'student', title: 'Subscriber', sub: 'iot/subscriber.py', to: '/subscriber_code' },
  { id: 'database', col: 4, row: 0, kind: 'platform', title: 'Database', sub: 'InfluxDB, your schema', to: '/data_notebooks' },
  { id: 'model', col: 0, row: 1, kind: 'student', title: 'Model & weather', sub: 'sensors, actuators, EPW', to: '/sensors_actuators' },
  { id: 'controller', col: 2, row: 1, kind: 'optional', title: 'Controller', sub: 'ai/controller.py', to: '/controller_code' },
  { id: 'operator', col: 3, row: 1, kind: 'student', title: 'Operator panel', sub: 'openHAB / Home Assistant', to: '/operator_panel' },
  { id: 'dashboards', col: 4, row: 1, kind: 'student', title: 'Dashboards', sub: 'Grafana, KPIs', to: '/grafana' },
];

const x = (n) => COL[n.col];
const y = (n) => ROW[n.row];
const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));
const midY = (id) => y(byId[id]) + H / 2;
const midX = (id) => x(byId[id]) + W / 2;
const right = (id) => x(byId[id]) + W;
const left = (id) => x(byId[id]);
const bottom = (id) => y(byId[id]) + H;
const top = (id) => y(byId[id]);

// [x1, y1, x2, y2, bothWays]
const EDGES = [
  [right('building'), midY('building'), left('gateway'), midY('gateway'), true],
  [right('gateway'), midY('gateway'), left('broker'), midY('broker'), true],
  [right('broker'), midY('broker'), left('subscriber'), midY('subscriber'), false],
  [right('subscriber'), midY('subscriber'), left('database'), midY('database'), false],
  [midX('model'), top('model'), midX('building'), bottom('building'), false],
  [midX('broker'), bottom('broker'), midX('controller'), top('controller'), true],
  [right('broker') - 40, bottom('broker'), left('operator') + 40, top('operator'), true],
  [midX('database'), bottom('database'), midX('dashboards'), top('dashboards'), false],
];

function Loop() {
  const navigate = useNavigate();
  const open = (to) => navigate(to);
  return (
    <div className="wl-loop">
      <svg viewBox="0 0 990 330" role="img" aria-label="Loop of the intelligent building: building, gateway, broker, subscriber, database, dashboards, with controller and operator panel on the broker">
        <defs>
          <marker id="wl-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 1 L9 5 L0 9 z" fill="#5b6b7f" />
          </marker>
        </defs>
        {EDGES.map(([x1, y1, x2, y2, both], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#5b6b7f" strokeWidth="1.6"
            markerEnd="url(#wl-arrow)" markerStart={both ? 'url(#wl-arrow)' : undefined} />
        ))}
        <text x={left('gateway') - 25} y={midY('gateway') - 10} className="wl-edge" textAnchor="middle">sensors</text>
        <text x={left('broker') - 25} y={midY('broker') - 10} className="wl-edge" textAnchor="middle">publish</text>
        <text x={midX('controller') + 10} y={bottom('broker') + 40} className="wl-edge">commands</text>
        {NODES.map((n) => (
          <g key={n.id} className={`wl-node wl-node--${n.kind}`} role="link" tabIndex={0}
            aria-label={`${n.title}: ${n.sub}`}
            onClick={() => open(n.to)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(n.to); } }}>
            <rect x={x(n)} y={y(n)} width={W} height={H} rx="10" />
            <text x={x(n) + W / 2} y={y(n) + 40} textAnchor="middle" className="wl-node__title">{n.title}</text>
            <text x={x(n) + W / 2} y={y(n) + 62} textAnchor="middle" className="wl-node__sub">{n.sub}</text>
          </g>
        ))}
      </svg>
      <ul className="wl-legend" aria-label="Legend">
        <li><i className="wl-dot wl-dot--student" /> You write it</li>
        <li><i className="wl-dot wl-dot--platform" /> We provide it</li>
        <li><i className="wl-dot wl-dot--optional" /> Optional</li>
      </ul>
    </div>
  );
}

// The design stage, before the building is instrumented: a few simulations teach a fast surrogate model,
// the optimiser searches the surrogate, and the best designs are checked with EnergyPlus.
const DESIGN = [
  { title: 'Design space', sub: 'variables and objectives', kind: 'student', to: '/design_problem' },
  { title: 'EnergyPlus', sub: 'a few simulations', kind: 'platform', to: '/surrogate_modeling' },
  { title: 'Surrogate', sub: 'learns, predicts fast', kind: 'student', to: '/surrogate_modeling' },
  { title: 'Optimiser', sub: 'searches the surrogate', kind: 'student', to: '/surrogate_modeling' },
  { title: 'Best designs', sub: 'trade-offs, verified', kind: 'platform', to: '/surrogate_modeling' },
];

function DesignFlow() {
  const navigate = useNavigate();
  const Y = 20;
  const last = COL[4] + W / 2;
  const first = COL[1] + W / 2;
  return (
    <div className="wl-loop">
      <svg viewBox="0 0 990 200" role="img" aria-label="Design optimisation: design space, EnergyPlus simulations, surrogate model, optimiser, best designs, checked back in EnergyPlus">
        <defs>
          <marker id="wl-arrow-d" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 1 L9 5 L0 9 z" fill="#5b6b7f" />
          </marker>
        </defs>
        {DESIGN.slice(1).map((_, i) => (
          <line key={i} x1={COL[i] + W} y1={Y + H / 2} x2={COL[i + 1]} y2={Y + H / 2}
            stroke="#5b6b7f" strokeWidth="1.6" markerEnd="url(#wl-arrow-d)" />
        ))}
        <path d={`M ${last} ${Y + H} V ${Y + H + 50} H ${first} V ${Y + H + 4}`} fill="none"
          stroke="#5b6b7f" strokeWidth="1.6" strokeDasharray="6 4" markerEnd="url(#wl-arrow-d)" />
        <text x={(first + last) / 2} y={Y + H + 42} textAnchor="middle" className="wl-edge">check the best designs, add simulations where the surrogate is weak</text>
        {DESIGN.map((n, i) => (
          <g key={n.title} className={`wl-node wl-node--${n.kind}`} role="link" tabIndex={0}
            aria-label={`${n.title}: ${n.sub}`}
            onClick={() => navigate(n.to)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(n.to); } }}>
            <rect x={COL[i]} y={Y} width={W} height={H} rx="10" />
            <text x={COL[i] + W / 2} y={Y + 40} textAnchor="middle" className="wl-node__title">{n.title}</text>
            <text x={COL[i] + W / 2} y={Y + 62} textAnchor="middle" className="wl-node__sub">{n.sub}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}

const AREAS = [
  {
    Icon: Sparkles,
    title: 'Surrogate Design Optimization',
    body: 'Find the best building without simulating every option: define the problem, sample the design space, train a surrogate and optimise on it.',
    tag: 'Start here',
    links: [
      { to: '/tutorials', text: 'Tutorials' },
      { to: '/design_problem', text: 'Problem definition' },
      { to: '/surrogate_modeling', text: 'Surrogate modelling' },
    ],
  },
  {
    Icon: Cpu,
    title: 'Building & devices',
    body: 'Open the model, choose what to sense and what to actuate, and write the gateway that plays all your field devices.',
    links: [
      { to: '/idf_editor', text: 'Model editor' },
      { to: '/sensors_actuators', text: 'Sensors & actuators' },
      { to: '/ems_programs', text: 'EMS programs' },
      { to: '/devices_code', text: 'Gateway' },
    ],
  },
  {
    Icon: CloudSun,
    title: 'Weather',
    body: 'Look inside the weather file of the session, change it, or build real years from Open-Meteo for the place you choose and simulate that year.',
    links: [
      { to: '/weather_explore', text: 'Explore weather' },
      { to: '/weather_edit', text: 'Create & edit weather' },
    ],
  },
  {
    Icon: Database,
    title: 'IoT & data',
    body: 'Subscribe to your topics, clean and check what arrives, keep it in InfluxDB, then query it and compute the energy signature of the baseline.',
    links: [
      { to: '/subscriber_code', text: 'Subscriber' },
      { to: '/data_notebooks', text: 'Data notebooks' },
    ],
  },
  {
    Icon: Gauge,
    title: 'BMS',
    body: 'Start your services and the building from the Control room, baseline first and controlled after. Give the operator a panel and the manager dashboards.',
    links: [
      { to: '/control_room', text: 'Control room' },
      { to: '/operator_panel', text: 'Operator panel' },
      { to: '/grafana', text: 'Dashboards' },
    ],
  },
  {
    Icon: Brain,
    title: 'AI',
    body: 'A controller that beats the baseline, from an IF-THEN rule up to a trained RL agent, and a forecasting model.',
    tag: 'Optional',
    links: [
      { to: '/controller_code', text: 'Controller' },
      { to: '/agent_training', text: 'Agent training' },
      { to: '/forecasting', text: 'Forecasting' },
    ],
  },
];

export default function WelcomePage() {
  return (
    <div className="wl">
      <header className="wl-hero">
        <p className="wl-hero__eyebrow">Intelligent Building Educational Platform</p>
        <h1>A real building, without the building.</h1>
        <p className="wl-hero__lead">
          EnergyPlus plays the building. First you look for a good design without simulating every
          option: you sample the design space, train a surrogate model and optimise on it. Then you
          install the sensors and actuators of that building, write everything that talks to it —
          gateway, subscriber, database, controller, dashboards — and find out whether it works.
        </p>
        <div className="wl-hero__actions">
          <Link to="/tutorials" className="wl-btn wl-btn--primary">Start with the tutorials <ArrowRight size={16} aria-hidden="true" /></Link>
          <Link to="/control_room" className="wl-btn wl-btn--ghost">Open the Control room</Link>
        </div>
      </header>

      <section className="wl-section">
        <h2>First, design the building</h2>
        <p className="wl-section__lead">
          There are too many possible designs to simulate them all. You simulate a few, a surrogate model learns to
          predict the rest, and an optimiser searches the surrogate for the best compromises.
        </p>
        <DesignFlow />
      </section>

      <section className="wl-section">
        <h2>Then, make it a smart building</h2>
        <p className="wl-section__lead">
          The building sends its sensors to a broker and receives commands from it; everything
          else listens to the broker. Click any block to open the page where you build it.
        </p>
        <Loop />
      </section>

      <section className="wl-section">
        <h2>Where you work</h2>
        <div className="wl-grid">
          {AREAS.map(({ Icon, title, body, tag, links }) => (
            <article className="wl-card" key={title}>
              <div className="wl-card__head">
                <span className="wl-card__icon"><Icon size={20} aria-hidden="true" /></span>
                <h3>{title}</h3>
                {tag && <span className="wl-card__tag">{tag}</span>}
              </div>
              <p>{body}</p>
              <div className="wl-card__links">
                {links.map((l) => <Link key={l.to} to={l.to} className="wl-chip">{l.text}</Link>)}
              </div>
            </article>
          ))}
        </div>
      </section>

      <p className="wl-foot">
        A demo session is loaded when the platform starts: a small house with the weather of Turin, its design
        problem and a complete working building to show (gateway, subscriber, controller, openHAB, Home Assistant,
        Grafana). The Sessions menu brings it back whenever you want it, and also offers the Lab.
      </p>
    </div>
  );
}
