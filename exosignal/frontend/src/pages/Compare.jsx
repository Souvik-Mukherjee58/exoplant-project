import React from 'react'
import { Link } from 'react-router-dom'

const Compare = () => {
  const [selectedPlanets, setSelectedPlanets] = useState([])
  const [loading] = useState(false)

  const mockPlanets = [
    { name: 'TOI-2136 b', radius: 2.1, mass: 6.5, period: 8.2, temp: 385, priority: 87 },
    { name: 'Kepler-69 c', radius: 1.7, mass: 3.1, period: 32.1, temp: 325, priority: 91 },
    { name: 'TOI-2336 b', radius: 1.9, mass: 5.2, period: 12.8, temp: 412, priority: 78 },
    { name: 'Kepler-442 b', radius: 1.34, mass: 2.3, period: 112.3, temp: 302, priority: 94 },
    { name: 'TOI-561 b', radius: 1.33, mass: 2.2, period: 1.3, temp: 478, priority: 72 },
  ]

  const togglePlanetSelection = (planet) => {
    if (selectedPlanets.find(p => p.name === planet.name)) {
      setSelectedPlanets(selectedPlanets.filter(p => p.name !== planet.name))
    } else {
      if (selectedPlanets.length < 4) {
        setSelectedPlanets([...selectedPlanets, planet])
      }
    }
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-exosignal-text mb-4">Compare Exoplanets</h1>
      <p className="text-exosignal-text/70 mb-6">
        Select up to 4 exoplanets to compare their properties, characteristics, and priority scores.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-4">
            <h3 className="text-lg font-semibold text-exosignal-text mb-4">Select Planets</h3>
            <div className="space-y-2">
              {mockPlanets.map((planet) => (
                <label
                  key={planet.name}
                  className={`block p-3 rounded-lg border transition cursor-pointer
                    ${selectedPlanets.find(p => p.name === planet.name)
                      ? 'bg-exosignal-blue/30 border-exosignal-accent'
                      : 'bg-space-dark border-exosignal-blue/20 hover:border-exosignal-blue/50'}`}
                >
                  <input
                    type="checkbox"
                    checked={!!selectedPlanets.find(p => p.name === planet.name)}
                    onChange={() => togglePlanetSelection(planet)}
                    className="mr-3 accent-exosignal-accent"
                  />
                  <span className="font-medium text-exosignal-text">{planet.name}</span>
                  <div className="text-xs text-exosignal-text/70 mt-1">
                    Priority: {planet.priority}
                  </div>
                </label>
              ))}
            </div>

            {selectedPlanets.length === 0 && (
              <p className="text-exosignal-text/70 text-sm mt-4">
                Select at least one planet to compare
              </p>
            )}
          </div>
        </div>

        <div className="lg:col-span-3">
          <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 overflow-hidden">
            {selectedPlanets.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-exosignal-blue/10">
                  <thead className="bg-space-dark">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">Property</th>
                      {selectedPlanets.map((planet) => (
                        <th key={planet.name} className="px-6 py-3 text-left text-xs font-medium text-exosignal-text/70 uppercase">
                          {planet.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-exosignal-blue/10">
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Radius</td>
                      {selectedPlanets.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.radius} R⊕
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Mass</td>
                      {selectedPlanets.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.mass} M⊕
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Period</td>
                      {selectedPlanets.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.period} days
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Temperature</td>
                      {selectedPlanets.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-text/70">
                          {planet.temp} K
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-exosignal-text font-medium">Priority Score</td>
                      {selectedPlanets.map((planet) => (
                        <td key={planet.name} className="px-6 py-4 text-exosignal-accent font-semibold">
                          {planet.priority}/100
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-12 text-center text-exosignal-text/70">
                <div className="w-12 h-12 mx-auto mb-4 text-exosignal-text/50">
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                  </svg>
                </div>
                <p className="text-lg">Select planets to compare</p>
                <p className="text-sm mt-2">Choose up to 4 exoplanets for side-by-side comparison</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Compare