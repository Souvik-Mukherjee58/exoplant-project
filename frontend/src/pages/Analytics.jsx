import React, { useMemo } from 'react'
import { useAnalytics } from '../hooks/useAnalytics'
import { useAnomalyPCA } from '../hooks/useAnalytics'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ScatterChart, Scatter
} from 'recharts'
import { formatPriority, formatAnomaly } from '../utils/formatters'

const COLORS = ['#00d4ff', '#10b981', '#eab308', '#9933ff', '#ef4444', '#6b7280', '#0099cc']

const Analytics = () => {
  const { stats, loading: statsLoading, error, refetch } = useAnalytics()
  const { data: pcaData, loading: pcaLoading } = useAnomalyPCA()

  // Real priority score histogram calculated from dataset (no synthetic distributions)
  const priorityChartData = useMemo(() => {
    if (stats?.priority_histogram && Array.isArray(stats.priority_histogram)) {
      return stats.priority_histogram
    }
    return [
      { range: '0-20', count: 0 },
      { range: '20-40', count: 0 },
      { range: '40-60', count: 0 },
      { range: '60-80', count: 0 },
      { range: '80-100', count: 0 }
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
  }, [stats?.discovery_method_distribution])

  // PCA visualization points
  const pcaChartPoints = useMemo(() => {
    if (!pcaData?.planets || !Array.isArray(pcaData.planets)) return []
    return pcaData.planets.map((name, i) => ({
      name,
      x: pcaData.pca_x?.[i] ?? 0,
      y: pcaData.pca_y?.[i] ?? 0,
      anomaly: pcaData.anomaly_score?.[i] ?? 0,
      priority: pcaData.target_priority_score?.[i] ?? 0,
      hz: pcaData.hz_status?.[i] ?? 'Unknown'
    }))
  }, [pcaData])

  if (statsLoading || pcaLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-exosignal-accent"></div>
          <p className="mt-4 text-exosignal-text">Loading target analytics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-space-darker rounded-lg border border-red-500/30 p-8 text-center max-w-xl mx-auto">
          <p className="text-exosignal-red font-medium mb-4">{error}</p>
          <button
            onClick={() => refetch()}
            className="bg-exosignal-blue text-space-dark font-medium px-5 py-2 rounded hover:bg-exosignal-accent transition"
          >
            Retry Analysis
          </button>
        </div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="p-8 text-center text-exosignal-text/70">
        No target analytics data available.
      </div>
    )
  }

  const scoreStats = stats.score_distribution || {}
  const anomalyStats = stats.anomaly_distribution || {}

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-exosignal-text">Target Prioritization Analytics</h1>
        <p className="text-exosignal-text/70 text-sm mt-1">
          Population-level distributions, habitable zone representation, and anomaly projections.
        </p>
      </div>

      {/* Summary Score Statistics */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
        <h2 className="text-lg font-semibold text-exosignal-text mb-4">Target Population Overview</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Total Targets</p>
            <p className="text-2xl font-bold text-exosignal-accent">{stats.total_planets}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Score Range</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(scoreStats.min)}–{formatPriority(scoreStats.max)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Mean Priority</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(scoreStats.mean)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Median Priority</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(scoreStats.median)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Standard Dev</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(scoreStats.std)}
            </p>
          </div>
        </div>
      </div>

      {/* Distribution Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Empirical Priority Score Distribution */}
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 flex flex-col">
          <h2 className="text-lg font-semibold text-exosignal-text mb-2">Priority Score Distribution</h2>
          <p className="text-xs text-exosignal-text/60 mb-4">Empirical histogram of target priority scores.</p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priorityChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis dataKey="range" tick={{ fill: '#a0a0a0', fontSize: 12 }} axisLine={{ stroke: '#333' }} />
                <YAxis tick={{ fill: '#a0a0a0', fontSize: 12 }} axisLine={{ stroke: '#333' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#05050a', border: '1px solid #00d4ff', borderRadius: '8px', color: '#fff' }}
                  formatter={(val) => [val, 'planets']}
                />
                <Bar dataKey="count" fill="#00d4ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Habitable Zone Breakdown */}
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 flex flex-col">
          <h2 className="text-lg font-semibold text-exosignal-text mb-2">Habitable Zone Breakdown</h2>
          <p className="text-xs text-exosignal-text/60 mb-4">Empirical distribution across circumstellar HZ classifications.</p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={hzDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
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
                  contentStyle={{ backgroundColor: '#05050a', border: '1px solid #00d4ff', borderRadius: '8px', color: '#fff' }}
                  formatter={(val) => [val, 'targets']}
                />
                <Legend wrapperStyle={{ paddingTop: '15px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Discovery Method Breakdown */}
      {discoveryDistribution.length > 0 && (
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8 flex flex-col">
          <h2 className="text-lg font-semibold text-exosignal-text mb-2">Discovery Methods</h2>
          <p className="text-xs text-exosignal-text/60 mb-4">Breakdown of detection techniques in the dataset.</p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={discoveryDistribution} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis type="number" tick={{ fill: '#a0a0a0', fontSize: 12 }} axisLine={{ stroke: '#333' }} />
                <YAxis type="category" dataKey="method" tick={{ fill: '#a0a0a0', fontSize: 12 }} axisLine={{ stroke: '#333' }} width={140} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#05050a', border: '1px solid #00d4ff', borderRadius: '8px', color: '#fff' }}
                  formatter={(val) => [val, 'planets']}
                />
                <Bar dataKey="count" fill="#0099cc" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* PCA Anomaly Feature Space */}
      {pcaChartPoints.length > 0 && (
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8 flex flex-col">
          <h2 className="text-lg font-semibold text-exosignal-text mb-2">PCA Feature Space & Anomaly Projection</h2>
          <p className="text-xs text-exosignal-text/70 mb-4">
            First two principal components showing exoplanet clustering. Color indicates outlier score.
          </p>
          <div className="h-96 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart data={pcaChartPoints}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis type="number" dataKey="x" name="PC1" tick={{ fill: '#a0a0a0', fontSize: 12 }} axisLine={{ stroke: '#333' }} />
                <YAxis type="number" dataKey="y" name="PC2" tick={{ fill: '#a0a0a0', fontSize: 12 }} axisLine={{ stroke: '#333' }} />
                <Tooltip
                  cursor={{ pointer: true }}
                  contentStyle={{ backgroundColor: '#05050a', border: '1px solid #00d4ff', borderRadius: '8px', color: '#fff' }}
                  formatter={(value, name, props) => [
                    <div key="name" style={{ fontWeight: 'bold' }}>{props.payload.name}</div>,
                    <div>PC1: {props.payload.x.toFixed(2)}</div>,
                    <div>PC2: {props.payload.y.toFixed(2)}</div>,
                    <div>Anomaly Score: {props.payload.anomaly.toFixed(3)}</div>,
                    <div>Priority Score: {props.payload.priority.toFixed(1)}</div>,
                    <div>HZ Status: {props.payload.hz}</div>
                  ]}
                />
                <Scatter
                  dataKey="y"
                  fill="#00d4ff"
                  shape="circle"
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Anomaly Statistics */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
        <h2 className="text-lg font-semibold text-exosignal-text mb-4">Unsupervised Anomaly Metrics</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Min Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(anomalyStats.min)}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Max Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(anomalyStats.max)}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Mean Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(anomalyStats.mean)}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <p className="text-exosignal-text/70 text-xs uppercase mb-1">Median Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(anomalyStats.median)}</p>
          </div>
        </div>
      </div>

      {/* Methodology Notes */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
        <h2 className="text-lg font-semibold text-exosignal-text mb-3">Analytical Methodology</h2>
        <ul className="space-y-2 text-exosignal-text/80 text-sm">
          <li>• <strong>Target Priority Score:</strong> Multi-parameter composite evaluating planetary physical viability, host star characteristics, and observational accessibility.</li>
          <li>• <strong>Habitable Zone:</strong> Assessed relative to stellar effective temperature and insolation flux boundaries.</li>
          <li>• <strong>Anomaly Detection:</strong> Evaluated via unsupervised ensemble (Isolation Forest) across key physical dimensions.</li>
          <li>• <strong>Observational Efficiency:</strong> Designed to prioritize high-yield candidates for follow-up spectroscopic characterization.</li>
        </ul>
      </div>
    </div>
  )
}

export default Analytics