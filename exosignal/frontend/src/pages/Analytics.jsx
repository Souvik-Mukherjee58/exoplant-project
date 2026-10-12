import React, { useState, useEffect } from 'react'
import BarChart from '../components/BarChart'
import { Link } from 'react-router-dom'

const Analytics = () => {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Mock API call to backend
    const fetchData = async () => {
      setLoading(true)
      try {
        // Simulate API response
        setTimeout(() => {
          setStats({
            total_planets: 411,
            score_distribution: {
              min: 12.3,
              max: 96.8,
              mean: 52.4,
              median: 48.7
            },
            top_targets: [
              { planet_name: 'Kepler-442 b', target_priority_score: 94.2 },
              { planet_name: 'Kepler-69 c', target_priority_score: 91.8 },
              { planet_name: 'TOI-2136 b', target_priority_score: 87.5 },
              { planet_name: 'TOI-561 b', target_priority_score: 72.3 },
              { planet_name: 'Proxima Centauri b', target_priority_score: 68.9 }
            ],
            anomaly_distribution: {
              min: 0.02,
              max: 0.98,
              mean: 0.34,
              median: 0.28
            }
          })
          setLoading(false)
        }, 500)
      } catch (err) {
        setError('Failed to load analytics data')
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-exosignal-accent"></div>
          <p className="mt-4 text-exosignal-text">Loading analytics data...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-space-darker rounded-lg p-6 text-center">
        <p className="text-exosignal-red">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 bg-exosignal-blue text-white px-4 py-2 rounded hover:bg-exosignal-accent transition"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!stats) {
    return <div className="text-exosignal-text">No analytics data available</div>
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">Analytics & Insights</h1>

      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">System Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Total Targets</p>
            <p className="text-2xl font-bold text-exosignal-accent">{stats.total_planets}</p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Score Range</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {stats.score_distribution.min?.toFixed(1)}–{stats.score_distribution.max?.toFixed(1)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Mean Score</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {stats.score_distribution.mean?.toFixed(1)}
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
            <p className="text-exosignal-text/70 text-sm mb-2">Median Score</p>
            <p className="text-2xl font-bold text-exosignal-accent">
              {stats.score_distribution.median?.toFixed(1)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
          <h2 className="text-xl font-semibold text-exosignal-text mb-4">Priority Score Distribution</h2>
          <BarChart
            data={[
              { range: '0-20', count: 48 },
              { range: '20-40', count: 68 },
              { range: '40-60', count: 92 },
              { range: '60-80', count: 124 },
              { range: '80-100', count: 79 }
            ]}
            labelField="range"
            valueField="count"
            color="bg-exosignal-blue/60"
            title="Exoplanets by Priority Score Range"
            formatValue={(value) => `${value} planets`}
          />
        </div>

        <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
          <h2 className="text-xl font-semibold text-exosignal-text mb-4">HZ Status Breakdown</h2>
          <BarChart
            data={[
              { status: 'Inside HZ', count: 68 },
              { status: 'Near HZ', count: 89 },
              { status: 'Outside HZ', count: 187 },
              { status: 'Insufficient data', count: 67 }
            ]}
            labelField="status"
            valueField="count"
            color="bg-emerald-500/60"
            title="Exoplanets by Habitable Zone Status"
            formatValue={(value) => `${value} planets`}
          />
        </div>
      </div>

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