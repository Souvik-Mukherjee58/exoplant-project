import React from 'react'

const StatCard = ({ label, value, unit, icon, trend, color = 'cyan' }) => {
  const colorClasses = {
    cyan: 'from-cyan-400 to-cyan-600',
    violet: 'from-violet-400 to-violet-600',
    emerald: 'from-emerald-400 to-emerald-600',
    amber: 'from-amber-400 to-amber-600',
  }

  const bgGradient = colorClasses[color] || colorClasses.cyan

  return (
    <div className="stat-card card-subtle">
      <div className="flex items-start justify-between mb-3">
        <div className="stat-label">{label}</div>
        {icon && <span className="text-2xl opacity-50">{icon}</span>}
      </div>
      <div className="flex items-baseline space-x-2">
        <span className="stat-value bg-gradient-to-r bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(135deg, var(--exosignal-cyan) 0%, var(--exosignal-violet) 100%)` }}>
          {value}
        </span>
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {trend && (
        <div className="mt-2 text-xs flex items-center space-x-1">
          <span className={trend > 0 ? 'text-emerald-400' : 'text-red-400'}>
            {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
          <span className="text-exosignal-text/50">vs previous</span>
        </div>
      )}
    </div>
  )
}

export default StatCard
