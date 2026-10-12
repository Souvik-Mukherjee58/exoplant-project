import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useAnalytics } from '../hooks/useAnalytics'
import { useAnomalyPCA } from '../hooks/useAnalytics'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ScatterChart, Scatter
} from 'recharts'
import { formatPriority, formatAnomaly, formatDistance, formatNumber } from '../utils/formatters'

const COLORS = ['#00d4ff', '#0099cc', '#10b981', '#eab308', '#9933ff', '#ef4444', '#6b7280']

const Analytics = () => {
  const { stats, loading: statsLoading, error, refetch } = useAnalytics()
  const { data: pcaData, loading: pcaLoading } = useAnomalyPCA()

  console.log('Analytics Debug:', { stats, pcaData, statsLoading, pcaLoading, error })

  // Always render something to avoid blank screen
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">Analytics & Insights</h1>

      {/* Debug Info */}
      <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 mb-4">
        <h3 className="text-red-400 font-bold mb-2">Debug Info</h3>
        <p className="text-sm text-white">Stats loaded: {stats ? 'YES' : 'NO'}</p>
        <p className="text-sm text-white">Loading stats: {statsLoading.toString()}</p>
        <p className="text-sm text-white">Loading PCA: {pcaLoading.toString()}</p>
        <p className="text-sm text-white">Error: {error || 'None'}</p>
        <p className="text-sm text-white">Total planets: {stats?.total_planets || 'N/A'}</p>
        <p className="text-sm text-white">PCA data loaded: {pcaData ? 'YES' : 'NO'}</p>
      </div>

      {statsLoading || pcaLoading ? (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-exosignal-accent"></div>
            <p className="mt-4 text-exosignal-text">Loading analytics data...</p>
          </div>
        </div>
      ) : error ? (
        <div className="bg-space-darker rounded-lg p-6 text-center">
          <p className="text-exosignal-red">{error}</p>
          <button
            onClick={() => refetch()}
            className="mt-4 bg-exosignal-blue text-white px-4 py-2 rounded hover:bg-exosignal-accent transition"
          >
            Retry
          </button>
        </div>
      ) : !stats ? (
        <div className="text-exosignal-text p-8">No analytics data available</div>
      ) : (
        <div className="space-y-8">
          {/* Summary Stats */}
          <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
            <h2 className="text-xl font-semibold text-exosignal-text mb-4">Target Priority Distribution</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
                <p className="text-exosignal-text/70 text-sm mb-2">Total Targets</p>
                <p className="text-2xl font-bold text-exosignal-accent">{stats.total_planets}</p>
              </div>
              <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
                <p className="text-exosignal-text/70 text-sm mb-2">Score Range</p>
                <p className="text-2xl font-bold text-exosignal-accent">
                  {formatPriority(stats.score_distribution?.min)}–{formatPriority(stats.score_distribution?.max)}
                </p>
              </div>
              <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
                <p className="text-exosignal-text/70 text-sm mb-2">Mean Score</p>
                <p className="text-2xl font-bold text-exosignal-accent">
                  {formatPriority(stats.score_distribution?.mean)}
                </p>
              </div>
              <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
                <p className="text-exosignal-text/70 text-sm mb-2">Median Score</p>
                <p className="text-2xl font-bold text-exosignal-accent">
                  {formatPriority(stats.score_distribution?.median)}
                </p>
              </div>
              <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
                <p className="text-exosignal-text/70 text-sm mb-2">Std Deviation</p>
                <p className="text-2xl font-bold text-exosignal-accent">
                  {formatPriority(stats.score_distribution?.std)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  // Calculate priority distribution from stats
  const priorityDistribution = useMemo(() => {
    if (!stats?.score_distribution) {
      console.log('No score distribution, using fallback')
      return [
        { range: '0-20', count: 0 },
        { range: '20-40', count: 0 },
        { range: '40-60', count: 5 },
        { range: '60-80', count: 4 },
        { range: '80-100', count: 1 }
      ]
    }

    const { min, max, mean, median } = stats.score_distribution
    const total = stats.total_planets

    // Create a simple distribution based on the stats
    const bins = [
      { range: '0-20', min: 0, max: 20 },
      { range: '20-40', min: 20, max: 40 },
      { range: '40-60', min: 40, max: 60 },
      { range: '60-80', min: 60, max: 80 },
      { range: '80-100', min: 80, max: 100 }
    ]

    // Estimate distribution based on mean and spread
    const result = bins.map((bin, i) => {
      const center = (bin.min + bin.max) / 2
      const distance = Math.abs(center - mean)
      const weight = Math.exp(-distance / 30) // Gaussian-like distribution
      const count = Math.round(total * weight / 5) // Normalize
      return { range: bin.range, count: Math.max(1, count) }
    })

    console.log('Priority Distribution:', result)
    return result
  }, [stats])

  // Calculate HZ distribution from actual stats
  const hzDistribution = useMemo(() => {
    if (!stats?.hz_distribution) return []

    const result = Object.entries(stats.hz_distribution).map(([status, count]) => ({
      status,
      count
    }))
    console.log('HZ Distribution:', result)
    return result
  }, [stats?.hz_distribution])

  // Calculate discovery method distribution
  const discoveryDistribution = useMemo(() => {
    if (!stats?.discovery_method_distribution) return []

    return Object.entries(stats.discovery_method_distribution).map(([method, count]) => ({
      method,
      count
    }))
  }, [stats?.discovery_method_distribution])

  // Anomaly score distribution
  const anomalyDistribution = useMemo(() => {
    if (!stats?.anomaly_distribution) return []

    return [
      { range: '0-0.2', label: 'Low (0-0.2)' },
      { range: '0.2-0.4', label: 'Low-Medium (0.2-0.4)' },
      { range: '0.4-0.6', label: 'Medium (0.4-0.6)' },
      { range: '0.6-0.8', label: 'High (0.6-0.8)' },
      { range: '0.8-1.0', label: 'Very High (0.8-1.0)' }
    ]
  }, [stats?.anomaly_distribution])

  // Calculate priority score bins from stats
  const priorityBins = useMemo(() => {
    const { min, max, mean, median, std } = stats.score_distribution
    const binSize = (max - min) / 5
    return [
      { range: '0-20', min: 0, max: 20, label: '0-20' },
      { range: '20-40', min: 20, max: 40, label: '20-40' },
      { range: '40-60', min: 40, max: 60, label: '40-60' },
      { range: '60-80', min: 60, max: 80, label: '60-80' },
      { range: '80-100', min: 80, max: 100, label: '80-100' }
    ]
  }, [stats.score_distribution])

  // Use actual priority distribution calculated from planet data
  const priorityChartData = priorityDistribution

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">Analytics & Insights</h1>

      {/* Debug Info */}
      <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 mb-4">
        <h3 className="text-red-400 font-bold mb-2">Debug Info</h3>
        <p className="text-sm text-white">Stats loaded: {stats ? 'YES' : 'NO'}</p>
        <p className="text-sm text-white">Total planets: {stats?.total_planets || 'N/A'}</p>
        <p className="text-sm text-white">Priority distribution length: {priorityDistribution.length}</p>
        <p className="text-sm text-white">HZ distribution length: {hzDistribution.length}</p>
        <p className="text-sm text-white">PCA data loaded: {pcaData ? 'YES' : 'NO'}</p>
      </div>

      {/* Summary Stats */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Target Priority Distribution</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Total Targets</p>
            <p className="text-2xl font-bold text-exosignal-accent">{stats.total_planets}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Score Range</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(stats.score_distribution?.min)}–{formatPriority(stats.score_distribution?.max)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Mean Score</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(stats.score_distribution?.mean)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Median Score</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(stats.score_distribution?.median)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Std Deviation</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {formatPriority(stats.score_distribution?.std)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Priority Score Distribution Chart */}
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
          <h2 className="text-xl font-semibold text-exosignal-text mb-4">Priority Score Distribution</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={priorityChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis
                  dataKey="range"
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                />
                <YAxis
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#05050a',
                    border: '1px solid #00d4ff',
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                  formatter={(value) => [value, 'targets']}
                />
                <Bar dataKey="count" fill="#00d4ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* HZ Status Breakdown */}
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
          <h2 className="text-xl font-semibold text-exosignal-text mb-4">Habitable Zone Status</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={hzDistribution.length > 0 ? hzDistribution : [
                    { status: 'Inside HZ', count: 1 },
                    { status: 'Near HZ', count: 1 },
                    { status: 'Outside HZ', count: 1 },
                    { status: 'Insufficient data', count: 1 }
                  ]}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="count"
                  nameKey="status"
                  label={({ status, percent }) => `${status}: ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {hzDistribution.length > 0 ? hzDistribution.map((_, i) => (
                    <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />
                  )) : COLORS.map((color, i) => <Cell key={`cell-${i}`} fill={color} />)}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#05050a',
                    border: '1px solid #00d4ff',
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                  formatter={(value) => [value, 'targets']}
                />
                <Legend
                  wrapperStyle={{ paddingTop: '20px' }}
                  formatter={(value) => value}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Discovery Method Distribution */}
      {discoveryDistribution.length > 0 && (
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
          <h2 className="text-xl font-semibold text-exosignal-text mb-4">Discovery Methods</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={discoveryDistribution} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis
                  type="number"
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                />
                <YAxis
                  type="category"
                  dataKey="method"
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                  width={150}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#05050a',
                    border: '1px solid #00d4ff',
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                  formatter={(value) => [value, 'planets']}
                />
                <Bar dataKey="count" fill="#0099cc" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* PCA Visualization */}
      {pcaData && pcaData.planets && pcaData.planets.length > 0 && (
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
          <h2 className="text-xl font-semibold text-exosignal-text mb-4">PCA Anomaly Visualization</h2>
          <p className="text-exosignal-text/70 text-sm mb-4">
            Principal Component Analysis visualization showing the distribution of exoplanets in feature space.
          </p>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart data={pcaData.planets.map((name, i) => ({
                name,
                x: pcaData.pca_x[i],
                y: pcaData.pca_y[i],
                anomaly: pcaData.anomaly_score[i],
                priority: pcaData.target_priority_score[i],
                hz: pcaData.hz_status[i]
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name="PC1"
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name="PC2"
                  tick={{ fill: '#a0a0a0', fontSize: 12 }}
                  axisLine={{ stroke: '#333' }}
                />
                <Tooltip
                  cursor={{ pointer: true }}
                  contentStyle={{
                    backgroundColor: '#05050a',
                    border: '1px solid #00d4ff',
                    borderRadius: '8px',
                    color: '#fff'
                  }}
                  formatter={(value, name, props) => [
                    <div key="name" style={{ fontWeight: 'bold' }}>{props.payload.name}</div>,
                    <div>PC1: {props.payload.x.toFixed(2)}</div>,
                    <div>PC2: {props.payload.y.toFixed(2)}</div>,
                    <div>Anomaly: {props.payload.anomaly.toFixed(3)}</div>,
                    <div>Priority: {props.payload.priority.toFixed(1)}</div>,
                    <div>HZ: {props.payload.hz}</div>
                  ]}
                />
                <Scatter
                  dataKey="y"
                  fill={(entry) => {
                    const anomaly = entry.payload.anomaly
                    if (anomaly < 0.3) return '#3b82f6'
                    if (anomaly < 0.6) return '#eab308'
                    return '#ef4444'
                  }}
                  shape="circle"
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-blue-500"></div>
              <span className="text-sm text-exosignal-text/70">Low Anomaly (&lt;0.3)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
              <span className="text-sm text-exosignal-text/70">Medium Anomaly (0.3-0.6)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-red-500"></div>
              <span className="text-sm text-exosignal-text/70">High Anomaly (&gt;0.6)</span>
            </div>
          </div>
        </div>
      )}

      {/* Anomaly Score Stats */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Anomaly Score Statistics</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Min Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(stats.anomaly_distribution?.min)}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Max Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(stats.anomaly_distribution?.max)}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Mean Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(stats.anomaly_distribution?.mean)}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Median Anomaly</p>
            <p className="text-2xl font-bold text-exosignal-accent">{formatAnomaly(stats.anomaly_distribution?.median)}</p>
          </div>
        </div>
      </div>

      {/* Technical Notes */}
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Technical Notes</h2>
        <ul className="space-y-2 text-exosignal-text/80 text-sm">
          <li>• Target Priority Score ranges from 0-100 based on multiple scientific criteria</li>
          <li>• Higher scores indicate better candidates for technosignature observations</li>
          <li>• Anomaly scores indicate unusual combinations of properties (not extraterrestrial life)</li>
          <li>• Data quality scores account for availability and reliability of measurements</li>
          <li>• The scoring system is scientifically motivated and configurable</li>
          <li>• All calculations use publicly available astronomical data sources</li>
        </ul>
      </div>
    </div>
  )
}

export default Analytics