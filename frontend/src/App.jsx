// src/App.jsx
import React, { useEffect } from 'react';
import { BrowserRouter as Router, useLocation, useNavigate } from 'react-router-dom';
import Header from './Header';
import { SensorsActuators, EmsProgramsPage } from './ModelEditor';
import IdfEditor from './IdfEditor';
import WelcomePage from './WelcomePage';
import SurrogateModeling from './SurrogateModeling';
import DesignProblem from './DesignProblem';
import Tutorials from './Tutorials';
import AgentTraining from './AgentTraining';
import Grafana from './Grafana';
import OperatorPanel from './OperatorPanel';
import ControlRoom from './ControlRoom';
import { DevicesCode, SubscriberCode, DataNotebooks, ControllerCode, Forecasting } from './WorkspacePages';
import { WeatherExplorePage, WeatherEditPage } from './Weather';
import Credits from './Credits';
import { AppProvider } from './AppContext';

/**
 * Every page stays mounted and is toggled with display, rather than swapped by
 * <Routes>. That is deliberate: the embedded Jupyter, Grafana, openHAB and Home Assistant
 * iframes would otherwise reload — losing kernel state — on every navigation.
 */
const PAGES = [
  { path: '/', Component: WelcomePage, scroll: true },
  { path: '/design_problem', Component: DesignProblem, scroll: true },
  { path: '/tutorials', Component: Tutorials },
  { path: '/surrogate_modeling', Component: SurrogateModeling },
  { path: '/idf_editor', Component: IdfEditor, scroll: true },
  { path: '/sensors_actuators', Component: SensorsActuators, scroll: true },
  { path: '/ems_programs', Component: EmsProgramsPage, scroll: true },
  { path: '/weather_explore', Component: WeatherExplorePage, scroll: true },
  { path: '/weather_edit', Component: WeatherEditPage, scroll: true },
  { path: '/devices_code', Component: DevicesCode },
  { path: '/subscriber_code', Component: SubscriberCode },
  { path: '/data_notebooks', Component: DataNotebooks },
  { path: '/controller_code', Component: ControllerCode },
  { path: '/agent_training', Component: AgentTraining },
  { path: '/forecasting', Component: Forecasting },
  { path: '/control_room', Component: ControlRoom, scroll: true },
  { path: '/grafana', Component: Grafana },
  { path: '/operator_panel', Component: OperatorPanel },
  { path: '/credits', Component: Credits, scroll: true },
];

function AppContent() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  // Old addresses of the model editor and the converter: keep links working.
  useEffect(() => {
    if (pathname === '/model_editor') navigate('/sensors_actuators', { replace: true });
    if (pathname === '/model_converter' || pathname === '/fmu_export') navigate('/control_room', { replace: true });
    if (pathname === '/simulator') navigate('/agent_training', { replace: true });
    if (pathname === '/base_simulation' || pathname === '/controlled_simulation') navigate('/control_room', { replace: true });
    if (pathname === '/weather_editor' || pathname === '/weather_library') navigate('/weather_edit', { replace: true });
    if (pathname === '/controller') navigate('/controller_code', { replace: true });
    if (pathname === '/openhab') navigate('/operator_panel?tool=openhab', { replace: true });
    if (pathname === '/homeassistant') navigate('/operator_panel?tool=homeassistant', { replace: true });
  }, [pathname, navigate]);

  return (
    <div className="app-pages">
      {PAGES.map(({ path, Component, scroll }) => (
        <div
          key={path}
          style={{
            display: pathname === path ? 'block' : 'none',
            position: 'absolute',
            inset: 0,
            overflow: scroll ? 'auto' : 'hidden',
          }}
        >
          <Component />
        </div>
      ))}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Router>
        <div className="app-root">
          <Header />
          <div className="app-main">
            <AppContent />
          </div>
        </div>
      </Router>
    </AppProvider>
  );
}
