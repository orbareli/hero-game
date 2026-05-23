import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

//const API = 'http://localhost:8000'
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const RARITY_COLOR = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }
const RARITY_BG    = { C: '#1e293b', R: '#1e3a5f', SR: '#2e1a47', UR: '#3d2a00' }

export default function Roster({ playerId, onSelectFighter }) {
  const [roster,  setRoster]  = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    if (!playerId) return
    setLoading(true)
    fetch(`${API}/player/${playerId}/roster`)
      .then(r => {
        if (!r.ok) throw new Error('Failed to load roster')
        return r.json()
      })
      .then(data => { setRoster(data); setLoading(false) })
      .catch(e  => { setError(e.message); setLoading(false) })
  }, [playerId])

  const handleSelect = (pc) => {
    setSelected(pc.id)
    if (onSelectFighter) onSelectFighter(pc.id)
  }

  if (loading) return <div className="section-loading">Loading roster…</div>
  if (error)   return <div className="section-error">Error: {error}</div>

  if (roster.length === 0) {
    return (
      <div className="roster-empty">
        <p>🎴 No characters yet!</p>
        <p>Head to the Shop to summon your first hero.</p>
      </div>
    )
  }

  return (
    <div className="roster-page">
      <div className="section-header">
        <h2>Your Roster</h2>
        <p className="section-subtitle">{roster.length} character{roster.length !== 1 ? 's' : ''} owned</p>
      </div>

      <div className="roster-grid">
        {roster.map((pc, i) => {
          const master = pc.master_data || {}
          const rarity = master.rarity || 'C'
          const isSelected = selected === pc.id

          return (
            <motion.div
              key={pc.id}
              className={`roster-card ${isSelected ? 'selected' : ''}`}
              style={{
                '--rarity-color': RARITY_COLOR[rarity],
                '--rarity-bg':    RARITY_BG[rarity],
              }}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => handleSelect(pc)}
            >
              {/* Rarity badge */}
              <div className="card-rarity" style={{ color: RARITY_COLOR[rarity] }}>
                {'★'.repeat(rarity === 'UR' ? 4 : rarity === 'SR' ? 3 : rarity === 'R' ? 2 : 1)}
                <span className="rarity-label">{rarity}</span>
              </div>

              {/* Avatar */}
              <div className="card-avatar">
                {master.faction === 'villain' ? '💀' : '🦸'}
              </div>

              {/* Name + faction */}
              <div className="card-name">{master.name || 'Unknown'}</div>
              <div className="card-faction" style={{ color: master.faction === 'villain' ? '#f87171' : '#60a5fa' }}>
                {master.faction}
              </div>

              {/* Level */}
              <div className="card-level">Lv.{pc.level}</div>

              {/* Stat block */}
              <div className="card-stats">
                <Stat label="HP"  value={pc.hp} />
                <Stat label="ATK" value={pc.atk} />
                <Stat label="DEF" value={pc.defense} />
                <Stat label="SPD" value={pc.spd} />
              </div>

              {/* Skill preview */}
              {master.skill_name && (
                <div className="card-skill">
                  <span className="skill-icon">✦</span>
                  <span>{master.skill_name}</span>
                </div>
              )}

              {/* Select button */}
              <button
                className={`card-select-btn ${isSelected ? 'selected' : ''}`}
                onClick={(e) => { e.stopPropagation(); handleSelect(pc) }}
              >
                {isSelected ? '✓ Selected for Battle' : 'Select for Battle'}
              </button>

              {/* Dupe counter */}
              {pc.duplicates > 0 && (
                <div className="card-dupes">+{pc.duplicates} dupes</div>
              )}
            </motion.div>
          )
        })}
      </div>

      {selected && (
        <motion.div
          className="roster-cta"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          Hero selected! Switch to the Battle tab to fight.
        </motion.div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat-item">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}