/** Colours, fonts and shadows are those of src/App.css; no new design. */

// Translucent surfaces keep their own alpha unless a class asks for one (bg-space-card versus bg-space-card/60).
const surface = (rgb, alpha) => {
  return ({ opacityValue }) =>
    opacityValue === undefined || String(opacityValue).startsWith('var(')
      ? `rgb(${rgb} / ${alpha})`
      : `rgb(${rgb} / ${opacityValue})`;
};

module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        space: {
          void: '#030409',
          dark: '#070a16',
          darker: '#04060d',
          surface: '#0c1228',
          card: surface('13 19 44', 0.85),
          inset: '#070a16',
          'card-hover': surface('19 29 66', 0.92),
          overlay: surface('5 8 20', 0.85),
        },
        exosignal: {
          blue: '#00d4ff',
          cyan: '#38bdf8',
          accent: '#0284c7',
          'accent-light': '#7dd3fc',
          purple: '#a855f7',
          'purple-light': '#c084fc',
          indigo: '#6366f1',
          'indigo-light': '#818cf8',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#f43f5e',
          red: '#ef4444',
          text: {
            DEFAULT: '#f8fafc',
            secondary: '#cbd5e1',
            muted: '#94a3b8',
            subtle: '#64748b',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Space Grotesk', 'Outfit', 'Inter', 'sans-serif'],
        orbitron: ['Orbitron', 'Space Grotesk', 'monospace'],
        mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
      },
      boxShadow: {
        'neon-cyan': 'var(--glow-cyan)',
        'neon-purple': 'var(--glow-purple)',
        'neon-emerald': 'var(--glow-emerald)',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
      },
      animation: {
        fadeIn: 'fadeIn 0.3s ease-out',
      },
    },
  },
};
