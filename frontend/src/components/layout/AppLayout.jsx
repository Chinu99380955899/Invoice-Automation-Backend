import { Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import classNames from 'classnames';

import Sidebar from './Sidebar.jsx';
import Topbar from './Topbar.jsx';

export default function AppLayout() {
  const collapsed = useSelector((s) => s.ui.sidebarCollapsed);
  return (
    <div className={classNames('app-shell', { collapsed })}>
      <Sidebar />
      <Topbar />
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
