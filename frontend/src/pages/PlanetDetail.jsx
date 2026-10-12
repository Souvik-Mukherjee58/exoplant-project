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

  const HZ_COLORS = {
    'Inside HZ': 'bg-emerald-500',
    'Near HZ': 'bg-yellow-500',
    'Outside HZ': 'bg-gray-500',
    'Insufficient data': 'bg-gray-400'
  }

  const PRIORITY_COMPONENT_LABELS = {
    planetary_relevance: 'Planetary Relevance',
    stellar_characteristics: 'Stellar Characteristics',
    observational_accessibility: 'Observational Accessibility',
    data_quality: 'Data Quality',
    anomaly_score: 'Anomaly Score',
    final_score: 'Priority Score',
  }

  const getPriorityComponents = () => {
    if (planet.priority_components) {
      return Object.entries(planet.priority_components)
        .filter(([key]) => key !== 'final_score')
        .map(([key, value]) => ({
          label: PRIORITY_COMPONENT_LABELS[key] || key,
          value: typeof value === 'number' ? value.toFixed(1) : value
        }))
    }
    return []
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
        <p className="text-exosignal-text/80 mb-4">
          {planet.explanation ||
            "This object received a high priority score primarily because of its favorable observational accessibility, planetary characteristics, and relatively unusual position within the analyzed dataset. The target's combination of properties makes it a compelling candidate for follow-up observation."}
        </p>
        <p className="text-exosignal-text/60 text-sm">
          <strong>Note:</strong> This analysis is based on measurable astronomical and observational
          properties only. The system does not claim to detect extraterrestrial intelligence or
          calculate the probability of life.
        </p>
      </section>

      {/* Recommendations for Follow-up */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mt-8">
        <h2 className="text-2xl font-bold text-exosignal-text mb-6">Suggested Observations</h2>
        <ul className="space-y-3 text-exosignal-text/80">
          <li className="flex items-start">
            <div className="w-3 h-3 bg-exosignal-accent rounded-s flex-shrink-0 mt-0.5" />
            <div className="ml-3 flex-1">
              <p className="font-medium">Transit Spectroscopy</p>
              <p className="text-xs text-exosignal-text/70">
                Characterize the planet's atmosphere during transit if within the habitable zone.
              </p>
            </div>
          </li>
          <li className="flex items-start">
            <div className="w-3 h-3 bg-exosignal-accent rounded-s flex-shrink-0 mt-0.5" />
            <div className="ml-3 flex-1">
              <p className="font-medium">Radial Velocity</p>
              <p className="text-xs text-exosignal-text/70">
                Refine planetary mass measurements and test system dynamics.
              </p>
            </div>
          </li>
          <li className="flex items-start">
            <div className="w-3 h-3 bg-exosignal-accent rounded-s flex-shrink-0 mt-0.5" />
            <div className="ml-3 flex-1">
              <p className="font-medium">Direct Imaging</p>
              <p className="text-xs text-exosignal-text/70">
                Search for atmospheric signatures if the planet is sufficiently distant from its star.
              </p>
            </div>
          </li>
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