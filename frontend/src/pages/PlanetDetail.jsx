import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { usePlanetDetail } from '../hooks/usePlanets'
import {
  formatRadius, formatMass, formatPeriod, formatTemperature,
  formatDistance, formatPriority, formatAnomaly, getHZColor, getHZText,
  formatDiscoveryMethod, formatStellarName
} from '../utils/formatters'
import TreeSHAPWaterfall from '../components/TreeSHAPWaterfall'
import SectionDivider from '../components/SectionDivider'
import SegmentedTabs from '../components/SegmentedTabs'
import Planet3DVisualizer from '../components/Planet3DVisualizer'


const PlanetDetail = () => {
  const { planetName } = useParams()
  const { planet, loading, error } = usePlanetDetail(planetName)
  const [activeTab, setActiveTab] = useState('overview')

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-4 font-mono">
        <div className="w-12 h-12 rounded-full border-4 border-exosignal-cyan/20 border-t-exosignal-cyan animate-spin"></div>
        <p className="text-xs text-exosignal-text-muted">Loading astrophysical parameters & TreeSHAP attributions...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-panel p-8 text-center text-rose-400 font-mono text-xs space-y-3">
        <p>Target retrieval error: {error}</p>
        <Link to="/explorer" className="btn-secondary-glass text-xs inline-block">
          ← Back to Explorer
        </Link>
      </div>
    )
  }

  if (!planet) {
    return (
      <div className="glass-panel p-8 text-center text-exosignal-text-muted font-mono text-xs">
        Planet target not found in active catalog.
      </div>
    )
  }

  const getDynamicExplanation = () => {
    if (planet.explanation) return planet.explanation
    if (!planet.priority_components) return 'Detailed breakdown unavailable for this target.'

    const hzDesc = planet.hz_status === 'Inside HZ' 
      ? 'It is situated squarely within the habitable zone of its host star.' 
      : planet.hz_status === 'Near HZ' 
      ? 'It orbits near the empirical habitable zone boundary.'
      : 'It orbits outside the circumstellar habitable zone.'

    const pScore = planet.priority_score ?? planet.ml_priority_score ?? planet.target_priority_score
    return `${planet.planet_name} achieves an overall priority score of ${formatPriority(pScore)}/100 under the multi-criteria ranking model. ${hzDesc} Its estimated distance is ${formatDistance(planet.distance)} with an equilibrium temperature of ~${Math.round(planet.equilibrium_temperature || 0)} K.`
  }

  const getSuggestedObservations = () => {
    const list = []
    const isTransiting = (planet.discovery_method || '').toLowerCase().includes('transit')
    const sma = planet.semi_major_axis
    const teq = planet.equilibrium_temperature

    if (isTransiting) {
      list.push({
        title: 'Transmission Spectroscopy (JWST NIRSpec / HST WFC3)',
        desc: `Because ${planet.planet_name} transits its host star, transit transmission spectroscopy can detect atmospheric chemical signatures during primary transit.`
      })
    }

    if (teq && teq > 600) {
      list.push({
        title: 'Secondary Eclipse / Thermal Emission',
        desc: `With an equilibrium temperature of ~${Math.round(teq)} K, secondary eclipse measurements can probe dayside thermal emission and atmospheric albedo.`
      })
    }

    list.push({
      title: 'High-Precision Radial Velocity (ESPRESSO / HARPS-N)',
      desc: 'High-resolution Doppler spectroscopy to refine dynamical planetary mass, constrain orbital eccentricity, and verify multi-planet architecture.'
    })

    if (sma && sma > 1.5) {
      list.push({
        title: 'High-Contrast Direct Imaging (Roman CGI / ELT)',
        desc: `With a semi-major axis of ${sma.toFixed(2)} AU, this planet has sufficient angular separation for coronagraphic direct imaging follow-up.`
      })
    }

    return list
  }

  const currentRank = planet.priority_rank ?? planet.ml_rank
  const currentScore = planet.priority_score ?? planet.ml_priority_score ?? planet.target_priority_score
  const heurScore = planet.heuristic_habitability_score ?? planet.target_priority_score

  const detailTabs = [
    { id: 'overview', label: 'Planetary Specs', icon: '🪐' },
    { id: 'explainability', label: 'TreeSHAP Attribution', icon: '🌲', badge: currentRank ? `#${currentRank}` : undefined },
    { id: 'protocols', label: 'Observation Protocols', icon: '🔭', badge: getSuggestedObservations().length },
    { id: 'all', label: 'Full Target Dossier', icon: '📑' }
  ]

  const showAll = activeTab === 'all'

  const getPresetForPlanet = () => {
    const name = (planet.planet_name || '').toLowerCase()
    if (name.includes('trappist')) return 'trappist1e'
    if (name.includes('toi-700') || name.includes('toi 700')) return 'toi700d'
    if (name.includes('k2-18') || name.includes('k2 18')) return 'k218b'
    if (name.includes('lhs-1140') || name.includes('lhs 1140')) return 'lhs1140b'
    if (name.includes('wasp') || (planet.planet_radius && planet.planet_radius > 6)) return 'wasp96b'
    if (planet.hz_status === 'Inside HZ') return 'trappist1e'
    if (planet.planet_radius && planet.planet_radius > 2.0) return 'k218b'
    return 'lhs1140b'
  }

  return (
    <div className="space-y-8">
      {/* Target Hero Header with 3D Planetary Animation */}
      <div className="divided-compartment">
        <div className="p-8 bg-gradient-to-br from-space-card to-exosignal-cyan/5">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Left specs & Title */}
            <div className="lg:col-span-8">
              <div className="flex items-center space-x-3 mb-2">
                <span className={`px-2.5 py-1 rounded-full text-xs font-mono font-bold ${
                  planet.hz_status === 'Inside HZ'
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : planet.hz_status === 'Near HZ'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                    : 'bg-slate-700/40 text-slate-300 border border-slate-600/40'
                }`}>
                  {planet.hz_status || 'Outside HZ'}
                </span>
                <span className="text-xs font-mono text-exosignal-text-muted">
                  Discovery: {planet.discovery_method || 'Transit'}
                </span>
              </div>

              {/* Planetary Animated Title */}
              <h1 className="text-3xl sm:text-5xl font-black font-orbitron planet-font-animated tracking-wider">
                {planet.planet_name}
              </h1>
              <p className="text-xs font-mono text-exosignal-cyan mt-1">
                Host Star: {planet.hostname || planet.stellar_name || planet.planet_name?.replace(/\s+[a-z]$/i, '') || '—'} • Distance: {formatDistance(planet.distance)}
              </p>

              {/* Quick Metrics Badge */}
              <div className="flex flex-wrap items-center gap-4 bg-space-void/90 p-4 rounded-2xl border border-exosignal-cyan/25 mt-5">
                <div>
                  <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">Priority Score</span>
                  <div className="text-3xl font-black font-mono text-exosignal-cyan">
                    {formatPriority(currentScore)}
                  </div>
                </div>
                {currentRank ? (
                  <div className="border-l border-exosignal-cyan/20 pl-4">
                    <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">Priority Rank</span>
                    <div className="text-2xl font-bold font-mono text-white">
                      #{currentRank}{' '}
                      {planet.rank_delta !== undefined && (
                        <span className={`text-xs ${planet.rank_delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          ({planet.rank_delta >= 0 ? `▲ +${planet.rank_delta}` : `▼ ${planet.rank_delta}`})
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="border-l border-exosignal-cyan/20 pl-4">
                    <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">Eligibility</span>
                    <div className="text-sm font-bold font-mono text-amber-400">
                      Unranked ({planet.exclusion_reason || 'Ineligible'})
                    </div>
                  </div>
                )}
                {heurScore !== undefined && (
                  <div className="border-l border-exosignal-cyan/20 pl-4">
                    <span className="text-[10px] font-mono text-exosignal-text-muted block uppercase">Habitability (Heuristic)</span>
                    <div className="text-xl font-bold font-mono text-emerald-400">
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
                  type: planet.hz_status === 'Inside HZ' ? 'Temperate Candidate' : planet.planet_radius > 6 ? 'Gas Giant' : planet.planet_radius > 1.8 ? 'Sub-Neptune' : 'Terrestrial',
                  radius: planet.planet_radius ? `${planet.planet_radius.toFixed(2)} R⊕` : '1.0 R⊕',
                  teq: planet.equilibrium_temperature ? `${Math.round(planet.equilibrium_temperature)} K` : '280 K',
                  period: planet.orbital_period ? `${planet.orbital_period.toFixed(1)} days` : '10 days',
                  transitDepth: '0.2%',
                  atmosphereColor: planet.hz_status === 'Inside HZ' ? 'rgba(16, 185, 129, 0.45)' : (planet.equilibrium_temperature > 800 ? 'rgba(245, 158, 11, 0.55)' : 'rgba(56, 189, 248, 0.45)'),
                  baseColor: planet.hz_status === 'Inside HZ' ? '#083344' : (planet.equilibrium_temperature > 800 ? '#7c2d12' : (planet.planet_radius > 2.0 ? '#1e1b4b' : '#312e81')),
                  landColor: planet.hz_status === 'Inside HZ' ? '#1d5a3a' : (planet.equilibrium_temperature > 800 ? '#b45309' : '#451a03'),
                  cloudColor: 'rgba(255, 255, 255, 0.65)',
                  rings: Boolean(planet.planet_radius && planet.planet_radius > 8),
                  banding: Boolean(planet.planet_radius && planet.planet_radius > 2.0),
                  glowHex: planet.hz_status === 'Inside HZ' ? '#10b981' : (planet.equilibrium_temperature > 800 ? '#f97316' : '#00d4ff')
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
        <SegmentedTabs
          tabs={detailTabs}
          activeTab={activeTab}
          onChange={setActiveTab}
        />
      </div>

      {/* SECTION 1: Physical Parameters & Narrative */}
      {(showAll || activeTab === 'overview') && (
        <div className="space-y-6">
          <SectionDivider
            number="01"
            title="Astrophysical Telemetry & Host Environment"
            subtitle="Derived planetary bulk density proxies, orbital mechanics, and stellar irradiance"
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
                <span className="text-[10px] font-mono text-exosignal-text-muted">EXOPLANET ARCHIVE</span>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Radius</span>
                    <span className="text-white font-bold text-sm">{formatRadius(planet.planet_radius)}</span>
                  </div>
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Estimated Mass</span>
                    <span className="text-white font-bold text-sm">{formatMass(planet.planet_mass)}</span>
                  </div>
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Orbital Period</span>
                    <span className="text-white font-bold text-sm">{formatPeriod(planet.orbital_period)}</span>
                  </div>
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-exosignal-cyan/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Equilibrium Temp</span>
                    <span className="text-white font-bold text-sm">{formatTemperature(planet.equilibrium_temperature)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Stellar Specs Compartment */}
            <div className="divided-compartment">
              <div className="compartment-header">
                <div className="flex items-center space-x-2">
                  <span className="text-base">⭐</span>
                  <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider text-exosignal-purple">
                    Host Star & Observation Geometry
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-exosignal-text-muted">STELLAR PROVENANCE</span>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Stellar Radius</span>
                    <span className="text-white font-bold text-sm">
                      {planet.stellar_radius ? `${planet.stellar_radius.toFixed(2)} R☉` : '—'}
                    </span>
                  </div>
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Stellar Temp</span>
                    <span className="text-white font-bold text-sm">
                      {planet.stellar_teff ? `${Math.round(planet.stellar_teff)} K` : '—'}
                    </span>
                  </div>
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Distance</span>
                    <span className="text-white font-bold text-sm">{formatDistance(planet.distance)}</span>
                  </div>
                  <div className="bg-space-void/80 p-3.5 rounded-xl border border-purple-500/15">
                    <span className="text-exosignal-text-muted block text-[10px]">Anomaly Score</span>
                    <span className="text-amber-400 font-bold text-sm">{formatAnomaly(planet.anomaly_score)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Dynamic Scientific Narrative Compartment */}
          <div className="divided-compartment">
            <div className="compartment-header">
              <h3 className="text-base font-bold text-white font-display">
                Atmospheric Prioritization Summary
              </h3>
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

      {/* SECTION 2: TreeSHAP Interpretability Waterfall */}
      {(showAll || activeTab === 'explainability') && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="TreeSHAP Feature Attribution"
            subtitle="Local Shapley feature importance waterfall explaining exactly why the model prioritized this target"
            badge="ML EXPLAINABILITY"
            accent="purple"
          />

          <div className="divided-compartment">
            <div className="p-6">
              <TreeSHAPWaterfall
                planetName={planet.planet_name}
                targetPriorityScore={planet.target_priority_score}
                mlPriorityScore={planet.ml_priority_score}
                mlRank={planet.ml_rank}
                rankDelta={planet.rank_delta}
              />
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Suggested Follow-up Strategies */}
      {(showAll || activeTab === 'protocols') && (
        <div className="space-y-4">
          <SectionDivider
            number="03"
            title="Recommended Observational Protocols"
            subtitle="Spectroscopy, transit timing, and high-contrast imaging follow-up strategies tailored to target characteristics"
            badge="MISSION STRATEGY"
            accent="emerald"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <h3 className="text-base font-bold text-white font-display">
                Instrument & Campaign Recommendations
              </h3>
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                {getSuggestedObservations().length} TARGET PROTOCOLS
              </span>
            </div>
            <div className="p-6">
              <div className="space-y-3">
                {getSuggestedObservations().map((obs, idx) => (
                  <div key={idx} className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/15 flex items-start space-x-3 hover:border-exosignal-cyan/40 transition-colors">
                    <span className="text-exosignal-cyan text-base mt-0.5">🔭</span>
                    <div>
                      <h4 className="font-bold text-white text-sm">{obs.title}</h4>
                      <p className="text-xs text-exosignal-text-muted mt-1 leading-relaxed">{obs.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PlanetDetail