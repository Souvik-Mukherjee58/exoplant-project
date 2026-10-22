import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { usePlanets } from '../hooks/usePlanets'
import { formatRadius, formatPeriod, formatTemperature, formatAnomaly, formatPriority, getHZColor } from '../utils/formatters'

const HZ_OPTIONS = ['All', 'Inside HZ', 'Near HZ', 'Outside HZ', 'Insufficient data']
const ITEMS_PER_PAGE = 25

const Explorer = () => {
  const [filters, setFilters] = useState({
    name: '',
    minPriority: 0,
    maxPriority: 100,
    hzStatus: 'All',
    sortBy: 'priority',
    sortOrder: 'desc'
  })
  const [currentPage, setCurrentPage] = useState(1)

  const queryParams = useMemo(() => {
    const params = { limit: 500 }
    if (filters.name && filters.name.trim()) {
      params.q = filters.name.trim()
    }
    if (filters.hzStatus && filters.hzStatus !== 'All') {
      params.hz_status = filters.hzStatus
    }
    const minP = Number(filters.minPriority)
    const maxP = Number(filters.maxPriority)
    if (!isNaN(minP) && !isNaN(maxP) && minP <= maxP) {
      params.min_priority = minP
      params.max_priority = maxP
    }
    return params
  }, [filters.name, filters.hzStatus, filters.minPriority, filters.maxPriority])

  const { planets, loading, error, refetch } = usePlanets(queryParams)

  const handleFilterChange = (e) => {
    const { name, value } = e.target
    setFilters(prev => ({ ...prev, [name]: value }))
    setCurrentPage(1)
  }

  const filteredAndSortedPlanets = useMemo(() => {
    return [...planets]
      .filter(p => {
        const nameMatch = !filters.name || p.planet_name?.toLowerCase().includes(filters.name.toLowerCase())
        const hzMatch = filters.hzStatus === 'All' || p.hz_status === filters.hzStatus
        const priorityMatch = p.target_priority_score >= filters.minPriority && p.target_priority_score <= filters.maxPriority
        return nameMatch && hzMatch && priorityMatch
      })
      .sort((a, b) => {
        const fieldA = a[filters.sortBy === 'priority' ? 'target_priority_score' : 'anomaly_score']
        const fieldB = b[filters.sortBy === 'priority' ? 'target_priority_score' : 'anomaly_score']
        const valA = typeof fieldA === 'number' ? fieldA : 0
        const valB = typeof fieldB === 'number' ? fieldB : 0
        return filters.sortOrder === 'asc' ? valA - valB : valB - valA
      })
  }, [planets, filters])

  const totalPages = Math.ceil(filteredAndSortedPlanets.length / ITEMS_PER_PAGE)
  const paginatedPlanets = filteredAndSortedPlanets.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  )

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">Exoplanet Explorer</h1>

      <p className="text-exosignal-text/70 mb-6">
        Search and filter exoplanets by various astronomical and observational characteristics.
        Filter by priority score, HZ status, anomaly score, or sort by priority and interest.
      </p>

      {/* Filters */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-exosignal-text/70 mb-1">Search</label>
            <input
              type="text"
              name="name"
              value={filters.name}
              onChange={handleFilterChange}
              placeholder="Planet name"
              className="w-full bg-space-dark border border-exosignal-blue/30 rounded px-3 py-2 text-exosignal-text focus:outline-none focus:border-exosignal-accent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-exosignal-text/70 mb-1">HZ Status</label>
            <select
              name="hzStatus"
              value={filters.hzStatus}
              onChange={handleFilterChange}
              className="w-full bg-space-dark border border-exosignal-blue/30 rounded px-3 py-2 text-exosignal-text focus:outline-none focus:border-exosignal-accent"
            >
              {HZ_OPTIONS.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-exosignal-text/70 mb-1">
              Min Priority: {filters.minPriority}
            </label>
            <input
              type="range"
              name="minPriority"
              min="0"
              max="100"
              value={filters.minPriority}
              onChange={handleFilterChange}
              className="w-full accent-exosignal-accent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-exosignal-text/70 mb-1">
              Max Priority: {filters.maxPriority}
            </label>
            <input
              type="range"
              name="maxPriority"
              min="0"
              max="100"
              value={filters.maxPriority}
              onChange={handleFilterChange}
              className="w-full accent-exosignal-accent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-exosignal-text/70 mb-1">
              Sort By
            </label>
            <div className="flex items-center space-x-2">
              <select
                name="sortBy"
                value={filters.sortBy}
                onChange={handleFilterChange}
                className="bg-space-dark border border-exosignal-blue/30 rounded px-2 py-1 text-exosignal-text focus:outline-none focus:border-exosignal-accent"
              >
                <option value="priority">Priority</option>
                <option value="anomaly">Anomaly</option>
              </select>
              <button
                onClick={() => setFilters(prev => ({ ...prev, sortOrder: prev.sortOrder === 'asc' ? 'desc' : 'asc' }))}
                className="bg-space-dark border border-exosignal-blue/30 rounded px-2 py-1 text-exosignal-text hover:bg-exosignal-blue/10 focus:outline-none"
              >
                {filters.sortOrder === 'asc' ? '↑' : '↓'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 overflow-hidden">
        {loading ? (
          <div className="p-6 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-exosignal-accent"></div>
            <p className="mt-2 text-exosignal-text/70">Loading exoplanet data...</p>
          </div>
        ) : error ? (
          <div className="p-6 text-center text-exosignal-red">
            <p>{error}</p>
            <button
              onClick={() => refetch()}
              className="mt-4 bg-exosignal-blue text-white px-4 py-2 rounded hover:bg-exosignal-accent transition"
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-exosignal-blue/10">
              <thead className="bg-space-dark">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Planet</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Radius (R⊕)</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Period (days)</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Temp (K)</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">HZ</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Anomaly</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Priority</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-exosignal-blue/10">
                {paginatedPlanets.map((planet) => (
                  <tr key={planet.planet_name} className="hover:bg-space-dark/50">
                    <td className="px-4 py-3 text-exosignal-text font-medium">
                      <Link to={`/planet/${planet.planet_name}`} className="hover:text-exosignal-accent">
                        {planet.planet_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-exosignal-text/70">
                      {formatRadius(planet.planet_radius)}
                    </td>
                    <td className="px-4 py-3 text-exosignal-text/70">
                      {formatPeriod(planet.orbital_period)}
                    </td>
                    <td className="px-4 py-3 text-exosignal-text/70">
                      {formatTemperature(planet.equilibrium_temperature)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`${getHZColor(planet.hz_status)} text-white text-xs px-2 py-1 rounded-full`}>
                        {planet.hz_status || 'Insufficient data'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-exosignal-text/70">
                      {formatAnomaly(planet.anomaly_score)}
                    </td>
                    <td className="px-4 py-3 text-exosignal-accent font-semibold">
                      {formatPriority(planet.target_priority_score)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <div className="text-exosignal-text/70">
            Showing {paginatedPlanets.length} of {filteredAndSortedPlanets.length} planets (page {currentPage} of {totalPages})
          </div>
          <div className="flex space-x-2">
            <button
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 bg-space-dark border border-exosignal-blue/30 rounded text-exosignal-text disabled:opacity-50 hover:bg-exosignal-blue/10"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage >= totalPages}
              className="px-4 py-2 bg-space-dark border border-exosignal-blue/30 rounded text-exosignal-text disabled:opacity-50 hover:bg-exosignal-blue/10"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Explorer