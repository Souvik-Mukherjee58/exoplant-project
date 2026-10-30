import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { planetsApi } from '../services/api';
import TreeSHAPWaterfall from './TreeSHAPWaterfall';
import { formatPriority, getIneligibleTooltip } from '../utils/formatters';

const SUGGESTED_QUERIES = ['kepler 452 b', 'TRAPPIST-1 e', 'TOI-700 d', 'K2-18 b', 'WASP-96 b'];

export const QuickSearchModal = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeShapPlanet, setActiveShapPlanet] = useState(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      setActiveShapPlanet(null);
    }
  }, [isOpen]);

  // Reset selected index whenever results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [results]);

  // Live search debounce
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await planetsApi.getAll({ q: query.trim(), limit: 8 });
        if (active) {
          const items = res?.items || res || [];
          setResults(items);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          setResults([]);
          setLoading(false);
        }
      }
    }, 200);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  // Keyboard navigation: Escape, ArrowDown, ArrowUp, Enter
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;

      if (e.key === 'Escape') {
        if (activeShapPlanet) {
          setActiveShapPlanet(null);
        } else {
          onClose();
        }
      } else if (e.key === 'ArrowDown') {
        if (results.length > 0 && !activeShapPlanet) {
          e.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % results.length);
        }
      } else if (e.key === 'ArrowUp') {
        if (results.length > 0 && !activeShapPlanet) {
          e.preventDefault();
          setSelectedIndex((prev) => (prev - 1 + results.length) % results.length);
        }
      } else if (e.key === 'Enter') {
        if (results.length > 0 && results[selectedIndex] && !activeShapPlanet) {
          e.preventDefault();
          const planet = results[selectedIndex];
          onClose();
          navigate(`/planet/${encodeURIComponent(planet.planet_name)}`);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, activeShapPlanet, onClose, results, selectedIndex, navigate]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      {/* Modal Container */}
      <div className="relative w-full max-w-2xl bg-space-card/95 border border-exosignal-cyan/40 rounded-2xl shadow-[0_0_50px_rgba(6,182,212,0.25)] overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header / Search Input */}
        <div className="p-4 border-b border-exosignal-cyan/20 flex items-center space-x-3 bg-space-void/90">
          <span className="text-exosignal-cyan text-lg" aria-hidden="true">
            🔍
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search exoplanet (e.g. kepler 452 b, TOI-700 d, TRAPPIST)..."
            aria-label="Search exoplanets"
            className="w-full bg-transparent text-white text-sm font-mono placeholder-slate-400 focus:outline-none"
          />
          {loading && (
            <div
              className="w-4 h-4 border-2 border-exosignal-cyan border-t-transparent rounded-full animate-spin"
              aria-label="Loading results"
            ></div>
          )}
          <button
            onClick={onClose}
            aria-label="Close search modal"
            className="text-xs font-mono px-2 py-1 rounded bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-colors"
          >
            ESC
          </button>
        </div>

        {/* Suggested Quick Chips */}
        <div className="px-4 py-2.5 bg-space-void/50 border-b border-exosignal-cyan/10 flex items-center space-x-2 overflow-x-auto text-xs font-mono">
          <span className="text-exosignal-text-muted shrink-0">Try:</span>
          {SUGGESTED_QUERIES.map((sq) => (
            <button
              key={sq}
              onClick={() => setQuery(sq)}
              aria-label={`Search for ${sq}`}
              className="px-2 py-0.5 rounded-full bg-exosignal-cyan/10 border border-exosignal-cyan/30 text-exosignal-cyan hover:bg-exosignal-cyan/20 transition-colors shrink-0"
            >
              {sq}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="p-4 overflow-y-auto flex-1 space-y-3">
          {/* Active SHAP Inspector View if selected */}
          {activeShapPlanet ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between bg-purple-950/40 border border-purple-500/40 p-3 rounded-xl">
                <div>
                  <span className="text-xs font-mono text-purple-300 uppercase tracking-wider">
                    Target SHAP Waterfall:
                  </span>
                  <h3 className="text-base font-orbitron font-bold text-white">
                    {activeShapPlanet}
                  </h3>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => {
                      onClose();
                      navigate(`/explorer?q=${encodeURIComponent(activeShapPlanet)}`);
                    }}
                    className="px-2.5 py-1 text-xs font-mono bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/40 rounded-lg hover:bg-exosignal-cyan/30"
                  >
                    🪐 View in Catalog
                  </button>
                  <button
                    onClick={() => setActiveShapPlanet(null)}
                    className="px-2.5 py-1 text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700 rounded-lg hover:text-white"
                  >
                    &larr; Back to Results
                  </button>
                </div>
              </div>

              <TreeSHAPWaterfall planetName={activeShapPlanet} />
            </div>
          ) : (
            <>
              {results.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-[11px] font-mono text-exosignal-text-muted uppercase">
                    Matching Targets ({results.length}) — Use ↑↓ to navigate, Enter to select
                  </div>
                  {results.map((planet, idx) => {
                    const isSelected = idx === selectedIndex;
                    return (
                      <div
                        key={planet.planet_name}
                        onClick={() => setSelectedIndex(idx)}
                        className={`flex items-center justify-between p-3 rounded-xl transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-space-void border-2 border-exosignal-cyan shadow-neon-cyan ring-1 ring-exosignal-cyan'
                            : 'bg-space-void/80 border border-exosignal-cyan/20 hover:border-exosignal-cyan/50 hover:bg-space-void'
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-orbitron font-bold text-sm text-white">
                              {planet.planet_name}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-mono border ${
                                planet.hz_status === 'Inside HZ'
                                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                                  : 'bg-slate-800 text-slate-400 border-slate-700'
                              }`}
                            >
                              {planet.hz_status || 'Unknown'}
                            </span>
                          </div>
                          <div className="text-xs font-mono text-exosignal-text-muted flex items-center space-x-3">
                            {(planet.priority_rank ?? planet.ml_rank) && (
                              <span>
                                Rank:{' '}
                                <strong className="text-exosignal-cyan">
                                  #{planet.priority_rank ?? planet.ml_rank}
                                </strong>
                              </span>
                            )}
                            <span>
                              Score:{' '}
                              {planet.priority_score != null ? (
                                <strong className="text-amber-300">
                                  {Number(planet.priority_score).toFixed(1)}
                                </strong>
                              ) : (
                                <span
                                  className="text-slate-400 cursor-help"
                                  title={getIneligibleTooltip(planet)}
                                >
                                  -
                                </span>
                              )}
                            </span>
                            {(planet.planet_radius ?? planet.radius_re) && (
                              <span>
                                R:{' '}
                                <strong>
                                  {Number(planet.planet_radius ?? planet.radius_re).toFixed(2)} R⊕
                                </strong>
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center space-x-2">
                          <button
                            type="button"
                            aria-label={`View TreeSHAP for ${planet.planet_name}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveShapPlanet(planet.planet_name);
                            }}
                            className="px-3 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 text-xs font-mono flex items-center space-x-1.5 transition-colors shadow-[0_0_10px_rgba(168,85,247,0.2)]"
                          >
                            <span>🌲</span>
                            <span>TreeSHAP</span>
                          </button>
                          <button
                            type="button"
                            aria-label={`Open dossier for ${planet.planet_name}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              onClose();
                              navigate(`/planet/${encodeURIComponent(planet.planet_name)}`);
                            }}
                            className="px-3 py-1.5 rounded-lg bg-exosignal-cyan/15 hover:bg-exosignal-cyan/25 text-exosignal-cyan border border-exosignal-cyan/30 text-xs font-mono transition-colors"
                          >
                            Dossier
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : query.trim() && !loading ? (
                <div className="py-8 text-center space-y-2">
                  <p className="text-sm font-mono text-exosignal-text-muted">
                    No target found matching "{query}"
                  </p>
                  <p className="text-xs text-slate-400">
                    Try searching by official catalog identifier, e.g. "Kepler-452 b", "kepler 452
                    b", "TRAPPIST-1 e"
                  </p>
                </div>
              ) : (
                <div className="py-6 text-center space-y-2 text-exosignal-text-muted">
                  <p className="text-xs font-mono">
                    Type an exoplanet name to search the archive and inspect its exact TreeSHAP
                    attribution waterfall.
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer info */}
        <div className="px-4 py-2 border-t border-exosignal-cyan/15 bg-space-void/90 flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span>Navigate with ↑↓ • Enter to select • ESC to exit</span>
          <span>Target Search &amp; TreeSHAP Inspector</span>
        </div>
      </div>
    </div>
  );
};

export default QuickSearchModal;
