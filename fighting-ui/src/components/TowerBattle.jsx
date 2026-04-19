/**
 * TowerBattle.jsx
 * ---------------
 * Thin wrapper around BattleArena3v3 that:
 *   1. Uses the tower WebSocket (ws/tower/{session_id}) instead of ws/battle3
 *   2. Passes persistent HP from floorData.team_state (not fresh DB values)
 *   3. Returns final_team_state to parent after battle ends
 *   4. Adds boss-specific visual styling
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const ELEMENT_COLOR = { Power: '#ef4444', Speed: '#22c55e', Tech: '#60a5fa' }
const ELEMENT_ICON  = { Power: '⚡', Speed: '💨', Tech: '⚙' }
const RARITY_COLOR  = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }

/**
 * Props:
 *   sessionId    – string
 *   floorData    – { floor, floor_type, is_boss, enemies, team_state }
 *   onBattleEnd  – (outcome, finalTeamState) => void
 *   onBack       – () => void
 */
export default function TowerBattle({ sessionId, floorData, onBattleEnd, onBack }) {
  const [state,         setState]         = useState(null)
  const [events,        setEvents]        = useState([])
  const [inputReq,      setInputReq]      = useState(null)
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [selectedSkill,  setSelectedSkill]  = useState(null)
  const [targetMode,     setTargetMode]     = useState('enemy')
  const [battleResult,   setBattleResult]   = useState(null)
  const [damagePopups,   setDamagePopups]   = useState([])
  const [phase,          setPhase]          = useState('connecting')
  const [enemyActing,    setEnemyActing]    = useState(null)
  const [critTargets,    setCritTargets]    = useState(new Set())

  const wsRef    = useRef(null)
  const logRef   = useRef(null)
  const popupId  = useRef(0)

  const isBoss = floorData?.is_boss

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/tower/${sessionId}`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type:    'start',
        enemies: floorData.enemies,
        is_boss: isBoss,
      }))
      setPhase('waiting')
    }

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      handleMessage(msg)
    }

    ws.onerror = () => setPhase('error')
    ws.onclose = () => {}
    return () => ws.close()
  }, [])

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'state':
        setState(msg.state)
        setPhase(msg.state.phase === 'player_input' ? 'player_turn' : 'enemy_turn')
        break
      case 'round_start':
        setState(msg.state)
        setEvents(prev => [...prev, { type: 'round', detail: `━━━ Round ${msg.round} ━━━`, id: Date.now() }])
        break
      case 'input_required':
        setInputReq(msg)
        setSelectedTarget(msg.enemy_targets[0]?.index ?? 0)
        setSelectedSkill(null)
        setTargetMode('enemy')
        setPhase('player_turn')
        setEnemyActing(null)
        break
      case 'enemy_acting':
        setEnemyActing(msg.actor_index)
        setPhase('enemy_turn')
        setInputReq(null)
        break
      case 'events':
        msg.events.forEach(ev => {
          setEvents(prev => [...prev, { ...ev, id: Date.now() + Math.random() }])
          if (ev.damage > 0) spawnPopup(ev.damage, ev.crit, ev.actor_team === 'player' ? 'right' : 'left')
          if (ev.heal   > 0) spawnHealPopup(ev.heal, ev.actor_team === 'player' ? 'left' : 'right')
          if (ev.crit && ev.target) {
            setCritTargets(prev => new Set([...prev, ev.target]))
            setTimeout(() => setCritTargets(prev => { const n = new Set(prev); n.delete(ev.target); return n }), 600)
          }
        })
        break
      case 'battle_end':
        setBattleResult(msg)
        setPhase('done')
        setInputReq(null)
        // Pass persistent state up so parent can POST /tower/{id}/complete
        if (onBattleEnd) onBattleEnd(msg.outcome, msg.final_team_state)
        break
      case 'error':
        setEvents(prev => [...prev, { type: 'error', detail: msg.message, id: Date.now() }])
        setPhase('error')
        break
    }
  }, [])

  const sendAction = (actionType, skillIdx = null) => {
    if (!wsRef.current || phase !== 'player_turn') return
    wsRef.current.send(JSON.stringify({
      type:         'action',
      action:       actionType,
      target_index: selectedTarget ?? 0,
      skill_index:  skillIdx ?? 0,
    }))
    setInputReq(null)
    setSelectedSkill(null)
    setPhase('waiting')
  }

  const spawnPopup = (value, isCrit, side) => {
    const id = popupId.current++
    setDamagePopups(prev => [...prev, {
      id, value, crit: isCrit, type: 'damage',
      x: side === 'right' ? 65 + Math.random() * 20 : 15 + Math.random() * 20,
      y: 20 + Math.random() * 40,
    }])
    setTimeout(() => setDamagePopups(prev => prev.filter(p => p.id !== id)), 1200)
  }

  const spawnHealPopup = (value, side) => {
    const id = popupId.current++
    setDamagePopups(prev => [...prev, {
      id, value, type: 'heal',
      x: side === 'right' ? 65 + Math.random() * 20 : 15 + Math.random() * 20,
      y: 20 + Math.random() * 40,
    }])
    setTimeout(() => setDamagePopups(prev => prev.filter(p => p.id !== id)), 1200)
  }

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [events])

  if (!state && phase === 'connecting') return (
    <div className="arena-loading"><div className="loading-spinner" /><p>Entering floor {floorData?.floor}…</p></div>
  )

  const actor = inputReq?.actor
  const { player_team, enemy_team } = state || { player_team: [], enemy_team: [] }

  return (
    <div className={`arena-3v3 ${isBoss ? 'boss-arena' : ''}`}>

      {/* Boss banner */}
      {isBoss && (
        <motion.div
          className="boss-banner"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          💀 BOSS FLOOR {floorData.floor}
        </motion.div>
      )}

      {/* Floor indicator */}
      <div className="tower-floor-badge">
        Floor {floorData?.floor} / 30 {isBoss ? '— BOSS' : ''}
      </div>

      {/* Damage popups */}
      <div className="popup-layer" aria-hidden>
        <AnimatePresence>
          {damagePopups.map(p => (
            <motion.div key={p.id}
              className={`dmg-popup ${p.type} ${p.crit ? 'crit' : ''}`}
              style={{ left: `${p.x}%`, top: `${p.y}%` }}
              initial={{ opacity: 1, y: 0, scale: p.crit ? 1.4 : 1 }}
              animate={{ opacity: 0, y: -50 }}
              transition={{ duration: 1.0 }}
            >
              {p.type === 'heal' ? `+${p.value}` : `-${p.value}`}
              {p.crit && <span className="popup-crit">!</span>}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Enemy row — boss gets special styling */}
      <div className={`team-row enemy-row ${isBoss ? 'boss-row' : ''}`}>
        {enemy_team.map((f, i) => (
          <TowerFighterCard
            key={f.char_id + i}
            fighter={f}
            side="enemy"
            isBoss={isBoss}
            isActive={enemyActing === i}
            isTarget={inputReq && selectedTarget === i && targetMode === 'enemy'}
            isSelectable={!!inputReq && f.is_alive && targetMode === 'enemy'}
            isCritShaking={critTargets.has(f.name)}
            onClick={() => inputReq && setSelectedTarget(i)}
          />
        ))}
      </div>

      {/* Status bar */}
      <div className="arena-status-bar">
        <span className="round-badge">Round {state?.round ?? 1}</span>
        <span className={`phase-badge ${phase}`}>
          {phase === 'player_turn' ? `${actor?.name}'s Turn`
           : phase === 'enemy_turn' ? 'Enemy Acting…'
           : phase === 'done' ? 'Battle Over' : '…'}
        </span>
        <button className="back-btn" onClick={onBack}>← Retreat</button>
      </div>

      {/* Player row — show persistent HP (blood effect when low) */}
      <div className="team-row player-row">
        {player_team.map((f, i) => (
          <TowerFighterCard
            key={f.pc_id + i}
            fighter={f}
            side="player"
            isBoss={false}
            isActive={inputReq?.actor?.pc_id === f.pc_id}
            isTarget={false}
            isSelectable={false}
            isCritShaking={critTargets.has(f.name)}
            onClick={() => {}}
            showPersistentWarning={f.hp < f.max_hp * 0.40}
          />
        ))}
      </div>

      {/* Action panel */}
      <AnimatePresence>
        {inputReq && phase === 'player_turn' && (
          <motion.div className="action-panel"
            initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }}>
            <div className="action-actor">
              <span className="actor-name">{actor?.name}</span>
              <div className="energy-bar-wrap" style={{ flex: 1 }}>
                <span className="energy-label">⚡ {actor?.energy}/100</span>
                <div className="energy-track">
                  <motion.div className="energy-fill" animate={{ width: `${actor?.energy}%` }} />
                </div>
              </div>
            </div>
            <div className="action-target-label">
              {targetMode === 'ally'
                ? <>Heal: <strong>{state?.player_team[selectedTarget]?.name ?? '—'}</strong></>
                : <>Target: <strong>{state?.enemy_team[selectedTarget]?.name ?? '—'}</strong></>}
            </div>
            <div className="action-buttons">
              <button className="action-btn attack"
                onClick={() => { setSelectedSkill(null); setTargetMode('enemy'); sendAction('attack', null) }}>
                ⚔ Basic Attack <span className="skill-cost">free</span>
              </button>
              {inputReq.skills?.map(skill => (
                <button key={skill.index}
                  className={['action-btn skill', !skill.can_afford ? 'disabled' : '', selectedSkill === skill.index ? 'selected-action' : '', skill.target === 'ally' ? 'ally-skill' : '', skill.target === 'self' ? 'self-skill' : ''].join(' ')}
                  disabled={!skill.can_afford}
                  title={skill.desc}
                  onClick={() => {
                    if (!skill.can_afford) return
                    if (skill.target === 'self') { setSelectedSkill(skill.index); sendAction('skill', skill.index) }
                    else if (skill.target === 'ally') { setSelectedSkill(skill.index); setTargetMode('ally'); setSelectedTarget(inputReq.ally_targets[0]?.index ?? 0) }
                    else { setSelectedSkill(skill.index); setTargetMode('enemy'); setSelectedTarget(inputReq.enemy_targets[0]?.index ?? 0) }
                  }}>
                  <span className="skill-icon">{skill.target === 'ally' ? '💚' : skill.target === 'self' ? '🔮' : '✦'}</span>
                  {skill.name} <span className="skill-cost">{skill.energy_cost}⚡</span>
                </button>
              ))}
            </div>
            {selectedSkill !== null && inputReq.skills[selectedSkill]?.target !== 'self' && (
              <motion.button className="confirm-btn"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                onClick={() => sendAction('skill', selectedSkill)}>
                ✓ Confirm — {inputReq.skills[selectedSkill]?.name}
              </motion.button>
            )}
            <div className="target-selector">
              {(targetMode === 'ally' ? inputReq.ally_targets : inputReq.enemy_targets)?.map(t => (
                <button key={t.index}
                  className={`target-btn ${selectedTarget === t.index ? 'selected' : ''} ${targetMode}`}
                  onClick={() => setSelectedTarget(t.index)}>
                  {targetMode === 'ally' ? '💚 ' : ''}{t.name}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Battle log */}
      <div className="battle-log-3v3" ref={logRef}>
        {events.map((ev, i) => (
          <motion.div key={ev.id ?? i}
            className={`log-line ${ev.type === 'round' ? '' : ev.actor_team === 'player' ? 'player' : 'enemy'}`}
            initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}>
            {ev.type === 'round'
              ? <div className="log-round">{ev.detail}</div>
              : <>
                  <span className="log-detail">{ev.detail}</span>
                  {ev.damage > 0 && <span className="log-dmg">-{ev.damage}</span>}
                  {ev.heal   > 0 && <span className="log-heal">+{ev.heal}</span>}
                  {ev.crit   && <span className="log-tag crit">CRIT</span>}
                  {ev.evaded && <span className="log-tag evade">EVADE</span>}
                </>}
          </motion.div>
        ))}
      </div>

      {/* Result overlay */}
      <AnimatePresence>
        {battleResult && (
          <motion.div className={`result-overlay ${battleResult.outcome}`}
            initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }}>
            <div className="result-title">
              {battleResult.outcome === 'win' ? '✓ Floor Cleared' : '💀 Defeated'}
            </div>
            <p style={{ color: 'var(--text-2)', marginTop: 8 }}>
              {battleResult.outcome === 'win' ? 'Your team carries their HP to the next floor.' : 'Your run ends here.'}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}


// ── Fighter card with tower-specific additions ────────────────────────────────
function TowerFighterCard({ fighter, side, isBoss, isActive, isTarget, isSelectable, onClick, showPersistentWarning, isCritShaking = false }) {
  const hpPct    = fighter.max_hp > 0 ? (fighter.hp / fighter.max_hp) * 100 : 0
  const hpColor  = hpPct > 50 ? '#22c55e' : hpPct > 20 ? '#eab308' : '#ef4444'
  const elemColor = ELEMENT_COLOR[fighter.element] || '#94a3b8'

  return (
    <motion.div
      className={[
        'fighter-3v3', side,
        isActive    ? 'active'     : '',
        isTarget    ? 'targeted'   : '',
        isSelectable ? 'selectable' : '',
        !fighter.is_alive ? 'dead' : '',
        isBoss      ? 'boss-fighter' : '',
        showPersistentWarning ? 'hp-warning' : '',
        isCritShaking ? 'crit-shake' : '',
      ].join(' ')}
      style={{ '--elem-color': elemColor }}
      onClick={isSelectable ? onClick : undefined}
      animate={isActive ? { scale: 1.06 } : { scale: 1 }}
    >
      {/* Persistent HP warning — blood splatter effect */}
      {showPersistentWarning && (
        <motion.div
          className="blood-warning"
          animate={{ opacity: [0.4, 0.9, 0.4] }}
          transition={{ repeat: Infinity, duration: 1.2 }}
        >⚠ LOW HP</motion.div>
      )}

      <div className="f3-element" style={{ color: elemColor }}>
        {ELEMENT_ICON[fighter.element]} {fighter.element}
      </div>
      <div className={`f3-avatar ${isBoss ? 'boss-avatar' : ''}`}>
        {fighter.portrait_id && fighter.portrait_id !== 'default'
          ? <img src={`/portraits/${fighter.portrait_id}.png`} alt={fighter.name}
                 className={side === 'enemy' ? 'enemy-flip' : ''}
                 onError={e => e.target.style.display='none'} />
          : <span>{side === 'player' ? '🦸' : '💀'}</span>}
      </div>
      <div className="f3-name">{fighter.name}</div>
      <div className="f3-rarity" style={{ color: RARITY_COLOR[fighter.rarity] }}>{fighter.rarity}</div>
      <div className="f3-hp-track">
        <motion.div className="f3-hp-fill" style={{ backgroundColor: hpColor }}
          animate={{ width: `${hpPct}%` }} transition={{ type: 'spring', stiffness: 80, damping: 18 }} />
      </div>
      <div className="f3-hp-text">{fighter.hp}/{fighter.max_hp}</div>
      {fighter.is_player && (
        <div className="f3-energy-track">
          <motion.div className="f3-energy-fill" animate={{ width: `${fighter.energy}%` }} />
        </div>
      )}
      {fighter.effects?.length > 0 && (
        <div className="f3-effects">
          {fighter.effects.map((e, i) => (
            <span key={i} className={`f3-effect ${e.name}`}>
              {e.name === 'poisoned' ? '☠' : e.name === 'atk_down' ? '↓' : e.name === 'stunned' ? '⚡' : '?'}
            </span>
          ))}
        </div>
      )}
      {!fighter.is_alive && <div className="f3-dead-overlay">💀</div>}
      {isTarget && <motion.div className="f3-target-ring" animate={{ scale: [1,1.15,1] }} transition={{ repeat: Infinity, duration: 0.8 }} />}
    </motion.div>
  )
}