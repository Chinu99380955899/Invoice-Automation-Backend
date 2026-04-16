import { useDispatch, useSelector } from 'react-redux';
import { useLocation } from 'react-router-dom';

import { logout } from '../../store/slices/authSlice.js';

const TITLES = {
  '/dashboard': 'Dashboard',
  '/invoices': 'Invoices',
  '/review': 'Review queue',
};

function initials(name = '') {
  return name
    .split(' ')
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export default function Topbar() {
  const dispatch = useDispatch();
  const user = useSelector((s) => s.auth.user);
  const { pathname } = useLocation();
  const title =
    TITLES[pathname] ||
    (pathname.startsWith('/invoices/') ? 'Invoice detail' : 'Invoice AI');

  return (
    <header className="topbar">
      <div className="topbar__title">{title}</div>
      <div className="topbar__user">
        {user && (
          <>
            <div>
              <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>
                {user.full_name}
              </div>
              <div>
                {user.email} — {user.role}
              </div>
            </div>
            <div className="avatar" title={user.full_name}>
              {initials(user.full_name)}
            </div>
            <button className="btn btn--ghost" onClick={() => dispatch(logout())}>
              Sign out
            </button>
          </>
        )}
      </div>
    </header>
  );
}
