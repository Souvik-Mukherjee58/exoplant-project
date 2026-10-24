import React, { useRef, useEffect, useState } from 'react'

/**
 * PLANETARY PRESETS with realistic astronomical parameters and color spectra
 */
export const PLANET_PRESETS = {
  trappist1e: {
    name: 'TRAPPIST-1 e',
    type: 'Temperate Terrestrial (Habitable Zone)',
    radius: '0.92 R⊕',
    teq: '251 K',
    period: '6.10 days',
    transitDepth: '0.55%',
    atmosphereColor: 'rgba(56, 189, 248, 0.45)', // Cyan aura
    baseColor: '#0a2342', // Deep oceanic blue
    landColor: '#1d5a3a', // Lush vegetation/continent
    cloudColor: 'rgba(255, 255, 255, 0.65)',
    rings: false,
    banding: false,
    glowHex: '#38bdf8'
  },
  toi700d: {
    name: 'TOI-700 d',
    type: 'Super-Earth (Inside HZ)',
    radius: '1.07 R⊕',
    teq: '269 K',
    period: '37.4 days',
    transitDepth: '0.08%',
    atmosphereColor: 'rgba(16, 185, 129, 0.45)', // Emerald aura
    baseColor: '#083344', // Turquoise ocean
    landColor: '#92400e', // Ochre iron-rich landmass
    cloudColor: 'rgba(240, 253, 250, 0.7)',
    rings: false,
    banding: false,
    glowHex: '#10b981'
  },
  k218b: {
    name: 'K2-18 b',
    type: 'Hycean Sub-Neptune (Atmospheric Methane)',
    radius: '2.61 R⊕',
    teq: '255 K',
    period: '32.9 days',
    transitDepth: '0.28%',
    atmosphereColor: 'rgba(168, 85, 247, 0.55)', // Violet methane glow
    baseColor: '#1e1b4b', // Deep indigo water world
    landColor: '#312e81', // Hydrogen-rich cloud deck
    cloudColor: 'rgba(216, 180, 254, 0.55)',
    rings: false,
    banding: true,
    glowHex: '#a855f7'
  },
  lhs1140b: {
    name: 'LHS 1140 b',
    type: 'High-Density Rocky Super-Earth',
    radius: '1.73 R⊕',
    teq: '235 K',
    period: '24.7 days',
    transitDepth: '0.12%',
    atmosphereColor: 'rgba(56, 189, 248, 0.35)',
    baseColor: '#451a03', // Dense silicate / iron crust
    landColor: '#78350f', // Basaltic terrain
    cloudColor: 'rgba(254, 243, 199, 0.45)',
    rings: false,
    banding: false,
    glowHex: '#f59e0b'
  },
  wasp96b: {
    name: 'WASP-96 b',
    type: 'Hot Gas Giant (Cloud-Free Water Features)',
    radius: '1.20 RJ',
    teq: '1285 K',
    period: '3.42 days',
    transitDepth: '1.45%',
    atmosphereColor: 'rgba(245, 158, 11, 0.55)', // Fiery golden sodium haze
    baseColor: '#7c2d12', // Amber gas layers
    landColor: '#b45309', // Atmospheric banded storms
    cloudColor: 'rgba(254, 215, 170, 0.65)',
    rings: true,
    banding: true,
    glowHex: '#f97316'
  }
}

/**
 * Real procedural 3D exoplanet visualizer with rotating surface, clouds,
 * Rayleigh scattering atmosphere aura, and interactive transit orbital beacon.
 */
const Planet3DVisualizer = ({
  initialPlanet = 'trappist1e',
  size = 360,
  showControls = true,
  interactive = true,
  className = ''
}) => {
  const canvasRef = useRef(null)
  const [selectedKey, setSelectedKey] = useState(initialPlanet)
  const [isRotating, setIsRotating] = useState(true)
  const [rotationSpeed, setRotationSpeed] = useState(1)
  const [isDragging, setIsDragging] = useState(false)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const rotationAngleRef = useRef(0)
  const cloudAngleRef = useRef(0)
  const transitAngleRef = useRef(0)

  const planet = PLANET_PRESETS[selectedKey] || PLANET_PRESETS.trappist1e

  // Handle drag interaction
  const handleMouseDown = (e) => {
    if (!interactive) return
    setIsDragging(true)
    setMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseMove = (e) => {
    if (!isDragging || !interactive) return
    const dx = e.clientX - mousePos.x
    rotationAngleRef.current += dx * 0.008
    cloudAngleRef.current += dx * 0.01
    setMousePos({ x: e.clientX, y: e.clientY })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animationFrameId

    // Canvas coordinate centers
    const width = size
    const height = size
    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    const centerX = width / 2
    const centerY = height / 2
    const radius = size * 0.36

    // Pre-generate pseudo-random continent and cloud features for consistent rotation
    const continents = []
    const numContinents = planet.banding ? 12 : 8
    for (let i = 0; i < numContinents; i++) {
      continents.push({
        lat: -60 + (i * 120) / numContinents + Math.sin(i * 1.5) * 15,
        lon: (i * 360) / numContinents,
        sizeLat: planet.banding ? 8 : 22 + (i % 3) * 8,
        sizeLon: planet.banding ? 180 : 35 + (i % 4) * 12,
        wobble: 1.5 + (i % 2) * 0.8
      })
    }

    const clouds = []
    for (let i = 0; i < 14; i++) {
      clouds.push({
        lat: -70 + (i * 140) / 14 + Math.cos(i) * 10,
        lon: (i * 420) / 14,
        width: 40 + (i % 5) * 15,
        height: 12 + (i % 3) * 6
      })
    }

    // Render loop
    const render = () => {
      ctx.clearRect(0, 0, width, height)

      if (isRotating && !isDragging) {
        rotationAngleRef.current += 0.004 * rotationSpeed
        cloudAngleRef.current += 0.0055 * rotationSpeed
        transitAngleRef.current += 0.015 * rotationSpeed
      }

      const rot = rotationAngleRef.current
      const cloudRot = cloudAngleRef.current
      const transitRot = transitAngleRef.current

      // ─── 1. ATMOSPHERIC RAYLEIGH SCATTERING GLOW (Outer Aura) ───
      const glowGrad = ctx.createRadialGradient(
        centerX, centerY, radius * 0.9,
        centerX, centerY, radius * 1.35
      )
      glowGrad.addColorStop(0, planet.atmosphereColor)
      glowGrad.addColorStop(0.5, planet.atmosphereColor.replace(/[\d.]+\)$/, '0.15)'))
      glowGrad.addColorStop(1, 'transparent')

      ctx.save()
      ctx.fillStyle = glowGrad
      ctx.beginPath()
      ctx.arc(centerX, centerY, radius * 1.35, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()

      // ─── 2. PLANETARY SPHERICAL BODY (Clipping path) ───
      ctx.save()
      ctx.beginPath()
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
      ctx.clip()

      // 2a. Base Planetary Ocean/Crust Background
      ctx.fillStyle = planet.baseColor
      ctx.fillRect(centerX - radius, centerY - radius, radius * 2, radius * 2)

      // 2b. Continents / Atmospheric Bands mapped to 3D Sphere
      ctx.fillStyle = planet.landColor
      continents.forEach((cont) => {
        // Compute relative longitude with rotation
        const currentLon = ((cont.lon + (rot * 180) / Math.PI) % 360) - 180
        // Only draw when on visible side facing observer (-90 to +90 deg)
        if (currentLon > -100 && currentLon < 100) {
          const latRad = (cont.lat * Math.PI) / 180
          const lonRad = (currentLon * Math.PI) / 180

          // Orthographic projection math
          const x = centerX + radius * Math.cos(latRad) * Math.sin(lonRad)
          const y = centerY - radius * Math.sin(latRad)
          const scale = Math.cos(lonRad) // Foreshortening towards sphere limb

          if (scale > 0) {
            ctx.beginPath()
            ctx.ellipse(
              x,
              y,
              Math.max(2, (cont.sizeLon * radius * 0.018 * scale)),
              Math.max(2, (cont.sizeLat * radius * 0.018)),
              0,
              0,
              Math.PI * 2
            )
            ctx.fill()
          }
        }
      })

      // 2c. Swirling Cloud Layer (Differentially rotating)
      ctx.fillStyle = planet.cloudColor
      clouds.forEach((cloud) => {
        const currentLon = ((cloud.lon + (cloudRot * 180) / Math.PI) % 360) - 180
        if (currentLon > -95 && currentLon < 95) {
          const latRad = (cloud.lat * Math.PI) / 180
          const lonRad = (currentLon * Math.PI) / 180

          const x = centerX + radius * Math.cos(latRad) * Math.sin(lonRad)
          const y = centerY - radius * Math.sin(latRad)
          const scale = Math.cos(lonRad)

          if (scale > 0) {
            ctx.beginPath()
            ctx.ellipse(
              x,
              y,
              Math.max(3, cloud.width * radius * 0.012 * scale),
              Math.max(2, cloud.height * radius * 0.012),
              -0.15,
              0,
              Math.PI * 2
            )
            ctx.fill()
          }
        }
      })

      // 2d. 3D Spherical Day/Night Terminator Shadow (Host Star Sunlight)
      // Light source comes from top-left (10 o'clock)
      const lightX = centerX - radius * 0.4
      const lightY = centerY - radius * 0.4
      const shadowGrad = ctx.createRadialGradient(
        lightX, lightY, radius * 0.1,
        centerX, centerY, radius * 1.05
      )
      shadowGrad.addColorStop(0, 'rgba(255, 255, 255, 0.18)') // Specular highlight
      shadowGrad.addColorStop(0.5, 'rgba(0, 0, 0, 0.0)')       // Midtones
      shadowGrad.addColorStop(0.75, 'rgba(2, 6, 23, 0.65)')    // Penumbra terminator
      shadowGrad.addColorStop(1, 'rgba(1, 2, 8, 0.96)')        // Nightside umbra

      ctx.fillStyle = shadowGrad
      ctx.fillRect(centerX - radius, centerY - radius, radius * 2, radius * 2)

      // 2e. Atmospheric Edge Scattering (Fresnel Rim Glow inside limb)
      const rimGrad = ctx.createRadialGradient(
        centerX, centerY, radius * 0.85,
        centerX, centerY, radius
      )
      rimGrad.addColorStop(0, 'rgba(255, 255, 255, 0)')
      rimGrad.addColorStop(0.7, planet.atmosphereColor.replace(/[\d.]+\)$/, '0.3)'))
      rimGrad.addColorStop(1, planet.atmosphereColor)

      ctx.fillStyle = rimGrad
      ctx.fillRect(centerX - radius, centerY - radius, radius * 2, radius * 2)

      ctx.restore() // End clipping

      // ─── 3. PLANETARY RINGS (Optional, e.g. for WASP-96 b) ───
      if (planet.rings) {
        ctx.save()
        ctx.translate(centerX, centerY)
        ctx.rotate(-0.35) // Tilt 20 degrees
        ctx.scale(1, 0.28) // Flatten into 3D ellipse perspective

        const ringGrad = ctx.createRadialGradient(0, 0, radius * 1.25, 0, 0, radius * 1.9)
        ringGrad.addColorStop(0, 'rgba(251, 191, 36, 0.0)')
        ringGrad.addColorStop(0.3, 'rgba(251, 191, 36, 0.4)')
        ringGrad.addColorStop(0.6, 'rgba(245, 158, 11, 0.15)')
        ringGrad.addColorStop(0.85, 'rgba(217, 119, 6, 0.45)')
        ringGrad.addColorStop(1, 'rgba(217, 119, 6, 0.0)')

        ctx.strokeStyle = ringGrad
        ctx.lineWidth = radius * 0.65
        ctx.beginPath()
        ctx.arc(0, 0, radius * 1.55, 0, Math.PI * 2)
        ctx.stroke()
        ctx.restore()
      }

      // ─── 4. TRANSIT SPECTROSCOPY ORBITAL PATH & PHOTOMETRIC BEACON ───
      ctx.save()
      const orbitA = radius * 1.45
      const orbitB = radius * 0.45

      // Orbital ellipse path line
      ctx.beginPath()
      ctx.ellipse(centerX, centerY, orbitA, orbitB, -0.22, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.2)'
      ctx.lineWidth = 1.2
      ctx.setLineDash([4, 6])
      ctx.stroke()

      // Orbital Transit Beacon (Telescope line of sight indicator)
      const beaconX = centerX + orbitA * Math.cos(transitRot) * Math.cos(-0.22) - orbitB * Math.sin(transitRot) * Math.sin(-0.22)
      const beaconY = centerY + orbitA * Math.cos(transitRot) * Math.sin(-0.22) + orbitB * Math.sin(transitRot) * Math.cos(-0.22)

      // Beacon glow
      const bGlow = ctx.createRadialGradient(beaconX, beaconY, 1, beaconX, beaconY, 12)
      bGlow.addColorStop(0, '#ffffff')
      bGlow.addColorStop(0.4, planet.glowHex)
      bGlow.addColorStop(1, 'transparent')

      ctx.fillStyle = bGlow
      ctx.beginPath()
      ctx.arc(beaconX, beaconY, 12, 0, Math.PI * 2)
      ctx.fill()

      // Beacon center dot
      ctx.fillStyle = '#ffffff'
      ctx.beginPath()
      ctx.arc(beaconX, beaconY, 2.5, 0, Math.PI * 2)
      ctx.fill()

      ctx.restore()

      animationFrameId = requestAnimationFrame(render)
    }

    render()

    return () => {
      cancelAnimationFrame(animationFrameId)
    }
  }, [selectedKey, isRotating, rotationSpeed, isDragging, size])

  return (
    <div className={`flex flex-col items-center select-none ${className}`}>
      {/* 3D Canvas Container with Drag Prompt */}
      <div
        className="relative group cursor-grab active:cursor-grabbing flex items-center justify-center"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <canvas
          ref={canvasRef}
          style={{ width: `${size}px`, height: `${size}px` }}
          className="transition-transform duration-300 group-hover:scale-105"
        />

        {/* Floating Planetary HUD Badge */}
        <div className="absolute top-2 left-2 pointer-events-none bg-space-void/85 border border-exosignal-cyan/30 rounded-xl px-3 py-1.5 backdrop-blur-md font-mono text-[11px] shadow-lg">
          <div className="text-exosignal-cyan font-bold tracking-wider uppercase flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span>{planet.name}</span>
          </div>
          <div className="text-[10px] text-exosignal-text-muted mt-0.5">
            {planet.type}
          </div>
        </div>

        {/* Orbiting Transit Telemetry Chip */}
        <div className="absolute bottom-2 right-2 pointer-events-none bg-space-void/85 border border-exosignal-cyan/30 rounded-xl px-3 py-1.5 backdrop-blur-md font-mono text-[10px] text-right">
          <span className="text-exosignal-text-muted block">Transit Depth</span>
          <span className="text-emerald-400 font-bold text-xs">{planet.transitDepth}</span>
        </div>

        {/* Mouse drag instruction hover hint */}
        <div className="absolute inset-x-0 bottom-6 text-center pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="bg-space-void/90 text-exosignal-cyan font-mono text-[10px] px-3 py-1 rounded-full border border-exosignal-cyan/40 shadow-neon-cyan">
            ✦ Drag mouse to rotate exoplanet in 3D ✦
          </span>
        </div>
      </div>

      {/* Preset Target Selector Pills & Rotation Speed */}
      {showControls && (
        <div className="w-full mt-4 space-y-3">
          {/* Target Tabs */}
          <div className="flex flex-wrap items-center justify-center gap-2">
            {Object.entries(PLANET_PRESETS).map(([key, p]) => (
              <button
                key={key}
                type="button"
                onClick={() => setSelectedKey(key)}
                className={`px-3 py-1.5 rounded-xl font-mono text-xs font-bold transition-all flex items-center space-x-1.5 ${
                  selectedKey === key
                    ? 'bg-exosignal-cyan/25 text-white border border-exosignal-cyan shadow-neon-cyan scale-105'
                    : 'bg-space-void/80 text-exosignal-text-muted hover:text-white border border-exosignal-cyan/15 hover:border-exosignal-cyan/40'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: p.glowHex }}
                ></span>
                <span>{p.name}</span>
              </button>
            ))}
          </div>

          {/* Quick Parameters Grid */}
          <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs bg-space-void/70 p-2.5 rounded-xl border border-exosignal-cyan/15">
            <div>
              <span className="text-[10px] text-exosignal-text-muted block">Radius</span>
              <span className="text-white font-bold">{planet.radius}</span>
            </div>
            <div>
              <span className="text-[10px] text-exosignal-text-muted block">Equilibrium Temp</span>
              <span className="text-exosignal-cyan font-bold">{planet.teq}</span>
            </div>
            <div>
              <span className="text-[10px] text-exosignal-text-muted block">Period</span>
              <span className="text-emerald-400 font-bold">{planet.period}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Planet3DVisualizer
