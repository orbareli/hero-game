import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const CATEGORY_COLOR = {
  atk:     '#ef4444',
  hp:      '#22c55e',
  energy:  '#fbbf24',
  crit:    '#c084fc',
  def:     '#60a5fa',
  utility: '#fb923c',
}
const CATEGORY_ICON = {
  atk: '⚔', hp: '❤', energy: '⚡', crit: '🎯', def: '🛡', utility: '✦',
}

/**
 * BuffSelect
 * Props:
 *   sessionId  – string
 *   onSelected – (updatedSession) => void
 */
export default function BuffSelect({ sessionId, onSelected }) {
  const [buffs,    setBuffs]    = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [chosen,   setChosen]   = useState(null)
  const [applying, setApplying] = useState(false)

  // Load buff choices on first render
  React.useEffect(() => {
    fetch(`http://localhost:8000/tower/${sessionId}/buffs`)
      .then(r => r.json())
      .then(d => setBuffs(d.buffs))
      .catch(console.error)
  }, [sessionId])

  const handleApply = async (buffId) => {
    if (applying) return
    setChosen(buffId)
    setApplying(true)
    try {
      const res  = await fetch(`http://localhost:8000/tower/${sessionId}/apply-buff`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ buff_id: buffId }),
      })
      const data = await res.json()
      if (onSelected) onSelected(data)
    } catch (e) {
      console.error(e)
    } finally {
      setApplying(false)
    }
  }

  if (!buffs) return <div className="section-loading">Loading buffs…</div>

  return (
    <div className="buff-select">
      <motion.h2
        className="buff-title"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        ✦ Choose a Power-Up
      </motion.h2>
      <p className="buff-subtitle">Select one permanent buff for your team</p>

      <div className="buff-cards">
        {buffs.map((buff, i) => {
          const color = CATEGORY_COLOR[buff.category] || '#94a3b8'
          const icon  = CATEGORY_ICON[buff.category]  || '✦'
          return (
            <motion.button
              key={buff.id}
              className={`buff-card ${chosen === buff.id ? 'selected' : ''}`}
              style={{ '--buff-color': color }}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              whileHover={{ scale: 1.04, y: -4 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => handleApply(buff.id)}
              disabled={applying}
            >
              <div className="buff-card-icon" style={{ color }}>
                {icon}
              </div>
              <div className="buff-card-category" style={{ color }}>
                {buff.category.toUpperCase()}
              </div>
              <div className="buff-card-name">{buff.name}</div>
              <div className="buff-card-desc">{buff.description}</div>

              {chosen === buff.id && applying && (
                <motion.div
                  className="buff-applying"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  Applying…
                </motion.div>
              )}
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
