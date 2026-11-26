import React, { useState } from 'react';
import SectionDivider from '../components/SectionDivider';
import SegmentedTabs from '../components/SegmentedTabs';

const About = () => {
  const [activeTab, setActiveTab] = useState('mission');

  const aboutTabs = [
    { id: 'mission', label: 'Project Mission', icon: '🌌' },
    { id: 'tech', label: 'Technical Stack', icon: '⚡' },
    { id: 'sources', label: 'Data Sources & Provenance', icon: '🛰️' },
    { id: 'all', label: 'Full Project Dossier', icon: '📑' },
  ];

  const showAll = activeTab === 'all';

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-exosignal-cyan/20 pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-mono text-exosignal-cyan uppercase tracking-wider font-bold mb-1">
            Mission Overview & Systems Architecture
          </div>
          <h1 className="text-3xl font-black text-white font-display">About ExoSignal</h1>
          <p className="text-sm text-exosignal-text-secondary mt-1 max-w-2xl">
            A scientific machine learning platform for exoplanet spectroscopic follow-up target
            prioritization.
          </p>
        </div>
        <div className="text-xs font-mono text-emerald-400 bg-space-void/90 px-3 py-1.5 rounded-xl border border-emerald-500/30">
          Public Source Code
        </div>
      </div>

      {/* Tab Division Control */}
      <div>
        <SegmentedTabs tabs={aboutTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {/* SECTION 1: Mission */}
      {(showAll || activeTab === 'mission') && (
        <div className="space-y-4">
          <SectionDivider
            number="01"
            title="Project Mission & Objective"
            subtitle="What the project ranks, and what it does not claim"
            badge="MISSION"
            accent="cyan"
          />

          <div className="divided-compartment p-8 space-y-4">
            <h3 className="text-lg font-bold text-white font-display">
              Exploratory Target Ranking
            </h3>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              ExoSignal is a data-driven exoplanet follow-up target prioritization system. Its goal
              is to explore how catalogue data can be used to rank targets. It has not been
              validated by astronomers. The ranking concerns candidates for atmospheric
              characterization and transmission spectroscopy.
            </p>
            <p className="text-sm text-exosignal-text-secondary leading-relaxed">
              The system evaluates measurable physical properties, insolation flux, stellar host
              parameters, and observational accessibility to produce a transparent, multi-component
              priority ranking backed by exact SHAP attributions.
            </p>
          </div>
        </div>
      )}

      {/* SECTION 2: Technical Architecture */}
      {(showAll || activeTab === 'tech') && (
        <div className="space-y-4">
          <SectionDivider
            number="02"
            title="Technical Architecture & Engine Stack"
            subtitle="DuckDB, regularized logistic regression, FastAPI and React"
            badge="TECH STACK"
            accent="purple"
          />

          <div className="divided-compartment p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div className="bg-space-void/80 p-5 rounded-xl border border-exosignal-cyan/20 space-y-3">
                <h3 className="font-bold text-exosignal-cyan text-sm font-mono uppercase">
                  Backend Engine
                </h3>
                <ul className="text-xs font-mono space-y-2 text-exosignal-text-secondary">
                  <li>• FastAPI (Python 3.11) asynchronous REST microservice</li>
                  <li>
                    • DuckDB in-memory analytical query engine (latency under load not yet measured;
                    see reports/LOADTEST.md)
                  </li>
                  <li>
                    • Regularized Logistic Regression (Variant A) prioritizing transmission
                    spectroscopy targets
                  </li>
                  <li>• Linear SHAP exact local and differential feature attributions</li>
                  <li>• Local model registry versioned with SHA-256 checksums</li>
                </ul>
              </div>

              <div className="bg-space-void/80 p-5 rounded-xl border border-purple-500/20 space-y-3">
                <h3 className="font-bold text-exosignal-purple text-sm font-mono uppercase">
                  Frontend Studio
                </h3>
                <ul className="text-xs font-mono space-y-2 text-exosignal-text-secondary">
                  <li>• React 18 with modern modular component architecture</li>
                  <li>• Vite build toolchain</li>
                  <li>
                    • Recharts responsive scientific bar, pie, radar, and scatter visualizations
                  </li>
                  <li>• Custom deep space glassmorphism design system</li>
                  <li>• Divided compartments with high-contrast architectural sectioning</li>
                </ul>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-xs">
              {['DuckDB', 'Logistic Reg.', 'FastAPI', 'SHAP', 'React + Vite'].map((tech) => (
                <div
                  key={tech}
                  className="bg-space-void/90 rounded-xl p-3 text-center text-white border border-exosignal-cyan/20 font-bold"
                >
                  {tech}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* SECTION 3: Data Sources */}
      {(showAll || activeTab === 'sources') && (
        <div className="space-y-4">
          <SectionDivider
            number="03"
            title="Data Sources & Astronomical Provenance"
            subtitle="Public catalogues, and labels that are not human-verified"
            badge="PROVENANCE"
            accent="emerald"
          />

          <div className="divided-compartment p-8 space-y-4 text-xs font-mono">
            <div className="p-4 rounded-xl bg-space-void/80 border border-emerald-500/20 space-y-1">
              <span className="text-emerald-400 font-bold text-sm block">
                NASA Exoplanet Archive (IPAC / Caltech)
              </span>
              <p className="text-exosignal-text-secondary">
                Composite planet parameter catalog containing archival orbital period, radii,
                masses, stellar effective temperatures, and near-IR K-band magnitudes.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-space-void/80 border border-exosignal-cyan/20 space-y-1">
              <span className="text-exosignal-cyan font-bold text-sm block">
                JWST Approved Targets & Literature
              </span>
              <p className="text-exosignal-text-secondary">
                Candidate JWST target labels compiled from public sources. They are not
                human-verified and are incomplete; every model metric that uses them is provisional.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default About;
