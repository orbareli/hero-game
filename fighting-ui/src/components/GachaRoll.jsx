import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const RARITY_CONFIG = {
  C:  { color: '#94a3b8', glow: 'rgba(148,163,184,0.4)', label: 'Common',    duration: 0.4 },
  R:  { color: '#60a5fa', glow: 'rgba(96,165,250,0.5)',  label: 'Rare',       duration: 0.6 },
  SR: { color: '#c084fc', glow: 'rgba(192,132,252,0.6)', label: 'Super Rare', duration: 0.9 },
  UR: { color: '#fbbf24', glow: 'rgba(251,191,36,0.8)',  label: 'Ultra Rare', duration: 1.3 },
}

/**
 * GachaRoll
 * Wraps the Shop's summon button and plays a rarity reveal animation.
 *
 * Props:
 *   playerId    – string
 *   coins       – number
 *   onResult    – (character, updatedPlayer) => void
 */
export default function GachaRoll({ playerId, coins, onResult }) {
  const [rolling,   setRolling]   = useState(false)
  const [revealed,  setRevealed]  = useState(null)  // character doc
  const [phase,     setPhase]     = useState('idle') // idle | flipping | revealing | done

  const COST = 100

  const handleRoll = async () => {
    if (rolling || coins < COST) return
    setRolling(true)
    setPhase('flipping')
    setRevealed(null)

    try {
      const res  = await fetch(`http://localhost:8000/shop/summon?player_id=${playerId}`, {
        method: 'POST',
      })
      const data = await res.json()
      if (!data.success) throw new Error(data.message || 'Summon failed')

      const char   = data.character
      const config = RARITY_CONFIG[char.rarity] || RARITY_CONFIG.C

      // Wait for flip animation, then reveal
      setTimeout(() => {
        setRevealed(char)
        setPhase('revealing')
        setTimeout(() => setPhase('done'), config.duration * 1000 + 400)
      }, 600)

      if (onResult) onResult(char, data.player)
    } catch (err) {
      setPhase('idle')
    } finally {
      setRolling(false)
    }
  }

  const dismiss = () => { setPhase('idle'); setRevealed(null) }

  const cfg = revealed ? RARITY_CONFIG[revealed.rarity] || RARITY_CONFIG.C : null

  return (
    <div className="gacha-wrap">
      {/* Roll button */}
      <button
        className={`gacha-btn ${coins < COST ? 'poor' : ''} ${rolling ? 'rolling' : ''}`}
        onClick={handleRoll}
        disabled={coins < COST || rolling}
      >
        {rolling ? '✨ Rolling…' : `🎲 Summon  🪙 ${COST}`}
      </button>

      {/* Odds display */}
      <div className="gacha-odds">
        {Object.entries(RARITY_CONFIG).map(([r, c]) => (
          <span key={r} style={{ color: c.color }}>
            {r} {r === 'C' ? '70%' : r === 'R' ? '20%' : r === 'SR' ? '8%' : '2%'}
          </span>
        ))}
      </div>

      {/* Animation overlay */}
      <AnimatePresence>
        {phase !== 'idle' && (
          <motion.div
            className="gacha-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={phase === 'done' ? dismiss : undefined}
          >
            <motion.div
              className="gacha-card-wrap"
              animate={
                phase === 'flipping'
                  ? { rotateY: [0, 90] }
                  : phase === 'revealing' || phase === 'done'
                    ? { rotateY: [90, 0] }
                    : {}
              }
              transition={{ duration: 0.5 }}
            >
              {/* Card back (spinning) */}
              {phase === 'flipping' && (
                <div className="gacha-card back">
                  <span className="gacha-question">?</span>
                </div>
              )}

              {/* Card front (revealed) */}
              {(phase === 'revealing' || phase === 'done') && revealed && (
                <motion.div
                  className="gacha-card front"
                  style={{
                    '--rarity-color': cfg.color,
                    '--rarity-glow':  cfg.glow,
                  }}
                  initial={{ scale: 0.8 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                >
                  {/* Rarity flash for SR/UR */}
                  {(revealed.rarity === 'SR' || revealed.rarity === 'UR') && (
                    <motion.div
                      className="gacha-flash"
                      initial={{ opacity: 0.9, scale: 0.5 }}
                      animate={{ opacity: 0, scale: 3 }}
                      transition={{ duration: cfg.duration }}
                    />
                  )}

                  <div className="gacha-rarity-label" style={{ color: cfg.color }}>
                    {'★'.repeat(revealed.rarity === 'UR' ? 4 : revealed.rarity === 'SR' ? 3 : revealed.rarity === 'R' ? 2 : 1)}
                    <span>{cfg.label}</span>
                  </div>

                  <div className="gacha-avatar">
                    {revealed.faction === 'villain' ? '💀' : '🦸'}
                  </div>

                  <div className="gacha-name">{revealed.name}</div>
                  <div className="gacha-faction">{revealed.faction}</div>
                  <div className="gacha-skill">✦ {revealed.skill_name}</div>

                  {phase === 'done' && (
                    <motion.div
                      className="gacha-tap-hint"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.5 }}
                    >
                      tap to close
                    </motion.div>
                  )}
                </motion.div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
