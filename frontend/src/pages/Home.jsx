import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTopTargets } from '../hooks/usePlanets';
import { useAnalytics } from '../hooks/useAnalytics';
import { formatPriority } from '../utils/formatters';
import { calculateHzPieData } from '../utils/hzDonut';
import { modelsApi, planetsApi } from '../services/api';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts';
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
  distance: 'Distance',
  semi_major_axis: 'Orbit Size',
  transit_depth_proxy: 'Transit Depth',
};

const PRODUCTION_MODEL_NAME = 'Logistic Regression (Variant A - All Features)';

/** Metrics of the served model from GET /evaluation/benchmark, under one set of names; null when unknown. */
export function productionMetrics(benchmark) {
  const summary =
    benchmark?.selected_production_model?.model_name === PRODUCTION_MODEL_NAME
      ? benchmark.selected_production_model
      : null;
  const entry = Array.isArray(benchmark?.leaderboard)
    ? benchmark.leaderboard.find((m) => m.model_name === PRODUCTION_MODEL_NAME)
    : null;
  if (!summary && !entry) return null;
  const pick = (a, b) => entry?.[a] ?? summary?.[b] ?? summary?.[a] ?? null;
  return {
    ap: pick('ap', 'mean_ap'),
    ap_std: pick('ap_std', 'mean_ap_std'),
    ap_ci95: pick('ap_ci95', 'ap_ci95'),
    'recall@50': pick('recall@50', 'mean_recall50'),
    'ndcg@25': pick('ndcg@25', 'mean_ndcg25'),
  };
}

const formatRadius = (r) => (r ? `${Number(r).toFixed(2)} R⊕` : 'not in archive');
const formatPeriodDays = (p) => (p ? `${Number(p).toFixed(1)} days` : 'not in archive');

const HZ_BADGE = {
  'Inside HZ': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  'Near HZ': 'bg-amber-500/20 text-amber-300 border-amber-500/40',
};
const hzBadgeClass = (hz) => HZ_BADGE[hz] || 'bg-slate-700/30 text-slate-300 border-slate-600/40';

/** A plain section heading: one title, one sentence of context. */
const SectionHeading = ({ title, children, action }) => (
  <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
    <div className="max-w-3xl">
      <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">{title}</h2>
      {children && (
        <p className="mt-1.5 text-sm text-exosignal-text-secondary leading-relaxed">{children}</p>
      )}
    </div>
    {action}
  </div>
);

const StatCard = ({ label, value, valueClass = 'text-white', note, accent }) => (
  <div className={`glass-panel p-5 ${accent}`}>
    <div className="text-xs font-semibold uppercase tracking-wide text-exosignal-text-muted mb-2">
      {label}
    </div>
    <div className={`text-2xl sm:text-3xl font-black font-mono ${valueClass}`}>{value}</div>
    {note && <div className="text-xs text-exosignal-text-muted mt-1.5 leading-snug">{note}</div>}
  </div>
);

/** One planet card, used for both the labelled targets and the new recommendations. */
const TargetCard = ({ target, rankLabel, scoreLabel, accentText, accentBorder, testId }) => (
  <div
    data-testid={testId}
    className={`glass-panel glass-panel-hover p-5 ${accentBorder} flex flex-col justify-between group`}
  >
    <div>
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className={`text-xs font-mono font-bold ${accentText}`}>{rankLabel}</span>
        <span
          className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${hzBadgeClass(
            target.hz
          )}`}
        >
          {target.hz}
        </span>
      </div>
      <Link
        to={`/planet/${encodeURIComponent(target.name)}`}
        className="block text-lg font-bold font-mono text-white hover:underline"
      >
        {target.name}
      </Link>
      <dl className="grid grid-cols-2 gap-2 my-3 text-xs bg-space-void/60 p-2.5 rounded-lg">
        <div>
          <dt className="text-exosignal-text-muted">Radius</dt>
          <dd className="text-white font-mono font-semibold">{target.radius}</dd>
        </div>
        <div>
          <dt className="text-exosignal-text-muted">Period</dt>
          <dd className="text-white font-mono font-semibold">{target.period}</dd>
        </div>
      </dl>
      <p className="text-xs text-exosignal-text-secondary leading-relaxed">{target.featureNote}</p>
    </div>
    <div className="pt-3 mt-4 border-t border-slate-800 flex items-center justify-between">
      <div className="text-xs text-exosignal-text-muted">
        {scoreLabel} <span className={`font-mono font-bold ${accentText}`}>{target.mlScore}</span>
      </div>
      <Link
        to={`/planet/${encodeURIComponent(target.name)}`}
        className={`text-xs font-semibold ${accentText} hover:underline`}
      >
        Why this rank →
      </Link>
    </div>
  </div>
);

const Home = () => {
  const { planets: topPlanets } = useTopTargets(8);
  const [knownTargets, setKnownTargets] = useState([]);
  const { stats } = useAnalytics();
  const [benchmark, setBenchmark] = useState(null);
  const [featureImportances, setFeatureImportances] = useState(null);

  useEffect(() => {
    modelsApi
      .getBenchmark('test')
      .then((res) => setBenchmark(res))
      .catch(() => null);

    modelsApi
      .getFeatureImportance()
      .then((res) => setFeatureImportances(res))
      .catch(() => null);

    planetsApi
      .getKnownTargets()
      .then((res) => setKnownTargets(Array.isArray(res) ? res : []))
      .catch(() => setKnownTargets([]));
  }, []);

  // Feature weights of the logistic regression (|standardized coefficient|), signed by direction
  const featureChartData = useMemo(() => {
    if (!Array.isArray(featureImportances?.top_features)) return [];
    return featureImportances.top_features
      .filter((f) => Number.isFinite(f.coefficient ?? f.gain))
      .slice(0, 8)
      .map((f) => {
        const coef = f.coefficient ?? f.gain;
        return {
          feature: FEATURE_LABEL_MAP[f.feature] || f.feature,
          coefficient: Number(Number(coef).toFixed(3)),
          abs_coefficient: Number(Math.abs(coef).toFixed(3)),
          direction: coef >= 0 ? 'positive' : 'negative',
        };
      });
  }, [featureImportances]);

  // Text alternative of the chart, generated from the same data
  const featureSummary = useMemo(
    () =>
      featureChartData
        .map((d) => `${d.feature} ${d.coefficient > 0 ? '+' : ''}${d.coefficient}`)
        .join(', '),
    [featureChartData]
  );

  const productionModel = useMemo(() => productionMetrics(benchmark), [benchmark]);

  // Planets labelled as JWST targets (labels are NOT human-verified), with out-of-fold rank
  const labelledTargets = useMemo(() => {
    if (!Array.isArray(knownTargets)) return [];
    return knownTargets
      .filter(
        (planet) =>
          Boolean(planet.is_jwst_target || planet.already_observed_jwst) &&
          planet.already_observed_jwst !== false
      )
      .slice(0, 4)
      .map((planet, index) => ({
        name: planet.planet_name || `Target ${index + 1}`,
        oofRank: planet.oof_ml_rank ?? planet.priority_rank ?? index + 1,
        radius: formatRadius(planet.planet_radius),
        period: formatPeriodDays(planet.orbital_period),
        hz: planet.hz_status || 'Insufficient data',
        mlScore: formatPriority(
          planet.oof_priority_score ?? planet.ml_priority_score ?? planet.priority_score
        ),
        featureNote: `${
          planet.kempton_size_class || 'Spectroscopic'
        } planet labelled as a JWST target (label not human-verified)`,
      }));
  }, [knownTargets]);

  // Highly ranked planets that the label set does not list as JWST targets
  const newRecommendations = useMemo(() => {
    if (!Array.isArray(topPlanets)) return [];
    return topPlanets
      .filter((planet) => !planet.already_observed_jwst && !planet.is_jwst_target)
      .slice(0, 4)
      .map((planet, index) => ({
        name: planet.planet_name || `Candidate ${index + 1}`,
        rank: planet.unobserved_rank ?? planet.priority_rank ?? index + 1,
        radius: formatRadius(planet.planet_radius),
        period: formatPeriodDays(planet.orbital_period),
        hz: planet.hz_status || 'Insufficient data',
        mlScore: formatPriority(planet.ml_priority_score ?? planet.priority_score),
        featureNote: `${
          planet.kempton_size_class || 'Spectroscopic'
        } planet that is not labelled as a JWST target`,
      }));
  }, [topPlanets]);

  const insideHz = useMemo(
    () =>
      calculateHzPieData(stats?.hz_distribution, stats?.total_planets).find(
        (d) => d.name === 'Inside HZ'
      ) || null,
    [stats?.hz_distribution, stats?.total_planets]
  );

  const apText =
    typeof productionModel?.ap === 'number'
      ? `${productionModel.ap.toFixed(4)} ± ${
          typeof productionModel.ap_std === 'number' ? productionModel.ap_std.toFixed(4) : '—'
        }`
      : '—';

  return (
    <div className="space-y-16">
      {/* 1. Hero */}
      <section className="relative pt-6 pb-4 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[450px] bg-gradient-to-tr from-exosignal-cyan/15 via-exosignal-purple/10 to-transparent blur-3xl pointer-events-none rounded-full"></div>

        <div className="relative max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
            <div className="inline-flex flex-wrap items-center justify-center gap-x-2 px-3.5 py-1.5 rounded-2xl sm:rounded-full bg-space-surface/90 border border-exosignal-cyan/40 text-xs font-orbitron text-exosignal-cyan">
              <span>NASA EXOPLANET ARCHIVE</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>RANKING MODEL</span>
              <span className="text-exosignal-cyan/50">•</span>
              <span>EXPLAINED SCORES</span>
            </div>

            <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight leading-[1.1] font-display">
              Target Prioritization for{' '}
              <span className="planet-font-animated font-orbitron block mt-2 text-2xl sm:text-4xl lg:text-5xl">
                Exoplanet Spectroscopy
              </span>
            </h1>

            <p className="text-base sm:text-lg text-exosignal-text-secondary max-w-2xl leading-relaxed">
              Telescope time on JWST is scarce. ExoSignal ranks known transiting planets by how
              promising they look for transmission spectroscopy, and shows which planet properties
              drive each rank. It is an exploratory ranking: no score is a probability of life.
            </p>

            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
              <Link to="/explorer" className="btn-primary-glow font-orbitron text-sm">
                <span>
                  Explore {stats?.total_planets ? `${stats.total_planets.toLocaleString()} ` : ''}
                  planets
                </span>
              </Link>
              <Link to="/top-targets" className="btn-secondary-glass font-orbitron text-xs">
                <span>Top targets</span>
              </Link>
              <Link
                to="/methodology"
                className="text-sm text-exosignal-text-secondary hover:text-white underline-offset-4 hover:underline"
              >
                How it works
              </Link>
            </div>
          </div>

          <div className="lg:col-span-5 flex justify-center">
            <div className="divided-compartment p-5 w-full max-w-md bg-space-void/60 border-exosignal-cyan/30">
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

      {/* 2. At a glance */}
      <section className="space-y-5">
        <SectionHeading title="At a glance" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Planets in the catalogue"
            value={stats?.total_planets?.toLocaleString() || '—'}
            note="From the NASA Exoplanet Archive"
            accent="border-exosignal-cyan/30"
          />
          <StatCard
            label="Model quality (average precision)"
            value={<span className="text-xl sm:text-2xl">{apText}</span>}
            valueClass="text-exosignal-cyan"
            note={
              productionModel ? (
                <>
                  Recall@50{' '}
                  {typeof productionModel['recall@50'] === 'number'
                    ? productionModel['recall@50'].toFixed(3)
                    : '—'}{' '}
                  · {benchmark?.n_positives ?? '—'} labels, not yet human-verified
                </>
              ) : (
                'Evaluation results not loaded'
              )
            }
            accent="border-exosignal-cyan/30"
          />
          <StatCard
            label="Inside the habitable zone"
            value={insideHz ? insideHz.value.toLocaleString() : '—'}
            valueClass="text-emerald-400"
            note={
              insideHz
                ? `${insideHz.percentage}% of the catalogue. An orbital distance range, not evidence of water or life`
                : 'Habitable zone data not loaded'
            }
            accent="border-emerald-500/30"
          />
          <StatCard
            label="Features explained per planet"
            value={
              featureImportances?.total_features ?? featureImportances?.all_features?.length ?? '—'
            }
            valueClass="text-exosignal-purple"
            note="Every score is split into exact per-feature contributions (linear SHAP)"
            accent="border-exosignal-purple/30"
          />
        </div>
      </section>

      {/* 3. One chart: what drives the ranking */}
      <section className="space-y-5">
        <SectionHeading
          title="What drives the ranking"
          action={
            <Link
              to="/analytics"
              className="text-sm font-semibold text-exosignal-cyan hover:underline whitespace-nowrap"
            >
              More charts in Analytics →
            </Link>
          }
        >
          Weights of the ranking model (standardized coefficients). Green raises a planet&apos;s
          rank, red lowers it.
        </SectionHeading>

        <figure className="glass-panel p-6 border-exosignal-cyan/30">
          {featureChartData.length > 0 ? (
            <div
              className="h-72 w-full"
              role="img"
              aria-label={`Bar chart of model weights: ${featureSummary}`}
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={featureChartData}
                  layout="vertical"
                  margin={{ top: 5, right: 25, left: 110, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#131c38" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    axisLine={{ stroke: '#1e293b' }}
                  />
                  <YAxis
                    type="category"
                    dataKey="feature"
                    tick={{ fill: '#f8fafc', fontSize: 11 }}
                    axisLine={{ stroke: '#1e293b' }}
                    width={105}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#070a16',
                      borderColor: '#00d4ff',
                      borderRadius: '12px',
                      color: '#ffffff',
                      fontSize: '12px',
                    }}
                    formatter={(value, name, item) => [
                      `${item.payload.coefficient > 0 ? '+' : ''}${item.payload.coefficient} (${
                        item.payload.direction
                      })`,
                      'Standardized coefficient',
                    ]}
                  />
                  <Bar dataKey="abs_coefficient" radius={[0, 6, 6, 0]}>
                    {featureChartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.direction === 'positive' ? '#10b981' : '#f43f5e'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-72 w-full flex items-center justify-center text-sm text-exosignal-text-muted border border-dashed border-slate-800 rounded-xl">
              Loading model weights…
            </div>
          )}
          {featureChartData[0] && (
            <figcaption className="mt-3 text-sm text-exosignal-text-secondary text-center">
              {featureChartData[0].feature} has the largest weight (
              {featureChartData[0].coefficient > 0 ? '+' : ''}
              {featureChartData[0].coefficient.toFixed(2)}).
            </figcaption>
          )}
        </figure>
      </section>

      {/* 4. Labelled JWST targets */}
      <section className="space-y-5" data-testid="golden-benchmark-section">
        <SectionHeading title="Labelled JWST targets: where our model ranks them">
          Out-of-fold ranks of planets that our label set lists as JWST targets. No label has been
          human-verified yet, so these results are provisional.
        </SectionHeading>
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5"
          data-testid="golden-targets-grid"
        >
          {labelledTargets.map((t) => (
            <TargetCard
              key={t.name}
              testId={`golden-target-${t.name}`}
              target={t}
              rankLabel={`OOF Rank #${t.oofRank}`}
              scoreLabel="Out-of-fold score"
              accentText="text-emerald-400"
              accentBorder="border-emerald-500/20"
            />
          ))}
        </div>
      </section>

      {/* 5. New recommendations */}
      <section className="space-y-5" data-testid="new-recommendations-section">
        <SectionHeading
          title="New recommendations (not labelled as JWST targets)"
          action={
            <Link
              to="/top-targets"
              className="text-sm font-semibold text-exosignal-cyan hover:underline whitespace-nowrap"
            >
              Full leaderboard →
            </Link>
          }
        >
          Highly ranked planets that our label set does not list as JWST targets. The label set is
          incomplete, so JWST may already have observed some of them.
        </SectionHeading>
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5"
          data-testid="unobserved-targets-grid"
        >
          {newRecommendations.map((t) => (
            <TargetCard
              key={t.name}
              testId={`recommendation-${t.name}`}
              target={t}
              rankLabel={`Rank #${t.rank}`}
              scoreLabel="Score"
              accentText="text-exosignal-cyan"
              accentBorder="border-exosignal-cyan/20"
            />
          ))}
        </div>
      </section>

      {/* 6. How it works */}
      <section className="space-y-5">
        <SectionHeading
          title="How it works"
          action={
            <Link
              to="/methodology"
              className="text-sm font-semibold text-exosignal-cyan hover:underline whitespace-nowrap"
            >
              Full methodology →
            </Link>
          }
        >
          From archive data to a ranked list. ExoSignal does not plan or schedule observations.
        </SectionHeading>
        <ol className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            [
              'Ingest',
              'NASA archive data, validated and deduplicated. Missing masses use an empirical mass-radius relation (a known limitation for large planets).',
            ],
            [
              'Derive features',
              'Spectroscopy metrics (TSM / ESM, Kempton et al. 2018), scale height, insolation and infrared brightness.',
            ],
            [
              'Rank',
              'A regularized logistic regression, evaluated with host-grouped cross-validation.',
            ],
            [
              'Serve',
              'DuckDB queries the catalogue straight from a Parquet file, behind a FastAPI API.',
            ],
            [
              'Explain',
              'Per-planet feature contributions, side-by-side comparisons, and a model registry with checksums.',
            ],
          ].map(([title, text], i) => (
            <li
              key={title}
              className="bg-space-void/80 p-4 rounded-xl border border-slate-800 space-y-2"
            >
              <div className="text-xs font-mono font-bold text-exosignal-cyan">
                {String(i + 1).padStart(2, '0')}
              </div>
              <h3 className="font-bold text-white text-sm">{title}</h3>
              <p className="text-xs text-exosignal-text-secondary leading-relaxed">{text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
};

export default Home;
