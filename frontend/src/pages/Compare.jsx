import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { usePlanets } from '../hooks/usePlanets'
import { formatRadius, formatMass, formatPeriod, formatTemperature, formatPriority, formatAnomaly, getHZColor } from '../utils/formatters'

const Compare = () => {
  const planetsParams = useMemo(() => ({ limit: 500 }), [])
  const { planets: availablePlanets, loading, error } = usePlanets(planetsParams)
  const [selectedPlanets, setSelectedPlanets] = useState([])

  const togglePlanetSelection = (planet) => {
    if (selectedPlanets.find(p => p.planet_name === planet.planet_name)) {
      setSelectedPlanets(selectedPlanets.filter(p => p.planet_name !== planet.planet_name))
    } else {
      if (selectedPlanets.length < 4) {
        setSelectedPlanets([...selectedPlanets, planet])
      }
    }
  }

  const comparisonData = useMemo(() => {
    if (selectedPlanets.length === 0) return []

    return selectedPlanets.map(planet => ({
      name: planet.planet_name,
      radius: planet.planet_radius ? formatRadius(planet.planet_radius) : '—',
      mass: planet.planet_mass ? formatMass(planet.planet_mass) : '—',
      period: planet.orbital_period ? formatPeriod(planet.orbital_period) : '—',
      temp: planet.equilibrium_temperature ? formatTemperature(planet.equilibrium_temperature) : '—',
      priority: planet.target_priority_score ? formatPriority(planet.target_priority_score) : '—',
      anomaly: planet.anomaly_score ? formatAnomaly(planet.anomaly_score) : '—',
      hz_status: planet.hz_status || 'Insufficient data',
      distance: planet.distance ? planet.distance.toFixed(1) + ' pc' : '—',
      stellar_name: planet.stellar_name || 'Unknown',
      discovery_method: planet.discovery_method || '—',
      earth_similarity: planet.earth_similarity ? planet.earth_similarity.toFixed(3) : '—',
      data_quality: planet.data_quality ? planet.data_quality.toFixed(3) : '—',
    }))
  }, [selectedPlanets])

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-4">Compare Exoplanets</h1>
      <p className="text-exosignal-text/70 mb-6">
        Select up to 4 exoplanets to compare their properties, characteristics, and priority scores.
      </p>

      {loading && (
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-exosignal-accent"></div>
          <p className="mt-2 text-exosignal-text/70">Loading planet data...</p>
        </div>
      )}

      {error && (
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 text-center text-exosignal-red">
          <p>Failed to load planet data: {error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Planet Selector */}
        <div className="lg:col-span-1">
          <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-4">
            <h3 className="text-lg font-semibold text-exosignal-text mb-4">Select Planets</h3>
            <div className="space-y-2">
              {availablePlanets.map((planet) => (
                <label
                  key={planet.planet_name}
                  className={`block p-3 rounded-lg border transition cursor-pointer
                    ${selectedPlanets.find(p => p.planet_name === planet.planet_name)
                      ? 'bg-exosignal-blue/30 border-exosignal-accent'
                      : 'bg-space-dark border-exosignal-blue/20 hover:border-exosignal-blue/50'}`}
                >
                  <input
                    type="checkbox"
                    checked={!!selectedPlanets.find(p => p.planet_name === planet.planet_name)}
                    onChange={() => togglePlanetSelection(planet)}
                    disabled={selectedPlanets.length >= 4 && !selectedPlanets.find(p => p.planet_name === planet.planet_name)}
                    className="mr-3 accent-exosignal-accent"
                  />
                  <span className="font-medium text-exosignal-text">{planet.planet_name}</span>
                  <div className="text-xs text-exosignal-text/70 mt-1 flex items-center gap-2">
                    <span>Priority: {planet.target_priority_score?.toFixed(1)}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${getHZColor(planet.hz_status)}`}>
                      {planet.hz_status || 'N/A'}
                    </span>
                  </div>
                </label>
              ))}
            </div>

            {selectedPlanets.length === 0 && (
              <p className="text-exosignal-text/70 text-sm mt-4">
                Select at least one planet to compare
              </p>
            )}

            {selectedPlanets.length > 0 && (
              <div className="mt-4 p-3 bg-space-dark rounded-lg border border-exosignal-blue/20">
                <p className="text-sm font-medium text-exosignal-text/70 mb-2">Selected:</p>
                <ul className="space-y-1">
                  {selectedPlanets.map((planet, index) => (
                    <li key={planet.planet_name} className="text-sm text-exosignal-text flex justify-between">
                      <span>#{index + 1} {planet.planet_name}</span>
                      <button
                        onClick={() => togglePlanetSelection(planet)}
                        className="text-exosignal-red hover:text-red-400 text-xs"
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* Comparison Table */}
        <div className="lg:col-span-3">
          <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 overflow-hidden">
            {comparisonData.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-exosignal-blue/10">
                  <thead className="bg-space-dark">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Property</th>
                      {comparisonData.map((planet) => (
                        <th key={planet.name} className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">
                          <Link to={`/planet/${planet.name}`} className="hover:text-exosignal-accent">
                            {planet.name}
                          </Link>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-exosignal-blue/10">
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Host Star</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.stellar_name}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Radius</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.radius}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Mass</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.mass}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Orbital Period</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.period}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Equilibrium Temp</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.temp}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Distance</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.distance}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Discovery Method</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.discovery_method}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">HZ Status</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4">
                          <span className={`text-xs px-2 py-1 rounded-full text-white ${getHZColor(planet.hz_status)}`}>
                            {planet.hz_status}
                          </span>
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Earth Similarity</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.earth_similarity}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Data Quality</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.data_quality}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Anomaly Score</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.anomaly}
                        </td>
                      ))}
                    </tr>
                    <tr className="bg-space-dark/50">
                      <td className="px-6 py-4 text-exosignal-text font-semibold">Priority Score</td>
                      {comparisonData.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-accent font-bold">
                          {planet.priority}/100
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-12 text-center text-exosignal-text/70">
                <div className="w-12 h-12 mx-auto mb-4 text-exosignal-text/50">
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                  </svg>
                </div>
                <p className="text-lg">Select planets to compare</p>
                <p className="text-sm mt-2">Choose up to 4 exoplanets for side-by-side comparison</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Compare