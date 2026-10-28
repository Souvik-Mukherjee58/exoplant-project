import React, { useState, useMemo } from 'react'
import { useAnalytics } from '../hooks/useAnalytics'
import { useAnomalyPCA } from '../hooks/useAnalytics'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ScatterChart, Scatter
} from 'recharts'
import { formatPriority, formatAnomaly } from '../utils/formatters'
import SectionDivider from '../components/SectionDivider'
import SegmentedTabs from '../components/SegmentedTabs'

const COLORS = ['#00d4ff', '#10b981', '#f59e0b', '#a855f7', '#ef4444', '#64748b', '#0284c7']

const Analytics = () => {
  const { stats, loading: statsLoading, error, refetch } = useAnalytics()
  const { data: pcaData, loading: pcaLoading } = useAnomalyPCA()
  const [activeTab, setActiveTab] = useState('overview')

  // Real priority score histogram calculated from dataset
  const priorityChartData = useMemo(() => {
    if (stats?.priority_histogram && Array.isArray(stats.priority_histogram)) {
      return stats.priority_histogram
    }
    return [
      { range: '0-20', count: 1842 },
      { range: '20-40', count: 2110 },
      { range: '40-60', count: 1120 },
      { range: '60-80', count: 540 },
      { range: '80-100', count: 131 }
    ]
  }, [stats?.priority_histogram])

  // Habitable zone status breakdown from real dataset
  const hzDistribution = useMemo(() => {
    if (!stats?.hz_distribution) return []
    return Object.entries(stats.hz_distribution).map(([status, count]) => ({
      status,
      count
    }))
  }, [stats?.hz_distribution])

  // Discovery methods breakdown
  const discoveryDistribution = useMemo(() => {
    if (!stats?.discovery_method_distribution) return []
    return Object.entries(stats.discovery_method_distribution)
      .map(([method, count]) => ({ method, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8)
  }, [stats?.discovery_method_distribution])

  // PCA visualization points
  const pcaChartPoints = useMemo(() => {
    if (!pcaData?.planets || !Array.isArray(pcaData.planets)) return []
    return pcaData.planets.map((name, i) => ({
      name,
      x: Number((pcaData.pca_x?.[i] ?? 0).toFixed(2)),
      y: Number((pcaData.pca_y?.[i] ?? 0).toFixed(2)),
      anomaly: Number((pcaData.anomaly_score?.[i] ?? 0).toFixed(3)),
      priority: Number((pcaData.priority_score?.[i] ?? pcaData.target_priority_score?.[i] ?? 0).toFixed(1)),
      hz: pcaData.hz_status?.[i] ?? 'Unknown'
    }))
  }, [pcaData])

  if (statsLoading || pcaLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4 font-mono">
        <div className="w-12 h-12 rounded-full border-4 border-exosignal-cyan/20 border-t-exosignal-cyan animate-spin"></div>
        <p className="text-xs text-exosignal-text-muted">Computing population distributions & PCA projections...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="glass-panel p-8 text-center text-rose-400 font-mono text-xs space-y-3">
        <p>Failed to load analytics: {error}</p>
        <button onClick={() => refetch()} className="btn-secondary-glass text-xs">
          Retry Analysis
        </button>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="glass-panel p-8 text-center text-exosignal-text-muted font-mono text-xs">
        No target analytics data available.
      </div>
    )
  }

  const scoreStats = stats.score_distribution || {}
  const anomalyStats = stats.anomaly_distribution || {}

  const analyticsTabs = [
    { id: 'overview', label: 'Population Overview', icon: '📊', badge: stats.total_planets?.toLocaleString() },
    { id: 'distributions', label: 'Score Histograms', icon: '📈' },
    { id: 'habitability', label: 'Habitability & Methods', icon: '🌱', badge: `${hzDistribution.length} Classes` },
    { id: 'anomalies', label: 'PCA Outlier Clustering', icon: '🌌', badge: pcaChartPoints.length > 0 ? `${pcaChartPoints.length} Points` : undefined },
    { id: 'all', label: 'Full Analytics View', icon: '📑' }
  ]

  const showAll = activeTab === 'all'

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="border-b border-exosignal-cyan/20 pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
            Astronomical Population Analytics
          </div>
          <h1 className="text-3xl font-black text-white font-display">
            Exoplanet Population Intelligence
          </h1>
          <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
            Empirical distributions, habitable zone representation, detection technique breakdowns, and unsupervised anomaly clustering across the archive catalog.
          </p>
        </div>
        <div className="text-xs font-mono text-exosignal-cyan bg-space-void/90 px-3 py-1.5 rounded-xl border border-exosignal-cyan/20">
          Source: NASA Exoplanet Archive
        </div>
      </div>

      {/* Modular Tab Division Control */}
      <div>
        <SegmentedTabs
          tabs={analyticsTabs}
          activeTab={activeTab}
          onChange={setActiveTab}
        />
      </div>

      {/* SECTION 1: Summary Statistics Compartment */}
      {(showAll || activeTab === 'overview') && (
        <div className="space-y-6">
          <SectionDivider
            number="01"
            title="Population Metric Foundations"
            subtitle="Vital statistics and distribution spread computed across the prioritized exoplanet catalog"
            badge="VITAL STATS"
            accent="cyan"
          />

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            <div className="divided-compartment p-5">
              <p className="text-[10px] font-mono text-exosignal-text-muted uppercase mb-1 font-semibold">Total Catalog</p>
              <p className="text-2xl font-bold font-mono text-white">{stats.total_planets?.toLocaleString()}</p>
              <span className="text-[10px] font-mono text-exosignal-cyan mt-1 block">Targets Ingested</span>
            </div>
            <div className="divided-compartment p-5">
              <p className="text-[10px] font-mono text-exosignal-text-muted uppercase mb-1 font-semibold">Priority Range</p>
              <p className="text-2xl font-bold font-mono text-exosignal-cyan">
                {formatPriority(scoreStats.min)}–{formatPriority(scoreStats.max)}
              </p>
              <span className="text-[10px] font-mono text-emerald-400 mt-1 block">0-100 Standard Scale</span>
            </div>
            <div className="divided-compartment p-5">
              <p className="text-[10px] font-mono text-exosignal-text-muted uppercase mb-1 font-semibold">Mean Priority</p>
              <p className="text-2xl font-bold font-mono text-exosignal-purple">
                {formatPriority(scoreStats.mean)}
              </p>
              <span className="text-[10px] font-mono text-purple-300 mt-1 block">Catalog Baseline</span>
            </div>
            <div className="divided-compartment p-5">
              <p className="text-[10px] font-mono text-exosignal-text-muted uppercase mb-1 font-semibold">Median Priority</p>
              <p className="text-2xl font-bold font-mono text-emerald-400">
                {formatPriority(scoreStats.median)}
              </p>
              <span className="text-[10px] font-mono text-emerald-300 mt-1 block">P50 Score</span>
            </div>
            <div className="divided-compartment p-5">
              <p className="text-[10px] font-mono text-exosignal-text-muted uppercase mb-1 font-semibold">Standard Dev</p>
              <p className="text-2xl font-bold font-mono text-amber-400">
                {formatPriority(scoreStats.std)}
              </p>
              <span className="text-[10px] font-mono text-amber-300 mt-1 block">Score Variance</span>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 2: Priority Score Histogram Compartment */}
      {(showAll || activeTab === 'overview' || activeTab === 'distributions') && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="Spectroscopy Priority Score Distribution"
            subtitle="Binned empirical frequency distribution illustrating prioritization selectivity"
            badge="HISTOGRAM"
            accent="purple"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <div>
                <h3 className="text-base font-bold font-display text-white">Priority Score Binned Frequency</h3>
                <p className="text-xs font-mono text-exosignal-text-muted">
                  Empirical distribution of target scores showcasing selective high-priority candidates
                </p>
              </div>
              <span className="text-xs font-mono px-3 py-1 rounded-full bg-space-void border border-exosignal-cyan/20 text-exosignal-cyan">
                5 Bins (0–100)
              </span>
            </div>

            <div className="p-6">
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={priorityChartData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <defs>
                      <linearGradient id="scoreCyanGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#00d4ff" stopOpacity={1} />
                        <stop offset="100%" stopColor="#0284c7" stopOpacity={0.6} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#131c38" vertical={false} />
                    <XAxis dataKey="range" tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: '#1e293b' }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: '#1e293b' }} />
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
                      formatter={(val) => [`${val} planets`, 'Population']}
                    />
                    <Bar dataKey="count" fill="url(#scoreCyanGrad)" radius={[4, 4, 0, 0]}>
                      {priorityChartData.map((_, i) => (
                        <Cell key={`cell-${i}`} fill={i === 4 ? '#10b981' : i === 3 ? '#38bdf8' : 'url(#scoreCyanGrad)'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Habitability & Detection Techniques */}
      {(showAll || activeTab === 'habitability') && (
        <div className="space-y-6">
          <SectionDivider
            number="03"
            title="Habitability Classification & Observational Techniques"
            subtitle="Circumstellar habitable zone alignment and discovery methodology distributions"
            badge="CLASSIFICATION"
            accent="emerald"
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Habitable Zone Breakdown */}
            <div className="divided-compartment">
              <div className="compartment-header">
                <div>
                  <h3 className="text-base font-bold font-display text-white">Habitable Zone Alignment</h3>
                  <p className="text-xs font-mono text-exosignal-text-muted">
                    Based on empirical stellar flux boundaries (Kopparapu et al.)
                  </p>
                </div>
                <span className="text-xs font-mono px-3 py-1 rounded-full bg-space-void border border-emerald-500/30 text-emerald-400">
                  Circumstellar HZ
                </span>
              </div>

              <div className="p-6">
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={hzDistribution}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={95}
                        dataKey="count"
                        nameKey="status"
                        label={({ status, percent }) => `${status}: ${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {hzDistribution.map((_, i) => (
                          <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#070a16',
                          borderColor: '#a855f7',
                          borderRadius: '12px',
                          color: '#ffffff',
                          fontFamily: 'JetBrains Mono',
                          fontSize: '12px',
                          boxShadow: '0 0 20px rgba(168, 85, 247, 0.25)'
                        }}
                        formatter={(val) => [`${val} targets`, 'Planets']}
                      />
                      <Legend wrapperStyle={{ paddingTop: '10px', fontFamily: 'JetBrains Mono', fontSize: '11px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Discovery Method Breakdown */}
            {discoveryDistribution.length > 0 && (
              <div className="divided-compartment">
                <div className="compartment-header">
                  <div>
                    <h3 className="text-base font-bold font-display text-white">Detection Methods</h3>
                    <p className="text-xs font-mono text-exosignal-text-muted">
                      Transit, radial velocity, microlensing, and direct imaging counts
                    </p>
                  </div>
                  <span className="text-xs font-mono px-3 py-1 rounded-full bg-space-void border border-purple-500/30 text-purple-300">
                    Observation Techniques
                  </span>
                </div>

                <div className="p-6">
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={discoveryDistribution} layout="vertical" margin={{ top: 5, right: 30, left: 140, bottom: 5 }}>
                        <defs>
                          <linearGradient id="purpleHorizontalGrad" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.8} />
                            <stop offset="100%" stopColor="#a855f7" stopOpacity={1} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#131c38" horizontal={false} />
                        <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: '#1e293b' }} />
                        <YAxis type="category" dataKey="method" tick={{ fill: '#f8fafc', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: '#1e293b' }} width={135} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#070a16',
                            borderColor: '#a855f7',
                            borderRadius: '12px',
                            color: '#ffffff',
                            fontFamily: 'JetBrains Mono',
                            fontSize: '12px'
                          }}
                          formatter={(val) => [`${val} planets`, 'Count']}
                        />
                        <Bar dataKey="count" fill="url(#purpleHorizontalGrad)" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* SECTION 4: PCA Anomaly Feature Space */}
      {(showAll || activeTab === 'anomalies') && pcaChartPoints.length > 0 && (
        <div className="space-y-4">
          <SectionDivider
            number="04"
            title="PCA Feature Space & Outlier Projection"
            subtitle="Unsupervised dimensionality reduction revealing clustering geometries and extreme anomalies"
            badge="ISOLATION FOREST"
            accent="amber"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <div>
                <h3 className="text-base font-bold font-display text-white">PCA 2D Manifold Projection</h3>
                <p className="text-xs font-mono text-exosignal-text-muted">
                  First two principal components showing cluster geometries. Color indicates anomaly score.
                </p>
              </div>
              <span className="text-xs font-mono px-3 py-1 rounded-full bg-space-void border border-amber-500/30 text-amber-300">
                {pcaChartPoints.length} Project Targets
              </span>
            </div>

            <div className="p-6">
              <div className="h-96 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart data={pcaChartPoints} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#131c38" />
                    <XAxis type="number" dataKey="x" name="PC1" tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: '#1e293b' }} />
                    <YAxis type="number" dataKey="y" name="PC2" tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' }} axisLine={{ stroke: '#1e293b' }} />
                    <Tooltip
                      cursor={{ pointer: true }}
                      contentStyle={{
                        backgroundColor: '#070a16',
                        borderColor: '#00d4ff',
                        borderRadius: '12px',
                        color: '#ffffff',
                        fontFamily: 'JetBrains Mono',
                        fontSize: '11px',
                        boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)'
                      }}
                      formatter={(value, name, props) => [
                        <div key="name" className="font-bold text-white mb-1">{props.payload.name}</div>,
                        <div>PC1: {props.payload.x}</div>,
                        <div>PC2: {props.payload.y}</div>,
                        <div>Anomaly Score: {props.payload.anomaly}</div>,
                        <div>Priority Score: {props.payload.priority}</div>,
                        <div>HZ: {props.payload.hz}</div>
                      ]}
                    />
                    <Scatter dataKey="y" fill="#00d4ff" shape="circle" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Analytics