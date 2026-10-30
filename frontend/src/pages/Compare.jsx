import React, { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { usePlanets } from '../hooks/usePlanets';
import {
  formatRadius,
  formatMass,
  formatPeriod,
  formatTemperature,
  formatPriority,
  formatAnomaly,
  getHZColor,
  getCleanHostStar,
} from '../utils/formatters';
import DifferentialSHAPComparison from '../components/DifferentialSHAPComparison';
import SectionDivider from '../components/SectionDivider';
import { PriorityScoreDisplay } from '../components/PriorityBadge';

const Compare = () => {
  const [searchParams] = useSearchParams();
  const planetsParams = useMemo(() => ({ limit: 500 }), []);
  const { planets: availablePlanets, loading, error } = usePlanets(planetsParams);
  const [selectedPlanets, setSelectedPlanets] = useState([]);
  const [selectorSearch, setSelectorSearch] = useState('');

  // Handle URL query parameters (e.g. /compare?planet_a=TOI-700%20d&planet_b=TRAPPIST-1%20e)
  useEffect(() => {
    if (availablePlanets && availablePlanets.length > 0 && selectedPlanets.length === 0) {
      const urlA = searchParams.get('planet_a');
      const urlB = searchParams.get('planet_b');
      const initial = [];

      if (urlA) {
        const foundA = availablePlanets.find(
          (p) => p.planet_name.toLowerCase() === urlA.toLowerCase()
        );
        if (foundA) initial.push(foundA);
      }
      if (urlB) {
        const foundB = availablePlanets.find(
          (p) => p.planet_name.toLowerCase() === urlB.toLowerCase()
        );
        if (foundB) initial.push(foundB);
      }

      if (initial.length > 0) {
        setSelectedPlanets(initial);
      } else {
        // Default to TOI-700 d and TRAPPIST-1 e if available
        const defaultA =
          availablePlanets.find((p) => p.planet_name === 'TOI-700 d') || availablePlanets[0];
        const defaultB =
          availablePlanets.find((p) => p.planet_name === 'TRAPPIST-1 e') || availablePlanets[1];
        if (defaultA && defaultB) {
          setSelectedPlanets([defaultA, defaultB]);
        }
      }
    }
  }, [availablePlanets, searchParams]);

  const togglePlanetSelection = (planet) => {
    if (selectedPlanets.find((p) => p.planet_name === planet.planet_name)) {
      setSelectedPlanets(selectedPlanets.filter((p) => p.planet_name !== planet.planet_name));
    } else {
      if (selectedPlanets.length < 4) {
        setSelectedPlanets([...selectedPlanets, planet]);
      }
    }
  };

  const filteredCatalogForSelection = useMemo(() => {
    if (!selectorSearch.trim()) return availablePlanets.slice(0, 30);
    return availablePlanets
      .filter((p) => p.planet_name.toLowerCase().includes(selectorSearch.toLowerCase()))
      .slice(0, 30);
  }, [availablePlanets, selectorSearch]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-exosignal-cyan/20 pb-6">
        <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
          Differential Analysis Engine
        </div>
        <h1 className="text-3xl font-black text-white font-display">
          Multi-Target Comparative Analysis
        </h1>
        <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
          Side-by-side physical parameter comparison and exact pairwise TreeSHAP differential
          feature attributions ($\Delta \phi_i$) explaining ranking reversals.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Planet Selection Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <div className="glass-panel p-5 border-exosignal-cyan/20">
            <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider mb-3">
              Target Selector (Max 4)
            </h3>

            {/* Search filter in selector */}
            <input
              type="text"
              value={selectorSearch}
              onChange={(e) => setSelectorSearch(e.target.value)}
              placeholder="Filter catalog..."
              className="w-full mb-3 bg-space-void border border-exosignal-cyan/30 rounded-xl px-3 py-1.5 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-exosignal-cyan"
            />

            {/* List */}
            <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
              {filteredCatalogForSelection.map((planet) => {
                const isSelected = selectedPlanets.some(
                  (p) => p.planet_name === planet.planet_name
                );
                return (
                  <button
                    key={planet.planet_name}
                    type="button"
                    onClick={() => togglePlanetSelection(planet)}
                    className={`w-full text-left p-2.5 rounded-xl border text-xs font-mono transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-exosignal-cyan/20 border-exosignal-cyan/50 text-white shadow-neon-cyan'
                        : 'bg-space-void/60 border-exosignal-cyan/10 text-exosignal-text-secondary hover:border-exosignal-cyan/30'
                    }`}
                  >
                    <span className="font-semibold truncate">{planet.planet_name}</span>
                    <span className="text-[10px] text-exosignal-cyan">
                      <PriorityScoreDisplay planet={planet} />
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Selected Pills */}
            {selectedPlanets.length > 0 && (
              <div className="mt-4 pt-3 border-t border-exosignal-cyan/15 space-y-2">
                <span className="text-[11px] font-mono text-exosignal-text-muted uppercase">
                  Selected Targets:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {selectedPlanets.map((planet) => (
                    <span
                      key={planet.planet_name}
                      className="px-2 py-1 rounded-lg bg-exosignal-cyan/15 border border-exosignal-cyan/30 text-white text-xs font-mono flex items-center space-x-1"
                    >
                      <span>{planet.planet_name}</span>
                      <button
                        onClick={() => togglePlanetSelection(planet)}
                        className="text-rose-400 hover:text-rose-300 ml-1 font-bold"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Comparison Displays */}
        <div className="lg:col-span-3 space-y-6">
          {selectedPlanets.length > 0 ? (
            <>
              {/* Section 01: Holographic Cards Grid */}
              <div className="space-y-4">
                <SectionDivider
                  number="01"
                  title="Target Physical Parameters & Radiative Environment"
                  subtitle="Side-by-side comparison of bulk radii, orbital period, equilibrium temperature, and ML priority"
                  badge={`${selectedPlanets.length} TARGETS`}
                  accent="cyan"
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                  {selectedPlanets.map((planet, idx) => (
                    <div
                      key={planet.planet_name}
                      className="divided-compartment p-5 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-space-void border border-exosignal-cyan/30 text-exosignal-cyan">
                            Target #{idx + 1}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
                              planet.hz_status === 'Inside HZ'
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-slate-700/40 text-slate-300'
                            }`}
                          >
                            {planet.hz_status || 'Outside HZ'}
                          </span>
                        </div>

                        <Link
                          to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                          className="block font-display text-xl font-bold text-white hover:text-exosignal-cyan transition-colors truncate"
                        >
                          {planet.planet_name}
                        </Link>

                        <div className="text-[11px] font-mono text-exosignal-text-muted mb-3 truncate">
                          Host: {getCleanHostStar(planet)}
                        </div>

                        <div className="space-y-1.5 text-xs font-mono bg-space-void/60 p-2.5 rounded-xl border border-exosignal-cyan/15 mb-3">
                          <div className="flex justify-between">
                            <span className="text-exosignal-text-muted">Radius:</span>
                            <span className="text-white font-bold">
                              {formatRadius(planet.planet_radius)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-exosignal-text-muted">Mass:</span>
                            <span className="text-white font-bold">
                              {formatMass(planet.planet_mass)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-exosignal-text-muted">Period:</span>
                            <span className="text-white font-bold">
                              {formatPeriod(planet.orbital_period)}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-exosignal-text-muted">Distance:</span>
                            <span className="text-white font-bold">
                              {planet.distance ? `${planet.distance.toFixed(1)} pc` : '—'}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="pt-2 border-t border-exosignal-cyan/15">
                        <div className="flex justify-between text-xs font-mono mb-1">
                          <span className="text-exosignal-text-muted">
                            Priority Score{' '}
                            {planet.priority_rank ? `(#${planet.priority_rank})` : ''}
                          </span>
                          <PriorityScoreDisplay
                            planet={planet}
                            className="text-exosignal-cyan font-bold"
                          />
                        </div>
                        <div className="w-full bg-space-void rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-exosignal-cyan to-exosignal-purple h-full rounded-full"
                            style={{
                              width: `${planet.priority_score != null ? Math.min(Math.max(planet.priority_score, 5), 100) : 0}%`,
                            }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Section 02: Exact Differential TreeSHAP Breakdown */}
              {selectedPlanets.length >= 2 && (
                <div className="space-y-4 pt-2">
                  <SectionDivider
                    number="02"
                    title="TreeSHAP Differential Feature Impact (Δφ)"
                    subtitle={`Pairwise feature attribution difference explaining why ${selectedPlanets[0].planet_name} scored differently than ${selectedPlanets[1].planet_name}`}
                    badge="DIFFERENTIAL SHAP"
                    accent="purple"
                  />

                  <div className="divided-compartment p-5">
                    <DifferentialSHAPComparison
                      planetA={selectedPlanets[0].planet_name}
                      planetB={selectedPlanets[1].planet_name}
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="glass-panel p-16 text-center text-exosignal-text-muted space-y-3">
              <span className="text-4xl">🔭</span>
              <h3 className="text-lg font-bold text-white font-display">
                No Exoplanet Targets Selected
              </h3>
              <p className="text-xs font-mono max-w-md mx-auto">
                Select targets from the catalog sidebar to compare physical characteristics and view
                exact TreeSHAP attributions.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Compare;
