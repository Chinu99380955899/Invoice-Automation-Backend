import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="auth-page">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <h1>404 — Page not found</h1>
        <p>The page you were looking for doesn&apos;t exist.</p>
        <Link to="/" className="btn btn--primary">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
