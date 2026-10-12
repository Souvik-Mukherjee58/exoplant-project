import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTopTargets } from '../hooks/usePlanets'
import { useFavorites } from '../context/FavoritesContext'
import { formatPriority, formatAnomaly, formatDistance, getHZColor } from '../utils/formatters'
import { motion } from 'framer-motion'

const TopTargets = () => {
  const [limit, setLimit] = useState(20)
  const { planets: topTargets, loading, error, refetch } = useTopTargets(limit)
  const { toggleFavorite, isFavorite } = useFavorites()

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-4">Top Priority Targets</h1>
      <p className="text-exosignal-text/70 mb-6">
        These exoplanet systems have the highest priority scores based on planetary
        characteristics, observational accessibility, and scientific interest.
      </p>

      <div className="flex items-center justify-between mb-6">
        <div className="text-exosignal-text/70">
          Show top:
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="ml-2 bg-space-dark border border-exosignal-blue/30 rounded px-2 py-1 text-exosignal-text focus:outline-none focus:border-exosignal-accent"
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>
      </div>

      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 overflow-hidden">
        <table className="min-w-full divide-y divide-exosignal-blue/10">
          <thead className="bg-space-dark">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Rank</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Planet</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Host Star</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Distance</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Priority</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Anomaly</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">HZ Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Favorite</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-exosignal-blue/10">
            {loading ? (
              <tr>
                <td colSpan="7" className="px-6 py-8 text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-exosignal-accent"></div>
                  <p className="mt-2 text-exosignal-text/70">Loading targets...</p>
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan="7" className="px-6 py-8 text-center text-exosignal-red">
                  <p>{error}</p>
                  <button
                    onClick={() => refetch()}
                    className="mt-4 bg-exosignal-blue text-white px-4 py-2 rounded hover:bg-exosignal-accent transition"
                  >
                    Retry
                  </button>
                </td>
              </tr>
            ) : (
              topTargets.map((planet, index) => (
                <motion.tr
                  key={planet.planet_name}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="hover:bg-space-dark/50"
                >
                  <td className="px-6 py-4 text-exosignal-accent font-bold">#{index + 1}</td>
                  <td className="px-6 py-4 text-exosignal-text font-medium">
                    <Link to={`/planet/${planet.planet_name}`} className="hover:text-exosignal-accent">
                      {planet.planet_name}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-exosignal-text/70">
                    {planet.stellar_name || 'Unknown'}
                  </td>
                  <td className="px-6 py-4 text-exosignal-text/70">
                    {formatDistance(planet.distance)}
                  </td>
                  <td className="px-6 py-4 text-exosignal-accent font-semibold">
                    {formatPriority(planet.target_priority_score)}
                  </td>
                  <td className="px-6 py-4 text-exosignal-text/70">
                    {formatAnomaly(planet.anomaly_score)}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-xs px-2 py-1 rounded-full text-white
                      ${getHZColor(planet.hz_status)}`}>
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
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default TopTargets