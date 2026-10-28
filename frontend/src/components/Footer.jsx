import React from 'react'
import { Link } from 'react-router-dom'

const Footer = () => {
  return (
    <footer className="mt-20 border-t border-exosignal-cyan/20 bg-space-void/90 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 mb-10">
          {/* Col 1: Platform Overview */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <span className="font-display text-xl font-black text-white">
                Exo<span className="text-gradient-cyan">Signal</span>
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-exosignal-cyan/20 text-exosignal-cyan border border-exosignal-cyan/30">
                v0.3.0
              </span>
            </div>
            <p className="text-xs text-exosignal-text-muted leading-relaxed">
              Production-grade machine learning platform optimizing telescope observation schedules for transmission and emission spectroscopy follow-up.
            </p>
            <div className="flex items-center space-x-2 text-xs font-mono text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>All Subsystems Operational</span>
            </div>
          </div>

          {/* Col 2: ML Engine */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono uppercase tracking-wider text-exosignal-cyan font-bold">
              Machine Learning Architecture
            </h4>
            <ul className="space-y-2 text-xs text-exosignal-text-muted">
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-cyan"></span>
                <span>LightGBM GBDT Learning-to-Rank</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-cyan"></span>
                <span>21 Astrophysical Feature Inputs</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-cyan"></span>
                <span>TreeSHAP Exact Feature Attribution</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-cyan"></span>
                <span>Out-of-Time Temporal Split (&ge; 2022 discoveries)</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-cyan"></span>
                <span>Cryptographic SHA256 Model Registry</span>
              </li>
            </ul>
          </div>

          {/* Col 3: Data & Astrometry */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono uppercase tracking-wider text-exosignal-purple font-bold">
              Astrophysical Ground Truth
            </h4>
            <ul className="space-y-2 text-xs text-exosignal-text-muted">
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-purple"></span>
                <span>NASA Exoplanet Archive (PS Comp Pars)</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-purple"></span>
                <span>Kempton et al. TSM / ESM Metrics</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-purple"></span>
                <span>Kopparapu et al. Habitable Zone Bounds</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-purple"></span>
                <span>Chen &amp; Kipping (2017) Mass-Radius Fallback</span>
              </li>
              <li className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-exosignal-purple"></span>
                <span>Confirmed JWST Cycle 1–3 Programs</span>
              </li>
            </ul>
          </div>

          {/* Col 4: Quick Links */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono uppercase tracking-wider text-exosignal-text-secondary font-bold">
              Navigation & Governance
            </h4>
            <div className="flex flex-col space-y-1 text-xs text-exosignal-text-muted">
              <Link to="/explorer" className="hover:text-exosignal-cyan transition-colors">Catalog Explorer</Link>
              <Link to="/top-targets" className="hover:text-exosignal-cyan transition-colors">Top Prioritized Targets</Link>
              <Link to="/compare" className="hover:text-exosignal-cyan transition-colors">Differential SHAP Comparison</Link>
              <Link to="/registry" className="hover:text-exosignal-cyan transition-colors">Model Registry & Lineage</Link>
              <Link to="/analytics" className="hover:text-exosignal-cyan transition-colors">Population Analytics & PCA</Link>
              <Link to="/methodology" className="hover:text-exosignal-cyan transition-colors">Formal Ranking Methodology</Link>
            </div>
          </div>
        </div>

        {/* Disclaimer & Copyright */}
        <div className="pt-8 border-t border-exosignal-cyan/10 flex flex-col md:flex-row items-center justify-between text-[11px] text-exosignal-text-subtle gap-4">
          <p>
            Scientific Disclaimer: Target Priority Scores represent comparative observational utility for spectroscopic follow-up. Scores do not represent a probability of extraterrestrial life.
          </p>
          <p className="font-mono">
            ExoSignal ML Systems • Open Scientific Follow-Up Prioritization
          </p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
