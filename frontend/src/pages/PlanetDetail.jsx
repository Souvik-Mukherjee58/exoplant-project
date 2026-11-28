import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import HzBadge from '../components/HzBadge';
import { usePlanetDetail } from '../hooks/usePlanets';
import {
  formatRadius,
  formatMass,
  formatPeriod,
  formatTemperature,
  formatDistance,
  formatPriority,
  formatRawScore,
  formatAnomaly,
  getCleanHostStar,
  getIneligibleTooltip,
} from '../utils/formatters';
import ShapWaterfall from '../components/ShapWaterfall';
import SectionDivider from '../components/SectionDivider';
import SegmentedTabs from '../components/SegmentedTabs';
import Planet3DVisualizer from '../components/Planet3DVisualizer';

/**
 * Mass label from the provenance recorded by the backend. Never claims "Measured" without evidence:
 * most archive masses of transiting planets come from a mass-radius relation, not a measurement.
 */
export const massLabel = (planet) => {
  switch (planet?.mass_source) {
    case 'measured':
      return 'Measured Mass';
    case 'archive_mr_relation':
      return 'Estimated Mass (archive mass-radius relation)';
    case 'chen_kipping_2017':
      return 'Estimated Mass (Chen & Kipping 2017)';
    default:
      if (planet?.mass_is_estimated === true) return 'Estimated Mass (mass-radius relation)';
      if (planet?.mass_is_estimated === false) return 'Measured Mass';
      return 'Mass (provenance not recorded)';
  }
};

const PlanetDetail = () => {
  const { planetName } = useParams();
  const { planet, loading, error } = usePlanetDetail(planetName);
  const [activeTab, setActiveTab] = useState('overview');

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-4 font-mono">
        <div className="w-12 h-12 rounded-full border-4 border-exosignal-cyan/20 border-t-exosignal-cyan animate-spin"></div>
        <p className="text-xs text-exosignal-text-muted">
          Loading astrophysical parameters & Linear SHAP attributions...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-panel p-8 text-center text-rose-400 font-mono text-xs space-y-3">
        <p>Target retrieval error: {error}</p>
        <Link to="/explorer" className="btn-secondary-glass text-xs inline-block">
          ← Back to Explorer
        </Link>
      </div>
    );
  }

  if (!planet) {
    return (
      <div className="glass-panel p-8 text-center text-exosignal-text-muted font-mono text-xs">
        Planet target not found in active catalog.
      </div>
    );
  }

  const getDynamicExplanation = () => {
    if (planet.explanation) return planet.explanation;
    if (!planet.priority_components) return 'Detailed breakdown unavailable for this target.';

    const hzDesc =
      planet.hz_status === 'Inside HZ'
        ? 'Its orbit lies inside the model habitable zone of its host star (an orbital distance range; it says nothing about surface conditions).'
        : planet.hz_status === 'Near HZ'
          ? 'It orbits near the model habitable zone boundary.'
          : planet.hz_status === 'Outside HZ'
            ? 'It orbits outside the model habitable zone.'
            : 'Its habitable zone position is unknown (insufficient data).';

    const teqDesc = planet.equilibrium_temperature
      ? `an equilibrium temperature of ~${Math.round(planet.equilibrium_temperature)} K`
      : 'no equilibrium temperature in the archive';

    if (planet.priority_score != null) {
      return `${planet.planet_name} has a ranking score of ${formatPriority(
        planet.priority_score
      )}/100 (not a probability). ${hzDesc} Its estimated distance is ${formatDistance(
        planet.distance
      )} with ${teqDesc}.`;
    }
    return `${planet.planet_name} is currently not eligible for priority ranking (${
      planet.exclusion_reason || 'non-transiting or missing parameter'
    }). ${hzDesc} Its estimated distance is ${formatDistance(planet.distance)} with ${teqDesc}.`;
  };

  const getSuggestedObservations = () => {
    const list = [];
    const isTransiting = planet.is_transiting === true;
    const sma = planet.semi_major_axis;
    const teq = planet.equilibrium_temperature;

    if (isTransiting) {
      list.push({
        title: 'Transmission Spectroscopy (JWST NIRSpec / HST WFC3)',
        desc: `Because ${planet.planet_name} transits its host star, transmission spectroscopy during primary transit is geometrically possible. Detectability depends on the atmosphere, which this catalogue does not model.`,
      });
    }

    if (teq && teq > 600) {
      list.push({
        title: 'Secondary Eclipse / Thermal Emission',
        desc: `With an equilibrium temperature of ~${Math.round(
          teq
        )} K, secondary eclipse measurements can probe dayside thermal emission and atmospheric albedo.`,
      });
    }

    list.push({
      title: 'High-Precision Radial Velocity (ESPRESSO / HARPS-N)',
      desc: 'High-resolution Doppler spectroscopy to refine dynamical planetary mass, constrain orbital eccentricity, and verify multi-planet architecture.',
    });

    if (sma && sma > 1.5 && planet.distance) {
      // Small-angle relation: 1 AU at 1 pc subtends 1 arcsec.
      const separationMas = (sma / planet.distance) * 1000;
      list.push({
        title: 'Direct Imaging (feasibility not assessed)',
        desc: `A semi-major axis of ${sma.toFixed(2)} AU at ${planet.distance.toFixed(
          1
        )} pc corresponds to at most ~${separationMas.toFixed(
          0
        )} mas for a circular orbit. Contrast and instrument limits are not modelled here.`,
      });
    }

    return list;
  };

  const currentRank = planet.priority_rank ?? planet.ml_rank;
  const currentScore = planet.priority_score;
  const heurScore =
    planet.heuristic_habitability_score ??
    planet.habitability_heuristic ??
    planet.target_priority_score;

  const detailTabs = [
    { id: 'overview', label: 'Planetary Specs', icon: '🪐' },
    {
      id: 'explainability',
      label: 'Linear SHAP Attribution',
      icon: '🌲',
      badge: currentRank ? `#${currentRank}` : undefined,
    },
    {
      id: 'protocols',
      label: 'Observation Protocols',
      icon: '🔭',
      badge: getSuggestedObservations().length,
    },
    { id: 'all', label: 'Full Target Dossier', icon: '📑' },
  ];

  const showAll = activeTab === 'all';

  const getPresetForPlanet = () => {
    const name = (planet.planet_name || '').toLowerCase();
    if (name.includes('trappist')) return 'trappist1e';
    if (name.includes('toi-700') || name.includes('toi 700')) return 'toi700d';
    if (name.includes('k2-18') || name.includes('k2 18')) return 'k218b';
    if (name.includes('lhs-1140') || name.includes('lhs 1140')) return 'lhs1140b';
    if (name.includes('wasp') || (planet.planet_radius && planet.planet_radius > 6))
      return 'wasp96b';
    if (planet.hz_status === 'Inside HZ') return 'trappist1e';
    if (planet.planet_radius && planet.planet_radius > 2.0) return 'k218b';
    return 'lhs1140b';
  };

  return (
    <div className="space-y-8">
      {/* Target Hero Header with 3D Planetary Animation */}
      <div className="divided-compartment">
        <div className="p-8 bg-gradient-to-br from-space-card to-exosignal-cyan/5">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Left specs & Title */}
            <div className="lg:col-span-8">
              <div className="flex items-center space-x-3 mb-2">
                <HzBadge status={planet.hz_status} size="lg" className="font-mono" />
                <span className="text-xs font-mono text-exosignal-text-muted">
                  Discovery: {planet.discovery_method || 'not in archive'}
                </span>
              </div>

              {/* Planetary Animated Title */}
              <h1 className="text-3xl sm:text-5xl font-black font-orbitron normal-case planet-font-animated tracking-wider">
                {planet.planet_name}
              </h1>
              <p className="text-xs font-mono text-exosignal-cyan mt-1">
                Host Star: {getCleanHostStar(planet)} • Distance: {formatDistance(planet.distance)}
              </p>

              {/* Quick Metrics Badge */}
              <div className="flex flex-wrap items-center gap-4 bg-space-inset p-4 rounded-2xl border border-exosignal-cyan/25 mt-5">
                <div>
                  <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">
                    Priority Percentile
                  </span>
                  <div
                    className="text-2xl sm:text-3xl font-black font-mono text-exosignal-cyan cursor-help"
                    title={
                      currentScore != null
                        ? `Raw score: ${formatRawScore(currentScore)}`
                        : undefined
                    }
                  >
                    {currentScore != null ? (
                      planet.percentile_rank_string || 'Percentile not available'
                    ) : (
                      <span
                        className="cursor-help text-slate-400"
                        title={getIneligibleTooltip(planet)}
                      >
                        -
                      </span>
                    )}
                  </div>
                  {currentScore != null && (
                    <span
                      className="text-[10px] font-mono text-slate-400 block cursor-help mt-0.5"
                      title={`Raw score: ${formatRawScore(currentScore)}`}
                    >
                      Score: {formatPriority(currentScore)}
                    </span>
                  )}
                </div>
                {currentRank ? (
                  <div className="border-l border-exosignal-cyan/20 pl-4">
                    <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">
                      Priority Rank
                    </span>
                    <div className="text-2xl font-bold font-mono text-white">
                      #{currentRank}{' '}
                      {planet.rank_delta != null && (
                        <span
                          className={`text-xs ${
                            planet.rank_delta >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          (
                          {planet.rank_delta >= 0
                            ? `▲ +${planet.rank_delta}`
                            : `▼ ${planet.rank_delta}`}
                          )
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="border-l border-exosignal-cyan/20 pl-4">
                    <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">
                      Eligibility
                    </span>
                    <div className="text-sm font-bold font-mono text-amber-400">
                      Unranked ({planet.exclusion_reason || 'Ineligible'})
                    </div>
                  </div>
                )}
                {heurScore !== undefined && heurScore !== null && (
                  <div className="border-l border-exosignal-cyan/20 pl-4">
                    <span
                      className="text-[10px] font-mono text-exosignal-text-muted block uppercase"
                      title="Habitability heuristic (not used for ranking)"
                    >
                      Habitability heuristic (not used for ranking)
                    </span>
                    <div
                      className="text-xl font-bold font-mono text-emerald-400 cursor-help"
                      title={`Raw score: ${formatRawScore(heurScore)}`}
                    >
                      {formatPriority(heurScore)}
                    </div>
                  </div>
                )}
                <div className="border-l border-exosignal-cyan/20 pl-4">
                  <Link
                    to={`/compare?planet_a=${encodeURIComponent(planet.planet_name)}`}
                    className="btn-secondary-glass text-xs py-1.5 px-3 block text-center"
                  >
                    Compare
                  </Link>
                </div>
              </div>
            </div>

            {/* Right: Real 3D Rotating Planet Sphere */}
            <div className="lg:col-span-4 flex justify-center">
              <Planet3DVisualizer
                initialPlanet={getPresetForPlanet()}
                customPlanet={{
                  name: planet.planet_name,
                  type:
                    planet.hz_status === 'Inside HZ'
                      ? 'Inside model HZ'
                      : planet.planet_radius > 6
                        ? 'Gas Giant'
                        : planet.planet_radius > 1.8
                          ? 'Sub-Neptune'
                          : planet.planet_radius > 0
                            ? 'Terrestrial size'
                            : 'Size unknown',
                  radius: planet.planet_radius
                    ? `${planet.planet_radius.toFixed(2)} R⊕`
                    : 'not in archive',
                  teq: planet.equilibrium_temperature
                    ? `${Math.round(planet.equilibrium_temperature)} K`
                    : 'not in archive',
                  period: planet.orbital_period
                    ? `${planet.orbital_period.toFixed(1)} days`
                    : 'not in archive',
                  transitDepth:
                    planet.planet_radius && planet.stellar_radius
                      ? `${(
                          (planet.planet_radius / (planet.stellar_radius * 109.1)) ** 2 *
                          100
                        ).toFixed(3)}%`
                      : 'not computable',
                  atmosphereColor:
                    planet.hz_status === 'Inside HZ'
                      ? 'rgba(16, 185, 129, 0.45)'
                      : planet.equilibrium_temperature > 800
                        ? 'rgba(245, 158, 11, 0.55)'
                        : 'rgba(56, 189, 248, 0.45)',
                  baseColor:
                    planet.hz_status === 'Inside HZ'
                      ? '#083344'
                      : planet.equilibrium_temperature > 800
                        ? '#7c2d12'
                        : planet.planet_radius > 2.0
                          ? '#1e1b4b'
                          : '#312e81',
                  landColor:
                    planet.hz_status === 'Inside HZ'
                      ? '#1d5a3a'
                      : planet.equilibrium_temperature > 800
                        ? '#b45309'
                        : '#451a03',
                  cloudColor: 'rgba(255, 255, 255, 0.65)',
                  rings: Boolean(planet.planet_radius && planet.planet_radius > 8),
                  banding: Boolean(planet.planet_radius && planet.planet_radius > 2.0),
                  glowHex:
                    planet.hz_status === 'Inside HZ'
                      ? '#10b981'
                      : planet.equilibrium_temperature > 800
                        ? '#f97316'
                        : '#00d4ff',
                }}
                size={220}
                showControls={false}
                interactive={true}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Tab Division Rail */}
      <div>
        <SegmentedTabs tabs={detailTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* SECTION 1: Physical Parameters & Narrative */}
      {(showAll || activeTab === 'overview') && (
        <div className="space-y-6">
          <SectionDivider
            number="01"
            title="Planet and host star"
            subtitle="Physical parameters from the NASA Exoplanet Archive"
            badge="TELEMETRY"
            accent="cyan"
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Planet Specs Compartment */}
            <div className="divided-compartment">
              <div className="compartment-header">
                <div className="flex items-center space-x-2">
                  <span className="text-base">🪐</span>
                  <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider text-exosignal-cyan">
                    Planetary Physical Parameters
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-exosignal-text-muted">
                  EXOPLANET ARCHIVE
                </span>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-space-inset p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Radius</span>
                    <span className="text-white font-bold text-sm">
                      {planet.planet_radius !== null &&
                      planet.planet_radius !== undefined &&
                      !isNaN(planet.planet_radius) ? (
                        formatRadius(planet.planet_radius)
                      ) : (
                        <span
                          title="Parameter not reported in NASA Exoplanet Archive"
                          className="text-slate-400 italic text-xs cursor-help"
                        >
                          not in archive
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      {massLabel(planet)}
                    </span>
                    <span className="text-white font-bold text-sm">
                      {planet.planet_mass !== null &&
                      planet.planet_mass !== undefined &&
                      !isNaN(planet.planet_mass) ? (
                        formatMass(planet.planet_mass)
                      ) : (
                        <span
                          title="Parameter not reported in NASA Exoplanet Archive"
                          className="text-slate-400 italic text-xs cursor-help"
                        >
                          not in archive
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      Orbital Period
                    </span>
                    <span className="text-white font-bold text-sm">
                      {planet.orbital_period !== null &&
                      planet.orbital_period !== undefined &&
                      !isNaN(planet.orbital_period) ? (
                        formatPeriod(planet.orbital_period)
                      ) : (
                        <span
                          title="Parameter not reported in NASA Exoplanet Archive"
                          className="text-slate-400 italic text-xs cursor-help"
                        >
                          not in archive
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      Equilibrium Temp
                    </span>
                    <span className="text-white font-bold text-sm">
                      {planet.equilibrium_temperature !== null &&
                      planet.equilibrium_temperature !== undefined &&
                      !isNaN(planet.equilibrium_temperature) ? (
                        formatTemperature(planet.equilibrium_temperature)
                      ) : (
                        <span
                          title="Parameter not reported in NASA Exoplanet Archive"
                          className="text-slate-400 italic text-xs cursor-help"
                        >
                          not in archive
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Stellar Specs Compartment */}
            <div className="divided-compartment">
              <div className="compartment-header">
                <div className="flex items-center space-x-2">
                  <span className="text-base">⭐</span>
                  <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider text-exosignal-purple-light">
                    Host Star & Observation Geometry
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-exosignal-text-muted">
                  STELLAR PROVENANCE
                </span>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-space-inset p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      Stellar Radius
                    </span>
                    <span className="text-white font-bold text-sm">
                      {planet.stellar_radius ? (
                        `${planet.stellar_radius.toFixed(2)} R☉`
                      ) : (
                        <span
                          title="Parameter not reported in NASA Exoplanet Archive"
                          className="text-slate-400 italic text-xs cursor-help"
                        >
                          not in archive
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      Stellar Temp
                    </span>
                    <span className="text-white font-bold text-sm">
                      {planet.stellar_effective_temperature ? (
                        `${Math.round(planet.stellar_effective_temperature)} K`
                      ) : (
                        <span
                          title="Parameter not reported in NASA Exoplanet Archive"
                          className="text-slate-400 italic text-xs cursor-help"
                        >
                          not in archive
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Distance</span>
                    <span className="text-white font-bold text-sm">
                      {formatDistance(planet.distance)}
                    </span>
                  </div>
                  <div className="bg-space-inset p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">
                      Anomaly Score
                    </span>
                    <span className="text-amber-400 font-bold text-sm">
                      {formatAnomaly(planet.anomaly_score)}
                    </span>
                    <span className="text-[10px] text-exosignal-text-muted block mt-1">
                      Statistical outlier score (exploratory). Not evidence of life or of anything
                      artificial.
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Dynamic Scientific Narrative Compartment */}
          <div className="divided-compartment">
            <div className="compartment-header">
              <h3 className="text-base font-bold text-white font-display">Ranking Summary</h3>
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-exosignal-cyan/15 text-exosignal-cyan border border-exosignal-cyan/30">
                SCIENTIFIC RATIONALE
              </span>
            </div>
            <div className="p-6">
              <p className="text-sm text-exosignal-text-secondary leading-relaxed font-sans">
                {getDynamicExplanation()}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 2: Linear SHAP Interpretability Waterfall */}
      {(showAll || activeTab === 'explainability') && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="Linear SHAP Feature Attribution"
            subtitle="How each feature moved this planet's score (Lundberg & Lee 2017)"
            badge="ML EXPLAINABILITY"
            accent="purple"
          />

          <div className="divided-compartment">
            <div className="p-6">
              {planet.eligible_for_transmission === false ? (
                <p className="text-sm text-exosignal-text-secondary">
                  No attribution: the model does not rank this planet (
                  {planet.exclusion_reason || 'not eligible'}).
                </p>
              ) : (
                <ShapWaterfall
                  planetName={planet.planet_name}
                  mlRank={planet.priority_rank ?? planet.ml_rank}
                  rankDelta={planet.rank_delta}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Suggested Follow-up Strategies */}
      {(showAll || activeTab === 'protocols') && (
        <div className="space-y-4">
          <SectionDivider
            number="03"
            title="Possible Follow-Up Methods"
            subtitle="Generic method suggestions from catalogue parameters; not an observing plan"
            badge="MISSION STRATEGY"
            accent="emerald"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <h3 className="text-base font-bold text-white font-display">
                Generic Method Suggestions
              </h3>
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                {getSuggestedObservations().length} METHODS
              </span>
            </div>
            <div className="p-6">
              <div className="space-y-3">
                {getSuggestedObservations().map((obs, idx) => (
                  <div
                    key={idx}
                    className="bg-space-inset p-4 rounded-xl border border-exosignal-cyan/15 flex items-start space-x-3 hover:border-exosignal-cyan/40 transition-colors"
                  >
                    <span className="text-exosignal-cyan text-base mt-0.5">🔭</span>
                    <div>
                      <h4 className="font-bold text-white text-sm">{obs.title}</h4>
                      <p className="text-xs text-exosignal-text-muted mt-1 leading-relaxed">
                        {obs.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlanetDetail;
