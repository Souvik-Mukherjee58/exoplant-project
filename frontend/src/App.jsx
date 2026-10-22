import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
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

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-space-dark text-exosignal-text">
        {/* Navigation */}
        <nav className="bg-space-darker border-b border-exosignal-blue/30 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <Link to="/" className="text-2xl font-bold text-exosignal-accent tracking-wide">
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
            <Route path="/" element={<Home />} />
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
      </div>
    </Router>
  )
}

export default App
