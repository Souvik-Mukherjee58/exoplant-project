import React from 'react'

const Methodology = () => {
  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-6">Methodology</h1>

      {/* Scientific Context */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Scientific Context</h2>
        <p className="text-exosignal-text/80 mb-4">
          Astronomical surveys have identified thousands of confirmed exoplanets and candidates.
          However, telescope observation time is limited, making it difficult to determine which
          systems deserve greater attention when searching for possible technosignatures.
        </p>
        <p className="text-exosignal-text/80 mb-4">
          ExoSignal addresses this by combining publicly available astronomical data with
          computational analysis and machine learning to provide a scientifically interpretable
          target priority ranking.
        </p>
      </section>

      {/* Data Pipeline */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Data Pipeline</h2>
        <ol className="list-decimal list-inside space-y-3 text-exosignal-text/80">
          <li>
            <strong>Data Ingestion:</strong> Collect exoplanet and stellar parameters from
            the NASA Exoplanet Archive composite table.
          </li>
          <li>
            <strong>Data Cleaning:</strong> Standardize column names, remove invalid records,
            convert data types, handle missing values explicitly
          </li>
          <li>
            <strong>Feature Engineering:</strong> Create derived features including Earth
            similarity indices, habitable zone classifications, and observational accessibility scores
          </li>
          <li>
            <strong>Missing Value Handling:</strong> Missing values are not fabricated; they are
            explicitly handled in calculations
          </li>
          <li>
            <strong>Feature Scaling:</strong> Normalize features for ML models
          </li>
          <li>
            <strong>ML Model:</strong> Anomaly detection using Isolation Forest and Local Outlier Factor
          </li>
          <li>
            <strong>Scientific Scoring:</strong> Combine ML outputs with domain-specific scoring
          </li>
          <li>
            <strong>Final Ranking:</strong> Rank exoplanets by target priority score
          </li>
        </ol>
      </section>

      {/* Scoring Framework */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Scoring Framework</h2>
        <p className="text-exosignal-text/80 mb-4">
          The Target Priority Score is calculated using five scientifically motivated components:
        </p>
        <div className="bg-space-dark rounded-lg p-6 border border-exosignal-blue/10">
          <pre className="text-sm font-mono text-exosignal-text/80">
{`Target Priority Score (0–100)
├── Planetary Relevance (25%)
│   ├── Radius relevance (Earth-like ~1.0 R⊕)
│   ├── Mass relevance (Earth-like ~1.0 M⊕)
│   ├── Temperature relevance (moderate ~300 K)
│   └── Orbital period relevance
├── Stellar Characteristics (25%)
│   ├── Stellar temperature relevance (Sun-like ~5778 K)
│   ├── Stellar radius relevance (~1.0 R☉)
│   └── Stellar metallicity relevance
├── Observational Accessibility (20%)
│   ├── Distance score (closer = better)
│   ├── Brightness score (brighter = better)
│   └── Transit detectability (larger/shorter = better)
├── Data Quality (15%)
│   └── Number of available measurements
└── Anomaly Score (15%)
    ├── Isolation Forest anomaly detection
    └── Local Outlier Factor anomaly detection`}
          </pre>
        </div>
      </section>

      {/* Scientific Constraints */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Scientific Constraints</h2>
        <ul className="space-y-2 text-exosignal-text/80">
          <li>
            <strong>No alien claims:</strong> The priority score does not represent the probability
            of extraterrestrial life or intelligence. It is a computational ranking intended to
            identify targets that may warrant further scientific investigation.
          </li>
          <li>
            <strong>Missing data:</strong> Missing values are handled explicitly and never fabricated.
            Planets with insufficient data are labeled "Insufficient data" rather than being assigned
            incorrect values.
          </li>
          <li>
            <strong>Anomaly ≠ Alien:</strong> Anomaly scores indicate unusual combinations of
            astronomical properties relative to the analyzed dataset, not extraterrestrial activity.
          </li>
          <li>
            <strong>Habitable Zone:</strong> HZ status is an approximate estimate based on stellar
            luminosity and orbital distance. Being in or near the HZ does not guarantee habitability.
          </li>
        </ul>
      </section>

      {/* Machine Learning */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Machine Learning Approach</h2>
        <p className="text-exosignal-text/80 mb-4">
          ExoSignal uses unsupervised machine learning for anomaly detection, not prediction.
          The models identify unusual combinations of astronomical properties without requiring
          labeled ground truth data (which doesn't exist for technosignature detection).
        </p>
        <div className="bg-space-dark rounded-lg p-6 border border-exosignal-blue/10">
          <h3 className="text-lg font-medium text-exosignal-text mb-3">Models Used</h3>
          <ul className="space-y-2 text-exosignal-text/80">
            <li>
              <strong>Isolation Forest:</strong> Identifies anomalies by isolating unusual observations.
              Anomalous points require fewer splits to isolate in the tree structure.
            </li>
            <li>
              <strong>Local Outlier Factor (LOF):</strong> Measures the local density deviation of a
              point relative to its neighbors. Points with significantly lower local density are flagged.
            </li>
          </ul>
          <p className="text-sm text-exosignal-text/60 mt-4">
            The combined anomaly score is the average of both model scores, normalized to 0–1 range
            where 1 indicates the most anomalous observations.
          </p>
        </div>
      </section>

      {/* Observational Suitability */}
      <section className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-8 mb-8">
        <h2 className="text-xl font-semibold text-exosignal-text mb-4">Observational Suitability</h2>
        <p className="text-exosignal-text/80 mb-4">
          Observational accessibility estimates how practical a target may be for observation
          using factors such as distance, stellar brightness, transit detectability, and data
          availability.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <h4 className="font-medium text-exosignal-text mb-2">Distance</h4>
            <p className="text-exosignal-text/70 text-sm">
              Closer stars are easier to observe. Distance score is calculated as 1/(1+d/100)
              where d is distance in parsecs.
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <h4 className="font-medium text-exosignal-text mb-2">Transit Detectability</h4>
            <p className="text-exosignal-text/70 text-sm">
              Larger planets with shorter orbital periods produce more detectable transit signals.
            </p>
          </div>
          <div className="bg-space-dark rounded-lg p-4 border border-exosignal-blue/10">
            <h4 className="font-medium text-exosignal-text mb-2">Data Quality</h4>
            <p className="text-exosignal-text/70 text-sm">
              Based on the number of available measurements (radius, mass, temperature, semi-major axis, eccentricity).
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

export default Methodology