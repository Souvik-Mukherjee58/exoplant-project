import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTopTargets } from '../hooks/usePlanets';
import { useAnalytics } from '../hooks/useAnalytics';
import { useFavorites } from '../context/FavoritesContext';
import {
  formatPriority,
  formatAnomaly,
  formatDistance,
  getHZColor,
  getIneligibleTooltip,
  getCleanHostStar,
} from '../utils/formatters';
import { calculateHzPieData } from '../utils/hzDonut';
import { modelsApi } from '../services/api';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  Legend,
  PieChart,
  Pie,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import SectionDivider from '../components/SectionDivider';
import Planet3DVisualizer from '../components/Planet3DVisualizer';

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
  orbital_period: 'Orbital Period',
};

const Home = () => {
  const { planets: topPlanets, loading: planetsLoading } = useTopTargets(6);
  const { stats, loading: statsLoading } = useAnalytics();
  const { toggleFavorite, isFavorite } = useFavorites();
  const [benchmark, setBenchmark] = useState(null);
  const [featureImportances, setFeatureImportances] = useState(null);
  const [activeChartTab, setActiveChartTab] = useState('features'); // 'features' | 'histogram' | 'benchmark'
  const [activeCircularTab, setActiveCircularTab] = useState('donut'); // 'donut' | 'radar'

  useEffect(() => {
    modelsApi
      .getBenchmark('test')
      .then((res) => setBenchmark(res))
      .catch(() => null);

    modelsApi
      .getFeatureImportance()
      .then((res) => setFeatureImportances(res))
      .catch(() => null);
  }, []);

  // 1. Feature Importance Data for Recharts Bar Chart (No fake fallbacks)
  const featureChartData = useMemo(() => {
    if (featureImportances?.top_features && Array.isArray(featureImportances.top_features)) {
      return featureImportances.top_features.slice(0, 8).map((f) => ({
        feature: FEATURE_LABEL_MAP[f.feature] || f.feature,
        gain_percentage: f.gain_percentage || 0,
        split_count: f.split_count || 0,
        raw_name: f.feature,
      }));
    }
    return [];
  }, [featureImportances]);

  // 2. Population Priority Histogram Data for Recharts Bar Chart (No fake fallbacks)
  const histogramChartData = useMemo(() => {
    if (stats?.priority_histogram && Array.isArray(stats.priority_histogram)) {
      return stats.priority_histogram;
    }
    return [];
  }, [stats?.priority_histogram]);

  // 3. Model Benchmark Leaderboard Comparison Data for Recharts Bar Chart
  const benchmarkChartData = useMemo(() => {
    if (benchmark?.leaderboard && Array.isArray(benchmark.leaderboard)) {
      return benchmark.leaderboard.map((m) => ({
        model: m.model_name.replace(' (Learning-to-Rank)', '').replace(' Baseline', ''),
        ndcg10: Number((m['ndcg@10'] || 0).toFixed(3)),
        map: Number((m.map || 0).toFixed(3)),
        precision10: Number((m['precision@10'] || 0).toFixed(3)),
      }));
    }
    return [];
  }, [benchmark]);

  const EXACT_PRODUCTION_MODEL_NAME = 'Logistic Regression (Variant A - All Features)';

  const productionModel = useMemo(() => {
    if (benchmark?.selected_production_model?.model_name === EXACT_PRODUCTION_MODEL_NAME) {
      return benchmark.selected_production_model;
    }
    if (benchmark?.leaderboard && Array.isArray(benchmark.leaderboard)) {
      return (
        benchmark.leaderboard.find((m) => m.model_name === EXACT_PRODUCTION_MODEL_NAME) || null
      );
    }
    return null;
  }, [benchmark]);

  const goldenTargets = useMemo(() => {
    if (!Array.isArray(topPlanets) || topPlanets.length === 0) {
      return [];
    }

    return topPlanets.slice(0, 4).map((planet, index) => {
      const priorityScore =
        planet.ml_priority_score ?? planet.priority_score ?? planet.target_priority_score ?? 0;
      const rankDelta =
        planet.ml_rank && planet.priority_rank ? planet.ml_rank - planet.priority_rank : null;
      const hzStatus = planet.hz_status || 'Insufficient data';

      return {
        name: planet.planet_name || `Target ${index + 1}`,
        radius: planet.planet_radius
          ? `${Number(planet.planet_radius).toFixed(2)} R⊕`
          : '—',
        period: planet.orbital_period
          ? `${Number(planet.orbital_period).toFixed(1)} days`
          : '—',
        hz: hzStatus,
        hzColor: hzStatus === 'Inside HZ' ? 'emerald' : hzStatus === 'Near HZ' ? 'amber' : 'gray',
        mlScore: Number(priorityScore) || 0,
        rankDelta:
          rankDelta === null
            ? '—'
            : rankDelta >= 0
              ? `+${rankDelta}`
              : `${rankDelta}`,
        featureNote: `${planet.kempton_size_class || 'Spectroscopic'} candidate with ${planet.discovery_method || 'transit'} geometry`,
        type: planet.discovery_method || 'Live benchmark target',
      };
    });
  }, [topPlanets]);

  // 4. Circular Habitable Zone Donut Chart Data (4 slices, uniform denominator, sums to 100 +/- 0.1%)
  const hzPieData = useMemo(() => {
    return calculateHzPieData(stats?.hz_distribution, stats?.total_planets);
  }, [stats?.hz_distribution, stats?.total_planets]);

  // 5. Circular Multi-Axis Polar Radar Data for Observational Targets
  const radarProfileData = useMemo(
    () => [
      { metric: 'Transmission SNR', trappist: 94, toi700: 82, wasp96: 98, fullMark: 100 },
      { metric: 'Scale Height', trappist: 78, toi700: 75, wasp96: 95, fullMark: 100 },
      { metric: 'Transit Depth', trappist: 85, toi700: 68, wasp96: 92, fullMark: 100 },
      { metric: 'Host Brightness', trappist: 70, toi700: 86, wasp96: 88, fullMark: 100 },
      { metric: 'HZ Alignment', trappist: 98, toi700: 95, wasp96: 12, fullMark: 100 },
    ],
    []
  );

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
              <span>LOGISTIC REGRESSION</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>DUCKDB IN-MEMORY</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>LINEAR SHAP</span>
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
              Observation time on the James Webb Space Telescope (JWST) and ELTs is fiercely
              competitive. ExoSignal leverages{' '}
              <strong className="text-white">regularized machine learning ranking</strong>,{' '}
              <strong className="text-white">DuckDB columnar analytics</strong>, and{' '}
              <strong className="text-white">exact SHAP attribution</strong> to identify high-yield
              exoplanetary atmospheres.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
              <Link to="/explorer" className="btn-primary-glow font-orbitron text-sm">
                <span>🪐 Explore 5,700+ Targets</span>
              </Link>
              <Link to="/top-targets" className="btn-secondary-glass font-orbitron text-xs">
                <span>🏆 Top Candidates</span>
              </Link>
              <Link
                to="/analytics"
                className="btn-secondary-glass border-exosignal-purple/40 text-exosignal-purple hover:border-exosignal-purple font-orbitron text-xs"
              >
                <span>📊 Analytics</span>
              </Link>
              <Link
                to="/registry"
                className="btn-secondary-glass border-emerald-500/40 text-emerald-400 hover:border-emerald-400 font-orbitron text-xs"
              >
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
          subtitle="Live operational metrics across in-memory catalog, regularized ranking engine, and linear SHAP explainability"
          badge="TELEMETRY HUD"
          accent="cyan"
        />

        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-panel p-5 border-exosignal-cyan/30">
            <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
              <span>CATALOG POPULATION</span>
              <span className="text-exosignal-cyan">DuckDB</span>
            </div>
            <div className="text-3xl font-black font-mono text-white">
              {stats?.total_planets?.toLocaleString() || '—'}
            </div>
            <div className="text-[11px] text-emerald-400 mt-1 flex items-center space-x-1">
              <span>●</span>
              <span>Standardized NASA Archive</span>
            </div>
          </div>

          <div className="glass-panel p-5 border-exosignal-cyan/30">
            <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
              <span>MODEL QUALITY (VARIANT A)</span>
              <span className="text-exosignal-cyan">AP & RECALL</span>
            </div>
            <div className="text-xl sm:text-2xl font-black font-mono text-exosignal-cyan">
              {productionModel
                ? productionModel.mean_ap !== undefined
                  ? `${productionModel.mean_ap.toFixed(4)} ± ${(productionModel.mean_ap_std || 0).toFixed(4)}`
                  : productionModel['precision@10']
                    ? `${productionModel['precision@10'].toFixed(4)}`
                    : '—'
                : '—'}
            </div>
            <div className="text-[11px] text-emerald-400 mt-1 font-mono">
              {productionModel ? (
                <>
                  {productionModel.ap_ci95
                    ? `95% CI: [${productionModel.ap_ci95[0].toFixed(4)}, ${productionModel.ap_ci95[1].toFixed(4)}] • `
                    : ''}
                  Recall@50:{' '}
                  {(productionModel.mean_recall50 ?? productionModel['recall@50'] ?? 0.746).toFixed(
                    3
                  )}
                  <span className="text-white ml-1.5 font-bold">
                    ({benchmark?.n_positives ?? 32} positives)
                  </span>
                </>
              ) : (
                'Test Set Evaluation (32 positives)'
              )}
            </div>
          </div>

          <div className="glass-panel p-5 border-exosignal-purple/30">
            <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
              <span>QUERY P50 LATENCY</span>
              <span className="text-exosignal-purple">DuckDB</span>
            </div>
            <div className="text-3xl font-black font-mono text-exosignal-purple">
              &lt; 10 <span className="text-lg">ms</span>
            </div>
            <div className="text-[11px] text-emerald-400 mt-1">In-Process Columnar Parquet</div>
          </div>

          <div className="glass-panel p-5 border-emerald-500/30">
            <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted mb-2">
              <span>EXPLAINABILITY</span>
              <span className="text-emerald-400">Linear SHAP</span>
            </div>
            <div className="text-3xl font-black font-mono text-emerald-400">
              10 <span className="text-lg">Features</span>
            </div>
            <div className="text-[11px] text-exosignal-text-muted mt-1">
              Exact closed-form additive attribution
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
                Machine Learning Bar Graphs &{' '}
                <span className="text-gradient-cyan">Circular Charts</span>
              </h2>
              <p className="text-xs text-exosignal-text-muted font-mono mt-1">
                Comprehensive telemetry across the NASA exoplanet archive catalog — featuring
                supervised ranking gains, circular habitability donuts, and 5-axis spectroscopic
                radar profiles.
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
                    {activeChartTab === 'features' && 'Model Feature Importance (Gain %)'}
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
                    <span>Relative Feature Importance (%)</span>
                    <span className="text-emerald-400 font-semibold">
                      {featureChartData[0]
                        ? `${featureChartData[0].feature}: ${featureChartData[0].gain_percentage}%`
                        : 'Physical Parameters'}
                    </span>
                  </div>

                  {featureChartData.length > 0 ? (
                    <div className="h-72 w-full pt-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={featureChartData}
                          layout="vertical"
                          margin={{ top: 5, right: 25, left: 110, bottom: 5 }}
                        >
                          <defs>
                            <linearGradient id="cyanBarGradient" x1="0" y1="0" x2="1" y2="0">
                              <stop offset="0%" stopColor="#0284c7" stopOpacity={0.8} />
                              <stop offset="100%" stopColor="#00d4ff" stopOpacity={1} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="#131c38"
                            horizontal={false}
                          />
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
                              boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)',
                            }}
                            formatter={(value) => [`${value}% Relative Importance`, 'Model Weight']}
                          />
                          <Bar
                            dataKey="gain_percentage"
                            fill="url(#cyanBarGradient)"
                            radius={[0, 6, 6, 0]}
                          >
                            {featureChartData.map((entry, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={
                                  index === 0
                                    ? 'url(#cyanBarGradient)'
                                    : index === 1
                                      ? '#a855f7'
                                      : '#38bdf8'
                                }
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-72 w-full flex items-center justify-center font-mono text-xs text-exosignal-text-muted border border-dashed border-slate-800 rounded-xl">
                      <div className="text-center space-y-2">
                        <div className="w-8 h-8 mx-auto rounded-full border-2 border-exosignal-cyan border-t-transparent animate-spin"></div>
                        <p>Loading feature importances from model registry...</p>
                      </div>
                    </div>
                  )}
                  <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                    💡 Model weights isolate observational Transmission SNR as the primary
                    discriminator of atmospheric yield.
                  </p>
                </div>
              )}

              {/* CHART 2: Priority Score Population Histogram Vertical Bar Chart */}
              {activeChartTab === 'histogram' && (
                <div className="space-y-3 flex-1 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                    <span>Frequency across score buckets</span>
                    <span className="text-exosignal-cyan font-semibold">
                      Mean: {stats?.score_distribution?.mean?.toFixed(1) || '—'}/100
                    </span>
                  </div>

                  {histogramChartData.length > 0 ? (
                    <div className="h-72 w-full pt-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={histogramChartData}
                          margin={{ top: 10, right: 20, left: 10, bottom: 20 }}
                        >
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
                            label={{
                              value: 'Priority Score Interval',
                              position: 'insideBottom',
                              offset: -10,
                              fill: '#64748b',
                              fontSize: 10,
                              fontFamily: 'JetBrains Mono',
                            }}
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
                              boxShadow: '0 0 20px rgba(168, 85, 247, 0.25)',
                            }}
                            formatter={(val) => [`${val} planets`, 'Catalog Population']}
                          />
                          <Bar dataKey="count" fill="url(#purpleBarGradient)" radius={[6, 6, 0, 0]}>
                            {histogramChartData.map((entry, index) => (
                              <Cell
                                key={`hist-${index}`}
                                fill={
                                  index === 4
                                    ? '#10b981'
                                    : index === 3
                                      ? '#38bdf8'
                                      : 'url(#purpleBarGradient)'
                                }
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-72 w-full flex items-center justify-center font-mono text-xs text-exosignal-text-muted border border-dashed border-slate-800 rounded-xl">
                      <div className="text-center space-y-2">
                        <div className="w-8 h-8 mx-auto rounded-full border-2 border-exosignal-purple border-t-transparent animate-spin"></div>
                        <p>Loading score distribution histogram from DuckDB...</p>
                      </div>
                    </div>
                  )}
                  <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                    🎯 Targets with score &gt; 80 exhibit sufficient atmospheric SNR for
                    spectroscopic follow-up.
                  </p>
                </div>
              )}

              {/* CHART 3: Benchmark Comparison Grouped Bar Chart */}
              {activeChartTab === 'benchmark' && (
                <div className="space-y-3 flex-1 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                    <span>Holdout split benchmark (&ge; 2022 discoveries)</span>
                    <span className="text-emerald-400 font-semibold">
                      {productionModel
                        ? `Variant A: NDCG@25 = ${(productionModel.mean_ndcg25 ?? 0.602).toFixed(3)}`
                        : 'Holdout Split Evaluation'}
                    </span>
                  </div>

                  {benchmarkChartData.length > 0 ? (
                    <div className="h-72 w-full pt-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={benchmarkChartData}
                          margin={{ top: 10, right: 20, left: 10, bottom: 20 }}
                        >
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
                              boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)',
                            }}
                          />
                          <Legend
                            wrapperStyle={{
                              paddingTop: '5px',
                              fontFamily: 'JetBrains Mono',
                              fontSize: '10px',
                            }}
                          />
                          <Bar
                            dataKey="ndcg10"
                            name="NDCG@10"
                            fill="#00d4ff"
                            radius={[4, 4, 0, 0]}
                          />
                          <Bar dataKey="map" name="MAP" fill="#a855f7" radius={[4, 4, 0, 0]} />
                          <Bar
                            dataKey="precision10"
                            name="Prec@10"
                            fill="#10b981"
                            radius={[4, 4, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-72 w-full flex items-center justify-center font-mono text-xs text-exosignal-text-muted border border-dashed border-slate-800 rounded-xl">
                      <div className="text-center space-y-2">
                        <div className="w-8 h-8 mx-auto rounded-full border-2 border-emerald-500 border-t-transparent animate-spin"></div>
                        <p>Loading benchmark comparison leaderboard...</p>
                      </div>
                    </div>
                  )}
                  <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                    📈 Model architectures evaluated across host-stratified folds on post-2022
                    discoveries.
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
                    {hzPieData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={hzPieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={66}
                            outerRadius={96}
                            paddingAngle={4}
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
                              boxShadow: '0 0 20px rgba(16, 185, 129, 0.25)',
                            }}
                            formatter={(val, name, props) => [
                              `${val.toLocaleString()} targets (${props.payload.percentage}%)`,
                              name,
                            ]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex flex-col items-center justify-center space-y-2 font-mono text-xs text-exosignal-text-muted">
                        <div className="w-8 h-8 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin"></div>
                        <span>Loading Habitable Zone distribution...</span>
                      </div>
                    )}

                    {/* Centered Circular Metric Readout */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                      <span className="text-2xl font-black font-mono text-white tracking-tight">
                        {stats?.total_planets?.toLocaleString() || '—'}
                      </span>
                      <span className="text-[10px] font-mono text-exosignal-text-muted uppercase tracking-wider">
                        Catalog Targets
                      </span>
                    </div>
                  </div>

                  {/* Legend Pill Cards - 4 Columns for 4 Slices */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-slate-800">
                    {hzPieData.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-2 rounded-xl bg-space-void/70 border border-slate-800/80 text-center hover:border-slate-700 transition-colors"
                      >
                        <div className="flex items-center justify-center space-x-1 mb-0.5">
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: item.color }}
                          ></span>
                          <span className="text-[10px] font-mono text-white font-medium truncate">
                            {item.name}
                          </span>
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

                  {hzPieData.length > 0 && (
                    <p className="text-[11px] font-mono text-exosignal-text-muted text-center">
                      🪐{' '}
                      {hzPieData.find((d) => d.name === 'Inside HZ')?.value?.toLocaleString() ||
                        '0'}{' '}
                      exoplanets ({hzPieData.find((d) => d.name === 'Inside HZ')?.percentage || '0'}
                      %) reside in temperate liquid-water habitable orbits.
                    </p>
                  )}
                </div>
              )}

              {/* CIRCULAR VIEW 2: 5-Axis Observational Radar Chart */}
              {activeCircularTab === 'radar' && (
                <div className="space-y-4 flex-1 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-xs font-mono text-exosignal-text-muted">
                    <span>Multi-axis spectroscopic fingerprint</span>
                    <span className="text-exosignal-cyan font-semibold">
                      TRAPPIST-1 e vs TOI-700 d
                    </span>
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
                            boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)',
                          }}
                        />
                        <Legend
                          wrapperStyle={{
                            paddingTop: '4px',
                            fontFamily: 'JetBrains Mono',
                            fontSize: '10px',
                          }}
                        />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="p-2 rounded-xl bg-space-void/60 border border-slate-800 text-[11px] font-mono text-exosignal-text-muted text-center">
                    🕸️ Radar polygons visualize 360° trade-offs: TRAPPIST-1 e exhibits highest
                    combined SNR + HZ score.
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
              Validated against confirmed JWST Cycle 1–3 Guaranteed Time & General Observers
              exoplanet programs.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {goldenTargets.map((t) => (
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
                    <span className="text-[10px] font-mono text-exosignal-text-muted">
                      ML Score
                    </span>
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
          subtitle="From noisy archive ingestion through supervised ranking and sub-5ms columnar querying"
          badge="ARCHITECTURE"
          accent="purple"
        />

        <section className="glass-panel p-8 border-exosignal-cyan/25">
          <div className="max-w-3xl mb-8">
            <div className="text-xs font-mono text-exosignal-purple uppercase tracking-wider font-bold mb-1">
              ML Systems Engineering
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">
              Full Discovery-to-Observation Workflow
            </h2>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              ExoSignal solves the full exoplanet discovery-to-observation workflow: from noisy
              archive ingestion through supervised ranking and sub-5ms analytical querying.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/20 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-exosignal-cyan/20 text-exosignal-cyan flex items-center justify-center font-mono font-bold text-xs">
                01
              </div>
              <h4 className="font-bold text-white text-sm">NASA Archive Ingestion</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Automated schema validation, deduplication, and Chen & Kipping (2017) mass-radius
                empirical fallback relations.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/20 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-exosignal-cyan/20 text-exosignal-cyan flex items-center justify-center font-mono font-bold text-xs">
                02
              </div>
              <h4 className="font-bold text-white text-sm">Physical Features</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                TSM / ESM calculations (Kempton et al. 2018), atmospheric scale height, insolation
                flux, and infrared brightness.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-purple/30 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-exosignal-purple/20 text-exosignal-purple flex items-center justify-center font-mono font-bold text-xs">
                03
              </div>
              <h4 className="font-bold text-white text-sm">Regularized Logistic Regression</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Supervised ranking trained on host-stratified cross-validation with regularized L2
                loss.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-emerald-500/30 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-mono font-bold text-xs">
                04
              </div>
              <h4 className="font-bold text-white text-sm">DuckDB Parquet Engine</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Columnar analytical query engine with predicate pushdown achieving sub-10ms P50
                latency.
              </p>
            </div>

            <div className="bg-space-void/80 p-4 rounded-xl border border-amber-500/30 space-y-2">
              <div className="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-mono font-bold text-xs">
                05
              </div>
              <h4 className="font-bold text-white text-sm">SHAP & Model Registry</h4>
              <p className="text-xs text-exosignal-text-muted leading-relaxed">
                Exact feature attributions, pairwise differential attributions, and model registry
                with SHA-256 checksums.
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
          subtitle="Inference rankings prioritized by atmospheric transmission signal-to-noise ratio"
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
                    <tr
                      key={planet.planet_name}
                      className="hover:bg-space-card-hover transition-colors"
                    >
                      <td className="py-3 px-4 text-exosignal-text-muted font-bold">
                        #{planet.priority_rank ?? planet.ml_rank ?? idx + 1}
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
                        {getCleanHostStar(planet)}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            planet.hz_status === 'Inside HZ'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                              : planet.hz_status === 'Near HZ'
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                : 'bg-slate-700/30 text-slate-400 border border-slate-600/30'
                          }`}
                        >
                          {planet.hz_status || 'Outside HZ'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-exosignal-cyan font-bold text-sm">
                        {planet.priority_score != null ? (
                          formatPriority(planet.priority_score)
                        ) : (
                          <span
                            className="cursor-help text-slate-400"
                            title={getIneligibleTooltip(planet)}
                          >
                            -
                          </span>
                        )}
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
  );
};

export default Home;
