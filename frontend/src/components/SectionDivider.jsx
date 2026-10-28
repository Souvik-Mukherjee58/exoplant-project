import React from 'react'

/**
 * SectionDivider - Cosmic dividing line with glowing accent badge and metadata
 * Provides high-contrast, beautiful architectural division between sections.
 */
const SectionDivider = ({
  number,
  title,
  subtitle,
  badge,
  icon,
  accent = 'cyan', // 'cyan' | 'purple' | 'emerald' | 'amber'
  align = 'left',
  className = ''
}) => {
  const accentClasses = {
    cyan: {
      lineLeft: 'from-transparent via-exosignal-cyan/25 to-exosignal-cyan/60',
      lineRight: 'from-exosignal-cyan/60 via-exosignal-cyan/25 to-transparent',
      text: 'text-exosignal-cyan',
      border: 'border-exosignal-cyan/30',
      bgBadge: 'bg-exosignal-cyan/10 text-exosignal-cyan border-exosignal-cyan/30',
      dot: 'bg-exosignal-cyan shadow-[0_0_8px_#38bdf8]'
    },
    purple: {
      lineLeft: 'from-transparent via-exosignal-purple/25 to-exosignal-purple/60',
      lineRight: 'from-exosignal-purple/60 via-exosignal-purple/25 to-transparent',
      text: 'text-exosignal-purple',
      border: 'border-exosignal-purple/30',
      bgBadge: 'bg-exosignal-purple/10 text-purple-300 border-purple-500/30',
      dot: 'bg-exosignal-purple shadow-[0_0_8px_#a855f7]'
    },
    emerald: {
      lineLeft: 'from-transparent via-emerald-400/25 to-emerald-400/60',
      lineRight: 'from-emerald-400/60 via-emerald-400/25 to-transparent',
      text: 'text-emerald-400',
      border: 'border-emerald-400/30',
      bgBadge: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
      dot: 'bg-emerald-400 shadow-[0_0_8px_#10b981]'
    },
    amber: {
      lineLeft: 'from-transparent via-amber-400/25 to-amber-400/60',
      lineRight: 'from-amber-400/60 via-amber-400/25 to-transparent',
      text: 'text-amber-400',
      border: 'border-amber-400/30',
      bgBadge: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
      dot: 'bg-amber-400 shadow-[0_0_8px_#f59e0b]'
    }
  }

  const currentTheme = accentClasses[accent] || accentClasses.cyan

  return (
    <div className={`relative pt-6 pb-2 ${className}`}>
      {/* Top Luminous Dividing Border */}
      <div className="relative flex items-center justify-between mb-4">
        <div className={`h-[1px] flex-1 bg-gradient-to-r ${currentTheme.lineLeft}`}></div>
        
        {/* Center/Anchor Chapter Badge */}
        <div className="mx-4 flex items-center space-x-2">
          {number && (
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-widest border ${currentTheme.bgBadge}`}>
              Section {number}
            </span>
          )}
          {badge && (
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono tracking-wider bg-space-void/90 text-exosignal-text-muted border border-exosignal-cyan/20">
              {badge}
            </span>
          )}
          <span className={`w-1.5 h-1.5 rounded-full ${currentTheme.dot}`}></span>
        </div>

        <div className={`h-[1px] flex-1 bg-gradient-to-r ${currentTheme.lineRight}`}></div>
      </div>

      {/* Optional Title & Subtitle block */}
      {(title || subtitle) && (
        <div className={`mb-6 ${align === 'center' ? 'text-center' : ''}`}>
          <div className="flex items-center space-x-2">
            {icon && <span className="text-xl">{icon}</span>}
            {title && (
              <h2 className="text-xl sm:text-2xl font-black text-white font-display tracking-tight">
                {title}
              </h2>
            )}
          </div>
          {subtitle && (
            <p className="text-xs sm:text-sm text-exosignal-text-secondary mt-1 font-mono max-w-3xl">
              {subtitle}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default SectionDivider
