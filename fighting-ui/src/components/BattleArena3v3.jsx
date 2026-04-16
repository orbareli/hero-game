import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const ELEMENT_COLOR = { Power: '#ef4444', Speed: '#22c55e', Tech: '#60a5fa' }
const ELEMENT_ICON  = { Power: '⚡', Speed: '💨', Tech: '⚙' }
const RARITY_COLOR  = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }
const ENERGY_SKILL_COST = 50

/**
 * BattleArena3v3
 * Props:
 *   playerId      – string
 *   playerTeam    – string[] of pc_ids
 *   enemyTeam     – string[] of char_ids
 *   onBattleEnd   – (outcome) => void
 *   onBack        – () => void   (return to team builder)
 */
export default function BattleArena3v3({ playerId, playerTeam, enemyTeam, onBattleEnd, onBack }) {
  const [state,         setState]         = useState(null)
  const [events,        setEvents]        = useState([])   // battle log
  const [inputReq,      setInputReq]      = useState(null) // {actor, valid_targets, can_use_skill}
  const [selectedTarget, setSelectedTarget] = useState(null)
  const [selectedSkill,  setSelectedSkill]  = useState(null)   // skill index or null (=attack)
  const [targetMode,     setTargetMode]     = useState('enemy') // 'enemy' | 'ally'
  const [battleResult,  setBattleResult]  = useState(null)
  const [damagePopups,  setDamagePopups]  = useState([])   // [{id,x,y,value,crit}]
  const [phase,         setPhase]         = useState('connecting')
  const [enemyActing,   setEnemyActing]   = useState(null) // highlighted enemy fighter
  const [battleState, setBattleState] = useState({
    player_team: [],
    enemy_team: [],
    turn_queue: [],
    phase: 'loading'
  });
  const wsRef     = useRef(null)
  const logRef    = useRef(null)
  const popupId   = useRef(0)

  // ── Connect WebSocket ─────────────────────────────────────────────────────
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/battle3')
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type:        'start',
        player_id:   playerId,
        player_team: playerTeam,
        enemy_team:  enemyTeam,
      }))
      setPhase('waiting')
    }

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      handleMessage(msg)
    }

    ws.onerror = () => setPhase('error')
    ws.onclose = () => {}

    return () => { ws.close() }
  }, [])

  const handleMessage = useCallback((msg) => {
    switch (msg.type) {

      case 'state':
        setState(msg.state)
        setPhase(msg.state.phase === 'player_input' ? 'player_turn' : 'enemy_turn')
        break

      case 'round_start':
        setState(msg.state)
        setEvents(prev => [...prev, {
          type: 'round', detail: `━━━ Round ${msg.round} ━━━`, id: Date.now()
        }])
        break

      case 'input_required':
        setInputReq(msg)
        setSelectedTarget(msg.enemy_targets[0]?.index ?? 0)
        setSelectedSkill(null)      // reset — player must explicitly pick
        setTargetMode('enemy')      // default targeting mode
        setPhase('player_turn')
        setEnemyActing(null)
        break

      case 'enemy_acting':
        setEnemyActing(msg.actor_index)
        setPhase('enemy_turn')
        setInputReq(null)
        break

      case 'events':
        // Add events to log and spawn damage popups
        msg.events.forEach(ev => {
          setEvents(prev => [...prev, { ...ev, id: Date.now() + Math.random() }])
          if (ev.damage > 0) {
            spawnPopup(ev.damage, ev.crit, ev.actor_team === 'player' ? 'right' : 'left')
          }
          if (ev.heal > 0) {
            spawnHealPopup(ev.heal, ev.actor_team === 'player' ? 'left' : 'right')
          }
        })
        break

      case 'battle_end':
        setBattleResult(msg)
        setPhase('done')
        setInputReq(null)
        if (onBattleEnd) onBattleEnd(msg.outcome)
        break

      case 'error':
        setEvents(prev => [...prev, { type: 'error', detail: msg.message, id: Date.now() }])
        setPhase('error')
        break
    }
  }, [])

  // ── Send player action ────────────────────────────────────────────────────
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

  // ── Damage popups ─────────────────────────────────────────────────────────
  const spawnPopup = (value, isCrit, side) => {
    const id = popupId.current++
    const x  = side === 'right' ? 65 + Math.random() * 20 : 15 + Math.random() * 20
    const y  = 20 + Math.random() * 40
    setDamagePopups(prev => [...prev, { id, x, y, value, crit: isCrit, type: 'damage' }])
    setTimeout(() => setDamagePopups(prev => prev.filter(p => p.id !== id)), 1200)
  }

  const spawnHealPopup = (value, side) => {
    const id = popupId.current++
    const x  = side === 'right' ? 65 + Math.random() * 20 : 15 + Math.random() * 20
    const y  = 20 + Math.random() * 40
    setDamagePopups(prev => [...prev, { id, x, y, value, type: 'heal' }])
    setTimeout(() => setDamagePopups(prev => prev.filter(p => p.id !== id)), 1200)
  }

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [events])

  if (phase === 'connecting' || !state) {
    return <div className="arena-loading"><div className="loading-spinner" /><p>Connecting…</p></div>
  }

  const { player_team, enemy_team } = state
  const actor = inputReq?.actor

  return (
    <div className="arena-3v3">

      {/* ── Damage popups (absolutely positioned overlay) ── */}
      <div className="popup-layer" aria-hidden>
        <AnimatePresence>
          {damagePopups.map(p => (
            <motion.div
              key={p.id}
              className={`dmg-popup ${p.type} ${p.crit ? 'crit' : ''}`}
              style={{ left: `${p.x}%`, top: `${p.y}%` }}
              initial={{ opacity: 1, y: 0, scale: p.crit ? 1.4 : 1 }}
              animate={{ opacity: 0, y: -50, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.0 }}
            >
              {p.type === 'heal' ? `+${p.value}` : `-${p.value}`}
              {p.crit && <span className="popup-crit">!</span>}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* ── Enemy team row ── */}
      <div className="team-row enemy-row">
        {enemy_team.map((f, i) => (
          <FighterCard3v3
            key={f.char_id + i}
            fighter={f}
            side="enemy"
            isActive={enemyActing === i}
            isTarget={inputReq && selectedTarget === i}
            isSelectable={!!inputReq && f.is_alive}
            onClick={() => inputReq && setSelectedTarget(i)}
          />
        ))}
      </div>

      {/* ── Round + phase indicator ── */}
      <div className="arena-status-bar">
        <span className="round-badge">Round {state.round}</span>
        <span className={`phase-badge ${phase}`}>
          {phase === 'player_turn' ? `${actor?.name}'s Turn` :
           phase === 'enemy_turn'  ? 'Enemy Acting…' :
           phase === 'done'        ? 'Battle Over' : '…'}
        </span>
        <button className="back-btn" onClick={onBack}>← Retreat</button>
      </div>

      {/* ── Player team row ── */}
      <div className="team-row player-row">
        {player_team.map((f, i) => (
          <FighterCard3v3
            key={f.pc_id + i}
            fighter={f}
            side="player"
            isActive={inputReq?.actor?.pc_id === f.pc_id}
            isTarget={false}
            isSelectable={false}
            onClick={() => {}}
          />
        ))}
      </div>

      {/* ── Action panel (shown only on player turn) ── */}
      <AnimatePresence>
        {inputReq && phase === 'player_turn' && (
          <motion.div
            className="action-panel"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 30 }}
          >
            {/* Actor + energy */}
            <div className="action-actor">
              <span className="actor-name">{actor?.name}</span>
              <EnergyBar energy={actor?.energy ?? 0} />
            </div>

            {/* Target display */}
            <div className="action-target-label">
              {targetMode === 'ally'
                ? <>Heal: <strong>{state?.player_team[selectedTarget]?.name ?? '—'}</strong></>
                : <>Target: <strong>{state?.enemy_team[selectedTarget]?.name ?? '—'}</strong></>
              }
            </div>

            {/* Skills + basic attack */}
            <div className="action-buttons">
              {/* Basic attack — always available, always targets enemy */}
              <button
                className={`action-btn attack ${selectedSkill === null ? 'selected-action' : ''}`}
                onClick={() => {
                  setSelectedSkill(null)
                  setTargetMode('enemy')
                  setSelectedTarget(inputReq.enemy_targets[0]?.index ?? 0)
                  sendAction('attack', null)
                }}
              >
                ⚔ Basic Attack
                <span className="skill-cost">free</span>
              </button>

              {/* One button per skill */}
              {inputReq.skills?.map(skill => (
                <button
                  key={skill.index}
                  className={[
                    'action-btn skill',
                    !skill.can_afford ? 'disabled' : '',
                    selectedSkill === skill.index ? 'selected-action' : '',
                    skill.target === 'ally' ? 'ally-skill' : '',
                    skill.target === 'self' ? 'self-skill' : '',
                  ].join(' ')}
                  disabled={!skill.can_afford}
                  title={skill.desc}
                  onClick={() => {
                    if (!skill.can_afford) return
                    const isAlly = skill.target === 'ally'
                    const isSelf = skill.target === 'self'
                    setSelectedSkill(skill.index)
                    if (isSelf) {
                      // Self-targeting: send immediately, no target needed
                      setTargetMode('enemy')
                      sendAction('skill', skill.index)
                    } else if (isAlly) {
                      setTargetMode('ally')
                      setSelectedTarget(inputReq.ally_targets[0]?.index ?? 0)
                    } else {
                      setTargetMode('enemy')
                      setSelectedTarget(inputReq.enemy_targets[0]?.index ?? 0)
                    }
                  }}
                >
                  <span className="skill-icon">
                    {skill.target === 'ally' ? '💚' : skill.target === 'self' ? '🔮' : '✦'}
                  </span>
                  {skill.name}
                  <span className="skill-cost">{skill.energy_cost}⚡</span>
                </button>
              ))}
            </div>

            {/* Confirm button — shown when a skill is selected and needs a target */}
            {selectedSkill !== null && inputReq.skills[selectedSkill]?.target !== 'self' && (
              <motion.button
                className="confirm-btn"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                onClick={() => sendAction('skill', selectedSkill)}
              >
                ✓ Confirm — {inputReq.skills[selectedSkill]?.name}
              </motion.button>
            )}

            {/* Target selector — shows enemy or ally list depending on skill */}
            <div className="target-selector">
              {(targetMode === 'ally' ? inputReq.ally_targets : inputReq.enemy_targets)?.map(t => (
                <button
                  key={t.index}
                  className={`target-btn ${selectedTarget === t.index ? 'selected' : ''} ${targetMode}`}
                  onClick={() => setSelectedTarget(t.index)}
                >
                  {targetMode === 'ally' ? '💚 ' : ''}
                  {t.name}
                  <span style={{ color: ELEMENT_COLOR[t.element], fontSize: '0.7rem' }}>
                    {' '}{ELEMENT_ICON[t.element]}
                  </span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Battle log ── */}
      <div className="battle-log-3v3" ref={logRef}>
        {events.map((ev, i) => <LogLine key={ev.id ?? i} event={ev} />)}
      </div>

      {/* ── Result overlay ── */}
      <AnimatePresence>
        {battleResult && (
          <motion.div
            className={`result-overlay ${battleResult.outcome}`}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <div className="result-title">
              {battleResult.outcome === 'win'  ? '🏆 VICTORY'
               : battleResult.outcome === 'loss' ? '💀 DEFEAT'
               : '🤝 DRAW'}
            </div>
            <div className="result-stats">
              <span>🪙 +{battleResult.rewards?.coins}</span>
              <span>⭐ +{battleResult.rewards?.xp} XP</span>
              <span>{battleResult.rounds} rounds</span>
            </div>
            <button className="result-btn" onClick={onBack}>← New Battle</button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Fighter card ──────────────────────────────────────────────────────────────
function FighterCard3v3({ fighter, side, isActive, isTarget, isSelectable, onClick }) {
  const hpPct    = fighter.max_hp > 0 ? (fighter.hp / fighter.max_hp) * 100 : 0
  const energyPct = fighter.energy ?? 0
  const elemColor = ELEMENT_COLOR[fighter.element] || '#94a3b8'
  const hpColor   = hpPct > 50 ? '#22c55e' : hpPct > 20 ? '#eab308' : '#ef4444'

  return (
    <motion.div
      className={[
        'fighter-3v3',
        side,
        isActive    ? 'active'    : '',
        isTarget    ? 'targeted'  : '',
        isSelectable ? 'selectable' : '',
        !fighter.is_alive ? 'dead' : '',
      ].join(' ')}
      style={{ '--elem-color': elemColor }}
      onClick={isSelectable ? onClick : undefined}
      animate={isActive ? { scale: 1.06 } : { scale: 1 }}
      whileHover={isSelectable ? { scale: 1.04, cursor: 'pointer' } : {}}
    >
      {/* Element badge */}
      <div className="f3-element" style={{ color: elemColor }}>
        {ELEMENT_ICON[fighter.element]} {fighter.element}
      </div>

      {/* Avatar */}
      <div className="f3-avatar">
        {fighter.portrait_id && fighter.portrait_id !== 'default' ? (
          <img
            src={`/portraits/${fighter.portrait_id}.png`}
            alt={fighter.name}
            className={side === 'enemy' ? 'enemy-flip' : ''}
            onError={e => { e.target.style.display = 'none' }}
          />
        ) : (
          <span>{side === 'player' ? '🦸' : '💀'}</span>
        )}
      </div>

      {/* Name + rarity */}
      <div className="f3-name">{fighter.name}</div>
      <div className="f3-rarity" style={{ color: RARITY_COLOR[fighter.rarity] }}>
        {fighter.rarity}
      </div>

      {/* HP bar */}
      <div className="f3-hp-track">
        <motion.div
          className="f3-hp-fill"
          style={{ backgroundColor: hpColor }}
          animate={{ width: `${hpPct}%` }}
          transition={{ type: 'spring', stiffness: 80, damping: 18 }}
        />
      </div>
      <div className="f3-hp-text">{fighter.hp}/{fighter.max_hp}</div>

      {/* Energy bar (player side only) */}
      {fighter.is_player && (
        <div className="f3-energy-track">
          <motion.div
            className="f3-energy-fill"
            animate={{ width: `${energyPct}%` }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
          />
        </div>
      )}

      {/* Status effects */}
      {fighter.effects?.length > 0 && (
        <div className="f3-effects">
          {fighter.effects.map((e, i) => (
            <span key={i} className={`f3-effect ${e.name}`} title={`${e.name} (${e.turns}t)`}>
              {e.name === 'poisoned' ? '☠' : e.name === 'atk_down' ? '↓ATK' : e.name === 'stunned' ? '⚡' : '?'}
            </span>
          ))}
        </div>
      )}

      {/* Dead overlay */}
      {!fighter.is_alive && (
        <div className="f3-dead-overlay">💀</div>
      )}

      {/* Target indicator */}
      {isTarget && (
        <motion.div
          className="f3-target-ring"
          animate={{ scale: [1, 1.15, 1] }}
          transition={{ repeat: Infinity, duration: 0.8 }}
        />
      )}
    </motion.div>
  )
}

// ── Energy bar ────────────────────────────────────────────────────────────────
function EnergyBar({ energy }) {
  return (
    <div className="energy-bar-wrap">
      <span className="energy-label">⚡ {energy}/100</span>
      <div className="energy-track">
        <motion.div
          className="energy-fill"
          animate={{ width: `${energy}%` }}
          transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        />
        <div className="energy-threshold" style={{ left: `${ENERGY_SKILL_COST}%` }} />
      </div>
    </div>
  )
}

// ── Battle log line ───────────────────────────────────────────────────────────
function LogLine({ event }) {
  if (event.type === 'round') {
    return <div className="log-round">{event.detail}</div>
  }
  const isPlayer = event.actor_team === 'player'
  const isError  = event.type === 'error'
  return (
    <motion.div
      className={`log-line ${isError ? 'error' : isPlayer ? 'player' : 'enemy'}`}
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.15 }}
    >
      <span className="log-detail">{event.detail}</span>
      {event.damage > 0 && <span className="log-dmg">-{event.damage}</span>}
      {event.heal   > 0 && <span className="log-heal">+{event.heal}</span>}
      {event.crit   && <span className="log-tag crit">CRIT</span>}
      {event.evaded && <span className="log-tag evade">EVADE</span>}
    </motion.div>
  )
}