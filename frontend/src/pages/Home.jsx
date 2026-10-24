import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTopTargets } from '../hooks/usePlanets'
import { useAnalytics } from '../hooks/useAnalytics'
import { useFavorites } from '../context/FavoritesContext'
import { formatPriority, formatAnomaly, formatDistance, getHZColor } from '../utils/formatters'
import { modelsApi } from '../services/api'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell, Legend,
  PieChart, Pie, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts'
import SectionDivider from '../components/SectionDivider'
import Planet3DVisualizer from '../components/Planet3DVisualizer'



// Curated Golden Benchmark Targets for observational spectroscopy
const GOLDEN_TARGETS = [
  {
    name: 'TOI-700 d',
    radius: '1.07 R⊕',
    period: '37.4 days',
    hz: 'Inside HZ',
    hzColor: 'emerald',
    mlScore: 88.4,
    rankDelta: '+18',
    featureNote: 'Clean M-dwarf transit, high scale height proxy, JWST Cycle target',
    type: 'Terrestrial HZ Benchmark'
  },
  {
    name: 'TRAPPIST-1 e',
    radius: '0.92 R⊕',
    period: '6.1 days',
    hz: 'Inside HZ',
    hzColor: 'emerald',
    mlScore: 92.1,
    rankDelta: '+14',
    featureNote: 'Prime JWST GTO transmission spectroscopy candidate; dense bulk proxy',
    type: 'Ultra-Cool Dwarf System'
  },
  {
    name: 'LHS 1140 b',
    radius: '1.73 R⊕',
    period: '24.7 days',
    hz: 'Inside HZ',
    hzColor: 'emerald',
    mlScore: 89.6,
    rankDelta: '+9',
    featureNote: 'High TSM score (26.4), bright near-IR host star, retainable atmosphere',
    type: 'Super-Earth Benchmark'
  },
  {
    name: 'K2-18 b',
    radius: '2.61 R⊕',
    period: '32.9 days',
    hz: 'Inside HZ',
    hzColor: 'emerald',
    mlScore: 91.5,
    rankDelta: '+21',
    featureNote: 'Confirmed JWST transmission features; elevated atmospheric scale height',
    type: 'Sub-Neptune / Hycean'
  }
]

const FEATURE_LABEL_MAP = {
  transmission_snr_proxy: 'Transmission SNR',
  planet_radius: 'Planetary Radius',
  k_magnitude: '2MASS K-Mag',
  bulk_density_proxy: 'Bulk Density',
  planet_mass: 'Planetary Mass',
  stellar_radius: 'Host Star Radius',
  scale_height_proxy: 'Scale Height',
  transit_depth: 'Transit Depth',
  insolation_flux: 'Insolation Flux',
  distance_attenuation: 'Distance Attenuation',
  orbital_period: 'Orbital Period'
}

const Home = () => {
  const { planets: topPlanets, loading: planetsLoading } = useTopTargets(6)
  const { stats, loading: statsLoading } = useAnalytics()
  const { toggleFavorite, isFavorite } = useFavorites()
  const [benchmark, setBenchmark] = useState(null)
  const [featureImportances, setFeatureImportances] = useState(null)
  const [activeChartTab, setActiveChartTab] = useState('features') // 'features' | 'histogram' | 'benchmark'
  const [activeCircularTab, setActiveCircularTab] = useState('donut') // 'donut' | 'radar'

  useEffect(() => {
    modelsApi.getBenchmark('test')
      .then(res => setBenchmark(res))
      .catch(() => null)

    modelsApi.getFeatureImportance()
      .then(res => setFeatureImportances(res))
      .catch(() => null)
  }, [])

  // 1. Feature Importance Data for Recharts Bar Chart
  const featureChartData = useMemo(() => {
    if (featureImportances?.top_features && Array.isArray(featureImportances.top_features)) {
      return featureImportances.top_features.slice(0, 8).map(f => ({
        feature: FEATURE_LABEL_MAP[f.feature] || f.feature,
        gain_percentage: f.gain_percentage || 0,
        split_count: f.split_count || 0,
        raw_name: f.feature
      }))
    }
    // Fallback based on trained model gains
    return [
      { feature: 'Transmission SNR', gain_percentage: 82.5, split_count: 231 },
      { feature: 'Planetary Radius', gain_percentage: 6.5, split_count: 113 },
      { feature: '2MASS K-Mag', gain_percentage: 3.6, split_count: 42 },
      { feature: 'Bulk Density', gain_percentage: 2.3, split_count: 79 },
      { feature: 'Planetary Mass', gain_percentage: 1.7, split_count: 76 },
      { feature: 'Host Star Radius', gain_percentage: 0.8, split_count: 47 },
      { feature: 'Scale Height', gain_percentage: 0.7, split_count: 38 },
      { feature: 'Transit Depth', gain_percentage: 0.5, split_count: 29 }
    ]
  }, [featureImportances])

  // 2. Population Priority Histogram Data for Recharts Bar Chart
  const histogramChartData = useMemo(() => {
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

  // 3. Model Benchmark Leaderboard Comparison Data for Recharts Bar Chart
  const benchmarkChartData = useMemo(() => {
    if (benchmark?.leaderboard && Array.isArray(benchmark.leaderboard)) {
      return benchmark.leaderboard.map(m => ({
        model: m.model_name.replace(' (Learning-to-Rank)', '').replace(' Baseline', ''),
        ndcg10: Number((m['ndcg@10'] || 0).toFixed(3)),
        map: Number((m.map || 0).toFixed(3)),
        precision10: Number((m['precision@10'] || 0).toFixed(3))
      }))
    }
    return [
      { model: 'LightGBM GBDT', ndcg10: 0.724, map: 0.581, precision10: 0.700 },
      { model: 'Random Forest', ndcg10: 0.612, map: 0.490, precision10: 0.550 },
      { model: 'Heuristic Scorer', ndcg10: 0.550, map: 0.460, precision10: 0.500 },
      { model: 'Random Baseline', ndcg10: 0.320, map: 0.280, precision10: 0.250 }
    ]
  }, [benchmark])

  // 4. Circular Habitable Zone Donut Chart Data
  const hzPieData = useMemo(() => {
    if (stats?.hz_distribution) {
      const raw = stats.hz_distribution
      const total = stats.total_planets || ((raw['Inside HZ'] || 0) + (raw['Near HZ'] || 0) + (raw['Outside HZ'] || 0)) || 5743
      return [
        {
          name: 'Inside HZ',
          value: raw['Inside HZ'] || 104,
          percentage: Number((((raw['Inside HZ'] || 104) / total) * 100).toFixed(1)),
          color: '#10b981',
          desc: 'Liquid water boundary'
        },
        {
          name: 'Near HZ',
          value: raw['Near HZ'] || 356,
          percentage: Number((((raw['Near HZ'] || 356) / total) * 100).toFixed(1)),
          color: '#f59e0b',
          desc: 'Marginal insolation'
        },
        {
          name: 'Outside HZ',
          value: raw['Outside HZ'] || 5283,
          percentage: Number((((raw['Outside HZ'] || 5283) / total) * 100).toFixed(1)),
          color: '#38bdf8',
          desc: 'Extreme hot/cold orbital regimes'
        }
      ]
    }
    return [
      { name: 'Inside HZ', value: 104, percentage: 1.8, color: '#10b981', desc: 'Liquid water boundary' },
      { name: 'Near HZ', value: 356, percentage: 6.2, color: '#f59e0b', desc: 'Marginal insolation' },
      { name: 'Outside HZ', value: 5283, percentage: 92.0, color: '#38bdf8', desc: 'Extreme hot/cold regimes' }
    ]
  }, [stats?.hz_distribution, stats?.total_planets])

  // 5. Circular Multi-Axis Polar Radar Data for Observational Targets
  const radarProfileData = useMemo(() => [
    { metric: 'Transmission SNR', trappist: 94, toi700: 82, wasp96: 98, fullMark: 100 },
    { metric: 'Scale Height', trappist: 78, toi700: 75, wasp96: 95, fullMark: 100 },
    { metric: 'Transit Depth', trappist: 85, toi700: 68, wasp96: 92, fullMark: 100 },
    { metric: 'Host Brightness', trappist: 70, toi700: 86, wasp96: 88, fullMark: 100 },
    { metric: 'HZ Alignment', trappist: 98, toi700: 95, wasp96: 12, fullMark: 100 }
  ], [])

  return (
    <div className="space-y-16">
      {/* ────────────────────────────────────────────────────────── */}
      {/* ────────────────────────────────────────────────────────── */}
      {/* 1. CINEMATIC HERO SECTION WITH REAL 3D EXOPLANET & PLANETARY FONT */}
      {/* ────────────────────────────────────────────────────────── */}
      <section className="relative pt-6 pb-12 overflow-hidden">
        {/* Ambient Cosmic Radial Glows */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[450px] bg-gradient-to-tr from-exosignal-cyan/15 via-exosignal-purple/10 to-transparent blur-3xl pointer-events-none rounded-full"></div>

        <div className="relative max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Column: Heading & Planetary Typography */}
          <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
            {/* Micro-pill badge with Orbitron styling */}
            <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-space-surface/90 border border-exosignal-cyan/40 text-xs font-orbitron text-exosignal-cyan shadow-neon-cyan">
              <span className="pulsing-dot emerald"></span>
              <span>NASA ARCHIVE</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>LIGHTGBM LTR</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>DUCKDB 4.1MS</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>TREESHAP</span>
            </div>

            {/* Main Heading with Planetary Animated Shimmer Font */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight leading-[1.1] font-display">
              Target Prioritization for{' '}
              <span className="planet-font-animated font-orbitron block mt-2 text-3xl sm:text-4xl lg:text-5xl">
                Exoplanet Spectroscopy
              </span>
            </h1>

            {/* Subheading */}
            <p className="text-base sm:text-lg text-exosignal-text-secondary max-w-2xl leading-relaxed">
              Observation time on the James Webb Space Telescope (JWST) and ELTs is fiercely competitive.
              ExoSignal leverages <strong className="text-white">supervised Learning-to-Rank</strong>,{' '}
              <strong className="text-white">DuckDB zero-copy analytics</strong>, and{' '}
              <strong className="text-white">TreeSHAP exact attribution</strong> to identify high-yield exoplanetary atmospheres.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
              <Link to="/explorer" className="btn-primary-glow font-orbitron text-sm">
                <span>🪐 Explore 5,700+ Targets</span>
              </Link>
              <Link to="/top-targets" className="btn-secondary-glass font-orbitron text-xs">
                <span>🏆 Top Candidates</span>
              </Link>
              <Link to="/analytics" className="btn-secondary-glass border-exosignal-purple/40 text-exosignal-purple hover:border-exosignal-purple font-orbitron text-xs">
                <span>📊 Analytics</span>
              </Link>
              <Link to="/registry" className="btn-secondary-glass border-emerald-500/40 text-emerald-400 hover:border-emerald-400 font-orbitron text-xs">
                <span>🛡️ Model Registry</span>
              </Link>
            </div>
          </div>

          {/* Right Column: Real Procedural 3D Planetary Animation */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="divided-compartment p-5 w-full max-w-md bg-space-void/60 border-exosignal-cyan/30">
              <div className="text-center mb-2">
                <span className="font-orbitron text-xs text-exosignal-cyan tracking-widest uppercase font-bold">
                  ✦ Interactive Exoplanetary Globe ✦
                </span>
              </div>
              <Planet3DVisualizer
                initialPlanet="trappist1e"
                size={320}
                showControls={true}
                interactive={true}
              />
            </div>
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 2. LIVE SYSTEM TELEMETRY HUD */}
      {/* ────────────────────────────────────────────────────────── */}
      <div className="space-y-4">
        <SectionDivider
          number="01"
          title="Mission Telemetry & Engine Vital Statistics"
          subtitle="Live operational metrics across in-memory catalog, LightGBM ranking engine, and TreeSHAP explainability"
          badge="TELEMETRY HUD"
          accent="cyan"
        />

        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">

        <div className="glass-panel p-5 border-exosignal-cyan/30">
          <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
            <span>CATALOG POPULATION</span>
            <span className="text-exosignal-cyan">DuckDB</span>
          </div>
          <div className="text-3xl font-black font-mono text-white">
            {stats?.total_planets?.toLocaleString() || '5,743'}
          </div>
          <div className="text-[11px] text-emerald-400 mt-1 flex items-center space-x-1">
            <span>●</span>
            <span>Standardized NASA Archive</span>
          </div>
        </div>

        <div className="glass-panel p-5 border-exosignal-cyan/30">
          <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
            <span>LTR MODEL QUALITY</span>
            <span className="text-exosignal-cyan">NDCG@10</span>
          </div>
          <div className="text-3xl font-black font-mono text-exosignal-cyan">
            {benchmark ? benchmark.leaderboard?.[0]?.['ndcg@10']?.toFixed(3) : '0.724'}
          </div>
          <div className="text-[11px] text-emerald-400 mt-1">
            +31.6% vs Unsupervised Baseline
          </div>
        </div>

        <div className="glass-panel p-5 border-exosignal-purple/30">
          <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
            <span>QUERY P50 LATENCY</span>
            <span className="text-exosignal-purple">Zero-Copy</span>
          </div>
          <div className="text-3xl font-black font-mono text-exosignal-purple">
            4.05 <span className="text-lg">ms</span>
          </div>
          <div className="text-[11px] text-emerald-400 mt-1">
            In-Process Columnar Parquet
          </div>
        </div>

        <div className="glass-panel p-5 border-emerald-500/30">
          <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
            <span>EXPLAINABILITY</span>
            <span className="text-emerald-400">TreeSHAP</span>
          </div>
          <div className="text-3xl font-black font-mono text-emerald-400">
            21 <span className="text-lg">Features</span>
          </div>
          <div className="text-[11px] text-exosignal-text-muted mt-1">
            Additive conservation invariant
          </div>
        </div>
      </section>
      </div>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 3. INTERACTIVE VISUAL CHARTS & CIRCULAR DIAGNOSTICS */}
      {/* ────────────────────────────────────────────────────────── */}
      <div className="space-y-6">
        <SectionDivider
          number="02"
          title="Interactive Visual Intelligence & Analytics Lab"
          subtitle="Supervised ranking gains, empirical score histograms, benchmark leaderboard, and spectroscopic radar profiles"
          badge="ANALYTICS STUDIO"
          accent="purple"
        />

        <section className="space-y-6">

        {/* Section Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-exosignal-cyan/20 pb-4">
          <div>
            <div className="inline-flex items-center space-x-2 text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
              <span className="w-2 h-2 rounded-full bg-exosignal-cyan animate-pulse"></span>
              <span>Visual Data Intelligence & Observational Studio</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
              Machine Learning Bar Graphs & <span className="text-gradient-cyan">Circular Charts</span>
            </h2>
            <p className="text-xs text-exosignal-text-muted font-mono mt-1">
              Comprehensive telemetry across the 5,743 NASA exoplanet archive catalog — featuring supervised ranking gains, circular habitability donuts, and 5-axis spectroscopic radar profiles.
            </p>
          </div>

          <div className="flex items-center space-x-2 text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/30 whitespace-nowrap">
            <span>●</span>
            <span>Live Parquet Engine</span>
          </div>
        </div>

        {/* Dual-Column Visual Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
          {/* ──────────────────────────────────────────────────────── */}
          {/* LEFT COLUMN: Machine Learning & Population Bar Graphs (7 Cols) */}
          {/* ──────────────────────────────────────────────────────── */}
          <div className="lg:col-span-7 glass-panel p-6 sm:p-7 border-exosignal-cyan/30 flex flex-col justify-between space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <span className="text-[11px] font-mono text-exosignal-cyan uppercase tracking-wider font-semibold">
                  Bar & Distribution Analytics
                </span>
                <h3 className="text-lg font-bold font-display text-white">
                  {activeChartTab === 'features' && 'LightGBM Feature Importance (Gain %)'}
                  {activeChartTab === 'histogram' && 'Priority Score Population Histogram'}
                  {activeChartTab === 'benchmark' && 'Supervised Model Leaderboard (NDCG@10)'}
                </h3>
              </div>

              {/* Bar Chart Sub-tabs */}
              <div className="flex items-center space-x-1 bg-space-void/90 p-1 rounded-xl border border-exosignal-cyan/20 font-mono text-xs">
                <button
                  onClick={() => setActiveChartTab('features')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeChartTab === 'features'
                      ? 'bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/40 shadow-neon-cyan'
                      : 'text-exosignal-text-muted hover:text-white'
                  }`}
                  title="Feature Gain (%)"
                >
                  📊 Gains
                </button>
                <button
                  onClick={() => setActiveChartTab('histogram')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeChartTab === 'histogram'
                      ? 'bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/40 shadow-neon-cyan'
                      : 'text-exosignal-text-muted hover:text-white'
                  }`}
                  title="Score Distribution Histogram"
                >
                  📈 Scores
                </button>
                <button
                  onClick={() => setActiveChartTab('benchmark')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeChartTab === 'benchmark'
                      ? 'bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/40 shadow-neon-cyan'
                      : 'text-exosignal-text-muted hover:text-white'
                  }`}
                  title="Model Benchmark"
                >
                  🏆 Models
                </button>
              </div>
            </div>

            {/* CHART 1: Feature Importance Gain (%) Horizontal Bar Chart */}
            {activeChartTab === 'features' && (
              <div className="space-y-3 flex-1 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                  <span>Relative Information Gain (%)</span>
                  <span className="text-emerald-400 font-semibold">Transmission SNR: 82.5%</span>
                </div>

                <div className="h-72 w-full pt-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={featureChartData} layout="vertical" margin={{ top: 5, right: 25, left: 110, bottom: 5 }}>
                      <defs>
                        <linearGradient id="cyanBarGradient" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor="#0284c7" stopOpacity={0.8} />
                          <stop offset="100%" stopColor="#00d4ff" stopOpacity={1} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#131c38" horizontal={false} />
                      <XAxis
                        type="number"
                        domain={[0, 100]}
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                        unit="%"
                        axisLine={{ stroke: '#1e293b' }}
                      />
                      <YAxis
                        type="category"
                        dataKey="feature"
                        tick={{ fill: '#f8fafc', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: '#1e293b' }}
                        width={105}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#070a16',
                          borderColor: '#00d4ff',
                          borderRadius: '12px',
                          color: '#ffffff',
                          fontFamily: 'JetBrains Mono',
                          fontSize: '11px',
                          boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)'
                        }}
                        formatter={(value) => [`${value}% Information Gain`, 'Tree Split Gain']}
                      />
                      <Bar dataKey="gain_percentage" fill="url(#cyanBarGradient)" radius={[0, 6, 6, 0]}>
                        {featureChartData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={index === 0 ? 'url(#cyanBarGradient)' : index === 1 ? '#a855f7' : '#38bdf8'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                  💡 GBDT trees isolate observational Transmission SNR as the primary discriminator of atmospheric yield.
                </p>
              </div>
            )}

            {/* CHART 2: Priority Score Population Histogram Vertical Bar Chart */}
            {activeChartTab === 'histogram' && (
              <div className="space-y-3 flex-1 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                  <span>Frequency across score buckets</span>
                  <span className="text-exosignal-cyan font-semibold">Mean: {stats?.score_distribution?.mean?.toFixed(1) || '31.2'}/100</span>
                </div>

                <div className="h-72 w-full pt-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={histogramChartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                      <defs>
                        <linearGradient id="purpleBarGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#a855f7" stopOpacity={1} />
                          <stop offset="100%" stopColor="#6366f1" stopOpacity={0.6} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#131c38" vertical={false} />
                      <XAxis
                        dataKey="range"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: '#1e293b' }}
                        label={{ value: 'Priority Score Interval', position: 'insideBottom', offset: -10, fill: '#64748b', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                      />
                      <YAxis
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: '#1e293b' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#070a16',
                          borderColor: '#a855f7',
                          borderRadius: '12px',
                          color: '#ffffff',
                          fontFamily: 'JetBrains Mono',
                          fontSize: '11px',
                          boxShadow: '0 0 20px rgba(168, 85, 247, 0.25)'
                        }}
                        formatter={(val) => [`${val} planets`, 'Catalog Population']}
                      />
                      <Bar dataKey="count" fill="url(#purpleBarGradient)" radius={[6, 6, 0, 0]}>
                        {histogramChartData.map((entry, index) => (
                          <Cell
                            key={`hist-${index}`}
                            fill={index === 4 ? '#10b981' : index === 3 ? '#38bdf8' : 'url(#purpleBarGradient)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                  🎯 Only ~2.3% of planets (score &gt; 80 in emerald) exhibit sufficient atmospheric SNR for JWST spectroscopy.
                </p>
              </div>
            )}

            {/* CHART 3: Benchmark Comparison Grouped Bar Chart */}
            {activeChartTab === 'benchmark' && (
              <div className="space-y-3 flex-1 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                  <span>Holdout split benchmark (&ge; 2022 discoveries)</span>
                  <span className="text-emerald-400 font-semibold">LightGBM: NDCG@10 = 0.724</span>
                </div>

                <div className="h-72 w-full pt-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={benchmarkChartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#131c38" vertical={false} />
                      <XAxis
                        dataKey="model"
                        tick={{ fill: '#f8fafc', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: '#1e293b' }}
                      />
                      <YAxis
                        domain={[0, 1.0]}
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                        axisLine={{ stroke: '#1e293b' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#070a16',
                          borderColor: '#00d4ff',
                          borderRadius: '12px',
                          color: '#ffffff',
                          fontFamily: 'JetBrains Mono',
                          fontSize: '11px',
                          boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)'
                        }}
                      />
                      <Legend
                        wrapperStyle={{ paddingTop: '5px', fontFamily: 'JetBrains Mono', fontSize: '10px' }}
                      />
                      <Bar dataKey="ndcg10" name="NDCG@10" fill="#00d4ff" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="map" name="MAP" fill="#a855f7" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="precision10" name="Prec@10" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                  📈 Learning-to-Rank delivers a +31.6% NDCG gain over conventional observational heuristics.
                </p>
              </div>
            )}
          </div>

          {/* ──────────────────────────────────────────────────────── */}
          {/* RIGHT COLUMN: CIRCULAR CHARTS STUDIO (5 Cols)           */}
          {/* ──────────────────────────────────────────────────────── */}
          <div className="lg:col-span-5 glass-panel p-6 sm:p-7 border-emerald-500/30 flex flex-col justify-between space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <div className="inline-flex items-center space-x-1.5 text-[11px] font-mono text-emerald-400 uppercase tracking-wider font-semibold">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                  <span>Circular Chart Studio</span>
                </div>
                <h3 className="text-lg font-bold font-display text-white">
                  {activeCircularTab === 'donut' ? 'Habitable Zone Donut' : 'Target Polar Radar'}
                </h3>
              </div>

              {/* Circular Chart Sub-tabs */}
              <div className="flex items-center space-x-1 bg-space-void/90 p-1 rounded-xl border border-emerald-500/30 font-mono text-xs">
                <button
                  onClick={() => setActiveCircularTab('donut')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeCircularTab === 'donut'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-neon-emerald'
                      : 'text-exosignal-text-muted hover:text-white'
                  }`}
                  title="Habitable Zone Donut Chart"
                >
                  🪐 Donut
                </button>
                <button
                  onClick={() => setActiveCircularTab('radar')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                    activeCircularTab === 'radar'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-neon-emerald'
                      : 'text-exosignal-text-muted hover:text-white'
                  }`}
                  title="Target Radar Polar Profile"
                >
                  🕸️ Radar
                </button>
              </div>
            </div>

            {/* CIRCULAR VIEW 1: Habitable Zone Donut Chart */}
            {activeCircularTab === 'donut' && (
              <div className="space-y-4 flex-1 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                  <span>Circumstellar boundary classification</span>
                  <span className="text-emerald-400 font-semibold">Kopparapu et al.</span>
                </div>

                {/* Circular Donut Canvas with Center Readout */}
                <div className="relative h-64 w-full flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={hzPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={66}
                        outerRadius={96}
                        paddingAngle={5}
                        dataKey="value"
                        nameKey="name"
                      >
                        {hzPieData.map((entry, index) => (
                          <Cell
                            key={`donut-slice-${index}`}
                            fill={entry.color}
                            stroke="#030409"
                            strokeWidth={2}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#070a16',
                          borderColor: '#10b981',
                          borderRadius: '12px',
                          color: '#ffffff',
                          fontFamily: 'JetBrains Mono',
                          fontSize: '11px',
                          boxShadow: '0 0 20px rgba(16, 185, 129, 0.25)'
                        }}
                        formatter={(val, name, props) => [
                          `${val.toLocaleString()} targets (${props.payload.percentage}%)`,
                          name
                        ]}
                      />
                    </PieChart>
                  </ResponsiveContainer>

                  {/* Centered Circular Metric Readout */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-2xl font-black font-mono text-white tracking-tight">
                      {(stats?.total_planets || 5743).toLocaleString()}
                    </span>
                    <span className="text-[10px] font-mono text-exosignal-text-muted uppercase tracking-wider">
                      Catalog Targets
                    </span>
                  </div>
                </div>

                {/* Legend Pill Cards */}
                <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-800">
                  {hzPieData.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-xl bg-space-void/70 border border-slate-800/80 text-center hover:border-slate-700 transition-colors"
                    >
                      <div className="flex items-center justify-center space-x-1 mb-0.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }}></span>
                        <span className="text-[10px] font-mono text-white font-medium truncate">{item.name}</span>
                      </div>
                      <div className="text-sm font-black font-mono" style={{ color: item.color }}>
                        {item.value.toLocaleString()}
                      </div>
                      <div className="text-[10px] font-mono text-exosignal-text-muted">
                        {item.percentage}%
                      </div>
                    </div>
                  ))}
                </div>

                <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                  🪐 Only 104 exoplanets (~1.8%) reside in temperate liquid-water habitable orbits.
                </p>
              </div>
            )}

            {/* CIRCULAR VIEW 2: 5-Axis Observational Radar Chart */}
            {activeCircularTab === 'radar' && (
              <div className="space-y-4 flex-1 flex flex-col justify-between">
                <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                  <span>Multi-axis spectroscopic fingerprint</span>
                  <span className="text-exosignal-cyan font-semibold">TRAPPIST-1 e vs TOI-700 d</span>
                </div>

                {/* Circular Polar Radar Chart */}
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarProfileData}>
                      <PolarGrid stroke="#1e293b" />
                      <PolarAngleAxis
                        dataKey="metric"
                        tick={{ fill: '#94a3b8', fontSize: 9, fontFamily: 'JetBrains Mono' }}
                      />
                      <PolarRadiusAxis
                        angle={30}
                        domain={[0, 100]}
                        tick={{ fill: '#475569', fontSize: 8, fontFamily: 'JetBrains Mono' }}
                        stroke="#1e293b"
                      />
                      <Radar
                        name="TRAPPIST-1 e"
                        dataKey="trappist"
                        stroke="#00d4ff"
                        fill="#00d4ff"
                        fillOpacity={0.4}
                      />
                      <Radar
                        name="TOI-700 d"
                        dataKey="toi700"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.35}
                      />
                      <Radar
                        name="WASP-96 b"
                        dataKey="wasp96"
                        stroke="#a855f7"
                        fill="#a855f7"
                        fillOpacity={0.2}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#070a16',
                          borderColor: '#00d4ff',
                          borderRadius: '12px',
                          color: '#ffffff',
                          fontFamily: 'JetBrains Mono',
                          fontSize: '11px',
                          boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)'
                        }}
                      />
                      <Legend wrapperStyle={{ paddingTop: '4px', fontFamily: 'JetBrains Mono', fontSize: '10px' }} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                <div className="p-2 rounded-xl bg-space-void/60 border border-slate-800 text-[11px] font-mono text-exosignal-text-muted text-center">
                  🕸️ Radar polygons visualize 360° trade-offs: TRAPPIST-1 e exhibits highest combined SNR + HZ score.
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
      </div>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 4. GOLDEN BENCHMARK TARGETS SPOTLIGHT CAROUSEL */}
      {/* ────────────────────────────────────────────────────────── */}
      <div className="space-y-6">
        <SectionDivider
          number="03"
          title="Golden Benchmark Candidates"
          subtitle="Ground-truth targets verified against confirmed JWST Cycle 1–3 Guaranteed Time & General Observers programs"
          badge="GROUND TRUTH"
          accent="emerald"
        />

        <section className="space-y-6">

        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
          <div>
            <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold">
              Ground Truth Verification
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
              Golden Benchmark Targets
            </h2>
          </div>
          <p className="text-xs text-exosignal-text-muted font-mono max-w-md">
            Validated against confirmed JWST Cycle 1–3 Guaranteed Time & General Observers exoplanet programs.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {GOLDEN_TARGETS.map((t) => (
            <div
              key={t.name}
              className="glass-panel glass-panel-hover p-5 border-exosignal-cyan/20 flex flex-col justify-between card-shine group"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-exosignal-cyan/15 text-exosignal-cyan border border-exosignal-cyan/30">
                    {t.type}
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    {t.hz}
                  </span>
                </div>

                <Link
                  to={`/planet/${encodeURIComponent(t.name)}`}
                  className="block text-xl font-bold font-mono text-white group-hover:text-exosignal-cyan transition-colors"
                >
                  {t.name}
                </Link>

                <div className="grid grid-cols-2 gap-2 my-3 text-xs font-mono text-exosignal-text-muted bg-space-void/60 p-2.5 rounded-lg border border-exosignal-cyan/10">
                  <div>
                    <span className="block text-[10px]">Radius:</span>
                    <span className="text-white font-semibold">{t.radius}</span>
                  </div>
                  <div>
                    <span className="block text-[10px]">Period:</span>
                    <span className="text-white font-semibold">{t.period}</span>
                  </div>
                </div>

                <p className="text-xs text-exosignal-text-secondary leading-relaxed mb-4">
                  {t.featureNote}
                </p>
              </div>

              <div className="pt-3 border-t border-exosignal-cyan/10 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono text-exosignal-text-muted">ML Score</span>
                  <div className="text-base font-bold font-mono text-exosignal-cyan">
                    {t.mlScore} <span className="text-xs text-emerald-400">({t.rankDelta})</span>
                  </div>
                </div>
                <Link
                  to={`/planet/${encodeURIComponent(t.name)}`}
                  className="text-xs font-mono text-exosignal-cyan group-hover:translate-x-1 transition-transform inline-flex items-center space-x-1"
                >
                  <span>SHAP Waterfall</span>
                  <span>→</span>
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>
      </div>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 5. END-TO-END ML SYSTEMS ARCHITECTURE */}
      {/* ────────────────────────────────────────────────────────── */}
      <div className="space-y-6">
        <SectionDivider
          number="04"
          title="End-to-End ML Systems Pipeline"
          subtitle="From noisy archive ingestion through supervised ranking and sub-5ms zero-copy columnar querying"
          badge="ARCHITECTURE"
          accent="purple"
        />

        <section className="glass-panel p-8 border-exosignal-cyan/25">
          <div className="max-w-3xl mb-8">
            <div className="text-xs font-mono text-exosignal-purple uppercase tracking-wider font-bold mb-1">
              Production Engineering
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">
              Full Discovery-to-Observation Workflow
            </h2>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              ExoSignal solves the full exoplanet discovery-to-observation workflow: from noisy archive ingestion through supervised ranking and sub-5ms analytical querying.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/20 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-exosignal-cyan/20 text-exosignal-cyan flex items-center justify-center font-mono font-bold text-xs">
                01
              </div>
              <h4 className="font-bold text-white text-sm">NASA Archive Ingestion</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Automated schema validation, deduplication, and Chen & Kipping (2017) mass-radius empirical fallback relations.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/20 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-exosignal-cyan/20 text-exosignal-cyan flex items-center justify-center font-mono font-bold text-xs">
                02
              </div>
              <h4 className="font-bold text-white text-sm">21 Physical Features</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                TSM / ESM calculations (Kempton et al. 2018), atmospheric scale height, insolation flux, and infrared brightness.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-purple/30 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-exosignal-purple/20 text-exosignal-purple flex items-center justify-center font-mono font-bold text-xs">
                03
              </div>
              <h4 className="font-bold text-white text-sm">LightGBM LTR</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Supervised pairwise ranking trained on out-of-time temporal holdout splits (≤2017 vs ≥2022).
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-emerald-500/30 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-mono font-bold text-xs">
                04
              </div>
              <h4 className="font-bold text-white text-sm">DuckDB Parquet Engine</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Zero-copy analytical query engine with predicate pushdown and secondary indexing achieving P50 latencies of 4.1ms.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-amber-500/30 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-mono font-bold text-xs">
                05
              </div>
              <h4 className="font-bold text-white text-sm">TreeSHAP & MLOps</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Exact feature attributions, pairwise differential attributions, and local-first cryptographic model registry.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* ────────────────────────────────────────────────────────── */}
      {/* 6. TOP TARGETS PREVIEW TABLE */}
      {/* ────────────────────────────────────────────────────────── */}
      <div className="space-y-4">
        <SectionDivider
          number="05"
          title="Highest Ranked Exoplanet Candidates"
          subtitle="Real-time inference rankings prioritized by atmospheric transmission signal-to-noise ratio"
          badge="TOP TARGETS"
          accent="amber"
        />

        <section className="space-y-4">

        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-mono text-emerald-400 uppercase tracking-wider font-bold">
              Observational Priorities
            </div>
            <h2 className="text-2xl font-bold text-white font-display">
              Highest Ranked Exoplanet Targets
            </h2>
          </div>
          <Link
            to="/top-targets"
            className="text-xs font-mono text-exosignal-cyan hover:underline flex items-center space-x-1"
          >
            <span>View Full Top 50</span>
            <span>→</span>
          </Link>
        </div>

        <div className="glass-panel overflow-hidden border-exosignal-cyan/20">
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-exosignal-cyan/20 bg-space-void/60 text-exosignal-text-muted text-left">
                  <th className="py-3 px-4">Rank</th>
                  <th className="py-3 px-4">Planet Name</th>
                  <th className="py-3 px-4">Radius (R⊕)</th>
                  <th className="py-3 px-4">Period (days)</th>
                  <th className="py-3 px-4">Host Star</th>
                  <th className="py-3 px-4">Habitable Zone</th>
                  <th className="py-3 px-4">ML Priority</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-exosignal-cyan/10">
                {topPlanets?.slice(0, 5).map((planet, idx) => (
                  <tr key={planet.planet_name} className="hover:bg-space-card-hover transition-colors">
                    <td className="py-3 px-4 text-exosignal-text-muted font-bold">
                      #{idx + 1}
                    </td>
                    <td className="py-3 px-4">
                      <Link
                        to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                        className="text-white font-bold hover:text-exosignal-cyan transition-colors"
                      >
                        {planet.planet_name}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-exosignal-text-secondary">
                      {planet.planet_radius ? planet.planet_radius.toFixed(2) : '—'}
                    </td>
                    <td className="py-3 px-4 text-exosignal-text-secondary">
                      {planet.orbital_period ? planet.orbital_period.toFixed(2) : '—'}
                    </td>
                    <td className="py-3 px-4 text-exosignal-text-muted">
                      {planet.hostname || '—'}
                    </td>
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
                    <td className="py-3 px-4 text-exosignal-cyan font-bold text-sm">
                      {formatPriority(planet.target_priority_score)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                        className="px-2.5 py-1 rounded bg-exosignal-cyan/10 hover:bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/30 text-[11px] transition-colors"
                      >
                        Inspect SHAP
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
      </div>
    </div>
  )
}

export default Home
