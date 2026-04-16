import { NavLink } from 'react-router-dom';

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '◧' },
  { to: '/invoices', label: 'Invoices', icon: '▤' },
  { to: '/review', label: 'Review Queue', icon: '◉' },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__brand-logo">IA</div>
        <span>Invoice AI</span>
      </div>
      <nav className="sidebar__nav">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `sidebar__link${isActive ? ' active' : ''}`
            }
          >
            <span style={{ width: 18 }}>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar__spacer" />
      <div className="sidebar__footer">
        <div>v1.0.0</div>
        <div>© {new Date().getFullYear()} Invoice AI</div>
      </div>
    </aside>
  );
}
