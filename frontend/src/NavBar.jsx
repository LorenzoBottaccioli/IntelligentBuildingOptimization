import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Brain, ChevronDown, ChevronRight, Cpu, CloudSun, Database, Gauge, Home, Sparkles } from 'lucide-react';
import './NavBar.css';

// Sections in pipeline order. A section opens to show its pages; the one the
// student is in stays open and its current page is marked, so both levels of
// "where am I" are always visible. Every page stays reachable at any time.
export const SECTIONS = [
  { id: 'home', label: 'Home', Icon: Home, to: '/' },
  {
    id: 'design',
    label: 'Surrogate Design Optimization',
    Icon: Sparkles,
    pages: [
      { to: '/tutorials', text: 'Tutorials (notebooks)' },
      { to: '/design_problem', text: 'Problem definition' },
      { to: '/surrogate_modeling', text: 'Surrogate modelling (notebook)' },
    ],
  },
  {
    id: 'devices',
    label: 'Building & devices',
    Icon: Cpu,
    pages: [
      { to: '/idf_editor', text: 'Model editor' },
      { to: '/sensors_actuators', text: 'Sensors & actuators' },
      { to: '/ems_programs', text: 'EMS programs' },
      { to: '/devices_code', text: 'Gateway' },
    ],
  },
  {
    id: 'weather',
    label: 'Weather',
    Icon: CloudSun,
    pages: [
      { to: '/weather_explore', text: 'Explore weather' },
      { to: '/weather_edit', text: 'Create & edit weather' },
    ],
  },
  {
    id: 'iot',
    label: 'IoT & data',
    Icon: Database,
    pages: [
      { to: '/subscriber_code', text: 'Subscriber' },
      { to: '/data_notebooks', text: 'Data notebooks' },
    ],
  },
  {
    id: 'ai',
    label: 'AI (optional)',
    Icon: Brain,
    pages: [
      { to: '/controller_code', text: 'Controller' },
      { to: '/agent_training', text: 'Agent training' },
      { to: '/forecasting', text: 'Forecasting' },
    ],
  },
  {
    id: 'bms',
    label: 'BMS',
    Icon: Gauge,
    pages: [
      { to: '/control_room', text: 'Control room' },
      { to: '/operator_panel', text: 'Operator panel' },
      { to: '/grafana', text: 'Dashboards' },
    ],
  },
];

const sectionOf = (pathname) =>
  SECTIONS.find((s) => s.to === pathname || s.pages?.some((p) => p.to === pathname));

export function SideMenu({ collapsed, onExpand }) {
  const { pathname } = useLocation();
  const current = sectionOf(pathname);
  const [open, setOpen] = useState(() => new Set(current ? [current.id] : []));

  // Arriving in a section (from a link, the Home page, the back button) opens it.
  useEffect(() => {
    if (current) setOpen((o) => (o.has(current.id) ? o : new Set(o).add(current.id)));
  }, [current]);

  const toggle = (id) => setOpen((o) => {
    const n = new Set(o);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <nav className="sidemenu" aria-label="Main">
      {SECTIONS.map((s) => {
        const isCurrent = current?.id === s.id;
        const cls = `sidemenu__section ${isCurrent ? 'is-current' : ''}`;
        if (!s.pages) {
          return (
            <Link key={s.id} to={s.to} className={cls} title={collapsed ? s.label : undefined}
              aria-current={pathname === s.to ? 'page' : undefined}>
              <s.Icon size={18} aria-hidden="true" />
              {!collapsed && <span className="sidemenu__label">{s.label}</span>}
            </Link>
          );
        }
        const isOpen = !collapsed && open.has(s.id);
        return (
          <div key={s.id} className="sidemenu__group">
            <button type="button" className={cls} aria-expanded={isOpen} title={collapsed ? s.label : undefined}
              onClick={() => (collapsed ? onExpand() : toggle(s.id))}>
              <s.Icon size={18} aria-hidden="true" />
              {!collapsed && (
                <>
                  <span className="sidemenu__label">{s.label}</span>
                  {isOpen ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
                </>
              )}
            </button>
            {isOpen && (
              <ul className="sidemenu__pages">
                {s.pages.map((p) => (
                  <li key={p.to}>
                    <Link to={p.to} className={`sidemenu__page ${pathname === p.to ? 'is-active' : ''}`}
                      aria-current={pathname === p.to ? 'page' : undefined}>
                      {p.text}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );
}
