import React, { useState, useEffect } from 'react';
import { explainabilityApi } from '../services/api';

/**
 * Linear SHAP Interpretability Waterfall (Lundberg & Lee 2017, NeurIPS)
 * Decomposes regularized logistic regression predictions into exact additive feature
 * contributions in log-odds units (Δ log-odds), alongside the base value, final logit,
 * and converted percentile rank score.
 */
export const ShapWaterfall = ({
  planetName,
  mlRank,
  rankDelta,
}) => {
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('summary'); // 'summary' or 'full'

  useEffect(() => {
    let isMounted = true;
    const fetchExplanation = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await explainabilityApi.getPlanetExplanation(planetName);
        if (isMounted) {
          setExplanation(data);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err?.response?.data?.detail || 'Failed to compute Linear SHAP explanation');
          setLoading(false);
        }
      }
    };

    if (planetName) {
      fetchExplanation();
    }

    return () => {
      isMounted = false;
    };
  }, [planetName]);

  if (loading) {
    return (
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-exosignal-accent"></div>
        <p className="mt-3 text-exosignal-text/70 text-sm font-mono">
          Computing exact Linear SHAP feature attributions (Lundberg & Lee 2017)...
        </p>
      </div>
    );
  }

  if (error || !explanation) {
    return (
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 text-center text-exosignal-text/60 font-mono">
        <p>Interpretability breakdown unavailable for this target: {error}</p>
      </div>
    );
  }

  const {
    ml_priority_score = explanation.priority_score ?? 0,
    mathematical_invariants = {},
    top_positive_drivers = [],
    top_negative_barriers = [],
    full_waterfall = [],
  } = explanation;

  const baseLogit = mathematical_invariants?.base_margin ?? explanation.base_logit ?? 0;
  const sumShap = mathematical_invariants?.sum_shap_margin ?? 0;
  const finalLogit = mathematical_invariants?.predicted_margin ?? explanation.final_logit ?? (baseLogit + sumShap);
  const residual = mathematical_invariants?.reconstruction_error ?? Math.abs(sumShap + baseLogit - finalLogit);
  const convertedPercentile = ml_priority_score;

  const displayedItems =
    viewMode === 'summary'
      ? [...top_positive_drivers, ...top_negative_barriers].sort(
          (a, b) => b.abs_importance - a.abs_importance
        )
      : full_waterfall;

  const maxAbsShap = Math.max(
    ...full_waterfall.map((i) => Math.abs(i.shap_value || 0)),
    0.01
  );

  // Formatter guaranteed never to display as 0.0 when |phi| > 0.01
  const formatLogOdds = (val) => {
    if (val === null || val === undefined || isNaN(val)) return '0.000 Δ log-odds';
    const num = Number(val);
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toFixed(3)} Δ log-odds`;
  };

  return (
    <section className="bg-space-darker rounded-lg border border-exosignal-blue/30 p-8">
      {/* Header with Title and Linear SHAP Citation Badges */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-exosignal-blue/10 gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-bold text-exosignal-text">
              Linear SHAP Interpretability Waterfall
            </h2>
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-exosignal-blue/20 text-exosignal-blue border border-exosignal-blue/40 font-mono">
              Lundberg & Lee (2017, NeurIPS)
            </span>
          </div>
          <p className="text-exosignal-text/70 text-sm mt-1">
            Exact local feature attribution decomposing the regularized logistic regression model's decision in log-odds units (Δ log-odds) into physical positive drivers and negative barriers.
          </p>
        </div>

        {/* Rank & Delta Badges */}
        <div className="flex items-center gap-2">
          {mlRank && (
            <div className="px-3 py-1.5 rounded-lg bg-space-dark border border-exosignal-blue/30 text-right">
              <span className="text-xs text-exosignal-text/60 block font-mono">ML Rank</span>
              <span className="text-base font-bold text-exosignal-accent font-mono">#{mlRank}</span>
            </div>
          )}
          {rankDelta !== null && rankDelta !== undefined && (
            <div className="px-3 py-1.5 rounded-lg bg-space-dark border border-exosignal-blue/30 text-right">
              <span className="text-xs text-exosignal-text/60 block font-mono">Rank Shift vs Heuristic</span>
              <span
                className={`text-base font-bold font-mono ${rankDelta > 0 ? 'text-emerald-400' : rankDelta < 0 ? 'text-rose-400' : 'text-gray-400'}`}
              >
                {rankDelta > 0 ? `▲ +${rankDelta}` : rankDelta < 0 ? `▼ ${rankDelta}` : '— 0'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* KPI Decomposition Cards: Base Logit, Sum SHAP, Final Logit, Converted Percentile */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 my-6">
        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
          <p className="text-xs text-exosignal-text/60 font-mono">Base Value (w₀)</p>
          <p className="text-xl font-bold font-mono text-exosignal-text mt-1">
            {baseLogit > 0 ? `+${baseLogit.toFixed(3)}` : baseLogit.toFixed(3)}
          </p>
          <p className="text-[11px] text-exosignal-text/50 mt-1 font-mono">Global intercept (log-odds)</p>
        </div>

        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
          <p className="text-xs text-exosignal-text/60 font-mono">Net Feature Shift (Σ φᵢ)</p>
          <p
            className={`text-xl font-bold font-mono mt-1 ${sumShap >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}
          >
            {sumShap >= 0 ? `+${sumShap.toFixed(3)}` : sumShap.toFixed(3)}
          </p>
          <p className="text-[11px] text-exosignal-text/50 mt-1 font-mono">Sum of Δ log-odds</p>
        </div>

        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/30 bg-exosignal-blue/5">
          <p className="text-xs text-exosignal-accent font-semibold font-mono">Final Logit (w·x + w₀)</p>
          <p className="text-xl font-extrabold font-mono text-exosignal-accent mt-1">
            {finalLogit > 0 ? `+${finalLogit.toFixed(3)}` : finalLogit.toFixed(3)}
          </p>
          <p className="text-[11px] text-exosignal-text/50 mt-1 font-mono">Predicted model margin</p>
        </div>

        <div className="bg-space-dark rounded-lg p-4 border border-emerald-500/20 bg-emerald-500/5">
          <p className="text-xs text-emerald-400 font-semibold font-mono">Converted Percentile</p>
          <p className="text-xl font-extrabold font-mono text-emerald-400 mt-1">
            {convertedPercentile.toFixed(1)} / 100
          </p>
          <p className="text-[11px] text-exosignal-text/50 mt-1 font-mono">σ(logit) · 100 calibrated score</p>
        </div>
      </div>

      {/* Invariant Bar */}
      <div className="p-2.5 rounded-lg bg-space-dark border border-exosignal-blue/15 flex flex-wrap items-center justify-between text-xs font-mono text-exosignal-text/70 mb-6 gap-2">
        <span className="text-emerald-400 font-semibold">
          Additive Invariant: Σ φᵢ + Base Value = Final Logit
        </span>
        <span className="text-[11px] text-exosignal-text/50">
          Reconstruction residual: {residual.toExponential(2)}
        </span>
      </div>

      {/* Toggle View Mode */}
      <div className="flex items-center justify-between mt-6 mb-4">
        <h3 className="text-base font-semibold text-exosignal-text">
          {viewMode === 'summary'
            ? 'Key Physical Drivers & Barriers (Δ log-odds)'
            : 'All Model Feature Contributions (Δ log-odds)'}
        </h3>
        <div className="flex items-center bg-space-dark p-1 rounded-lg border border-exosignal-blue/20">
          <button
            onClick={() => setViewMode('summary')}
            className={`px-3 py-1 rounded text-xs font-medium font-mono transition ${viewMode === 'summary' ? 'bg-exosignal-blue text-space-darker font-bold' : 'text-exosignal-text/70 hover:text-white'}`}
          >
            Key Drivers (10)
          </button>
          <button
            onClick={() => setViewMode('full')}
            className={`px-3 py-1 rounded text-xs font-medium font-mono transition ${viewMode === 'full' ? 'bg-exosignal-blue text-space-darker font-bold' : 'text-exosignal-text/70 hover:text-white'}`}
          >
            Full Waterfall ({full_waterfall.length})
          </button>
        </div>
      </div>

      {/* Waterfall List */}
      <div className="space-y-3 mt-4">
        {displayedItems.map((item) => {
          const isPos = item.direction === 'positive' || item.shap_value >= 0;
          const barWidthPercent = Math.min(
            100,
            Math.max(4, Math.round((Math.abs(item.shap_value) / maxAbsShap) * 100))
          );

          return (
            <div
              key={item.feature}
              className="bg-space-dark rounded-lg p-3 border border-exosignal-blue/15 hover:border-exosignal-blue/40 transition"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-sm gap-2">
                <div className="flex-1 min-w-[200px]">
                  <span className="font-semibold text-exosignal-text">{item.display_name}</span>
                  <span className="text-xs font-mono text-exosignal-accent ml-2">
                    ({item.raw_value})
                  </span>
                  {item.description && (
                    <p className="text-xs text-exosignal-text/50 mt-0.5">{item.description}</p>
                  )}
                </div>

                <div className="flex items-center gap-4 text-right">
                  <span
                    className={`text-sm font-bold font-mono min-w-[130px] ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}
                  >
                    {formatLogOdds(item.shap_value)}
                  </span>
                </div>
              </div>

              {/* Dual-Direction Relative Bar */}
              <div className="mt-2 w-full bg-space-darker h-2 rounded-full overflow-hidden flex items-center">
                <div className="w-1/2 flex justify-end">
                  {!isPos && (
                    <div
                      className="bg-rose-500 h-2 rounded-l-full transition-all duration-500"
                      style={{ width: `${barWidthPercent}%` }}
                    />
                  )}
                </div>
                <div className="w-[2px] h-full bg-exosignal-blue/40" />
                <div className="w-1/2 flex justify-start">
                  {isPos && (
                    <div
                      className="bg-emerald-400 h-2 rounded-r-full transition-all duration-500"
                      style={{ width: `${barWidthPercent}%` }}
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Explanatory Physical Legend */}
      <div className="mt-6 pt-4 border-t border-exosignal-blue/10 flex flex-wrap items-center justify-between text-xs text-exosignal-text/60 gap-4 font-mono">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block" />
            <span>Positive Driver (+Δ log-odds elevates rank)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
            <span>Negative Barrier (-Δ log-odds suppresses rank)</span>
          </div>
        </div>
        <span>Citation: Lundberg & Lee (2017, NeurIPS)</span>
      </div>
    </section>
  );
};

export const TreeSHAPWaterfall = ShapWaterfall;
export default ShapWaterfall;

