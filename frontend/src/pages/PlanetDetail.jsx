import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { usePlanetDetail } from '../hooks/usePlanets'
import {
  formatRadius, formatMass, formatPeriod, formatTemperature,
  formatDistance, formatPriority, formatAnomaly, getHZColor, getHZText,
  formatDiscoveryMethod, formatStellarName
} from '../utils/formatters'

const PlanetDetail = () => {
  const { planetName } = useParams()
  const { planet, loading, error } = usePlanetDetail(planetName)

  if (loading) {
    return (
      <div className="min-h-screen bg-space-dark flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-exosignal-accent"></div>
          <p className="mt-4 text-exosignal-text">Loading planet details...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-space-darker rounded-lg p-6 text-center">
        <p className="text-exosignal-red">{error}</p>
        <Link to="/top-targets" className="text-exosignal-blue mt-4 hover:text-exosignal-accent">
          Back to Targets
        </Link>
      </div>
    )
  }

  if (!planet) {
    return <div>Planet not found</div>
  }

  const PRIORITY_COMPONENT_LABELS = {
    planetary_relevance: 'Planetary Relevance',
    stellar_characteristics: 'Stellar Characteristics',
    observational_accessibility: 'Observational Accessibility',
    data_quality: 'Data Quality',
    anomaly_score: 'Anomaly Score',
    final_score: 'Priority Score',
  }

  // Generate dynamic explanation based on actual score breakdown
  const getDynamicExplanation = () => {
    if (planet.explanation) return planet.explanation
    if (!planet.priority_components) return 'Detailed breakdown unavailable for this target.'

    const components = Object.entries(planet.priority_components)
      .filter(([k]) => k !== 'final_score')
      .sort((a, b) => b[1] - a[1])

    const top = components[0] ? `${PRIORITY_COMPONENT_LABELS[top[0]] || top[0]} (${top[1]?.toFixed(1)}/100)` : ''
    const second = components[1] ? `${PRIORITY_COMPONENT_LABELS[second[1]] || second[0]} (${second[1]?.toFixed(1)}/100)` : ''

    const hzDesc = planet.hz_status === 'Inside HZ' 
      ? 'It is situated squarely within the habitable zone of its host star.' 
      : planet.hz_status === 'Near HZ' 
      ? 'It orbits near the empirical habitable zone boundary.'
      : 'It orbits outside the circumstellar habitable zone.'

    return `This target achieves an overall priority score of ${formatPriority(planet.target_priority_score)}/100, driven primarily by strong ${top}${second ? ` followed by ${second}` : ''}. ${hzDesc} Its estimated distance is ${formatDistance(planet.distance)}.`
  }

  // Generate tailored observational follow-up strategies
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

  return (
    <div className="min-h-screen bg-space-dark text-exosignal-text">
      {/* Back button */}
      <div className="mx-6 my-6">
        <Link to="/top-targets" className="text-exosignal-blue hover:text-exosignal-accent text-sm">
          ← Back to Top Targets
        </Link>
      </div>

      {/* Planet Overview */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8">
        <h2 className="text-2xl font-bold text-exosignal-text mb-6">Planet Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <h3 className="text-lg font-medium text-exosignal-blue mb-4">Planet Details</h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-exosignal-text/70 text-sm">Planet Name</dt>
                <dd className="font-mono text-exosignal-accent">{planet.planet_name}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Radius</dt>
                <dd>{formatRadius(planet.planet_radius)}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Mass</dt>
                <dd>{formatMass(planet.planet_mass)}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Orbital Period</dt>
                <dd>{formatPeriod(planet.orbital_period)}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Equilibrium Temperature</dt>
                <dd>{formatTemperature(planet.equilibrium_temperature)}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Discovery Method</dt>
                <dd>{formatDiscoveryMethod(planet.discovery_method)}</dd>
              </div>
            </dl>
          </div>

          <div>
            <h3 className="text-lg font-medium text-exosignal-blue mb-4">Host Star</h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-exosignal-text/70 text-sm">Star Name</dt>
                <dd className="font-mono">{formatStellarName(planet.stellar_name)}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Effective Temperature</dt>
                <dd>{planet.stellar_effective_temperature ? formatTemperature(planet.stellar_effective_temperature) : '—'}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Stellar Radius</dt>
                <dd>{formatNumber(planet.stellar_radius, 2)} R☉</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Stellar Mass</dt>
                <dd>{formatNumber(planet.stellar_mass, 2)} M☉</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Metallicity</dt>
                <dd>{formatNumber(planet.stellar_metallicity, 3)}</dd>
              </div>
              <div>
                <dt className="text-exosignal-text/70 text-sm">Distance</dt>
                <dd>{formatDistance(planet.distance)}</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      {/* Scientific Assessment */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8">
        <h2 className="text-2xl font-bold text-exosignal-text mb-6">Scientific Assessment</h2>

        <div className="grid grid-cols-2 gap-6">
          {/* HZ Relevance */}
          <div>
            <h4 className="text-lg font-medium text-exosignal-blue mb-4">Habitable Zone Status</h4>
            <p className="text-exosignal-text/70 text-sm">
              {getHZText(planet.hz_status)}
            </p>
            <div className="mt-4">
              <span className={`inline-block px-2 py-1 rounded-full text-white text-xs
                ${getHZColor(planet.hz_status)}`}>
                {getHZText(planet.hz_status)}
              </span>
            </div>
          </div>

          {/* Earth Similarity */}
          <div>
            <h4 className="text-lg font-medium text-exosignal-blue mb-4">Earth Similarity</h4>
            <p className="text-exosignal-text/70 text-sm">
              {formatNumber(planet.earth_similarity, 3)}
            </p>
          </div>

          {/* Observation Accessibility */}
          <div>
            <h4 className="text-lg font-medium text-exosignal-blue mb-4">Observation Accessibility</h4>
            <p className="text-exosignal-text/70 text-sm">
              {formatNumber(planet.observational_accessibility, 3)}
            </p>
          </div>

          {/* Data Quality */}
          <div>
            <h4 className="text-lg font-medium text-exosignal-blue mb-4">Data Quality</h4>
            <p className="text-exosignal-text/70 text-sm">
              {formatNumber(planet.data_quality, 3)}
            </p>
          </div>
        </div>

        {/* Anomaly Score */}
        <div className="mt-8 p-6 bg-space-dark rounded-lg border border-exosignal-blue/20">
          <h4 className="text-lg font-medium text-exosignal-blue mb-4">Anomaly Score</h4>
          <p className="text-4xl font-bold text-exosignal-accent">
            {formatAnomaly(planet.anomaly_score)}
          </p>
          <p className="text-exosignal-text/70 mt-1">
            {planet.anomaly_score_description || 'Lower scores are typical; higher scores indicate unusual combinations of properties.'}
          </p>
        </div>

        {/* Priority Score */}
        <div className="mt-8 p-6 bg-space-dark rounded-lg border border-exosignal-blue/20">
          <h4 className="text-lg font-medium text-exosignal-blue mb-4">Target Priority Score</h4>
          <p className="text-5xl font-extrabold text-exosignal-accent">
            {formatPriority(planet.target_priority_score)}/100
          </p>
          <p className="text-exosignal-text/70 mt-2">
            Based on planetary relevance, stellar characteristics, observational
            accessibility, data quality, and anomaly score.
          </p>

          {/* Component Breakdown */}
          {planet.priority_components && (
            <div className="mt-6">
              <h5 className="text-sm font-medium text-exosignal-text/70 mb-3">Component Breakdown</h5>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(planet.priority_components)
                  .filter(([key]) => key !== 'final_score')
                  .map(([key, value]) => (
                    <div key={key} className="bg-space-darker rounded-lg p-3 border border-exosignal-blue/10">
                      <p className="text-xs text-exosignal-text/70 mb-1">
                        {PRIORITY_COMPONENT_LABELS[key] || key}
                      </p>
                      <p className="text-xl font-bold text-exosignal-accent">
                        {typeof value === 'number' ? value.toFixed(1) : value}
                      </p>
                    </div>
                  ))}
                <div className="bg-space-darker rounded-lg p-3 border border-exosignal-blue/10 md:col-span-2">
                  <p className="text-xs text-exosignal-text/70 mb-1">Final Priority Score</p>
                  <p className="text-xl font-bold text-exosignal-accent">
                    {planet.priority_components.final_score?.toFixed(1) || formatPriority(planet.target_priority_score)}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Explanation Section */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8">
        <h2 className="text-2xl font-bold text-exosignal-text mb-6">Why This Target?</h2>
        <p className="text-exosignal-text/90 mb-4 leading-relaxed">
          {getDynamicExplanation()}
        </p>
        <p className="text-exosignal-text/60 text-sm">
          <strong>Note:</strong> Target prioritization is evaluated from measurable astrophysical parameters,
          spectroscopic accessibility, and stellar properties to optimize telescope resource allocation.
        </p>
      </section>

      {/* Recommendations for Follow-up */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mt-8">
        <h2 className="text-2xl font-bold text-exosignal-text mb-6">Suggested Follow-Up Observations</h2>
        <ul className="space-y-4 text-exosignal-text/80">
          {getSuggestedObservations().map((obs, idx) => (
            <li key={idx} className="flex items-start">
              <div className="w-3 h-3 bg-exosignal-accent rounded-sm flex-shrink-0 mt-1" />
              <div className="ml-3 flex-1">
                <p className="font-semibold text-exosignal-text">{obs.title}</p>
                <p className="text-sm text-exosignal-text/70 mt-0.5">{obs.desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export default PlanetDetail

// Helper function for formatting numbers (inline since it's simple)
function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) {
    return '—'
  }
  return value.toFixed(decimals)
}