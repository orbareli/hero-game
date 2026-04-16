import React, { useMemo } from 'react'
import { motion } from 'framer-motion'

const FLOOR_ICON = {
  battle:  '⚔',
  boss:    '💀',
  revive:  '💚',
  buff:    '✦',
  start:   '🏁',
}
const FLOOR_COLOR = {
  battle:  '#60a5fa',
  boss:    '#ef4444',
  revive:  '#22c55e',
  buff:    '#fbbf24',
  start:   '#94a3b8',
}

const TOTAL = 30

/**
 * TowerMap
 * Props:
 *   currentFloor   – number (1–30)
 *   floorHistory   – [{floor, outcome}]
 *   onSelectFloor  – (floor) => void  (only current floor is clickable)
 *   pendingBuff    – bool
 *   session        – full session object
 */
export default function TowerMap({ currentFloor, floorHistory, onSelectFloor, pendingBuff, session }) {
  const historyMap = useMemo(() => {
    const m = {}
    for (const h of (floorHistory || [])) m[h.floor] = h.outcome
    return m
  }, [floorHistory])

  const getFloorType = (f) => {
    if (f === 0) return 'start'
    if ([14, 24].includes(f)) return 'revive'
    if (f % 5 === 0) return 'boss'
    return 'battle'
  }

  // Build floor nodes from top (30) to bottom (1) for visual tower feel
  const floors = Array.from({ length: TOTAL }, (_, i) => TOTAL - i)

  return (
    <div className="tower-map">
      <div className="tower-title">
        <span className="tower-icon">🗼</span>
        <h2>Tower of Trials</h2>
        <p className="tower-subtitle">Floor {currentFloor} / {TOTAL}</p>
      </div>

      {/* Active buffs strip */}
      {session?.active_buffs?.length > 0 && (
        <div className="tower-buffs-strip">
          {session.active_buffs.map(b => (
            <span key={b.id} className={`buff-pip ${b.category}`} title={b.description}>
              {b.name}
            </span>
          ))}
        </div>
      )}

      {/* Pending buff warning */}
      {pendingBuff && (
        <motion.div
          className="pending-buff-banner"
          animate={{ opacity: [0.6, 1, 0.6] }}
          transition={{ repeat: Infinity, duration: 1.4 }}
        >
          ✦ Choose a buff before advancing!
        </motion.div>
      )}

      {/* Floor nodes */}
      <div className="tower-floors">
        {floors.map(f => {
          const ftype    = getFloorType(f)
          const outcome  = historyMap[f]
          const isCurrent = f === currentFloor
          const isCleared = outcome === 'win'
          const isFailed  = outcome === 'loss'
          const isLocked  = f > currentFloor
          const isBoss    = ftype === 'boss'

          return (
            <motion.div
              key={f}
              className={[
                'floor-node',
                ftype,
                isCurrent ? 'current' : '',
                isCleared ? 'cleared' : '',
                isFailed  ? 'failed'  : '',
                isLocked  ? 'locked'  : '',
                isBoss    ? 'boss-node' : '',
              ].join(' ')}
              style={{ '--floor-color': FLOOR_COLOR[ftype] }}
              onClick={() => isCurrent && !pendingBuff && onSelectFloor(f)}
              whileHover={isCurrent && !pendingBuff ? { scale: 1.06 } : {}}
              animate={isCurrent ? { boxShadow: ['0 0 0 0 rgba(249,115,22,0)', '0 0 0 8px rgba(249,115,22,0.3)', '0 0 0 0 rgba(249,115,22,0)'] } : {}}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              {/* Floor number badge */}
              <div className="floor-num">{f}</div>

              {/* Icon */}
              <div className={`floor-icon ${isBoss ? 'boss-icon' : ''}`}>
                {isCleared ? '✓' : isFailed ? '✗' : FLOOR_ICON[ftype]}
              </div>

              {/* Label */}
              <div className="floor-label">
                {isBoss ? 'BOSS' : ftype === 'revive' ? 'REVIVE' : ftype === 'buff' ? 'BUFF' : `F${f}`}
              </div>

              {/* Current floor arrow */}
              {isCurrent && (
                <motion.div
                  className="current-arrow"
                  animate={{ x: [0, 4, 0] }}
                  transition={{ repeat: Infinity, duration: 0.8 }}
                >▶</motion.div>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Team status bar */}
      {session?.team && (
        <div className="tower-team-status">
          <p className="status-title">Your Squad</p>
          <div className="squad-row">
            {session.team.map((m, i) => {
              const hpPct = m.max_hp > 0 ? (m.current_hp / m.max_hp) * 100 : 0
              return (
                <div key={i} className={`squad-card ${!m.is_alive ? 'dead' : ''}`}>
                  <div className="squad-portrait">
                    {m.portrait_id && m.portrait_id !== 'default'
                      ? <img src={`/portraits/${m.portrait_id}.png`} alt={m.name}
                             onError={e => e.target.style.display='none'} />
                      : <span>🦸</span>
                    }
                  </div>
                  <div className="squad-name">{m.name}</div>
                  <div className="squad-hp-track">
                    <motion.div
                      className="squad-hp-fill"
                      style={{
                        backgroundColor: hpPct > 50 ? '#22c55e' : hpPct > 20 ? '#eab308' : '#ef4444',
                      }}
                      animate={{ width: `${hpPct}%` }}
                    />
                  </div>
                  <div className="squad-hp-text">
                    {m.is_alive ? `${m.current_hp}/${m.max_hp}` : '💀 Dead'}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
