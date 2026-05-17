import React from 'react';

/**
 * Global ErrorBoundary — prevents a single broken component from crashing
 * the entire SPA with a "Uncaught runtime errors" red overlay.
 *
 * Strategy:
 *  - Catches React render errors via componentDidCatch.
 *  - Shows a compact, themed fallback inside the affected subtree.
 *  - Allows the user to retry (re-mount the children) without a hard reload.
 *  - Logs the error to console for debugging.
 *
 * Use:
 *   <ErrorBoundary scope="alpha-page">
 *     <PriceExpectationV2Page />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
    this._handleReset = this._handleReset.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    const scope = this.props.scope || 'global';
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary:${scope}]`, error, errorInfo);
    this.setState({ errorInfo });
    // best-effort telemetry (no PII)
    try {
      const url = (typeof window !== 'undefined' && window.location && window.location.pathname) || '';
      const payload = {
        scope,
        url,
        message: String(error && error.message || error),
        stack: String(error && error.stack || '').slice(0, 4000),
      };
      const api = process.env.REACT_APP_BACKEND_URL || '';
      if (api && typeof fetch !== 'undefined') {
        fetch(`${api}/api/ui/telemetry/error`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(() => {});
      }
    } catch (_e) { /* swallow */ }
  }

  _handleReset() {
    this.setState({ hasError: false, error: null, errorInfo: null });
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const compact = !!this.props.compact;
    const scope = this.props.scope || 'block';
    const message = (this.state.error && this.state.error.message) || 'Unexpected error';

    return (
      <div
        data-testid={`error-boundary-${scope}`}
        role="alert"
        style={{
          padding: compact ? '12px 14px' : '20px 22px',
          margin: compact ? '8px 0' : '16px 0',
          background: 'rgba(220, 38, 38, 0.04)',
          border: '1px solid rgba(220, 38, 38, 0.18)',
          borderRadius: 10,
          color: '#7f1d1d',
          fontSize: compact ? 12 : 13,
          lineHeight: 1.55,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div style={{ fontWeight: 600, color: '#991b1b' }}>
            {compact ? 'Module error' : 'This block failed to render'}
          </div>
          <button
            type="button"
            onClick={this._handleReset}
            data-testid={`error-boundary-retry-${scope}`}
            style={{
              fontSize: 12,
              padding: '4px 10px',
              borderRadius: 6,
              border: '1px solid rgba(220, 38, 38, 0.35)',
              background: 'rgba(220, 38, 38, 0.08)',
              color: '#991b1b',
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
        {!compact && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#7f1d1d', opacity: 0.85, wordBreak: 'break-word' }}>
            {message}
          </div>
        )}
      </div>
    );
  }
}

export default ErrorBoundary;
