import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const API = 'http://localhost:8000'

const RARITY_COLOR  = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }
const ELEMENT_COLOR = { Power: '#ef4444', Speed: '#22c55e', Tech: '#60a5fa' }
const ELEMENT_ICON  = { Power: '⚡', Speed: '💨', Tech: '⚙' }

/**
 * TeamBuilder
 * Props:
 *   playerId        – string
 *   onTeamReady     – (playerTeamIds: string[], enemyTeamIds: string[]) => void
 *   allChars        – master character list (from GET /characters)
 */
export default function TeamBuilder({ playerId, onTeamReady, allChars = [] }) {
  const [roster,       setRoster]       = useState([])
  const [playerTeam,   setPlayerTeam]   = useState([])   // pc_ids, max 3
  const [enemyTeam,    setEnemyTeam]    = useState([])   // char_ids, max 3
  const [loading,      setLoading]      = useState(true)

  useEffect(() => {
    if (!playerId) return
    fetch(`${API}/player/${playerId}/roster`)
      .then(r => r.json())
      .then(data => { setRoster(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [playerId])

  const togglePlayer = (pcId) => {
    setPlayerTeam(prev =>
      prev.includes(pcId)
        ? prev.filter(id => id !== pcId)
        : prev.length < 3 ? [...prev, pcId] : prev
    )
  }

  const toggleEnemy = (charId) => {
    setEnemyTeam(prev =>
      prev.includes(charId)
        ? prev.filter(id => id !== charId)
        : prev.length < 3 ? [...prev, charId] : prev
    )
  }

  const canStart = playerTeam.length > 0 && enemyTeam.length > 0

  const villains = allChars.filter(c => c.faction === 'villain')

  if (loading) return <div className="section-loading">Loading roster…</div>

  return (
    <div className="team-builder">
      <div className="tb-header">
        <h2>Build Your Team</h2>
        <p className="section-subtitle">Select up to 3 heroes and up to 3 enemies</p>
      </div>

      {/* ── Player team slots ── */}
      <div className="tb-slots">
        {[0, 1, 2].map(i => {
          const pcId  = playerTeam[i]
          const pc    = roster.find(r => r.id === pcId)
          const name  = pc?.master_data?.name
          const elem  = pc?.master_data?.element
          return (
            <div key={i} className={`tb-slot ${pcId ? 'filled' : 'empty'}`}>
              {pcId ? (
                <>
                  <span className="slot-icon">{ELEMENT_ICON[elem] || '🦸'}</span>
                  <span className="slot-name">{name}</span>
                  {elem && <span className="slot-elem" style={{ color: ELEMENT_COLOR[elem] }}>{elem}</span>}
                  <button className="slot-remove" onClick={() => togglePlayer(pcId)}>✕</button>
                </>
              ) : (
                <span className="slot-placeholder">+ Hero {i + 1}</span>
              )}
            </div>
          )
        })}
      </div>

      <div className="vs-label">VS</div>

      {/* ── Enemy team slots ── */}
      <div className="tb-slots enemy">
        {[0, 1, 2].map(i => {
          const charId = enemyTeam[i]
          const char   = allChars.find(c => c.id === charId)
          const elem   = char?.element
          return (
            <div key={i} className={`tb-slot enemy ${charId ? 'filled' : 'empty'}`}>
              {charId ? (
                <>
                  <span className="slot-icon">{ELEMENT_ICON[elem] || '💀'}</span>
                  <span className="slot-name">{char?.name}</span>
                  {elem && <span className="slot-elem" style={{ color: ELEMENT_COLOR[elem] }}>{elem}</span>}
                  <button className="slot-remove" onClick={() => toggleEnemy(charId)}>✕</button>
                </>
              ) : (
                <span className="slot-placeholder">+ Enemy {i + 1}</span>
              )}
            </div>
          )
        })}
      </div>

      <div className="tb-panels">
        {/* ── Hero picker ── */}
        <div className="tb-panel">
          <h3 className="panel-title">Your Heroes</h3>
          <div className="tb-card-grid">
            {roster.map(pc => {
              const master   = pc.master_data || {}
              const selected = playerTeam.includes(pc.id)
              const elem     = master.element
              return (
                <motion.button
                  key={pc.id}
                  className={`tb-card hero ${selected ? 'selected' : ''} ${playerTeam.length >= 3 && !selected ? 'maxed' : ''}`}
                  style={{ '--elem-color': ELEMENT_COLOR[elem] || '#60a5fa' }}
                  onClick={() => togglePlayer(pc.id)}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <div className="tbc-rarity" style={{ color: RARITY_COLOR[master.rarity] }}>
                    {master.rarity}
                  </div>
                  <div className="tbc-avatar">🦸</div>
                  <div className="tbc-name">{master.name}</div>
                  {elem && (
                    <div className="tbc-elem" style={{ color: ELEMENT_COLOR[elem] }}>
                      {ELEMENT_ICON[elem]} {elem}
                    </div>
                  )}
                  <div className="tbc-stats">
                    <span>Lv.{pc.level}</span>
                    <span>HP {pc.hp}</span>
                    <span>ATK {pc.atk}</span>
                  </div>
                  <div className="tbc-skill">✦ {master.skill_name}</div>
                  {selected && <div className="tbc-check">✓</div>}
                </motion.button>
              )
            })}
          </div>
        </div>

        {/* ── Enemy picker ── */}
        <div className="tb-panel">
          <h3 className="panel-title">Choose Enemies</h3>
          <div className="tb-card-grid">
            {villains.map(char => {
              const selected = enemyTeam.includes(char.id)
              const elem     = char.element
              return (
                <motion.button
                  key={char.id}
                  className={`tb-card villain ${selected ? 'selected' : ''} ${enemyTeam.length >= 3 && !selected ? 'maxed' : ''}`}
                  style={{ '--elem-color': ELEMENT_COLOR[elem] || '#ef4444' }}
                  onClick={() => toggleEnemy(char.id)}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  <div className="tbc-rarity" style={{ color: RARITY_COLOR[char.rarity] }}>
                    {char.rarity}
                  </div>
                  <div className="tbc-avatar">💀</div>
                  <div className="tbc-name">{char.name}</div>
                  {elem && (
                    <div className="tbc-elem" style={{ color: ELEMENT_COLOR[elem] }}>
                      {ELEMENT_ICON[elem]} {elem}
                    </div>
                  )}
                  <div className="tbc-stats">
                    <span>HP {char.base_hp}</span>
                    <span>ATK {char.base_atk}</span>
                    <span>SPD {char.base_spd}</span>
                  </div>
                  <div className="tbc-skill">✦ {char.skill_name}</div>
                  {selected && <div className="tbc-check">✓</div>}
                </motion.button>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Start button ── */}
      <motion.button
        className={`tb-start-btn ${canStart ? '' : 'disabled'}`}
        onClick={() => canStart && onTeamReady(playerTeam, enemyTeam)}
        disabled={!canStart}
        whileHover={canStart ? { scale: 1.04 } : {}}
        whileTap={canStart ? { scale: 0.97 } : {}}
      >
        {canStart
          ? `⚔ Fight! (${playerTeam.length}v${enemyTeam.length})`
          : 'Select at least 1 hero and 1 enemy'}
      </motion.button>
    </div>
  )
}
