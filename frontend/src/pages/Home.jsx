import React from 'react'
import { Link } from 'react-router-dom'
import { useTopTargets } from '../hooks/usePlanets'
import { useAnalytics } from '../hooks/useAnalytics'
import { useFavorites } from '../context/FavoritesContext'
import { formatPriority, formatAnomaly, formatDistance, getHZColor } from '../utils/formatters'
import { motion } from 'framer-motion'

const Home = () => {
  const { planets: topPlanets, loading: planetsLoading } = useTopTargets(5)
  const { stats, loading: statsLoading } = useAnalytics()
  const { toggleFavorite, isFavorite } = useFavorites()

  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-space-dark to-space-darker py-16">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl font-extrabold text-exosignal-text mb-4">
            ExoSignal
          </h1>
          <p className="text-xl text-exosignal-blue mb-8">
            Data-Driven Exoplanet Follow-Up Target Prioritization Platform
          </p>
          <p className="text-exosignal-text/80 mb-8 max-w-3xl mx-auto leading-relaxed">
            Telescope observation time is scarce. ExoSignal leverages archive astronomical
            parameters and multi-criteria scoring to identify and rank candidate exoplanet
            systems for spectroscopic characterization and observational follow-up.
          </p>
          <div className="flex justify-center space-x-4">
            <Link
              to="/explorer"
              className="bg-exosignal-accent text-space-dark px-6 py-3 rounded-lg font-semibold hover:bg-exosignal-blue transition"
            >
              Explore Targets
            </Link>
            <Link
              to="/top-targets"
              className="border border-exosignal-blue text-exosignal-blue px-6 py-3 rounded-lg font-semibold hover:bg-exosignal-blue/10 transition"
            >
              View Top Targets
            </Link>
            <Link
              to="/methodology"
              className="border border-exosignal-blue text-exosignal-blue px-6 py-3 rounded-lg font-semibold hover:bg-exosignal-blue/10 transition"
            >
              Learn About the Method
            </Link>
          </div>
        </div>
      </section>

      {/* Important Disclaimer */}
      <section className="bg-space-darker border-y border-exosignal-blue/30 py-6">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-exosignal-text/70 text-sm">
            <strong>Important:</strong> The priority score does not represent the probability of
            extraterrestrial life or intelligence. It is a computational ranking intended to
            identify targets that may warrant further scientific investigation.
          </p>
        </div>
      </section>

      {/* Stats Section */}
      {(statsLoading || !stats) ? (
        <section className="py-12">
          <h2 className="text-2xl font-bold text-exosignal-text mb-6">System Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20 animate-pulse">
              <p className="text-exosignal-text/70 text-sm">Total Planets Analyzed</p>
              <p className="text-3xl font-bold text-exosignal-accent">—</p>
            </div>
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20 animate-pulse">
              <p className="text-exosignal-text/70 text-sm">Priority Score Range</p>
              <p className="text-3xl font-bold text-exosignal-accent">—</p>
            </div>
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20 animate-pulse">
              <p className="text-exosignal-text/70 text-sm">Mean Priority</p>
              <p className="text-3xl font-bold text-exosignal-accent">—</p>
            </div>
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20 animate-pulse">
              <p className="text-exosignal-text/70 text-sm">Anomaly Score Range</p>
              <p className="text-3xl font-bold text-exosignal-accent">—</p>
            </div>
          </div>
        </section>
      ) : (
        <section className="py-12">
          <h2 className="text-2xl font-bold text-exosignal-text mb-6">System Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20">
              <p className="text-exosignal-text/70 text-sm">Total Planets Analyzed</p>
              <p className="text-3xl font-bold text-exosignal-accent">{stats.total_planets}</p>
            </div>
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20">
              <p className="text-exosignal-text/70 text-sm">Priority Score Range</p>
              <p className="text-3xl font-bold text-exosignal-accent">
                {formatPriority(stats.score_distribution?.min)}–{formatPriority(stats.score_distribution?.max)}
              </p>
            </div>
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20">
              <p className="text-exosignal-text/70 text-sm">Mean Priority</p>
              <p className="text-3xl font-bold text-exosignal-accent">
                {formatPriority(stats.score_distribution?.mean)}
              </p>
            </div>
            <div className="bg-space-darker rounded-lg p-6 border border-exosignal-blue/20">
              <p className="text-exosignal-text/70 text-sm">Anomaly Score Range</p>
              <p className="text-3xl font-bold text-exosignal-accent">
                {formatAnomaly(stats.anomaly_distribution?.min)}–{formatAnomaly(stats.anomaly_distribution?.max)}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Top Targets Preview */}
      <section className="py-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-exosignal-text">Top Priority Targets</h2>
          <Link to="/top-targets" className="text-exosignal-blue hover:text-exosignal-accent text-sm">
            View All →
          </Link>
        </div>
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 overflow-hidden">
          {planetsLoading ? (
            <div className="p-6 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-exosignal-accent"></div>
              <p className="mt-2 text-exosignal-text/70">Loading targets...</p>
            </div>
          ) : (
            <table className="min-w-full divide-y divide-exosignal-blue/10">
              <thead className="bg-space-dark">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Rank</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Planet</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Priority</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Anomaly</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">HZ Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Favorite</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-exosignal-blue/10">
                {topPlanets.map((planet, index) => (
                  <motion.tr
                    key={planet.planet_name}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="hover:bg-space-dark/50"
                  >
                    <td className="px-6 py-4 text-exosignal-text/70">#{index + 1}</td>
                    <td className="px-6 py-4 text-exosignal-text font-medium">
                      <Link to={`/planet/${planet.planet_name}`} className="hover:text-exosignal-accent">
                        {planet.planet_name}
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-exosignal-accent font-semibold">
                      {formatPriority(planet.target_priority_score)}
                    </td>
                    <td className="px-6 py-4 text-exosignal-text/70">
                      {formatAnomaly(planet.anomaly_score)}
                    </td>
                    <td className="px-6 py-4 text-exosignal-text/70">
                      <span className={`text-xs px-2 py-1 rounded-full text-white ${getHZColor(planet.hz_status)}`}>
                        {planet.hz_status || 'Insufficient data'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleFavorite(planet)}
                        className={`text-2xl transition hover:scale-110 ${isFavorite(planet.planet_name) ? 'text-yellow-400' : 'text-gray-500 hover:text-yellow-400'}`}
                        title={isFavorite(planet.planet_name) ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        {isFavorite(planet.planet_name) ? '⭐' : '☆'}
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}

export default Home
