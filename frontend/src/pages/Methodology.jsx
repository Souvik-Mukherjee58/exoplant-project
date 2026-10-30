import React, { useState } from 'react';
import SectionDivider from '../components/SectionDivider';
import SegmentedTabs from '../components/SegmentedTabs';

const Methodology = () => {
  const [activeTab, setActiveTab] = useState('framework');

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
              oversubscribed by factors of 4× to 7×.
            </p>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              ExoSignal addresses this by fusing NASA Exoplanet Archive composite physical
              parameters with supervised regularized logistic regression models, columnar querying
              in DuckDB, and exact linear SHAP attribution to provide an empirically grounded target
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
                  Applies Chen & Kipping (2017) probabilistic mass-radius relations when dynamical
                  RV masses are unmeasured.
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
                  directly in memory with sub-10ms latency.
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
            subtitle="Multi-component ranking formulation combining supervised ML and domain astrophysical models"
            badge="FORMULATION"
            accent="emerald"
          />

          <div className="divided-compartment">
            <div className="compartment-header">
              <h3 className="text-base font-bold text-white font-display">
                Mathematical Component Hierarchy (0–100 Scale)
              </h3>
              <span className="text-xs font-mono text-emerald-400">
                Regularized Logistic Regression (Variant A)
              </span>
            </div>
            <div className="p-6">
              <div className="bg-space-void/90 rounded-xl p-5 border border-exosignal-cyan/20">
                <pre className="text-xs font-mono text-exosignal-cyan leading-relaxed overflow-x-auto">
                  {`Target Priority Score (0–100)
├── Planetary Bulk Properties (25%)
│   ├── Planetary Radius (Earth-like / Sub-Neptune boundary ~1.6–2.0 R⊕)
│   ├── Planetary Mass & Bulk Density Proxy (g/cm³)
│   ├── Equilibrium Temperature (~200–350 K temperate window)
│   └── Insolation Flux (S/S⊕)
├── Host Star & Radiative Environment (25%)
│   ├── Host Star Effective Temperature (Teff)
│   ├── Stellar Radius (R☉) — smaller M-dwarfs yield higher transit depths
│   └── 2MASS Near-Infrared K-Magnitude (stellar flux in spectroscopy bands)
├── Observational Transmission Yield (20%)
│   ├── Transmission SNR Proxy (~ (Rp² · H) / (Rs² · 10^(0.2·K)))
│   ├── Atmospheric Scale Height (H = k·T / (μ·g))
│   └── Distance Attenuation (parsec geometric dilution)
├── Data Quality & Completeness (15%)
│   └── Non-missing parameter coverage across critical orbital elements
└── Anomaly Index (15%)
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
            subtitle="Transparent caveats, methodological boundaries, and anti-hallucination standards"
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
                  spectroscopic hardware. A high score does not represent probability of
                  extraterrestrial biosignatures.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-space-void/80 border border-exosignal-cyan/20">
                <span className="text-exosignal-cyan font-bold block mb-1">
                  02 // Zero Fabrication of Missing Data
                </span>
                <p className="text-exosignal-text-secondary leading-relaxed">
                  Missing parameters are treated explicitly via documented physical fallbacks (e.g.
                  Chen & Kipping mass estimation) or penalized under data completeness. Missing
                  values are never fabricated.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-space-void/80 border border-amber-500/20">
                <span className="text-amber-400 font-bold block mb-1">
                  03 // Habitable Zone Approximations
                </span>
                <p className="text-exosignal-text-secondary leading-relaxed">
                  Circumstellar habitable zone boundaries follow Kopparapu et al. (2013) 1D
                  radiative-convective equilibrium models. Being inside the HZ is a necessary but
                  insufficient condition for habitability.
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
