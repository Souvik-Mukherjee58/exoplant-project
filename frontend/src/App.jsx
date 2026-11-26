import React from 'react';
import { BrowserRouter as Router, Link, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Home from './pages/Home';
import Explorer from './pages/Explorer';
import TopTargets from './pages/TopTargets';
import PlanetDetail from './pages/PlanetDetail';
import Compare from './pages/Compare';
import Analytics from './pages/Analytics';
import Methodology from './pages/Methodology';
import About from './pages/About';
import Favorites from './pages/Favorites';
import ModelRegistry from './pages/ModelRegistry';
import './App.css';

const NotFound = () => (
  <div className="glass-panel p-8 text-center font-mono text-sm">
    <h1 className="text-xl font-bold text-white mb-3">Page not found</h1>
    <Link to="/" className="btn-secondary-glass text-xs inline-block">
      Back to home
    </Link>
  </div>
);

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col bg-space-void text-exosignal-text">
        {/* Modern Glowing Navigation Bar */}
        <Navbar />

        {/* Main Content Area */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/top-targets" element={<TopTargets />} />
            <Route path="/favorites" element={<Favorites />} />
            <Route path="/planet/:planetName" element={<PlanetDetail />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/registry" element={<ModelRegistry />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>

        {/* Modern Scientific Footer */}
        <Footer />
      </div>
    </Router>
  );
}

export default App;
