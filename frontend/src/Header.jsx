import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronsLeft, ChevronsRight, Menu, Scale, X } from 'lucide-react';
import { SideMenu } from './NavBar';
import SessionMenu, { SessionTools } from './SessionMenu';
import FileUploadBar from './FileUploadBar';
import './Header.css';

// The blue sidebar, full height: identity on top, the sections as a menu below.
// It folds to icons to leave room for the notebooks; on phones it is a drawer.
const Header = () => {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebarCollapsed') === '1'; } catch (e) { return false; }
  });
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    try { localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0'); } catch (e) { /* private mode */ }
  }, [collapsed]);

  // On phones the drawer closes once a page is chosen.
  useEffect(() => { setDrawerOpen(false); }, [pathname]);

  // The phone drawer always shows labels.
  const folded = collapsed && !drawerOpen;

  return (
    <>
      <button
        type="button"
        className="sidebar__burger"
        aria-label={drawerOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={drawerOpen}
        onClick={() => setDrawerOpen((o) => !o)}
      >
        {drawerOpen ? <X size={20} /> : <Menu size={20} />}
      </button>
      <aside className={`sidebar ${folded ? 'is-collapsed' : ''} ${drawerOpen ? 'is-open' : ''}`}>
        <div className="sidebar__brand">
          <img src="/polito_logo.png" alt="Politecnico di Torino" className="sidebar__logo" />
          {!folded && <span className="sidebar__title">Intelligent Building Educational Platform</span>}
        </div>
        <div className="sidebar__session">
          <SessionMenu collapsed={folded} onExpand={() => setCollapsed(false)} />
          <FileUploadBar collapsed={folded} onExpand={() => setCollapsed(false)} />
          <SessionTools collapsed={folded} onExpand={() => setCollapsed(false)} />
        </div>
        <SideMenu collapsed={folded} onExpand={() => setCollapsed(false)} />
        <Link to="/credits" className="sidebar__collapse sidebar__credits" title="Credits & licences" aria-label="Credits and licences">
          <Scale size={18} />{!folded && <span>Credits &amp; licences</span>}
        </Link>
        <button
          type="button"
          className="sidebar__collapse"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand the menu' : 'Collapse the menu'}
          title={collapsed ? 'Expand the menu' : 'Collapse the menu'}
        >
          {collapsed ? <ChevronsRight size={18} /> : <><ChevronsLeft size={18} /> <span>Collapse</span></>}
        </button>
      </aside>
    </>
  );
};

export default Header;
