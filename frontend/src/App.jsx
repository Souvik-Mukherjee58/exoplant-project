import React, { Suspense } from 'react';
import { BrowserRouter as Router, Link, Routes, Route, useLocation } from 'react-router-dom';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ErrorBoundary, { reloadPage } from './components/ErrorBoundary';
import Home from './pages/Home';
import { isChunkLoadError, lazyWithRetry } from './utils/lazyWithRetry';
import './App.css';

// The landing page loads with the app; every other page is its own chunk, fetched on first visit.
const Explorer = lazyWithRetry(() => import('./pages/Explorer'));
const TopTargets = lazyWithRetry(() => import('./pages/TopTargets'));
const PlanetDetail = lazyWithRetry(() => import('./pages/PlanetDetail'));
const Compare = lazyWithRetry(() => import('./pages/Compare'));
const Analytics = lazyWithRetry(() => import('./pages/Analytics'));
const Methodology = lazyWithRetry(() => import('./pages/Methodology'));
const About = lazyWithRetry(() => import('./pages/About'));
const Favorites = lazyWithRetry(() => import('./pages/Favorites'));
const ModelRegistry = lazyWithRetry(() => import('./pages/ModelRegistry'));
const LAZY_PAGES = [
  Explorer,
  TopTargets,
  PlanetDetail,
  Compare,
  Analytics,
  Methodology,
  About,
  Favorites,
  ModelRegistry,
];
const retryFailedPages = () => LAZY_PAGES.forEach((page) => page.retry());

const PageLoading = () => (
  <p
    role="status"
    className="glass-panel p-8 text-center font-mono text-sm text-exosignal-text-muted"
  >
    Loading page…
  </p>
);

/** Shown instead of a blank screen when a page cannot be downloaded or fails to render. */
export const PageError = ({ error, retry }) => (
  <div role="alert" className="glass-panel p-8 text-center font-mono text-sm space-y-4">
    <h1 className="text-xl font-bold text-white">This page could not be loaded</h1>
    <p className="text-exosignal-text-muted">
      {isChunkLoadError(error)
        ? 'Part of the application could not be downloaded. Check your connection; if ExoSignal was just updated, reloading the page loads the new version.'
        : 'An unexpected error occurred while showing this page.'}
    </p>
    <div className="flex flex-wrap justify-center gap-3">
      <button type="button" onClick={retry} className="btn-secondary-glass text-xs">
        Try again
      </button>
      <button type="button" onClick={reloadPage} className="btn-secondary-glass text-xs">
        Reload page
      </button>
      <Link to="/" className="btn-secondary-glass text-xs inline-block">
        Back to home
      </Link>
    </div>
  </div>
);

/** The routes, inside an error boundary that is cleared when the address changes. */
const RoutedPages = () => {
  const { pathname } = useLocation();
  return (
    <ErrorBoundary
      label={`Page ${pathname}`}
      resetKey={pathname}
      onRetry={retryFailedPages}
      fallback={(props) => <PageError {...props} />}
    >
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/top-targets" element={<TopTargets />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/planet/:planetName" element={<PlanetDetail />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/registry" element={<ModelRegistry />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
};

const NotFound = () => (
  <div className="glass-panel p-8 text-center font-mono text-sm">
    <h1 className="text-xl font-bold text-white mb-3">Page not found</h1>
    <Link to="/" className="btn-secondary-glass text-xs inline-block">
      Back to home
    </Link>
  </div>
);

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col text-exosignal-text">
        {/* Modern Glowing Navigation Bar */}
        <Navbar />

        {/* Main Content Area */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <RoutedPages />
        </main>

        {/* Modern Scientific Footer */}
        <Footer />
      </div>
    </Router>
  );
}

export default App;
