import React, { useState, useEffect } from 'react';
import { explainabilityApi } from '../services/api';

export const TreeSHAPWaterfall = ({
  planetName,
  targetPriorityScore,
  mlPriorityScore,
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
          setError(err?.response?.data?.detail || 'Failed to compute TreeSHAP explanation');
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
        <p className="mt-3 text-exosignal-text/70 text-sm">
          Computing exact SHAP feature attributions...
        </p>
      </div>
    );
  }

  if (error || !explanation) {
    return (
      <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6 text-center text-exosignal-text/60">
        <p>Interpretability breakdown unavailable for this target: {error}</p>
      </div>
    );
  }

  const {
    base_score,
    ml_priority_score = explanation.priority_score,
    score_delta_from_base,
    mathematical_invariants,
    top_positive_drivers,
    top_negative_barriers,
    full_waterfall,
  } = explanation;

  const displayedItems =
    viewMode === 'summary'
      ? [...top_positive_drivers, ...top_negative_barriers].sort(
          (a, b) => b.abs_importance - a.abs_importance
        )
      : full_waterfall;

  const maxAbsImpact = Math.max(...full_waterfall.map((i) => Math.abs(i.score_impact)), 1.0);

  return (
    <section className="bg-space-darker rounded-lg border border-exosignal-blue/30 p-8">
      {/* Header with Title and ML Rank Badges */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-exosignal-blue/10 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-exosignal-text">
              TreeSHAP Interpretability Waterfall
            </h2>
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-exosignal-blue/20 text-exosignal-blue border border-exosignal-blue/40">
              Lundberg et al. (Nature MI 2020)
            </span>
          </div>
          <p className="text-exosignal-text/70 text-sm mt-1">
            Exact local feature attribution decomposing the ML model's decision into physical
            positive drivers and negative barriers.
          </p>
        </div>

        {/* Rank & Delta Badges */}
        <div className="flex items-center gap-2">
          {mlRank && (
            <div className="px-3 py-1.5 rounded-lg bg-space-dark border border-exosignal-blue/30 text-right">
              <span className="text-xs text-exosignal-text/60 block">ML Rank</span>
              <span className="text-base font-bold text-exosignal-accent">#{mlRank}</span>
            </div>
          )}
          {rankDelta !== null && rankDelta !== undefined && (
            <div className="px-3 py-1.5 rounded-lg bg-space-dark border border-exosignal-blue/30 text-right">
              <span className="text-xs text-exosignal-text/60 block">Rank Shift vs Heuristic</span>
              <span
                className={`text-base font-bold ${rankDelta > 0 ? 'text-emerald-400' : rankDelta < 0 ? 'text-rose-400' : 'text-gray-400'}`}
              >
                {rankDelta > 0 ? `▲ +${rankDelta}` : rankDelta < 0 ? `▼ ${rankDelta}` : '— 0'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* KPI Decomposition Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 my-6">
        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
          <p className="text-xs text-exosignal-text/60">Catalog Base Score</p>
          <p className="text-2xl font-bold text-exosignal-text mt-1">{base_score.toFixed(1)}</p>
          <p className="text-xs text-exosignal-text/50 mt-1">Global population expectation</p>
        </div>

        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
          <p className="text-xs text-exosignal-text/60">Net Feature Shift</p>
          <p
            className={`text-2xl font-bold mt-1 ${score_delta_from_base >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}
          >
            {score_delta_from_base >= 0
              ? `+${score_delta_from_base.toFixed(1)}`
              : score_delta_from_base.toFixed(1)}{' '}
            pts
          </p>
          <p className="text-xs text-exosignal-text/50 mt-1">Sum of SHAP physical contributions</p>
        </div>

        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/30 bg-exosignal-blue/5">
          <p className="text-xs text-exosignal-accent font-semibold">Predicted ML Score</p>
          <p className="text-2xl font-extrabold text-exosignal-accent mt-1">
            {ml_priority_score.toFixed(1)}
          </p>
          <p className="text-xs text-exosignal-text/50 mt-1">Supervised ML Ranker</p>
        </div>

        <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/20">
          <p className="text-xs text-exosignal-text/60">Mathematical Invariant</p>
          <p className="text-xs font-mono text-emerald-400 mt-2 font-semibold">
            Σ φᵢ + Base = Prediction
          </p>
          <p className="text-[11px] font-mono text-exosignal-text/50 mt-1">
            Residual: {mathematical_invariants.reconstruction_error.toExponential(2)}
          </p>
        </div>
      </div>

      {/* Toggle View Mode */}
      <div className="flex items-center justify-between mt-6 mb-4">
        <h3 className="text-base font-semibold text-exosignal-text">
          {viewMode === 'summary'
            ? 'Key Physical Drivers & Barriers'
            : 'All 21 Model Feature Contributions'}
        </h3>
        <div className="flex items-center bg-space-dark p-1 rounded-lg border border-exosignal-blue/20">
          <button
            onClick={() => setViewMode('summary')}
            className={`px-3 py-1 rounded text-xs font-medium transition ${viewMode === 'summary' ? 'bg-exosignal-blue text-space-darker font-bold' : 'text-exosignal-text/70 hover:text-white'}`}
          >
            Key Drivers (10)
          </button>
          <button
            onClick={() => setViewMode('full')}
            className={`px-3 py-1 rounded text-xs font-medium transition ${viewMode === 'full' ? 'bg-exosignal-blue text-space-darker font-bold' : 'text-exosignal-text/70 hover:text-white'}`}
          >
            Full Waterfall (21)
          </button>
        </div>
      </div>

      {/* Waterfall List */}
      <div className="space-y-3 mt-4">
        {displayedItems.map((item) => {
          const isPos = item.direction === 'positive';
          const barWidthPercent = Math.min(
            100,
            Math.round((Math.abs(item.score_impact) / maxAbsImpact) * 100)
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
                  <span className="text-xs font-mono text-exosignal-text/60">
                    φ ={' '}
                    {item.shap_value > 0
                      ? `+${item.shap_value.toFixed(3)}`
                      : item.shap_value.toFixed(3)}
                  </span>
                  <span
                    className={`text-sm font-bold min-w-[70px] ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}
                  >
                    {isPos ? `+${item.score_impact.toFixed(1)}` : item.score_impact.toFixed(1)} pts
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
      <div className="mt-6 pt-4 border-t border-exosignal-blue/10 flex flex-wrap items-center justify-between text-xs text-exosignal-text/60 gap-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block" />
            <span>Positive Driver (elevates priority score)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
            <span>Negative Barrier (lowers priority score)</span>
          </div>
        </div>
        <span>Feature scale factor derived from population margin calibration</span>
      </div>
    </section>
  );
};

export default TreeSHAPWaterfall;
