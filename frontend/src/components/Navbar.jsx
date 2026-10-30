import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useFavorites } from '../context/FavoritesContext';
import { healthApi } from '../services/api';
import QuickSearchModal from './QuickSearchModal';

const NAV_ITEMS = [
  { path: '/', label: 'Home', icon: '🌌' },
  { path: '/explorer', label: 'Explorer', icon: '🪐' },
  { path: '/top-targets', label: 'Top Targets', icon: '🏆' },
  { path: '/compare', label: 'Compare', icon: '⚡' },
  { path: '/analytics', label: 'Analytics', icon: '📊' },
  { path: '/registry', label: 'Model Registry', icon: '🛡️' },
  { path: '/methodology', label: 'Methodology', icon: '🔬' },
];

const Navbar = () => {
  const location = useLocation();
  const { favorites } = useFavorites();
  const [systemStatus, setSystemStatus] = useState({ ok: true, version: 'v1_2026-10-23' });
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [quickSearchOpen, setQuickSearchOpen] = useState(false);

  // Global keyboard shortcut: Ctrl+K or / to open Quick Search
  useEffect(() => {
    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea') return;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setQuickSearchOpen(true);
      } else if (e.key === '/') {
        e.preventDefault();
        setQuickSearchOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    healthApi
      .check()
      .then((res) => {
        if (res) {
          setSystemStatus({
            ok: res.status === 'ok',
            version: res.artifact_version || 'v1_active',
          });
        }
      })
      .catch(() => setSystemStatus({ ok: false, version: 'offline' }));
  }, []);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-space-void/85 border-b border-exosignal-cyan/20 shadow-2xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <Link to="/" className="flex items-center space-x-3 group">
              <div className="relative w-10 h-10 flex items-center justify-center rounded-xl bg-gradient-to-br from-exosignal-cyan/20 to-exosignal-purple/30 border border-exosignal-cyan/40 shadow-neon-cyan transition-transform group-hover:scale-105">
                <svg
                  className="w-6 h-6 text-exosignal-cyan"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="5"
                    fill="currentColor"
                    fillOpacity="0.3"
                    stroke="currentColor"
                  />
                  <ellipse
                    cx="12"
                    cy="12"
                    rx="10"
                    ry="4"
                    stroke="currentColor"
                    strokeDasharray="2 2"
                    transform="rotate(-25 12 12)"
                  />
                </svg>
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
              </div>
              <div className="flex flex-col">
                <div className="flex items-center space-x-2">
                  <span className="font-orbitron text-2xl font-black tracking-wider text-white group-hover:text-exosignal-cyan transition-colors">
                    EXO<span className="planet-font-animated">SIGNAL</span>
                  </span>

                  <span className="text-[10px] font-mono tracking-widest uppercase px-2 py-0.5 rounded-full bg-exosignal-cyan/15 text-exosignal-cyan border border-exosignal-cyan/30">
                    ML RANKER
                  </span>
                </div>
                <span className="text-[11px] font-mono text-exosignal-text-muted hidden xl:inline">
                  Atmospheric Spectroscopy Prioritization
                </span>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden lg:flex items-center space-x-1" aria-label="Main Navigation">
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`relative px-3.5 py-2 rounded-xl text-sm font-semibold transition-all duration-200 flex items-center space-x-1.5 ${
                    isActive
                      ? 'text-white bg-exosignal-cyan/15 border border-exosignal-cyan/40 shadow-neon-cyan'
                      : 'text-exosignal-text-secondary hover:text-white hover:bg-space-card'
                  }`}
                >
                  <span className="text-xs" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Telemetry Chip, Quick Search & Favorites (Desktop) */}
          <div className="hidden lg:flex items-center space-x-3">
            {/* Quick Search Trigger Pill */}
            <button
              onClick={() => setQuickSearchOpen(true)}
              aria-label="Search targets and launch SHAP (Ctrl+K or /)"
              className="glass-pill hover:border-exosignal-cyan/60 text-xs font-mono text-exosignal-text-secondary hover:text-white transition-all flex items-center space-x-1.5 cursor-pointer bg-space-void/60"
              title="Search targets & launch SHAP (Ctrl+K or /)"
            >
              <span className="text-exosignal-cyan" aria-hidden="true">
                🔍
              </span>
              <span>Search Target</span>
              <kbd className="text-[10px] bg-space-card px-1.5 py-0.5 rounded border border-slate-700 text-slate-400 font-mono">
                Ctrl+K
              </kbd>
            </button>

            {/* Live System Telemetry */}
            <div
              className="glass-pill text-xs font-mono text-exosignal-text-secondary"
              aria-label="DuckDB In-Memory telemetry"
            >
              <span className={`pulsing-dot ${systemStatus.ok ? 'emerald' : 'cyan'}`}></span>
              <span>DuckDB In-Memory</span>
              <span className="text-exosignal-cyan/60">•</span>
              <span className="text-exosignal-cyan">&lt; 10ms P50</span>
            </div>

            {/* Favorites Counter Pill */}
            <Link
              to="/favorites"
              aria-label={`Saved Watchlist Targets, ${favorites?.length || 0} targets`}
              className="glass-pill hover:border-exosignal-purple/60 text-xs font-mono text-exosignal-text-secondary transition-colors"
              title="Saved Watchlist Targets"
            >
              <span className="text-amber-400" aria-hidden="true">
                ★
              </span>
              <span>Watchlist</span>
              {favorites && favorites.length > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-300 font-bold text-[11px]">
                  {favorites.length}
                </span>
              )}
            </Link>
          </div>

          {/* Quick Search & Favorites on Tablet/Mobile */}
          <div className="flex lg:hidden items-center space-x-2 mr-2">
            <button
              onClick={() => setQuickSearchOpen(true)}
              aria-label="Quick Search Targets"
              className="glass-pill text-xs font-mono text-exosignal-cyan flex items-center space-x-1"
              title="Quick Search"
            >
              <span aria-hidden="true">🔍</span>
              <span>Search</span>
            </button>
            <Link
              to="/favorites"
              aria-label={`Watchlist with ${favorites?.length || 0} items`}
              className="hidden sm:flex glass-pill text-xs font-mono text-amber-300"
            >
              ★ Watchlist {favorites && favorites.length > 0 && `(${favorites.length})`}
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <div className="lg:hidden flex items-center">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileMenuOpen}
              className="p-2 rounded-lg bg-space-card border border-exosignal-cyan/30 text-exosignal-cyan"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                {mobileMenuOpen ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-exosignal-cyan/20 bg-space-void/95 px-4 pt-3 pb-4 space-y-2">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              onClick={() => setMobileMenuOpen(false)}
              className={`block px-3 py-2 rounded-lg text-sm font-medium ${
                location.pathname === item.path
                  ? 'bg-exosignal-cyan/20 text-exosignal-cyan font-bold'
                  : 'text-exosignal-text hover:bg-space-card'
              }`}
            >
              {item.icon} {item.label}
            </Link>
          ))}
          <Link
            to="/favorites"
            onClick={() => setMobileMenuOpen(false)}
            className="block px-3 py-2 rounded-lg text-sm font-medium text-amber-300 hover:bg-space-card"
          >
            ★ Watchlist ({favorites?.length || 0})
          </Link>
        </div>
      )}

      {/* Quick Search Modal */}
      <QuickSearchModal isOpen={quickSearchOpen} onClose={() => setQuickSearchOpen(false)} />
    </header>
  );
};

export default Navbar;
