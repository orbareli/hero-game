/**
 * TowerMode.jsx
 * -------------
 * Top-level controller for the Tower of Trials.
 * Manages state machine: map → battle → buff_select → revive → map → …
 *
 * Phase state machine:
 *   'loading'      – initial load
 *   'no_run'       – no active session, show start screen
 *   'team_select'  – pick 3 fighters to begin the run
 *   'map'          – view tower floors, select current floor
 *   'battle'       – in BattleArena3v3 (tower variant)
 *   'buff_select'  – choose buff after clearing a buff floor
 *   'revive'       – revive node: pick a dead fighter to restore
 *   'run_end'      – won or failed
 */

import React, { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import TowerMap      from './TowerMap'
import TowerBattle   from './TowerBattle'
import BuffSelect    from './BuffSelect'

const API = 'http://localhost:8000'

export default function TowerMode({ playerId, allChars, roster, onBack }) {
  const [phase,    setPhase]    = useState('loading')
  const [session,  setSession]  = useState(null)
  const [floor,    setFloor]    = useState(null)    // current floor details from API
  const [error,    setError]    = useState(null)

  // ── Load or resume active run ─────────────────────────────────────────────
  const loadRun = useCallback(async () => {
    try {
      const res  = await fetch(`${API}/tower/player/${playerId}/active`)
      const data = await res.json()
      if (data.session) {
        setSession(data.session)
        setPhase(data.session.pending_buff ? 'buff_select' : 'map')
      } else {
        setPhase('no_run')
      }
    } catch (e) {
      setError(e.message)
      setPhase('no_run')
    }
  }, [playerId])

  useEffect(() => { loadRun() }, [loadRun])

  // ── Start a new run ───────────────────────────────────────────────────────
  const startRun = async (pcIds) => {
    try {
      const res  = await fetch(`${API}/tower/start`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ player_id: playerId, pc_ids: pcIds }),
      })
      const data = await res.json()
      setSession(data)
      setPhase('map')
    } catch (e) {
      setError(e.message)
    }
  }

  // ── Player clicks a floor node ────────────────────────────────────────────
  const handleFloorSelect = async (floorNum) => {
    try {
      const res  = await fetch(`${API}/tower/${session.id}/floor`)
      const data = await res.json()
      setFloor(data)

      if (data.floor_type === 'revive') {
        setPhase('revive')
      } else {
        setPhase('battle')
      }
    } catch (e) {
      setError(e.message)
    }
  }

  // ── Battle finished ───────────────────────────────────────────────────────
  const handleBattleEnd = async (outcome, finalTeamState) => {
    try {
      const res  = await fetch(`${API}/tower/${session.id}/complete`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ outcome, team_state: finalTeamState }),
      })
      const data = await res.json()

      if (data.status === 'failed') {
        setSession(prev => ({ ...prev, team: data.team, status: 'failed' }))
        setPhase('run_end')
        return
      }
      if (data.status === 'completed') {
        setSession(prev => ({ ...prev, status: 'completed' }))
        setPhase('run_end')
        return
      }

      // Update session with new floor + team
      setSession(prev => ({
        ...prev,
        current_floor: data.next_floor,
        team:          data.team,
        pending_buff:  data.buff_offered,
      }))

      if (data.buff_offered) {
        setPhase('buff_select')
      } else {
        setPhase('map')
      }
    } catch (e) {
      setError(e.message)
    }
  }

  // ── Buff selected ─────────────────────────────────────────────────────────
  const handleBuffSelected = (updatedData) => {
    setSession(prev => ({
      ...prev,
      team:         updatedData.team,
      active_buffs: [...(prev.active_buffs || []), updatedData.buff],
      pending_buff: false,
    }))
    setPhase('map')
  }

  // ── Revive node ───────────────────────────────────────────────────────────
  const handleRevive = async (targetPcId) => {
    try {
      const res  = await fetch(`${API}/tower/${session.id}/revive`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ target_pc_id: targetPcId }),
      })
      const data = await res.json()
      setSession(prev => ({
        ...prev,
        current_floor: data.next_floor,
        team:          data.team,
      }))
      setPhase('map')
    } catch (e) {
      setError(e.message)
    }
  }

  // ── Abandon run ───────────────────────────────────────────────────────────
  const handleAbandon = async () => {
    if (!session?.id) return
    await fetch(`${API}/tower/${session.id}/abandon`, { method: 'POST' })
    setSession(null)
    setPhase('no_run')
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="tower-mode">
      <AnimatePresence mode="wait">

        {/* ── Loading ── */}
        {phase === 'loading' && (
          <motion.div key="loading" className="arena-loading"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="loading-spinner" />
            <p>Entering the Tower…</p>
          </motion.div>
        )}

        {/* ── No active run ── */}
        {phase === 'no_run' && (
          <motion.div key="no_run" className="tower-start-screen"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="tower-start-hero">🗼</div>
            <h2>Tower of Trials</h2>
            <p>30 floors. One team. HP persists between battles.</p>
            <p className="tower-start-sub">Choose 3 heroes wisely — they carry their wounds forward.</p>
            <TowerTeamPicker roster={roster} onStart={startRun} />
            <button className="back-btn" style={{ marginTop: 16 }} onClick={onBack}>← Back</button>
          </motion.div>
        )}

        {/* ── Tower map ── */}
        {phase === 'map' && session && (
          <motion.div key="map"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <TowerMap
              currentFloor={session.current_floor}
              floorHistory={session.floor_history || []}
              onSelectFloor={handleFloorSelect}
              pendingBuff={session.pending_buff}
              session={session}
            />
            <button className="back-btn" style={{ marginTop: 12 }} onClick={handleAbandon}>
              🏳 Abandon Run
            </button>
          </motion.div>
        )}

        {/* ── Battle ── */}
        {phase === 'battle' && session && floor && (
          <motion.div key="battle"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <TowerBattle
              sessionId={session.id}
              floorData={floor}
              onBattleEnd={handleBattleEnd}
              onBack={() => setPhase('map')}
            />
          </motion.div>
        )}

        {/* ── Buff select ── */}
        {phase === 'buff_select' && session && (
          <motion.div key="buff"
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
            <BuffSelect sessionId={session.id} onSelected={handleBuffSelected} />
          </motion.div>
        )}

        {/* ── Revive node ── */}
        {phase === 'revive' && session && (
          <motion.div key="revive" className="revive-screen"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="revive-icon">💚</div>
            <h2>Revive Node</h2>
            <p>Choose one fallen fighter to restore to 30% HP</p>
            <div className="revive-options">
              {session.team.filter(m => !m.is_alive).map(m => (
                <button key={m.pc_id} className="revive-btn"
                  onClick={() => handleRevive(m.pc_id)}>
                  Revive {m.name}
                </button>
              ))}
              {session.team.every(m => m.is_alive) && (
                <p>All fighters are alive — continue to the next floor.</p>
              )}
              <button className="back-btn" style={{ marginTop: 12 }}
                onClick={() => handleRevive(null)}>
                Skip Revive →
              </button>
            </div>
          </motion.div>
        )}

        {/* ── Run ended ── */}
        {phase === 'run_end' && session && (
          <motion.div key="end" className={`run-end-screen ${session.status}`}
            initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
            <div className="run-end-icon">
              {session.status === 'completed' ? '🏆' : '💀'}
            </div>
            <h2>
              {session.status === 'completed' ? 'Tower Conquered!' : 'Run Over'}
            </h2>
            <p>Reached floor {session.current_floor} / 30</p>
            <p>Floors cleared: {(session.floor_history || []).filter(f => f.outcome === 'win').length}</p>
            <div className="run-end-buffs">
              {(session.active_buffs || []).map(b => (
                <span key={b.id} className="buff-pip">{b.name}</span>
              ))}
            </div>
            <button className="tb-start-btn" onClick={() => { setSession(null); setPhase('no_run') }}>
              Start New Run
            </button>
            <button className="back-btn" style={{ marginTop: 8 }} onClick={onBack}>
              ← Exit Tower
            </button>
          </motion.div>
        )}

      </AnimatePresence>

      {error && (
        <div className="section-error" style={{ marginTop: 16 }}>{error}</div>
      )}
    </div>
  )
}


// ── Team picker (inline, simpler than full TeamBuilder) ───────────────────────
function TowerTeamPicker({ roster, onStart }) {
  const [selected, setSelected] = useState([])

  const toggle = (pcId) => {
    setSelected(prev =>
      prev.includes(pcId) ? prev.filter(id => id !== pcId)
        : prev.length < 3  ? [...prev, pcId]
        : prev
    )
  }

  return (
    <div className="tower-team-picker">
      <p className="picker-label">{selected.length}/3 heroes selected</p>
      <div className="tb-card-grid" style={{ maxWidth: 600 }}>
        {roster.map(pc => {
          const m = pc.master_data || {}
          const sel = selected.includes(pc.id)
          return (
            <motion.button
              key={pc.id}
              className={`tb-card hero ${sel ? 'selected' : ''}`}
              onClick={() => toggle(pc.id)}
              whileHover={{ scale: 1.03 }}
            >
              <div className="tbc-rarity" style={{ color: { C:'#94a3b8',R:'#60a5fa',SR:'#c084fc',UR:'#fbbf24' }[m.rarity] }}>{m.rarity}</div>
              <div className="tbc-avatar">🦸</div>
              <div className="tbc-name">{m.name}</div>
              <div className="tbc-stats">
                <span>HP {pc.hp}</span>
                <span>ATK {pc.atk}</span>
              </div>
              {sel && <div className="tbc-check">✓</div>}
            </motion.button>
          )
        })}
      </div>
      <motion.button
        className={`tb-start-btn ${selected.length === 0 ? 'disabled' : ''}`}
        onClick={() => selected.length > 0 && onStart(selected)}
        disabled={selected.length === 0}
        style={{ marginTop: 16 }}
      >
        {selected.length > 0 ? `Enter Tower with ${selected.length} hero${selected.length>1?'es':''}` : 'Select at least 1 hero'}
      </motion.button>
    </div>
  )
}
