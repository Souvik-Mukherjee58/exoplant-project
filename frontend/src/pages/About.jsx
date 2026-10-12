import React from 'react'

const About = () => {
  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">About ExoSignal</h1>

      {/* Project Mission */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Project Mission</h2>
        <p className="text-exosignal-text/80 mb-4">
          ExoSignal is an AI-assisted exoplanet technosignature target prioritization system.
          Its goal is to help astronomers identify the most promising exoplanet systems for
          follow-up observations in the search for possible technosignatures.
        </p>
        <p className="text-exosignal-text/80 mb-4">
          The system does not claim to detect extraterrestrial civilizations or calculate the
          probability that aliens exist on a planet. Instead, it computes a scientifically
          interpretable target priority score based on measurable astronomical and observational
          characteristics.
        </p>
      </section>

      {/* Data Sources */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Data Sources</h2>
        <ul className="list-disc list-inside space-y-2 text-exosignal-text/80">
          <li>
            NASA Exoplanet Archive — primary source for confirmed exoplanet parameters
          </li>
          <li>
            NASA Exoplanet Catalog — additional data on exoplanet systems
          </li>
          <li>
            ESA Gaia mission — stellar information including effective temperature, radius, and
            luminosity
          </li>
          <li>
            Scientific literature and catalog entries for supplementary data where available
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
              <li>FastAPI with Python</li>
              <li>Pandas and NumPy for data processing</li>
              <li>scikit-learn for ML anomaly detection</li>
              <li>SQLite for data persistence</li>
              <li>Modular services architecture</li>
            </ul>
          </div>
          <div className="text-exosignal-text/80">
            <h3 className="font-medium text-exosignal-blue mb-3">Frontend</h3>
            <ul className="list-disc list-inside space-y-2">
              <li>React with React Router</li>
              <li>Vite build tool</li>
              <li>Tailwind CSS for styling</li>
              <li>Recharts/Plotly for visualizations</li>
              <li>Custom scientific typography</li>
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