import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Reporting hook — send to Sentry / your backend in production.
    console.error('[ErrorBoundary]', error, info);
  }

  handleReset = () => {
    this.setState({ error: null });
    window.location.assign('/');
  };

  render() {
    if (this.state.error) {
      return (
        <div className="auth-page">
          <div className="auth-card">
            <h1>Something went wrong</h1>
            <p>
              An unexpected error has occurred. The team has been notified.
              You can try reloading the page or returning home.
            </p>
            <details style={{ marginBottom: 16 }}>
              <summary className="muted">Technical details</summary>
              <pre className="mono" style={{ whiteSpace: 'pre-wrap' }}>
                {String(this.state.error?.stack || this.state.error)}
              </pre>
            </details>
            <button className="btn btn--primary" onClick={this.handleReset}>
              Go to home
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
