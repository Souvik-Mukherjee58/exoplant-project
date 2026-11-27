import React from 'react';

/**
 * Catches errors while rendering its children (including a lazy component whose code chunk failed to
 * download) and renders `fallback({ error, retry })` instead of letting React unmount the whole app.
 *
 * - The error is logged to the console with `label` (no request data or user input is logged).
 * - `retry()` clears the error and calls `onRetry` (for example to re-import a failed lazy component).
 * - When `resetKey` changes (for example the route), a shown error is cleared and `onRetry` is called.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.retry = this.retry.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error(`[ExoSignal] ${this.props.label || 'Component'} failed to render:`, error);
  }

  componentDidUpdate(prevProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.retry();
    }
  }

  retry() {
    this.props.onRetry?.();
    this.setState({ error: null });
  }

  render() {
    if (this.state.error) {
      return this.props.fallback({ error: this.state.error, retry: this.retry });
    }
    return this.props.children;
  }
}

export default ErrorBoundary;

/** Reloading fetches the current index.html, which names the chunks of the version now deployed. */
export const reloadPage = () => window.location.reload();
