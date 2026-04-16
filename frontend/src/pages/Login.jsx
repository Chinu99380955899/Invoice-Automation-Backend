import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Navigate, useLocation } from 'react-router-dom';

import { login } from '../store/slices/authSlice.js';

export default function Login() {
  const dispatch = useDispatch();
  const { state } = useLocation();
  const { user, status } = useSelector((s) => s.auth);
  const [email, setEmail] = useState('admin@invoice.local');
  const [password, setPassword] = useState('Admin@12345');

  useEffect(() => {
    document.title = 'Sign in — Invoice Automation';
  }, []);

  if (user) {
    return <Navigate to={state?.from?.pathname || '/dashboard'} replace />;
  }

  const submit = (e) => {
    e.preventDefault();
    dispatch(login({ email, password }));
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <h1>Invoice Automation</h1>
        <p>Sign in to process invoices and manage approvals.</p>
        <div className="form-control">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
        </div>
        <div className="form-control">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        <button
          type="submit"
          className="btn btn--primary"
          style={{ width: '100%', marginTop: 8 }}
          disabled={status === 'loading'}
        >
          {status === 'loading' ? 'Signing in…' : 'Sign in'}
        </button>
        <p style={{ marginTop: 24, fontSize: 12 }} className="muted">
          Default dev login seeded at startup: admin@invoice.local / Admin@12345
        </p>
      </form>
    </div>
  );
}
