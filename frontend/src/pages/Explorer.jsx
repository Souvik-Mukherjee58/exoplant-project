import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { usePlanets } from '../hooks/usePlanets'
import { useFavorites } from '../context/FavoritesContext'
import { formatRadius, formatPeriod, formatTemperature, formatAnomaly, formatPriority, getHZColor } from '../utils/formatters'
import SectionDivider from '../components/SectionDivider'


const HZ_OPTIONS = ['All', 'Inside HZ', 'Near HZ', 'Outside HZ']
const ITEMS_PER_PAGE = 24

const Explorer = () => {
  const [filters, setFilters] = useState({
    name: '',
    minPriority: 0,
    maxPriority: 100,
    hzStatus: 'All',
    sortBy: 'priority',
    sortOrder: 'desc',
    terrestrialOnly: false
  })
  const [viewMode, setViewMode] = useState('grid') // 'grid' | 'table'
  const [currentPage, setCurrentPage] = useState(1)
  const { toggleFavorite, isFavorite } = useFavorites()

  const queryParams = useMemo(() => {
    const params = { limit: 1000 }
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
    const { name, value, type, checked } = e.target
    setFilters(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
    setCurrentPage(1)
  }

  const handleQuickPreset = (preset) => {
    if (preset === 'hz') {
      setFilters(prev => ({ ...prev, hzStatus: 'Inside HZ', minPriority: 60 }))
    } else if (preset === 'superEarth') {
      setFilters(prev => ({ ...prev, terrestrialOnly: true }))
    } else if (preset === 'top') {
      setFilters(prev => ({ ...prev, minPriority: 80, hzStatus: 'All' }))
    } else if (preset === 'reset') {
      setFilters({
        name: '',
        minPriority: 0,
        maxPriority: 100,
        hzStatus: 'All',
        sortBy: 'priority',
        sortOrder: 'desc',
        terrestrialOnly: false
      })
    }
    setCurrentPage(1)
  }

  const filteredAndSortedPlanets = useMemo(() => {
    return [...planets]
      .filter(p => {
        const nameMatch = !filters.name || p.planet_name?.toLowerCase().includes(filters.name.toLowerCase())
        const hzMatch = filters.hzStatus === 'All' || p.hz_status === filters.hzStatus
        const priorityMatch = p.target_priority_score >= filters.minPriority && p.target_priority_score <= filters.maxPriority
        const terrestrialMatch = !filters.terrestrialOnly || (p.planet_radius && p.planet_radius <= 1.8)
        return nameMatch && hzMatch && priorityMatch && terrestrialMatch
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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-exosignal-cyan/20 pb-6">
        <div>
          <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
            Astronomical Catalog Explorer
          </div>
          <h1 className="text-3xl font-black text-white font-display">
            Exoplanet Target Database
          </h1>
          <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
            Columnar zero-copy queries over NASA archive parameters. Filter by planetary radius, habitable zone alignment, transit probability, and ML priority rank.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center space-x-2 bg-space-void/90 p-1 rounded-xl border border-exosignal-cyan/20">
          <button
            onClick={() => setViewMode('grid')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all ${
              viewMode === 'grid'
                ? 'bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/40 shadow-neon-cyan'
                : 'text-exosignal-text-muted hover:text-white'
            }`}
          >
            🔲 Card Grid
          </button>
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all ${
              viewMode === 'table'
                ? 'bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/40 shadow-neon-cyan'
                : 'text-exosignal-text-muted hover:text-white'
            }`}
          >
            📋 Data Table
          </button>
        </div>
      </div>

      {/* Section 01: Modern Filter HUD */}
      <div className="space-y-4">
        <SectionDivider
          number="01"
          title="Catalog Search & Columnar Filters"
          subtitle="Real-time multi-attribute query engine with parameter pushdown"
          badge="QUERY FILTERS"
          accent="cyan"
        />

        <div className="divided-compartment p-6 space-y-4">
          {/* Quick Filter Presets */}
          <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-exosignal-cyan/15">
            <span className="text-xs font-mono text-exosignal-text-muted uppercase">Quick Presets:</span>
            <button
              onClick={() => handleQuickPreset('hz')}
              className="px-2.5 py-1 rounded-full text-xs font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 transition-colors"
            >
              🌟 Habitable Zone (Inside HZ)
            </button>
            <button
              onClick={() => handleQuickPreset('superEarth')}
              className="px-2.5 py-1 rounded-full text-xs font-mono bg-exosignal-cyan/15 text-exosignal-cyan border border-exosignal-cyan/30 hover:bg-exosignal-cyan/25 transition-colors"
            >
              🌍 Rocky Super-Earths (&le; 1.8 R⊕)
            </button>
            <button
              onClick={() => handleQuickPreset('top')}
              className="px-2.5 py-1 rounded-full text-xs font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25 transition-colors"
            >
              🏆 Top Tier Targets (&gt; 80)
            </button>
            <button
              onClick={() => handleQuickPreset('reset')}
              className="px-2.5 py-1 rounded-full text-xs font-mono bg-space-void text-exosignal-text-muted border border-slate-700 hover:text-white transition-colors"
            >
              Reset Filters
            </button>
          </div>

          {/* Inputs Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* Search Input */}
            <div>
              <label className="block text-xs font-mono text-exosignal-text-muted mb-1">Target Name</label>
              <input
                type="text"
                name="name"
                value={filters.name}
                onChange={handleFilterChange}
                placeholder="e.g. TOI-700, TRAPPIST"
                className="w-full bg-space-void/90 border border-exosignal-cyan/30 rounded-xl px-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-exosignal-cyan"
              />
            </div>

            {/* HZ Status */}
            <div>
              <label className="block text-xs font-mono text-exosignal-text-muted mb-1">Habitable Zone Status</label>
              <select
                name="hzStatus"
                value={filters.hzStatus}
                onChange={handleFilterChange}
                className="w-full bg-space-void/90 border border-exosignal-cyan/30 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-exosignal-cyan"
              >
                {HZ_OPTIONS.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>

            {/* Min Priority */}
            <div>
              <div className="flex justify-between items-center text-xs font-mono text-exosignal-text-muted mb-1">
                <span>Min Priority</span>
                <span className="text-exosignal-cyan font-bold">{filters.minPriority}</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                name="minPriority"
                value={filters.minPriority}
                onChange={handleFilterChange}
                className="w-full accent-exosignal-cyan cursor-pointer"
              />
            </div>

            {/* Sort Field */}
            <div>
              <label className="block text-xs font-mono text-exosignal-text-muted mb-1">Sort Field</label>
              <div className="flex space-x-1">
                <select
                  name="sortBy"
                  value={filters.sortBy}
                  onChange={handleFilterChange}
                  className="w-full bg-space-void/90 border border-exosignal-cyan/30 rounded-xl px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-exosignal-cyan"
                >
                  <option value="priority">Priority Score</option>
                  <option value="anomaly">Anomaly Score</option>
                </select>
                <button
                  type="button"
                  onClick={() => setFilters(prev => ({ ...prev, sortOrder: prev.sortOrder === 'asc' ? 'desc' : 'asc' }))}
                  className="px-3 bg-space-void/90 border border-exosignal-cyan/30 rounded-xl text-exosignal-cyan font-mono hover:bg-space-card"
                  title="Toggle Sort Direction"
                >
                  {filters.sortOrder === 'asc' ? '↑' : '↓'}
                </button>
              </div>
            </div>

            {/* Results Summary Counter */}
            <div className="flex flex-col justify-end">
              <div className="bg-space-void/80 p-2.5 rounded-xl border border-exosignal-cyan/20 text-center font-mono">
                <span className="text-[10px] text-exosignal-text-muted block uppercase">Filtered Targets</span>
                <span className="text-base font-bold text-exosignal-cyan">
                  {filteredAndSortedPlanets.length} <span className="text-xs text-exosignal-text-muted">/ {planets.length}</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 02: Results Rendering */}
      <div className="space-y-4">
        <SectionDivider
          number="02"
          title="Catalog Targets & Observational Yield"
          subtitle="Real-time paginated results with physical parameter profiles and ML priority scores"
          badge={`${filteredAndSortedPlanets.length} MATCHING TARGETS`}
          accent="purple"
        />

        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-3">
            <div className="w-10 h-10 rounded-full border-4 border-exosignal-cyan/20 border-t-exosignal-cyan animate-spin"></div>
            <p className="text-xs font-mono text-exosignal-text-muted">Querying DuckDB In-Memory Parquet Database...</p>
          </div>
        ) : error ? (
          <div className="glass-panel p-8 text-center text-rose-400 font-mono text-xs space-y-3">
            <p>Failed to query catalog: {error}</p>
            <button onClick={() => refetch()} className="btn-secondary-glass text-xs">Retry Query</button>
          </div>
        ) : viewMode === 'grid' ? (
          /* ─── CARD GRID VIEW ─── */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">

          {paginatedPlanets.map((planet) => {
            const isFav = isFavorite(planet.planet_name)
            return (
              <div
                key={planet.planet_name}
                className="glass-panel glass-panel-hover p-5 border-exosignal-cyan/20 flex flex-col justify-between card-shine group"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
                      planet.hz_status === 'Inside HZ'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        : planet.hz_status === 'Near HZ'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : 'bg-slate-700/30 text-slate-400 border border-slate-600/30'
                    }`}>
                      {planet.hz_status || 'Outside HZ'}
                    </span>
                    <button
                      onClick={() => toggleFavorite(planet)}
                      className="text-base transition-transform hover:scale-125"
                      title={isFav ? 'Remove from Watchlist' : 'Add to Watchlist'}
                    >
                      {isFav ? '★' : '☆'}
                    </button>
                  </div>

                  <Link
                    to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                    className="block font-display text-lg font-bold text-white group-hover:text-exosignal-cyan transition-colors truncate"
                  >
                    {planet.planet_name}
                  </Link>

                  <div className="text-[11px] font-mono text-exosignal-text-muted mb-3 truncate">
                    Host: {planet.hostname || 'Unknown Star'}
                  </div>

                  {/* Physical Parameters Pill Grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-space-void/60 p-2.5 rounded-xl border border-exosignal-cyan/10 mb-4">
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Radius</span>
                      <span className="text-white font-semibold">{formatRadius(planet.planet_radius)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Period</span>
                      <span className="text-white font-semibold">{formatPeriod(planet.orbital_period)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Temp</span>
                      <span className="text-white font-semibold">{formatTemperature(planet.equilibrium_temperature)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Anomaly</span>
                      <span className="text-amber-400 font-semibold">{formatAnomaly(planet.anomaly_score)}</span>
                    </div>
                  </div>
                </div>

                {/* Score Bar & Actions */}
                <div className="space-y-3 pt-2 border-t border-exosignal-cyan/10">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-exosignal-text-muted">Target Priority</span>
                    <span className="text-exosignal-cyan font-bold text-sm">
                      {formatPriority(planet.target_priority_score)}
                    </span>
                  </div>
                  <div className="w-full bg-space-void rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-exosignal-cyan to-exosignal-purple h-full rounded-full"
                      style={{ width: `${Math.min(Math.max(planet.target_priority_score, 5), 100)}%` }}
                    ></div>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-1">
                    <Link
                      to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                      className="w-full text-center py-1.5 rounded-lg bg-exosignal-cyan/15 hover:bg-exosignal-cyan/25 text-exosignal-cyan text-xs font-mono font-semibold transition-colors border border-exosignal-cyan/30"
                    >
                      SHAP Details
                    </Link>
                    <Link
                      to={`/compare?planet_a=${encodeURIComponent(planet.planet_name)}`}
                      className="px-2.5 py-1.5 rounded-lg bg-space-void hover:bg-space-card text-exosignal-purple text-xs font-mono font-semibold transition-colors border border-exosignal-purple/30"
                      title="Compare against another target"
                    >
                      Compare
                    </Link>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        /* ─── DATA TABLE VIEW ─── */
        <div className="glass-panel overflow-hidden border-exosignal-cyan/20">
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-exosignal-cyan/20 bg-space-void/70 text-exosignal-text-muted text-left">
                  <th className="py-3 px-4">Planet</th>
                  <th className="py-3 px-4">Radius (R⊕)</th>
                  <th className="py-3 px-4">Period (days)</th>
                  <th className="py-3 px-4">Equilibrium Temp</th>
                  <th className="py-3 px-4">Habitable Zone</th>
                  <th className="py-3 px-4">Anomaly Score</th>
                  <th className="py-3 px-4">Target Priority</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-exosignal-cyan/10">
                {paginatedPlanets.map((planet) => (
                  <tr key={planet.planet_name} className="hover:bg-space-card-hover transition-colors">
                    <td className="py-3 px-4">
                      <Link
                        to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                        className="text-white font-bold hover:text-exosignal-cyan transition-colors"
                      >
                        {planet.planet_name}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-exosignal-text-secondary">{formatRadius(planet.planet_radius)}</td>
                    <td className="py-3 px-4 text-exosignal-text-secondary">{formatPeriod(planet.orbital_period)}</td>
                    <td className="py-3 px-4 text-exosignal-text-secondary">{formatTemperature(planet.equilibrium_temperature)}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        planet.hz_status === 'Inside HZ'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : planet.hz_status === 'Near HZ'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-slate-700/30 text-slate-400 border border-slate-600/30'
                      }`}>
                        {planet.hz_status || 'Outside HZ'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-amber-400 font-semibold">{formatAnomaly(planet.anomaly_score)}</td>
                    <td className="py-3 px-4 text-exosignal-cyan font-bold text-sm">{formatPriority(planet.target_priority_score)}</td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <Link
                        to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                        className="px-2.5 py-1 rounded bg-exosignal-cyan/10 hover:bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/30 text-[11px] transition-colors"
                      >
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs pt-4">
          <div className="text-exosignal-text-muted">
            Page <span className="text-white font-bold">{currentPage}</span> of{' '}
            <span className="text-white font-bold">{totalPages}</span> ({filteredAndSortedPlanets.length} total targets)
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
              className="px-3 py-1.5 rounded-lg bg-space-void border border-exosignal-cyan/30 text-white disabled:opacity-40 hover:bg-space-card"
            >
              ← Previous
            </button>
            <button
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage >= totalPages}
              className="px-3 py-1.5 rounded-lg bg-space-void border border-exosignal-cyan/30 text-white disabled:opacity-40 hover:bg-space-card"
            >
              Next →
            </button>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}


export default Explorer