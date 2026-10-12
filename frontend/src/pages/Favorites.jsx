import React from 'react'
import { Link } from 'react-router-dom'
import { useFavorites } from '../context/FavoritesContext'
import { formatPriority, formatAnomaly, formatDistance, getHZColor } from '../utils/formatters'
import { motion } from 'framer-motion'

const Favorites = () => {
  const { favorites, removeFavorite, isFavorite } = useFavorites()

  if (favorites.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-6xl mb-4">⭐</div>
        <h2 className="text-2xl font-bold text-exosignal-text mb-2">No favorites yet</h2>
        <p className="text-exosignal-text/70 mb-6">
          Start exploring and bookmark your favorite exoplanets!
        </p>
        <Link
          to="/top-targets"
          className="inline-block bg-exosignal-accent text-space-dark px-6 py-3 rounded-lg font-semibold hover:bg-exosignal-blue transition"
        >
          Explore Top Targets
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-4">Your Favorites</h1>
      <p className="text-exosignal-text/70 mb-6">
        Your bookmarked exoplanets for quick access.
      </p>

      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 overflow-hidden">
        <table className="min-w-full divide-y divide-exosignal-blue/10">
          <thead className="bg-space-dark">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Planet</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Host Star</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Distance</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Priority</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Anomaly</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">HZ Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-exosignal-blue/10">
            {favorites.map((planet, index) => (
              <motion.tr
                key={planet.planet_name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="hover:bg-space-dark/50"
              >
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
                    onClick={() => removeFavorite(planet.planet_name)}
                    className="text-exosignal-red hover:text-red-400 transition"
                    title="Remove from favorites"
                  >
                    ✕
                  </button>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default Favorites
