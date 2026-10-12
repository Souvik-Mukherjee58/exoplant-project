import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import axios from 'axios'
import Home from './pages/Home'
import Explorer from './pages/Explorer'
import TopTargets from './pages/TopTargets'
import PlanetDetail from './pages/PlanetDetail'
import Compare from './pages/Compare'
import Analytics from './pages/Analytics'
import Methodology from './pages/Methodology'
import About from './pages/About'
import Favorites from './pages/Favorites'
import './App.css'

const API_BASE_URL = 'http://localhost:8000/api/v1'

function App() {
  const [planets, setPlanets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    const fetchPlanets = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/planets?limit=50`)
        setPlanets(response.data)
        setError(null)
      } catch (err) {
        setError('Failed to load exoplanet data')
        console.error('Error fetching planets:', err)
      } finally {
        setLoading(false)
      }
    }

    const fetchStats = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/analysis`)
        setStats(response.data)
      } catch (err) {
        console.error('Error fetching stats:', err)
      }
    }

    fetchPlanets()
    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-space-dark flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-exosignal-accent"></div>
          <p className="mt-4 text-exosignal-text">Loading ExoSignal data...</p>
        </div>
      </div>
    )
  }

  return (
    <Router>
      <div className="min-h-screen bg-space-dark text-exosignal-text">
        {/* Navigation */}
        <nav className="bg-space-darker border-b border-exosignal-blue/30">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <Link to="/" className="text-2xl font-bold text-exosignal-accent">
                  ExoSignal
                </Link>
              </div>
              <div className="flex items-center space-x-4">
                <Link to="/" className="text-exosignal-text hover:text-exosignal-accent">Home</Link>
                <Link to="/explorer" className="text-exosignal-text hover:text-exosignal-accent">Explorer</Link>
                <Link to="/top-targets" className="text-exosignal-text hover:text-exosignal-accent">Top Targets</Link>
                <Link to="/favorites" className="text-exosignal-text hover:text-exosignal-accent">Favorites</Link>
                <Link to="/analytics" className="text-exosignal-text hover:text-exosignal-accent">Analytics</Link>
                <Link to="/methodology" className="text-exosignal-text hover:text-exosignal-accent">Methodology</Link>
                <Link to="/about" className="text-exosignal-text hover:text-exosignal-accent">About</Link>
              </div>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<Home planets={planets} stats={stats} />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/top-targets" element={<TopTargets />} />
            <Route path="/favorites" element={<Favorites />} />
            <Route path="/planet/:planetName" element={<PlanetDetail />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/about" element={<About />} />
          </Routes>
        </main>

        {/* Error Toast */}
        {error && (
          <div className="fixed bottom-4 right-4 bg-red-900 border border-red-500 text-white px-4 py-3 rounded">
            {error}
          </div>
        )}
      </div>
    </Router>
  )
}

export default App
