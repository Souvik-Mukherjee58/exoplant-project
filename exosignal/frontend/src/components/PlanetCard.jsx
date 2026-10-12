import React from 'react'
import { Link } from 'react-router-dom'

const PlanetCard = ({ planet }) => {
  const HZ_COLORS = {
    'Inside HZ': 'bg-emerald-500',
    'Near HZ': 'bg-yellow-500',
    'Outside HZ': 'bg-gray-500',
    'Insufficient data': 'bg-gray-400'
  }

  if (!planet) return null

  return (
    <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-4 hover:bg-space-dark/50 transition">
      <div className="flex items-start space-x-4">
        <div className="w-10 h-10 flex-shrink-0 bg-exosignal-blue/20 rounded-lg flex items-center justify-center">
          <span className="text-exosignal-blue text-lg">{planet.planet_name?.charAt(0) || '?'}</span>
        </div>
        <div className="flex-1">
          <h3 className="font-medium text-exosignal-text mb-1">
            <Link to={`/planet/${planet.planet_name}`} className="hover:text-exosignal-accent">
              {planet.planet_name}
            </Link>
          </h3>
          <div className="flex items-center space-x-2 text-exosignal-text/70 text-sm mb-2">
            <div className={`w-3 h-3 rounded-full ${HZ_COLORS[planet.hz_status || 'Insufficient data']}`}></div>
            <span>{planet.hz_status || 'Insufficient data'}</span>
          </div>
          <div className="flex items-center space-x-4 text-exosignal-text/70 text-sm">
            <div>
              <span className="font-medium">{planet.target_priority_score?.toFixed(1) || '—'}</span>
              <span className="text-exosignal-text/60">Priority</span>
            </div>
            <div>
              <span className="font-medium">{planet.anomaly_score?.toFixed(2) || '—'}</span>
              <span className="text-exosignal-text/60">Anomaly</span>
            </div>
            <div>
              <span className="font-medium">{planet.distance?.toFixed(1) || '—'}</span>
              <span className="text-exosignal-text/60">pc</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PlanetCard