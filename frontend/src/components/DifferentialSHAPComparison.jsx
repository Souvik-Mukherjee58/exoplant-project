import React, { useState, useEffect } from 'react'
import { explainabilityApi } from '../services/api'

export const DifferentialSHAPComparison = ({ planetA, planetB }) => {
  const [diffExplanation, setDiffExplanation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    let isMounted = true
    const fetchDiff = async () => {
      if (!planetA || !planetB) return
      try {
        setLoading(true)
        setError(null)
        const data = await explainabilityApi.getComparisonExplanation(planetA, planetB)
        if (isMounted) {
          setDiffExplanation(data)
          setLoading(false)
        }
      } catch (err) {
        if (isMounted) {
          setError(err?.response?.data?.detail || 'Failed to compute differential attribution')
          setLoading(false)
        }
      }
    }

    fetchDiff()

    return () => {
      isMounted = false
    }
  }, [planetA, planetB])

  if (loading) {
    return (
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 text-center">
        <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-exosignal-accent"></div>
        <p className="mt-2 text-exosignal-text/70 text-xs">
          Computing pairwise differential TreeSHAP attribution: Δφ = φ({planetA}) - φ({planetB})...
        </p>
      </div>
    )
  }

  if (error || !diffExplanation) {
    return (
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-4 text-center text-exosignal-text/60 text-xs">
        <p>Differential attribution unavailable: {error}</p>
      </div>
    )
  }

  const {
    planet_a,
    planet_b,
    planet_a_score,
    planet_b_score,
    score_advantage,
    primary_drivers_for_advantage,
    primary_drivers_for_disadvantage,
    differential_waterfall
  } = diffExplanation

  const displayedItems = showAll
    ? differential_waterfall
    : [...primary_drivers_for_advantage, ...primary_drivers_for_disadvantage].sort((a, b) => b.abs_diff - a.abs_diff)

  const favoredPlanet = score_advantage >= 0 ? planet_a : planet_b
  const absAdvantage = Math.abs(score_advantage)

  return (
    <div className="bg-space-darker rounded-lg border border-exosignal-blue/30 p-6 mt-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-exosignal-blue/10 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-exosignal-text">
              Differential Ranking Attribution (Δ TreeSHAP)
            </h3>
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-exosignal-blue/20 text-exosignal-blue">
              Pairwise Delta
            </span>
          </div>
          <p className="text-xs text-exosignal-text/70 mt-1">
            Explains precisely which astrophysical parameter differences drive the ranking separation between {planet_a} and {planet_b}.
          </p>
        </div>

        <div className="text-right">
          <span className="text-xs text-exosignal-text/60 block">ML Score Differential</span>
          <span className="text-lg font-extrabold text-exosignal-accent">
            {favoredPlanet} (+{absAdvantage.toFixed(1)} pts)
          </span>
        </div>
      </div>

      {/* Primary Driver Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-4">
        <div className="bg-space-dark rounded-lg p-3 border border-emerald-500/30">
          <p className="text-xs font-semibold text-emerald-400 mb-2">
            Features Favoring {planet_a}
          </p>
          <ul className="space-y-1.5 text-xs">
            {primary_drivers_for_advantage.slice(0, 3).map((item) => (
              <li key={item.feature} className="flex justify-between items-center text-exosignal-text/80">
                <span>{item.display_name} ({item.planet_a_value} vs {item.planet_b_value})</span>
                <span className="font-mono text-emerald-400 font-bold">+{item.diff_score_impact.toFixed(1)} pts</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-space-dark rounded-lg p-3 border border-rose-500/30">
          <p className="text-xs font-semibold text-rose-400 mb-2">
            Features Favoring {planet_b}
          </p>
          <ul className="space-y-1.5 text-xs">
            {primary_drivers_for_disadvantage.slice(0, 3).map((item) => (
              <li key={item.feature} className="flex justify-between items-center text-exosignal-text/80">
                <span>{item.display_name} ({item.planet_b_value} vs {item.planet_a_value})</span>
                <span className="font-mono text-rose-400 font-bold">{item.diff_score_impact.toFixed(1)} pts</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Toggle View */}
      <div className="flex justify-between items-center mt-4 mb-2">
        <span className="text-xs font-semibold text-exosignal-text/70">
          {showAll ? 'All 21 Feature Differential Shifts' : 'Top Discrepant Feature Shifts'}
        </span>
        <button
          onClick={() => setShowAll(!showAll)}
          className="text-xs text-exosignal-blue hover:text-exosignal-accent underline"
        >
          {showAll ? 'Show Top Shifts' : 'Show All 21 Features'}
        </button>
      </div>

      {/* Differential Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-exosignal-blue/20 text-exosignal-text/60">
              <th className="py-2 pr-3">Astrophysical Feature</th>
              <th className="py-2 px-3">{planet_a}</th>
              <th className="py-2 px-3">{planet_b}</th>
              <th className="py-2 px-3 text-right">Advantage</th>
              <th className="py-2 pl-3 text-right">Net Impact</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-exosignal-blue/10">
            {displayedItems.map((item) => {
              const favorsA = item.advantage === 'Planet A'
              return (
                <tr key={item.feature} className="hover:bg-space-dark/60 transition">
                  <td className="py-2 pr-3 font-medium text-exosignal-text">{item.display_name}</td>
                  <td className="py-2 px-3 font-mono text-exosignal-text/80">{item.planet_a_value}</td>
                  <td className="py-2 px-3 font-mono text-exosignal-text/80">{item.planet_b_value}</td>
                  <td className="py-2 px-3 text-right">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${favorsA ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                      {favorsA ? planet_a : planet_b}
                    </span>
                  </td>
                  <td className={`py-2 pl-3 text-right font-mono font-bold ${favorsA ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {favorsA ? `+${item.diff_score_impact.toFixed(1)}` : `${item.diff_score_impact.toFixed(1)}`} pts
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default DifferentialSHAPComparison
