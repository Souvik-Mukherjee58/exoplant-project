import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { planetsApi } from '../services/api';
import { useTopTargets } from '../hooks/usePlanets';
import { useFavorites } from '../context/FavoritesContext';
import {
  formatDistance,
  formatRadius,
  formatPeriod,
  formatPriority,
  formatRawScore,
  getCleanHostStar,
} from '../utils/formatters';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import SectionDivider from '../components/SectionDivider';

const TopTargets = () => {
  const [activeTab, setActiveTab] = useState('unobserved'); // 'unobserved' | 'validation'
  const [limit, setLimit] = useState(25);
  const [includeObserved, setIncludeObserved] = useState(false);
  const { toggleFavorite, isFavorite } = useFavorites();

  // Candidate top targets (defaults to unobserved, toggled to all eligible)
  const {
    planets: candidateTargets,
    loading: loadingCandidates,
    error: errorCandidates,
  } = useTopTargets(limit, !includeObserved);

  // Validation known JWST targets (OOF evaluation)
  const [knownTargets, setKnownTargets] = useState([]);
  const [loadingKnown, setLoadingKnown] = useState(false);
  const [errorKnown, setErrorKnown] = useState(null);

  const fetchKnownTargets = useCallback(async () => {
    setLoadingKnown(true);
    setErrorKnown(null);
    try {
      const data = await planetsApi.getKnownTargets();
      setKnownTargets(data || []);
    } catch (err) {
      console.error('Failed to load known targets:', err);
      setErrorKnown('Failed to load known JWST targets');
    } finally {
      setLoadingKnown(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'validation' && knownTargets.length === 0) {
      fetchKnownTargets();
    }
  }, [activeTab, knownTargets.length, fetchKnownTargets]);

  // Current view dataset
  const activePlanets = useMemo(() => {
    if (activeTab === 'validation') {
      return knownTargets.slice(0, limit);
    }
    return candidateTargets?.slice(0, limit) || [];
  }, [activeTab, knownTargets, candidateTargets, limit]);

  const loading = activeTab === 'validation' ? loadingKnown : loadingCandidates;
  const error = activeTab === 'validation' ? errorKnown : errorCandidates;

  const podium = activePlanets.slice(0, 3);

  // Top 10 chart data
  const top10ChartData = useMemo(() => {
    if (!activePlanets || activePlanets.length === 0) return [];
    return activePlanets.slice(0, 10).map((p, idx) => {
      const rankNum =
        activeTab === 'validation'
          ? p.oof_ml_rank ?? idx + 1
          : includeObserved
            ? p.priority_rank ?? idx + 1
            : p.unobserved_rank ?? p.priority_rank ?? idx + 1;
      const tsmVal = p.tsm != null ? Number(p.tsm.toFixed(1)) : null;
      const isExtrapolated = Number(p.planet_radius) > 10.0;
      const tsmThresh =
        isExtrapolated || p.tsm_threshold == null ? null : Number(p.tsm_threshold.toFixed(1));
      return {
        name: p.planet_name,
        rank: `#${rankNum}`,
        tsm: tsmVal,
        threshold: tsmThresh,
        isExtrapolated,
        anomaly: p.anomaly_score != null ? Number((p.anomaly_score * 100).toFixed(1)) : null,
        percentile: p.percentile_rank ?? null,
      };
    });
  }, [activePlanets, activeTab, includeObserved]);

  const renderKemptonThreshold = (planet) => {
    const radius = Number(planet.planet_radius);
    if (!isNaN(radius) && radius > 10.0) {
      return (
        <span className="text-amber-400 italic text-[11px]">
          outside Kempton (2018) size classes — extrapolated
        </span>
      );
    }
    const threshold = planet.tsm_threshold;
    if (threshold == null) {
      return (
        <span className="text-slate-400 italic text-[11px]">size-class threshold unavailable</span>
      );
    }
    if (planet.tsm == null) {
      return <span className="text-slate-400 italic text-[11px]">TSM not computable</span>;
    }
    const passes = planet.tsm >= threshold;
    return (
      <span className={passes ? 'text-emerald-400 font-bold' : 'text-slate-400'}>
        ≥ {threshold} ({passes ? 'Passes' : 'Under'})
      </span>
    );
  };

  return (
    <div className="space-y-10">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-exosignal-cyan/20 pb-6">
        <div>
          <div className="text-xs font-mono text-amber-400 uppercase tracking-wider font-bold mb-1">
            Prioritization Leaderboard
          </div>
          <h1 className="text-3xl font-black text-white font-display">
            {activeTab === 'validation'
              ? 'Labelled JWST Targets: Out-Of-Fold Ranks'
              : 'Top Atmospheric Spectroscopy Candidates'}
          </h1>
          <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
            {activeTab === 'validation'
              ? 'Planets labelled as JWST targets, scored out-of-fold (grouped by host star): no planet is scored by a model trained on its own system. The labels are not human-verified.'
              : 'Planets that our incomplete, unverified label set does not list as JWST targets, ranked by regularized logistic regression, with Kempton et al. (2018) TSM context. Some may already have been observed.'}
          </p>
        </div>

        {/* Limit Selector */}
        <div className="flex items-center space-x-2 font-mono text-xs">
          <span className="text-exosignal-text-muted">Display Top:</span>
          {[10, 25, 50].map((num) => (
            <button
              key={num}
              onClick={() => setLimit(num)}
              aria-label={`Display top ${num} targets`}
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

      {/* View Switcher Tabs */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-2 bg-space-void/90 rounded-2xl border border-exosignal-cyan/20">
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setActiveTab('unobserved')}
            className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition-all ${
              activeTab === 'unobserved'
                ? 'bg-gradient-to-r from-exosignal-cyan/20 to-blue-500/20 text-white border border-exosignal-cyan shadow-neon-cyan'
                : 'text-exosignal-text-muted hover:text-white hover:bg-slate-800/40'
            }`}
          >
            <span>🔭 Not Labelled As Targets</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-mono">
              Model Rank
            </span>
          </button>

          <button
            onClick={() => setActiveTab('validation')}
            className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition-all ${
              activeTab === 'validation'
                ? 'bg-gradient-to-r from-purple-500/20 to-amber-500/20 text-white border border-purple-400 shadow-neon-emerald'
                : 'text-exosignal-text-muted hover:text-white hover:bg-slate-800/40'
            }`}
          >
            <span>🔬 Labelled JWST Targets</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/40 font-mono">
              Out-of-Fold
            </span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3 px-3">
          {activeTab === 'unobserved' && (
            <label className="flex items-center space-x-2 text-xs font-mono text-slate-300 cursor-pointer select-none px-3 py-1.5 rounded-xl bg-space-void border border-slate-700 hover:border-exosignal-cyan transition">
              <input
                type="checkbox"
                checked={includeObserved}
                onChange={(e) => setIncludeObserved(e.target.checked)}
                className="rounded border-slate-700 text-exosignal-cyan focus:ring-0 cursor-pointer"
                data-testid="toggle-include-observed"
              />
              <span>Include planets labelled as JWST targets</span>
            </label>
          )}

          <div className="text-[11px] font-mono text-exosignal-text-muted">
            {activeTab === 'unobserved' ? (
              <span className={includeObserved ? 'text-cyan-400' : 'text-emerald-400'}>
                {includeObserved
                  ? '● One ranking, including labelled planets (out-of-fold scores)'
                  : '● Labelled planets are left out'}
              </span>
            ) : (
              <span className="text-purple-300">
                ● 5-fold StratifiedGroupKFold, grouped by host star
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Explanatory Banner for Validation */}
      {activeTab === 'validation' && (
        <div className="glass-panel p-4 rounded-xl border border-purple-500/30 bg-purple-950/10 text-xs font-mono text-purple-200 flex items-start space-x-3">
          <span className="text-lg">🛡️</span>
          <div>
            <div className="font-bold text-white mb-0.5">How These Scores Are Computed</div>
            Each score shown here comes from a model that was fitted without any planet of the same
            host star (
            <code className="text-exosignal-cyan">StratifiedGroupKFold(n=5, group=hostname)</code>).
            The labels themselves are not human-verified, so these ranks are provisional.
          </div>
        </div>
      )}

      {/* Top 3 Podium Cards (hidden on phones: the first three leaderboard cards show the same planets) */}
      {!loading && podium.length >= 3 && (
        <div className="hidden md:block space-y-4">
          <SectionDivider
            number="01"
            title={
              activeTab === 'validation'
                ? 'Labelled JWST Targets: First Three'
                : 'Highest Ranked: First Three'
            }
            subtitle={
              activeTab === 'validation'
                ? 'Top 3 planets labelled as JWST targets (labels not human-verified), by out-of-fold rank'
                : 'Top 3 planets not labelled as JWST targets, by model rank. The label set is incomplete'
            }
            badge={activeTab === 'validation' ? 'LABELLED (OUT-OF-FOLD)' : 'FIRST THREE'}
            accent={activeTab === 'validation' ? 'purple' : 'amber'}
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {podium.map((planet, idx) => {
              const isFirst = idx === 0;
              const medal = isFirst ? '🥇 First' : idx === 1 ? '🥈 Second' : '🥉 Third';
              const borderGlow = isFirst
                ? 'border-amber-400/50 shadow-neon-emerald'
                : idx === 1
                  ? 'border-slate-300/40'
                  : 'border-amber-700/40';
              const isFav = isFavorite(planet.planet_name);
              const displayRank =
                activeTab === 'validation'
                  ? planet.oof_ml_rank ?? idx + 1
                  : includeObserved
                    ? planet.priority_rank ?? idx + 1
                    : planet.unobserved_rank ?? planet.priority_rank ?? idx + 1;
              const currentScore =
                activeTab === 'validation'
                  ? planet.oof_priority_score ?? planet.priority_score
                  : planet.priority_score ?? planet.ml_priority_score;

              return (
                <div
                  key={planet.planet_name}
                  className={`glass-panel p-6 border ${borderGlow} relative overflow-hidden flex flex-col justify-between card-shine`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span
                        className={`text-[11px] font-mono font-bold uppercase px-2.5 py-0.5 rounded-full ${
                          isFirst
                            ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                            : 'bg-space-void text-slate-300 border border-slate-700'
                        }`}
                      >
                        {medal} · #{displayRank}
                      </span>
                      <button
                        type="button"
                        onClick={() => toggleFavorite(planet)}
                        aria-label={
                          isFav
                            ? `Remove ${planet.planet_name} from the watchlist`
                            : `Add ${planet.planet_name} to the watchlist`
                        }
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
                      Host Star: {getCleanHostStar(planet)}
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-space-void/70 p-3 rounded-xl border border-exosignal-cyan/15 mb-4">
                      <div>
                        <span className="text-[10px] text-exosignal-text-muted block">Radius</span>
                        <span className="text-white font-bold">
                          {formatRadius(planet.planet_radius)}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-exosignal-text-muted block">
                          Orbital Period
                        </span>
                        <span className="text-white font-bold">
                          {formatPeriod(planet.orbital_period)}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-exosignal-text-muted block">
                          Distance
                        </span>
                        <span className="text-white font-bold">
                          {formatDistance(planet.distance)}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-exosignal-text-muted block">
                          Size Class
                        </span>
                        <span className="text-exosignal-cyan font-bold truncate block">
                          {planet.kempton_size_class || 'Terrestrial'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Percentile Rank & TSM Context */}
                  <div className="pt-3 border-t border-exosignal-cyan/15 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-mono text-exosignal-text-muted uppercase">
                        Percentile Rank
                      </span>
                      <span
                        className="px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 cursor-help"
                        title={`Raw score: ${formatRawScore(currentScore)}`}
                      >
                        {planet.percentile_rank_string || 'Percentile not available'}
                      </span>
                    </div>

                    <div className="bg-space-void/60 p-2.5 rounded-lg border border-slate-700/60 font-mono text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-exosignal-text-muted text-[11px]">TSM Metric:</span>
                        <span className="font-bold text-amber-300">
                          {planet.tsm != null ? planet.tsm.toFixed(1) : '—'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2 mt-1 text-[10px]">
                        <span className="text-exosignal-text-muted">Kempton Threshold:</span>
                        {renderKemptonThreshold(planet)}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <span
                        className="text-[10px] font-mono text-exosignal-text-muted cursor-help"
                        title={`Raw score: ${formatRawScore(currentScore)}`}
                      >
                        Score:{' '}
                        <span className="text-white font-bold">{formatPriority(currentScore)}</span>
                      </span>
                      <Link
                        to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                        className="btn-primary-glow text-xs py-1.5 px-3"
                      >
                        SHAP Waterfall
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Comparative Bar Graph */}
      {!loading && top10ChartData.length > 0 && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="Top 10 Transmission Spectroscopy Metric (TSM) vs Kempton Thresholds"
            subtitle="The TSM of each planet and the cutoff that Kempton et al. (2018) suggest for its size class; not a feasibility study"
            badge="TSM"
            accent="cyan"
          />

          <div className="divided-compartment p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-exosignal-cyan/15 pb-3 gap-2">
              <div>
                <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
                  Transmission Spectroscopy Metric
                </div>
                <h3 className="text-xl font-bold font-display text-white">TSM of the First Ten</h3>
              </div>
              <span className="text-xs font-mono text-amber-400">
                ● TSM and the cutoff suggested by Kempton et al. (2018)
              </span>
            </div>

            <div className="h-72 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={top10ChartData}
                  margin={{ top: 10, right: 30, left: 10, bottom: 25 }}
                >
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
                      boxShadow: '0 0 20px rgba(0, 212, 255, 0.25)',
                    }}
                  />
                  <Legend
                    wrapperStyle={{
                      paddingTop: '15px',
                      fontFamily: 'JetBrains Mono',
                      fontSize: '11px',
                    }}
                  />
                  <Bar dataKey="tsm" name="TSM" fill="url(#cyanGradient)" radius={[4, 4, 0, 0]} />
                  <Bar
                    dataKey="threshold"
                    name="Kempton et al. (2018) cutoff"
                    fill="url(#amberGradient)"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Leaderboard Table */}
      <div className="space-y-4">
        <SectionDivider
          number="03"
          title={
            activeTab === 'validation'
              ? 'Labelled JWST Targets'
              : 'Atmospheric Spectroscopy Leaderboard'
          }
          subtitle={
            activeTab === 'validation'
              ? 'Out-of-fold ranks and TSM of planets labelled as JWST targets'
              : 'Planets not labelled as JWST targets, by model rank, with percentile and Kempton cutoff'
          }
          badge={`${activePlanets?.length || 0} TARGETS LOADED`}
          accent={activeTab === 'validation' ? 'purple' : 'cyan'}
        />

        <div className="divided-compartment overflow-hidden">
          <div className="compartment-header text-xs font-mono flex items-center justify-between">
            <span className="text-exosignal-text-secondary font-bold">
              {activeTab === 'validation'
                ? `Labelled planets (${activePlanets?.length || 0})`
                : `Planets not labelled as JWST targets (${activePlanets?.length || 0})`}
            </span>
            <span className={activeTab === 'validation' ? 'text-purple-400' : 'text-emerald-400'}>
              {activeTab === 'validation' ? '● Out-of-fold scores' : '● Labelled planets left out'}
            </span>
          </div>

          {/* Cards on small screens: the 11-column table does not fit a phone */}
          {!loading && !error && (
            <ol className="md:hidden divide-y divide-exosignal-cyan/10">
              {activePlanets.map((planet, index) => {
                const pRank =
                  activeTab === 'validation'
                    ? planet.oof_ml_rank ?? index + 1
                    : includeObserved
                      ? planet.priority_rank ?? index + 1
                      : planet.unobserved_rank ?? planet.priority_rank ?? index + 1;
                const currentScore =
                  activeTab === 'validation'
                    ? planet.oof_priority_score ?? planet.priority_score
                    : planet.priority_score ?? planet.ml_priority_score;
                const isFav = isFavorite(planet.planet_name);
                return (
                  <li key={planet.planet_name} className="px-4 py-3 space-y-1">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="font-mono min-w-0 truncate">
                        <span className="font-bold text-amber-400">#{pRank}</span>
                        <span className="text-exosignal-text-muted">
                          {' '}
                          · {getCleanHostStar(planet)}
                        </span>
                      </span>
                      <span
                        className={`shrink-0 whitespace-nowrap px-2 py-0.5 rounded-full text-[11px] font-bold ${
                          planet.hz_status === 'Inside HZ'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                            : planet.hz_status === 'Near HZ'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              : 'bg-slate-700/30 text-slate-300 border border-slate-600/30'
                        }`}
                      >
                        {planet.hz_status || 'Insufficient data'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <Link
                        to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                        className="min-w-0 font-mono font-bold text-white hover:text-exosignal-cyan break-words"
                      >
                        {planet.planet_name}
                      </Link>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => toggleFavorite(planet)}
                          aria-label={
                            isFav
                              ? `Remove ${planet.planet_name} from the watchlist`
                              : `Add ${planet.planet_name} to the watchlist`
                          }
                          className="w-8 h-8 text-lg leading-none"
                        >
                          {isFav ? '★' : '☆'}
                        </button>
                        <Link
                          to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                          className="whitespace-nowrap px-2.5 py-1.5 rounded bg-exosignal-cyan/10 text-exosignal-cyan border border-exosignal-cyan/30 text-xs"
                        >
                          Why this rank
                        </Link>
                      </div>
                    </div>
                    <div className="text-xs">
                      <span
                        className="font-bold text-cyan-300"
                        title={`Raw score: ${formatRawScore(currentScore)}`}
                      >
                        {planet.percentile_rank_string || 'Percentile not available'}
                      </span>
                      <span className="font-mono text-exosignal-text-muted">
                        {' '}
                        · Score {formatPriority(currentScore)}
                      </span>
                    </div>
                    <div className="text-xs text-exosignal-text-secondary">
                      TSM{' '}
                      <span className="font-mono text-amber-300">
                        {planet.tsm != null ? planet.tsm.toFixed(1) : '—'}
                      </span>{' '}
                      (cutoff {renderKemptonThreshold(planet)}) ·{' '}
                      <span className="font-mono text-white">
                        {formatRadius(planet.planet_radius)}
                      </span>{' '}
                      ·{' '}
                      <span className="font-mono text-white">
                        {formatPeriod(planet.orbital_period)}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}

          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-exosignal-cyan/20 bg-space-void/80 text-exosignal-text-muted text-left">
                  <th className="py-3.5 px-4">
                    {activeTab === 'validation' ? 'OOF Rank' : 'Rank'}
                  </th>
                  <th className="py-3.5 px-4">Planet Name</th>
                  <th className="py-3.5 px-4">Percentile Rank</th>
                  <th className="py-3.5 px-4">TSM / Kempton Threshold</th>
                  <th className="py-3.5 px-4">Radius (R⊕)</th>
                  <th className="py-3.5 px-4">Period (days)</th>
                  <th className="py-3.5 px-4">Host Star</th>
                  <th className="py-3.5 px-4">Distance (ly)</th>
                  <th className="py-3.5 px-4">Habitable Zone</th>
                  <th className="py-3.5 px-4 text-center">Watchlist</th>
                  <th className="py-3.5 px-4 text-right">Attribution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-exosignal-cyan/10">
                {loading ? (
                  <tr>
                    <td colSpan="11" className="py-12 text-center text-exosignal-text-muted">
                      <div className="w-8 h-8 mx-auto mb-2 rounded-full border-2 border-exosignal-cyan border-t-transparent animate-spin"></div>
                      Retrieving target rankings from DuckDB engine...
                    </td>
                  </tr>
                ) : error ? (
                  <tr>
                    <td colSpan="11" className="py-8 text-center text-rose-400">
                      Failed to load targets: {error}
                    </td>
                  </tr>
                ) : (
                  activePlanets.map((planet, index) => {
                    const isFav = isFavorite(planet.planet_name);
                    const pRank =
                      activeTab === 'validation'
                        ? planet.oof_ml_rank ?? index + 1
                        : includeObserved
                          ? planet.priority_rank ?? index + 1
                          : planet.unobserved_rank ?? planet.priority_rank ?? index + 1;
                    const currentScore =
                      activeTab === 'validation'
                        ? planet.oof_priority_score ?? planet.priority_score
                        : planet.priority_score ?? planet.ml_priority_score;

                    return (
                      <tr
                        key={planet.planet_name}
                        className="hover:bg-space-card-hover transition-colors"
                      >
                        <td className="py-3.5 px-4 font-bold text-amber-400">#{pRank}</td>
                        <td className="py-3.5 px-4">
                          <Link
                            to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                            className="font-bold text-white hover:text-exosignal-cyan transition-colors"
                          >
                            {planet.planet_name}
                          </Link>
                          {planet.already_observed_jwst && (
                            <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] bg-purple-500/20 text-purple-300 border border-purple-500/30">
                              JWST
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <div
                            className="font-bold text-cyan-300 cursor-help"
                            title={`Raw score: ${formatRawScore(currentScore)}`}
                          >
                            {planet.percentile_rank_string || 'Percentile not available'}
                          </div>
                          <div
                            className="text-[10px] font-mono text-exosignal-text-muted cursor-help"
                            title={`Raw score: ${formatRawScore(currentScore)}`}
                          >
                            Score: {formatPriority(currentScore)}
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="font-bold text-amber-300">
                            TSM: {planet.tsm != null ? planet.tsm.toFixed(1) : '—'}
                          </div>
                          <div className="text-[10px] text-exosignal-text-muted">
                            Threshold: {renderKemptonThreshold(planet)}{' '}
                            {!(Number(planet.planet_radius) > 10.0) &&
                              `(${planet.kempton_size_class || 'Terrestrial'})`}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-exosignal-text-secondary">
                          {formatRadius(planet.planet_radius)}
                        </td>
                        <td className="py-3.5 px-4 text-exosignal-text-secondary">
                          {formatPeriod(planet.orbital_period)}
                        </td>
                        <td className="py-3.5 px-4 text-exosignal-text-muted">
                          {getCleanHostStar(planet)}
                        </td>
                        <td className="py-3.5 px-4 text-exosignal-text-secondary">
                          {formatDistance(planet.distance)}
                        </td>
                        <td className="py-3.5 px-4">
                          <span
                            className={`inline-block whitespace-nowrap px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              planet.hz_status === 'Inside HZ'
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                                : planet.hz_status === 'Near HZ'
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                  : 'bg-slate-700/30 text-slate-400 border border-slate-600/30'
                            }`}
                          >
                            {planet.hz_status || 'Insufficient data'}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <button
                            type="button"
                            onClick={() => toggleFavorite(planet)}
                            aria-label={
                              isFav
                                ? `Remove ${planet.planet_name} from the watchlist`
                                : `Add ${planet.planet_name} to the watchlist`
                            }
                            className="hover:scale-125 transition-transform"
                          >
                            {isFav ? '★' : '☆'}
                          </button>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <Link
                            to={`/planet/${encodeURIComponent(planet.planet_name)}`}
                            className="inline-block whitespace-nowrap px-2.5 py-1 rounded bg-exosignal-cyan/10 hover:bg-exosignal-cyan/25 text-exosignal-cyan border border-exosignal-cyan/30 text-[11px] transition-colors"
                          >
                            SHAP Waterfall
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TopTargets;
