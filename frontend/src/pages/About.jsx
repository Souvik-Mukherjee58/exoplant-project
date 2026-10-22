import React from 'react'

const About = () => {
  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">About ExoSignal</h1>

      {/* Project Mission */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Project Mission</h2>
        <p className="text-exosignal-text/80 mb-4">
          ExoSignal is a data-driven exoplanet follow-up target prioritization system.
          Its goal is to assist astronomers in optimizing telescope observation time by identifying
          and ranking candidates for atmospheric characterization and spectroscopic follow-up.
        </p>
        <p className="text-exosignal-text/80 mb-4">
          The system evaluates measurable physical properties, insolation flux, stellar host parameters,
          and observational accessibility to produce a transparent, multi-component priority ranking.
        </p>
      </section>

      {/* Data Sources */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Data Sources</h2>
        <ul className="list-disc list-inside space-y-2 text-exosignal-text/80">
          <li>
            NASA Exoplanet Archive (IPAC / Caltech) — confirmed exoplanet parameters and stellar measurements
          </li>
          <li>
            Peer-reviewed spectroscopic follow-up literature and transit survey catalogs
          </li>
        </ul>
      </section>

      {/* Technical Architecture */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Technical Architecture</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div className="text-exosignal-text/80">
            <h3 className="font-medium text-exosignal-blue mb-3">Backend</h3>
            <ul className="list-disc list-inside space-y-2">
              <li>FastAPI (Python) REST Service</li>
              <li>Pandas and NumPy for vectorized data pipelines</li>
              <li>scikit-learn for outlier and feature analysis</li>
              <li>Typed Pydantic schemas and structured validation</li>
              <li>Modular service and scoring architecture</li>
            </ul>
          </div>
          <div className="text-exosignal-text/80">
            <h3 className="font-medium text-exosignal-blue mb-3">Frontend</h3>
            <ul className="list-disc list-inside space-y-2">
              <li>React 18 with React Router v6</li>
              <li>Vite build tool</li>
              <li>Scientific dark mode design system (CSS custom properties)</li>
              <li>Recharts interactive data visualizations</li>
              <li>Accessible responsive layouts</li>
            </ul>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {['React', 'FastAPI', 'scikit-learn', 'pandas', 'Plotly'].map(
            tech => (
              <div
                key={tech}
                className="bg-space-dark rounded-lg p-3 text-center text-exosignal-text/70"
              >
                {tech}
              </div>
            )
          )}
        </div>
      </section>

      {/* Scientific Limitations */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Scientific Limitations</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 border-l-4 border-exosignal-blue">
            <p className="font-medium text-exosignal-blue mb-2">Data Limitations</p>
            <ul className="list-disc list-inside text-exosignal-text/80">
              <li>Parameter coverage varies across exoplanet systems</li>
              <li>Many properties have significant measurement uncertainties</li>
              <li>Distances and parameters for many systems are estimated</li>
              <li>Stellar properties for all systems may not be available</li>
            </ul>
          </div>
          <div className="p-4 border-l-4 border-exosignal-blue">
            <p className="font-medium text-exosignal-blue mb-2">Methodological Limitations</p>
            <ul className="list-disc list-inside text-exosignal-text/80">
              <li>Priority scores are computationally derived rankings</li>
              <li>Weights and formulas are scientifically motivated but not definitively calibrated</li>
              <li>Habitable zone estimates are approximate</li>
              <li>Anomaly scores detect unusual patterns, not extraterrestrial activity</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Contact / References */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">References</h2>
        <ul className="list-disc list-inside text-exosignal-text/80 space-y-1">
          <li>
            NASA Exoplanet Archive: <a
              href="https://exoplanetarchive.ipac.caltech.edu"
              target="_blank"
              className="text-exosignal-blue hover:underline"
            >exoplanetarchive.ipac.caltech.edu</a>
          </li>
          <li>
            NASA Exoplanet Catalog: <a
              href="https://nasa.gov/exoplanets"
              target="_blank"
              className="text-exosignal-blue hover:underline"
            >nasa.gov/exoplanets</a>
          </li>
          <li>
            ESA Gaia Archive: <a
              href="https://gea.esac.esa.int/archive/"
              target="_blank"
              className="text-exosignal-blue hover:underline"
            >gea.esac.esa.int/archive</a>
          </li>
        </ul>
        <p className="mt-4 text-exosignal-text/70">
          This project is for research and educational purposes only.
        </p>
      </section>
    </div>
  )
}

export default About