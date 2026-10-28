import React, { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTopTargets } from '../hooks/usePlanets'
import { useFavorites } from '../context/FavoritesContext'
import { formatPriority, formatAnomaly, formatDistance, formatRadius, formatPeriod, getHZColor } from '../utils/formatters'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend, Cell
} from 'recharts'
import SectionDivider from '../components/SectionDivider'


const TopTargets = () => {
  const [limit, setLimit] = useState(25)
  const { planets: topTargets, loading, error, refetch } = useTopTargets(limit)
  const { toggleFavorite, isFavorite } = useFavorites()

  const podium = topTargets?.slice(0, 3) || []

  // Top 10 data prepared for bar chart
  const top10ChartData = useMemo(() => {
    if (!topTargets || topTargets.length === 0) return []
    return topTargets.slice(0, 10).map((p, idx) => ({
      name: p.planet_name,
      rank: p.priority_rank ? `#${p.priority_rank}` : `#${idx + 1}`,
      priority: Number((p.priority_score ?? p.ml_priority_score ?? p.target_priority_score)?.toFixed(1) || 0),
      anomaly: Number(((p.anomaly_score || 0) * 100).toFixed(1)),
      hz: p.hz_status
    }))
  }, [topTargets])

  return (
    <div className="space-y-10">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-exosignal-cyan/20 pb-6">
        <div>
          <div className="text-xs font-mono text-amber-400 uppercase tracking-wider font-bold mb-1">
            Prioritization Leaderboard
          </div>
          <h1 className="text-3xl font-black text-white font-display">
            Top Atmospheric Spectroscopy Candidates
          </h1>
          <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
            Ranked by the 21-feature Supervised Learning-to-Rank LightGBM model, optimized for JWST and ELT transmission and emission SNR yield.
          </p>
        </div>

        {/* Limit Selector */}
        <div className="flex items-center space-x-2 font-mono text-xs">
          <span className="text-exosignal-text-muted">Display Top:</span>
          {[10, 25, 50].map((num) => (
            <button
              key={num}
              onClick={() => setLimit(num)}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all ${
                limit === num
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-neon-emerald'
                  : 'bg-space-void text-exosignal-text-muted hover:text-white border border-slate-700'
              }`}
            >
              {num}
            </button>
          ))}
        </div>
      </div>

      {/* Top 3 Podium Cards */}
      {!loading && podium.length >= 3 && (
        <div className="space-y-4">
          <SectionDivider
            number="01"
            title="Prime Spectroscopy Targets Podium"
            subtitle="Top 3 ranked candidates exhibiting peak transmission signal-to-noise ratio and atmospheric scale height"
            badge="TOP PODIUM"
            accent="amber"
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

          {podium.map((planet, idx) => {
            const isFirst = idx === 0
            const medal = isFirst ? '🥇 #1 Prime Target' : idx === 1 ? '🥈 #2 Runner-Up' : '🥉 #3 High Yield'
            const borderGlow = isFirst ? 'border-amber-400/50 shadow-neon-emerald' : idx === 1 ? 'border-slate-300/40' : 'border-amber-700/40'
            const isFav = isFavorite(planet.planet_name)

            return (
              <div
                key={planet.planet_name}
                className={`glass-panel p-6 border ${borderGlow} relative overflow-hidden flex flex-col justify-between card-shine`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className={`text-[11px] font-mono font-bold uppercase px-2.5 py-0.5 rounded-full ${isFirst ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40' : 'bg-space-void text-slate-300 border border-slate-700'}`}>
                      {medal}
                    </span>
                    <button
                      onClick={() => toggleFavorite(planet)}
                      className="text-lg hover:scale-125 transition-transform"
                    >
                      {isFav ? '★' : '☆'}
                    </button>
                  </div>

                  <Link
                    to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                    className="block font-display text-2xl font-bold text-white hover:text-exosignal-cyan transition-colors"
                  >
                    {planet.planet_name}
                  </Link>

                  <div className="text-xs font-mono text-exosignal-text-muted mb-4">
                    Host Star: {planet.hostname || planet.stellar_name || planet.planet_name?.replace(/\s+[a-z]$/i, '') || '—'}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-space-void/70 p-3 rounded-xl border border-exosignal-cyan/15 mb-4">
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Radius</span>
                      <span className="text-white font-bold">{formatRadius(planet.planet_radius)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Orbital Period</span>
                      <span className="text-white font-bold">{formatPeriod(planet.orbital_period)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Distance</span>
                      <span className="text-white font-bold">{formatDistance(planet.distance)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-exosignal-text-muted block">Habitable Zone</span>
                      <span className="text-emerald-400 font-bold">{planet.hz_status || 'Inside HZ'}</span>
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-exosignal-cyan/15 flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono text-exosignal-text-muted">Priority Score</span>
                    <div className="text-xl font-bold font-mono text-gradient-gold">
                      {formatPriority(planet.priority_score ?? planet.ml_priority_score ?? planet.target_priority_score)} / 100
                    </div>
                  </div>
                  <Link
                    to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                    className="btn-primary-glow text-xs py-1.5 px-3"
                  >
                    SHAP Waterfall
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* COMPARATIVE BAR GRAPH: TOP 10 TARGET SCORING PROFILES */}
      {/* ────────────────────────────────────────────────────────── */}
      {!loading && top10ChartData.length > 0 && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="Top 10 Targets Scoring Profiles & Anomaly Indices"
            subtitle="Side-by-side comparison of supervised target priority scores against isolation forest anomaly indices"
            badge="PROFILE COMPARISON"
            accent="purple"
          />

          <div className="divided-compartment p-6 space-y-4">

          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-exosignal-cyan/15 pb-3 gap-2">
            <div>
              <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
                Comparative Analytics
              </div>
              <h3 className="text-xl font-bold font-display text-white">
                Top 10 Targets Scoring Profile Bar Graph
              </h3>
            </div>
            <span className="text-xs font-mono text-emerald-400">
              ● Side-by-Side ML Priority vs Atmospheric Anomaly
            </span>
          </div>

          <div className="h-72 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={top10ChartData} margin={{ top: 10, right: 30, left: 10, bottom: 25 }}>
                <defs>
                  <linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4ff" stopOpacity={1} />
                    <stop offset="100%" stopColor="#0284c7" stopOpacity={0.6} />
                  </linearGradient>
                  <linearGradient id="amberGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity={1} />
                    <stop offset="100%" stopColor="#d97706" stopOpacity={0.6} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#131c38" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#f8fafc', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  axisLine={{ stroke: '#1e293b' }}
                  angle={-15}
                  textAnchor="end"
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  axisLine={{ stroke: '#1e293b' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#070a16',
                    borderColor: '#00d4ff',
                    borderRadius: '12px',
                    color: '#ffffff',
                    fontFamily: 'JetBrains Mono',
                    fontSize: '12px',
                    boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)'
                  }}
                />
                <Legend
                  wrapperStyle={{ paddingTop: '15px', fontFamily: 'JetBrains Mono', fontSize: '11px' }}
                />
                <Bar dataKey="priority" name="Target Priority Score (0-100)" fill="url(#cyanGradient)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="anomaly" name="Anomaly Index (×100)" fill="url(#amberGradient)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        </div>
      )}

      {/* Section 03: Full Leaderboard Table */}
      <div className="space-y-4">
        <SectionDivider
          number="03"
          title="Atmospheric Spectroscopy Leaderboard"
          subtitle="Ranked candidate catalog with planetary parameters, host star brightness, and local TreeSHAP attribution links"
          badge={`${topTargets?.length || 0} CANDIDATES`}
          accent="cyan"
        />

        <div className="divided-compartment overflow-hidden">
          <div className="compartment-header text-xs font-mono">
            <span className="text-exosignal-text-secondary font-bold">

            Prioritized Catalog Candidates ({topTargets?.length || 0} Targets Loaded)
          </span>
          <span className="text-emerald-400">● LightGBM Supervised LTR Active</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-exosignal-cyan/20 bg-space-void/80 text-exosignal-text-muted text-left">
                <th className="py-3.5 px-4">Rank</th>
                <th className="py-3.5 px-4">Planet Name</th>
                <th className="py-3.5 px-4">Radius (R⊕)</th>
                <th className="py-3.5 px-4">Period (days)</th>
                <th className="py-3.5 px-4">Host Star</th>
                <th className="py-3.5 px-4">Distance (pc)</th>
                <th className="py-3.5 px-4">Habitable Zone</th>
                <th className="py-3.5 px-4">Anomaly</th>
                <th className="py-3.5 px-4">Priority Score</th>
                <th className="py-3.5 px-4 text-center">Watchlist</th>
                <th className="py-3.5 px-4 text-right">Attribution</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-exosignal-cyan/10">
              {loading ? (
                <tr>
                  <td colSpan="11" className="py-12 text-center text-exosignal-text-muted">
                    <div className="w-8 h-8 mx-auto mb-2 rounded-full border-2 border-exosignal-cyan border-t-transparent animate-spin"></div>
                    Retrieving prioritized targets from DuckDB engine...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan="11" className="py-8 text-center text-rose-400">
                    Failed to load targets: {error}
                  </td>
                </tr>
              ) : (
                topTargets.map((planet, index) => {
                  const isFav = isFavorite(planet.planet_name)
                  const pRank = planet.priority_rank ?? planet.ml_rank ?? (index + 1)
                  const pScore = planet.priority_score ?? planet.ml_priority_score ?? planet.target_priority_score
                  return (
                    <tr key={planet.planet_name} className="hover:bg-space-card-hover transition-colors">
                      <td className="py-3.5 px-4 font-bold text-amber-400">
                        #{pRank}
                      </td>
                      <td className="py-3.5 px-4">
                        <Link
                          to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                          className="font-bold text-white hover:text-exosignal-cyan transition-colors"
                        >
                          {planet.planet_name}
                        </Link>
                      </td>
                      <td className="py-3.5 px-4 text-exosignal-text-secondary">{formatRadius(planet.planet_radius)}</td>
                      <td className="py-3.5 px-4 text-exosignal-text-secondary">{formatPeriod(planet.orbital_period)}</td>
                      <td className="py-3.5 px-4 text-exosignal-text-muted">{planet.hostname || planet.stellar_name || '—'}</td>
                      <td className="py-3.5 px-4 text-exosignal-text-secondary">{formatDistance(planet.distance)}</td>
                      <td className="py-3.5 px-4">
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
                      <td className="py-3.5 px-4 text-amber-400">{formatAnomaly(planet.anomaly_score)}</td>
                      <td className="py-3.5 px-4 text-exosignal-cyan font-bold text-sm">
                        {formatPriority(pScore)}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <button
                          onClick={() => toggleFavorite(planet)}
                          className="hover:scale-125 transition-transform"
                        >
                          {isFav ? '★' : '☆'}
                        </button>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                          className="px-2.5 py-1 rounded bg-exosignal-cyan/10 hover:bg-exosignal-cyan/25 text-exosignal-cyan border border-exosignal-cyan/30 text-[11px] transition-colors"
                        >
                          SHAP Waterfall
                        </Link>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
      </div>
    </div>
  )
}

export default TopTargets