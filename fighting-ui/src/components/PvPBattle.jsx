/**
 * PvPBattle.jsx
 * -------------
 * The battle UI for local PvP.
 *
 * Differences from BattleArena3v3:
 *  - Receives an already-connected WebSocket + initial state (from PvPLobby)
 *  - role prop: 'player1' | 'player2' determines which side you control
 *  - 'waiting' message type → show "Opponent's turn" overlay
 *  - Both teams labelled "Your Team" / "Opponent's Team" from each player's POV
 *  - No AI — human actions only, both sides
 *
 * The server's engine still calls Player 1's team "player_team" and
 * Player 2's team "enemy_team". From P2's perspective the labels are flipped
 * in the UI only — the action messages use the same format.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const ELEMENT_COLOR = { Power: '#ef4444', Speed: '#22c55e', Tech: '#60a5fa', Mystic: '#c084fc', Bio: '#86efac', Cosmic: '#fbbf24' }
const ELEMENT_ICON  = { Power: '⚡', Speed: '💨', Tech: '⚙', Mystic: '🔮', Bio: '🌿', Cosmic: '✨' }
const RARITY_COLOR  = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }

/**
 * Props:
 *   ws           – the already-open WebSocket from PvPLobby
 *   role         – 'player1' | 'player2'
 *   initialState – BattleState dict from 'battle_start' message
 *   onBack       – () => void
 */
export default function PvPBattle({ ws, role, initialState, onBack }) {
  const [state,          setState]          = useState(initialState)
  const [events,         setEvents]         = useState([])
  const [inputReq,       setInputReq]       = useState(null)
  const [waitingMsg,     setWaitingMsg]     = useState(null)
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [selectedSkill,  setSelectedSkill]  = useState(null)
  const [targetMode,     setTargetMode]     = useState('enemy')
  const [battleResult,   setBattleResult]   = useState(null)
  const [damagePopups,   setDamagePopups]   = useState([])
  const [phase,          setPhase]          = useState('fighting')
  const [critTargets,    setCritTargets]    = useState(new Set())

  const logRef  = useRef(null)
  const popupId = useRef(0)
  const wsRef   = useRef(ws)

  // ── Wire up the existing WebSocket to this component ─────────────────────
  useEffect(() => {
    const socket = wsRef.current
    socket.onmessage = (evt) => handleMessage(JSON.parse(evt.data))
    socket.onerror   = () => setEvents(prev => [...prev, {
      id: Date.now(), type: 'error', detail: 'Connection error', actor_team: 'system',
    }])
    return () => { socket.onmessage = null }
  }, [])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [events])

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {

      case 'state':
        setState(msg.state)
        setWaitingMsg(null)
        break

      case 'round_start':
        setState(msg.state)
        setEvents(prev => [...prev, {
          id: Date.now(), type: 'round',
          detail: `━━━ Round ${msg.round} ━━━`, actor_team: 'system',
        }])
        break

      case 'input_required':
        // Only show action UI if it's this player's turn
        setInputReq(msg)
        setSelectedTarget(msg.enemy_targets[0]?.index ?? 0)
        setSelectedSkill(null)
        setTargetMode('enemy')
        setWaitingMsg(null)
        setPhase('player_turn')
        break

      case 'waiting':
        // Opponent's turn — show waiting overlay
        setInputReq(null)
        setWaitingMsg(msg.message)
        setPhase('waiting')
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
        setWaitingMsg(null)
        break

      case 'error':
        setEvents(prev => [...prev, { id: Date.now(), type: 'error', detail: msg.message, actor_team: 'system' }])
        setPhase('error')
        break
    }
  }, [role])

  const sendAction = (actionType, skillIdx = null) => {
    if (!wsRef.current || phase !== 'player_turn') return
    wsRef.current.send(JSON.stringify({
      type:         'action',
      action:       actionType,
      target_index: selectedTarget ?? 0,
      skill_index:  skillIdx ?? 0,
    }))
    setInputReq(null)
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

  if (!state) return <div className="arena-loading"><div className="loading-spinner" /><p>Loading battle…</p></div>

  // From each player's POV: "my team" vs "opponent team"
  // P1: player_team = my team,  enemy_team = opponent
  // P2: enemy_team  = my team,  player_team = opponent
  const myTeam  = role === 'player1' ? state.player_team : state.enemy_team
  const oppTeam = role === 'player1' ? state.enemy_team  : state.player_team

  const actor   = inputReq?.actor

  return (
    <div className="arena-3v3 pvp-arena">

      {/* PvP role banner */}
      <div className="pvp-role-strip">
        <span className={`pvp-badge ${role}`}>
          {role === 'player1' ? '👤 Player 1' : '👤 Player 2'}
        </span>
        <span className="pvp-vs-label">vs</span>
        <span className="pvp-badge opponent">
          {role === 'player1' ? '👤 Player 2' : '👤 Player 1'}
        </span>
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

      {/* Opponent's team (top) */}
      <div className="team-row enemy-row">
        <div className="team-label-strip opp">Opponent's Team</div>
        {oppTeam.map((f, i) => (
          <PvPFighterCard
            key={f.pc_id + i}
            fighter={f}
            side="enemy"
            isTarget={inputReq && selectedTarget === i && targetMode === 'enemy'}
            isSelectable={!!inputReq && f.is_alive && targetMode === 'enemy'}
            isCritShaking={critTargets.has(f.name)}
            onClick={() => inputReq && setSelectedTarget(i)}
          />
        ))}
      </div>

      {/* Status bar */}
      <div className="arena-status-bar">
        <span className="round-badge">Round {state.round ?? 1}</span>
        <span className={`phase-badge ${phase}`}>
          {phase === 'player_turn' ? `${actor?.name}'s Turn — YOUR MOVE`
           : phase === 'waiting'    ? 'Opponent Acting…'
           : phase === 'done'       ? 'Battle Over'
           : '…'}
        </span>
        <button className="back-btn" onClick={onBack}>✕ Leave</button>
      </div>

      {/* Your team (bottom) */}
      <div className="team-row player-row">
        <div className="team-label-strip mine">Your Team</div>
        {myTeam.map((f, i) => (
          <PvPFighterCard
            key={f.pc_id + i}
            fighter={f}
            side="player"
            isTarget={false}
            isSelectable={false}
            isCritShaking={critTargets.has(f.name)}
            isActive={inputReq?.actor?.pc_id === f.pc_id}
            onClick={() => {}}
          />
        ))}
      </div>

      {/* ── Waiting overlay ── */}
      <AnimatePresence>
        {waitingMsg && (
          <motion.div className="pvp-waiting-overlay"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="loading-spinner" />
            <p>{waitingMsg}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Action panel (only shown when it's YOUR turn) ── */}
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
                ? <>Heal: <strong>{myTeam[selectedTarget]?.name ?? '—'}</strong></>
                : <>Target: <strong>{oppTeam[selectedTarget]?.name ?? '—'}</strong></>}
            </div>

            <div className="action-buttons">
              {/* Basic attack */}
              <button className="action-btn attack"
                onClick={() => { setSelectedSkill(null); setTargetMode('enemy'); sendAction('attack', null) }}>
                ⚔ Basic Attack <span className="skill-cost">free</span>
              </button>

              {/* Skills */}
              {inputReq.skills?.map(skill => (
                <button key={skill.index}
                  className={['action-btn skill',
                    !skill.can_afford ? 'disabled' : '',
                    selectedSkill === skill.index ? 'selected-action' : '',
                    skill.target === 'ally' ? 'ally-skill' : '',
                    skill.target === 'self' ? 'self-skill' : '',
                  ].join(' ')}
                  disabled={!skill.can_afford}
                  title={skill.desc}
                  onClick={() => {
                    if (!skill.can_afford) return
                    if (skill.target === 'self') { sendAction('skill', skill.index) }
                    else if (skill.target === 'ally') { setSelectedSkill(skill.index); setTargetMode('ally'); setSelectedTarget(0) }
                    else { setSelectedSkill(skill.index); setTargetMode('enemy'); setSelectedTarget(inputReq.enemy_targets[0]?.index ?? 0) }
                  }}>
                  <span className="skill-icon">{skill.target === 'ally' ? '💚' : skill.target === 'self' ? '🔮' : '✦'}</span>
                  {skill.name} <span className="skill-cost">{skill.energy_cost}⚡</span>
                </button>
              ))}

              {/* Tactical move */}
              {inputReq.tactical && (
                <button
                  className={['action-btn tactical',
                    `tactical-${inputReq.tactical.move}`,
                  ].join(' ')}
                  title={inputReq.tactical.desc}
                  onClick={() => sendAction('tactical', null)}>
                  <span className="skill-icon">{inputReq.tactical.icon}</span>
                  {inputReq.tactical.label}
                  <span className="skill-cost">free</span>
                </button>
              )}
            </div>

            {/* Confirm button for targeted skills */}
            {selectedSkill !== null && inputReq.skills[selectedSkill]?.target !== 'self' && (
              <motion.button className="confirm-btn"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                onClick={() => sendAction('skill', selectedSkill)}>
                ✓ Confirm — {inputReq.skills[selectedSkill]?.name}
              </motion.button>
            )}

            {/* Target selector */}
            <div className="target-selector">
              {(targetMode === 'ally' ? inputReq.ally_targets : inputReq.enemy_targets)?.map(t => (
                <button key={t.index}
                  className={`target-btn ${selectedTarget === t.index ? 'selected' : ''} ${targetMode}`}
                  onClick={() => setSelectedTarget(t.index)}>
                  {targetMode === 'ally' ? '💚 ' : ''}{t.name}
                  <span style={{ color: ELEMENT_COLOR[t.element], fontSize: '0.7rem' }}>
                    {' '}{ELEMENT_ICON[t.element]}
                  </span>
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
                  {ev.is_aoe && <span className="log-tag aoe">AoE</span>}
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
              {battleResult.outcome === 'win' ? '🏆 VICTORY' : battleResult.outcome === 'loss' ? '💀 DEFEAT' : '🤝 DRAW'}
            </div>
            <p className="pvp-result-msg">{battleResult.message}</p>
            <button className="result-btn" onClick={onBack}>← Back to Menu</button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Fighter card ──────────────────────────────────────────────────────────────
function PvPFighterCard({ fighter, side, isActive, isTarget, isSelectable, isCritShaking, onClick }) {
  const hpPct    = fighter.max_hp > 0 ? (fighter.hp / fighter.max_hp) * 100 : 0
  const hpColor  = hpPct > 50 ? '#22c55e' : hpPct > 20 ? '#eab308' : '#ef4444'
  const elemColor = ELEMENT_COLOR[fighter.element] || '#94a3b8'

  return (
    <motion.div
      className={[
        'fighter-3v3', side,
        isActive      ? 'active'     : '',
        isTarget      ? 'targeted'   : '',
        isSelectable  ? 'selectable' : '',
        !fighter.is_alive ? 'dead'   : '',
        isCritShaking ? 'crit-shake' : '',
      ].join(' ')}
      style={{ '--elem-color': elemColor }}
      onClick={isSelectable ? onClick : undefined}
      animate={isActive ? { scale: 1.06 } : { scale: 1 }}
      whileHover={isSelectable ? { scale: 1.04 } : {}}
    >
      <div className="f3-element" style={{ color: elemColor }}>
        {ELEMENT_ICON[fighter.element]} {fighter.element}
      </div>
      <div className="f3-avatar">
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
          <motion.div className="f3-energy-fill" animate={{ width: `${fighter.energy ?? 0}%` }} />
        </div>
      )}
      {fighter.effects?.length > 0 && (
        <div className="f3-effects">
          {fighter.effects.map((e, i) => (
            <span key={i} className={`f3-effect ${e.name}`}>
              {e.name === 'poisoned' ? '☠' : e.name === 'atk_down' ? '↓ATK'
               : e.name === 'stunned' ? '⚡' : e.name === 'focused' ? '🎯'
               : e.name === 'guarding' ? '🛡' : '?'}
            </span>
          ))}
        </div>
      )}
      {!fighter.is_alive && <div className="f3-dead-overlay">💀</div>}
      {isTarget && (
        <motion.div className="f3-target-ring"
          animate={{ scale: [1, 1.15, 1] }} transition={{ repeat: Infinity, duration: 0.8 }} />
      )}
    </motion.div>
  )
}
