import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Home, Telescope, Star, Heart, BarChart3, Flask, Info, X, Menu } from 'lucide-react'

const Sidebar = ({ isOpen, setIsOpen }) => {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Home', icon: Home },
    { path: '/explorer', label: 'Explorer', icon: Telescope },
    { path: '/top-targets', label: 'Top Targets', icon: Star },
    { path: '/favorites', label: 'Favorites', icon: Heart },
    { path: '/analytics', label: 'Analytics', icon: BarChart3 },
    { path: '/methodology', label: 'Methodology', icon: Flask },
    { path: '/about', label: 'About', icon: Info },
  ]

  const isActive = (path) => {
    return location.pathname === path || (path !== '/' && location.pathname.startsWith(path))
  }

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full bg-space-darker/95 backdrop-blur-xl border-r border-exosignal-blue/20 z-50 transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } lg:translate-x-0 lg:static lg:z-0 w-64`}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-exosignal-blue/10">
            <Link to="/" className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 to-violet-500 flex items-center justify-center text-space-dark font-bold text-xl shadow-lg shadow-cyan-500/20">
                E
              </div>
              <div>
                <h1 className="text-xl font-bold text-gradient">ExoSignal</h1>
                <p className="text-xs text-exosignal-text/60">Exoplanet Analysis</p>
              </div>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setIsOpen(false)}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                    isActive(item.path)
                      ? 'bg-exosignal-blue/10 text-exosignal-cyan border border-exosignal-blue/20'
                      : 'text-exosignal-text/70 hover:text-exosignal-cyan hover:bg-exosignal-blue/5'
                  }`}
                >
                  <Icon size={20} />
                  <span className="font-medium">{item.label}</span>
                </Link>
              )
            })}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-exosignal-blue/10">
            <div className="text-xs text-exosignal-text/50 space-y-1">
              <p>Scientific Research Dashboard</p>
              <p>Prioritization Scores ≠ Probability of Life</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}

export default Sidebar
