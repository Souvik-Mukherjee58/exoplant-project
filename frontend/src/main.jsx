import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import ErrorBoundary, { reloadPage } from './components/ErrorBoundary';
import { FavoritesProvider } from './context/FavoritesContext';
import './index.css';

/** Last resort, outside the router: the page still says what happened and how to recover. */
const AppError = () => (
  <div
    role="alert"
    className="min-h-screen flex flex-col items-center justify-center gap-4 bg-space-void text-exosignal-text font-mono text-sm p-8 text-center"
  >
    <h1 className="text-xl font-bold text-white">ExoSignal could not be displayed</h1>
    <p className="text-exosignal-text-muted">
      Reloading the page usually fixes this, for example after an update.
    </p>
    <button type="button" onClick={reloadPage} className="btn-secondary-glass text-xs">
      Reload page
    </button>
  </div>
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary label="Application" fallback={() => <AppError />}>
    <FavoritesProvider>
      <App />
    </FavoritesProvider>
  </ErrorBoundary>
);
