import React, { useState, useEffect } from 'react';
import SectionDivider from '../components/SectionDivider';
import SegmentedTabs from '../components/SegmentedTabs';
import { methodologyApi } from '../services/api';

const Methodology = () => {
  const [activeTab, setActiveTab] = useState('framework');
  const [weightsData, setWeightsData] = useState(null);

  useEffect(() => {
    let isMounted = true;
    methodologyApi
      .getWeights()
      .then((data) => {
        if (isMounted) setWeightsData(data);
      })
      .catch((err) => {
        console.error('Failed to load methodology weights:', err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const methodologyTabs = [
    { id: 'context', label: 'Scientific Context', icon: '🔭' },
    { id: 'pipeline', label: 'Data Pipeline', icon: '⚙️' },
    { id: 'framework', label: 'Scoring Framework', icon: '📐' },
    { id: 'constraints', label: 'Scientific Constraints', icon: '⚖️' },
    { id: 'all', label: 'Full Methodology Document', icon: '📑' },
  ];

  const showAll = activeTab === 'all';

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-exosignal-cyan/20 pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
            Astrophysical Methodology & Physics Basis
          </div>
          <h1 className="text-3xl font-black text-white font-display">
            Prioritization Methodology & Scientific Gating
          </h1>
          <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
            Mathematical foundations, 21-feature engineering formulations, unsupervised outlier
            detection, and empirical ranking constraints.
          </p>
        </div>
        <div className="text-xs font-mono text-exosignal-cyan bg-space-void/90 px-3 py-1.5 rounded-xl border border-exosignal-cyan/20">
          Supervised ML Ranker + SHAP
        </div>
      </div>

      {/* Modular Tab Division Control */}
      <div>
        <SegmentedTabs tabs={methodologyTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* SECTION 1: Scientific Context */}
      {(showAll || activeTab === 'context') && (
        <div className="space-y-4">
          <SectionDivider
            number="01"
            title="Scientific Context & Mission Rationale"
            subtitle="The observational bottleneck in high-resolution transmission and emission spectroscopy"
            badge="CONTEXT"
            accent="cyan"
          />

          <div className="divided-compartment p-8 space-y-4">
            <h3 className="text-lg font-bold text-white font-display">
              Observational Time Scarcity
            </h3>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              Astronomical surveys like Kepler, K2, and TESS have identified thousands of confirmed
              exoplanets and candidates. However, observation time on premiere spectroscopic
              observatories (JWST, HST, and upcoming Extremely Large Telescopes) is intensely
              oversubscribed.
            </p>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              ExoSignal addresses this by fusing NASA Exoplanet Archive composite physical
              parameters with supervised regularized logistic regression models, columnar querying
              in DuckDB, and exact linear SHAP attribution to provide an exploratory target
              prioritization index.
            </p>
          </div>
        </div>
      )}

      {/* SECTION 2: Data Pipeline */}
      {(showAll || activeTab === 'pipeline') && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="End-to-End Data Processing Pipeline"
            subtitle="Deterministic multistage ETL, schema standardization, and physics-informed feature derivation"
            badge="DATA PIPELINE"
            accent="purple"
          />

          <div className="divided-compartment p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/20 space-y-1.5">
                <span className="text-exosignal-cyan font-bold block text-sm">
                  01 // Ingestion & Manifest Validation
                </span>
                <p className="text-exosignal-text-muted">
                  Ingests composite parameters from the NASA Exoplanet Archive with SHA256 integrity
                  hashing and local snapshot versioning.
                </p>
              </div>
              <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-cyan/20 space-y-1.5">
                <span className="text-exosignal-cyan font-bold block text-sm">
                  02 // Physical Fallbacks
                </span>
                <p className="text-exosignal-text-muted">
                  Uses an empirical mass-radius power law when the archive has no mass. Known
                  defect: above 1.23 R⊕ the served artifact uses M = 2.69 R^0.93, which is not the
                  Chen & Kipping (2017) relation and is too small for giant planets, so their TSM is
                  overstated. A corrected relation awaits the next model rebuild.
                </p>
              </div>
              <div className="bg-space-void/80 p-4 rounded-xl border border-exosignal-purple/20 space-y-1.5">
                <span className="text-exosignal-purple font-bold block text-sm">
                  03 // Spectroscopic Feature Extraction
                </span>
                <p className="text-exosignal-text-muted">
                  Derives physical metrics: Transmission Spectroscopy Metric (TSM), Emission
                  Spectroscopy Metric (ESM), and atmospheric scale height.
                </p>
              </div>
              <div className="bg-space-void/80 p-4 rounded-xl border border-emerald-500/20 space-y-1.5">
                <span className="text-emerald-400 font-bold block text-sm">
                  04 // Parquet Columnar Storage
                </span>
                <p className="text-exosignal-text-muted">
                  Serializes processed tables to columnar Snappy-compressed Parquet, queried
                  directly in memory. Latency under load is not yet measured (see
                  reports/LOADTEST.md).
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Scoring Framework */}
      {(showAll || activeTab === 'framework') && (
        <div className="space-y-4">
          <SectionDivider
            number="03"
            title="Scoring Framework & Feature Weighting"
            subtitle="The heuristic composite. The ranking itself comes from the supervised model"
            badge="FORMULATION"
            accent="emerald"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <div>
                <h3 className="text-base font-bold text-white font-display">
                  Mathematical Component Hierarchy (0–100 Scale)
                </h3>
                <span className="text-[11px] font-mono text-exosignal-text-muted">
                  Dynamic weights synchronized from priority_scorer.py config via GET
                  /api/v1/methodology/weights
                </span>
              </div>
              <span className="text-xs font-mono text-emerald-400">
                {weightsData ? '● Live Scorer Config' : 'Loading Scorer Config...'}
              </span>
            </div>
            <div className="p-6">
              {/* Category Weight Pills */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5 font-mono text-xs">
                <div className="bg-space-void/90 p-3 rounded-xl border border-exosignal-cyan/30 text-center">
                  <span className="text-[10px] text-exosignal-text-muted block uppercase">
                    Planetary
                  </span>
                  <span className="text-lg font-bold text-exosignal-cyan">
                    {weightsData?.percentages?.planetary_relevance ?? '—'}%
                  </span>
                </div>
                <div className="bg-space-void/90 p-3 rounded-xl border border-blue-500/30 text-center">
                  <span className="text-[10px] text-exosignal-text-muted block uppercase">
                    Accessibility
                  </span>
                  <span className="text-lg font-bold text-blue-400">
                    {weightsData?.percentages?.observational_accessibility ?? '—'}%
                  </span>
                </div>
                <div className="bg-space-void/90 p-3 rounded-xl border border-amber-500/30 text-center">
                  <span className="text-[10px] text-exosignal-text-muted block uppercase">
                    Stellar
                  </span>
                  <span className="text-lg font-bold text-amber-400">
                    {weightsData?.percentages?.stellar_characteristics ?? '—'}%
                  </span>
                </div>
                <div className="bg-space-void/90 p-3 rounded-xl border border-purple-500/30 text-center">
                  <span className="text-[10px] text-exosignal-text-muted block uppercase">
                    Completeness
                  </span>
                  <span className="text-lg font-bold text-purple-400">
                    {weightsData?.percentages?.data_quality ?? '—'}%
                  </span>
                </div>
                <div className="bg-space-void/90 p-3 rounded-xl border border-rose-500/30 text-center col-span-2 sm:col-span-1">
                  <span className="text-[10px] text-exosignal-text-muted block uppercase">
                    Anomaly
                  </span>
                  <span className="text-lg font-bold text-rose-400">
                    {weightsData?.percentages?.anomaly_score ?? '—'}%
                  </span>
                </div>
              </div>

              <div className="bg-space-void/90 rounded-xl p-5 border border-exosignal-cyan/20">
                <pre
                  className="text-xs font-mono text-exosignal-cyan leading-relaxed overflow-x-auto"
                  tabIndex={0}
                >
                  {`Heuristic Composite Score (0–100; not used for the ranking)
├── Planetary Relevance (${weightsData?.percentages?.planetary_relevance ?? '—'}%)
│   ├── Earth Similarity Index (ESI) (Schulze-Makuch et al. 2011)
│   ├── Circumstellar Habitable Zone Position (Kopparapu et al. 2013/2014)
│   └── Planetary Radius Envelope (Terrestrial / Super-Earth regime)
├── Observational Accessibility (${weightsData?.percentages?.observational_accessibility ?? '—'}%)
│   ├── Distance
│   ├── 2MASS K (or J) Magnitude
│   └── Transit Depth and Period Proxy
├── Stellar Characteristics (${weightsData?.percentages?.stellar_characteristics ?? '—'}%)
│   ├── Host Star Effective Temperature (Teff)
│   ├── Stellar Radius (R☉) — smaller dwarfs maximize transit depth
│   └── Stellar Metallicity
├── Data Quality & Completeness (${weightsData?.percentages?.data_quality ?? '—'}%)
│   └── Non-missing parameter coverage across critical orbital elements
└── Anomaly Index (${weightsData?.percentages?.anomaly_score ?? '—'}%)
    ├── Isolation Forest Outlier Score
    └── Local Outlier Factor (LOF) density deviation`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 4: Scientific Constraints */}
      {(showAll || activeTab === 'constraints') && (
        <div className="space-y-4">
          <SectionDivider
            number="04"
            title="Scientific Constraints & Guardrails"
            subtitle="Caveats and methodological boundaries"
            badge="GUARDRAILS"
            accent="amber"
          />

          <div className="divided-compartment p-6">
            <div className="space-y-4 text-xs font-mono">
              <div className="p-4 rounded-xl bg-space-void/80 border border-emerald-500/20">
                <span className="text-emerald-400 font-bold block mb-1">
                  01 // No Extraterrestrial Claims
                </span>
                <p className="text-exosignal-text-secondary leading-relaxed">
                  Priority scores indicate suitability for atmospheric characterization with current
                  spectroscopic hardware. A high priority score is not a probability of life. A high
                  anomaly score means that a planet is a statistical outlier in the catalogue, often
                  because of unusual or uncertain data; it is not evidence of extraterrestrial
                  activity.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-space-void/80 border border-exosignal-cyan/20">
                <span className="text-exosignal-cyan font-bold block mb-1">02 // Missing Data</span>
                <p className="text-exosignal-text-secondary leading-relaxed">
                  Missing values are shown as missing. Inside the models they are handled by an
                  empirical mass estimate, by median imputation (ranking and anomaly models) or by a
                  neutral default (heuristic score). These substitutes are modelling assumptions,
                  not measurements.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-space-void/80 border border-amber-500/20">
                <span className="text-amber-400 font-bold block mb-1">
                  03 // Habitable Zone Approximations
                </span>
                <p className="text-exosignal-text-secondary leading-relaxed">
                  Circumstellar habitable zone boundaries follow Kopparapu et al. (2013) 1D
                  radiative-convective models, which are valid for host stars of 2600–7200 K. 80
                  catalogue planets orbit stars outside that range; their classification is an
                  extrapolation. Lying inside the zone does not show that a planet is habitable.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Methodology;
