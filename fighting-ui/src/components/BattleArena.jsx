import React, { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const API = 'http://localhost:8000'

const RARITY_COLOR = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }
const FACTION_ICON = { hero: '🦸', villain: '💀' }

const EMPTY_FIGHTER = { name: '—', hp: 0, maxHp: 0, portrait_id: null }

export default function BattleArena({
  playerId,
  playerCharId,
  enemyCharId,
  onSetEnemyCharId,
  onBattleEnd,
}) {
  const [allChars,      setAllChars]      = useState([])
  const [log,           setLog]           = useState([])
  const [result,        setResult]        = useState(null)
  const [isFighting,    setIsFighting]    = useState(false)
  const [status,        setStatus]        = useState('idle')
  const [selectedEnemy, setSelectedEnemy] = useState(enemyCharId || null)

  const [player, setPlayer] = useState(EMPTY_FIGHTER)
  const [enemy,  setEnemy]  = useState(EMPTY_FIGHTER)

  const scrollRef = useRef(null)
  const wsRef     = useRef(null)

  // Pre-load player HP + portrait from roster on mount
  useEffect(() => {
    if (!playerId) return
    fetch(`${API}/player/${playerId}/roster`)
      .then(r => r.json())
      .then(roster => {
        const pc = playerCharId
          ? roster.find(r => r.id === playerCharId)
          : roster[0]
        if (pc) {
          setPlayer({
            name:       pc.master_data?.name       || '—',
            hp:         pc.hp,
            maxHp:      pc.hp,
            portrait_id: pc.master_data?.portrait_id || null,
          })
        }
      })
      .catch(console.error)
  }, [playerId, playerCharId])

  // When enemy is selected, show its HP + portrait immediately
  useEffect(() => {
    if (!selectedEnemy || allChars.length === 0) return
    const char = allChars.find(c => c.id === selectedEnemy)
    if (char) {
      setEnemy({
        name:       char.name,
        hp:         char.base_hp,
        maxHp:      char.base_hp,
        portrait_id: char.portrait_id || null,
      })
    }
    if (onSetEnemyCharId) onSetEnemyCharId(selectedEnemy)
  }, [selectedEnemy, allChars])

  // Load master character list, auto-select first villain
  useEffect(() => {
    fetch(`${API}/characters`)
      .then(r => r.json())
      .then(chars => {
        setAllChars(chars)
        if (!selectedEnemy) {
          const first = chars.find(c => c.faction === 'villain')
          if (first) setSelectedEnemy(first.id)
        }
      })
      .catch(console.error)
  }, [])

  // Auto-scroll log
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [log])

  // ── Start battle ──────────────────────────────────────────────────────────
  const startBattle = useCallback(() => {
    if (!playerCharId || !selectedEnemy || isFighting) return

    setLog([])
    setResult(null)
    setIsFighting(true)
    setStatus('connecting')

    const ws = new WebSocket(`ws://localhost:8000/ws/battle`)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('fighting')
      ws.send(JSON.stringify({
        player_id:      playerId,
        player_char_id: playerCharId,
        enemy_char_id:  selectedEnemy,
      }))
    }

    ws.onmessage = (evt) => {
      const data = JSON.parse(evt.data)

      if (data.type === 'ready') {
        // Server sends confirmed stats + portrait_id — set both atomically
        setPlayer({
          name:        data.player_char.name,
          hp:          data.player_char.hp,
          maxHp:       data.player_char.max_hp,
          portrait_id: data.player_char.portrait_id || null,
        })
        setEnemy({
          name:        data.enemy_char.name,
          hp:          data.enemy_char.hp,
          maxHp:       data.enemy_char.max_hp,
          portrait_id: data.enemy_char.portrait_id || null,
        })

      } else if (data.type === 'event') {
        setLog(prev => [...prev, data])
        if (data.action !== 'start') {
          setPlayer(prev => ({ ...prev, hp: data.p_hp }))
          setEnemy(prev =>  ({ ...prev, hp: data.e_hp }))
        }

      } else if (data.type === 'result') {
        setResult(data)
        setIsFighting(false)
        setStatus('done')
        if (onBattleEnd) onBattleEnd()
        ws.close()

      } else if (data.type === 'error') {
        setLog(prev => [...prev, {
          type: 'error', detail: data.message,
          actor: 'system', action: 'error', turn: 0,
        }])
        setIsFighting(false)
        setStatus('idle')
        ws.close()
      }
    }

    ws.onerror = () => {
      setLog(prev => [...prev, {
        type: 'error',
        detail: 'WebSocket connection failed — is the backend running?',
        actor: 'system', action: 'error', turn: 0,
      }])
      setIsFighting(false)
      setStatus('idle')
    }

    ws.onclose = () => {}

  }, [playerId, playerCharId, selectedEnemy, isFighting])

  // ── Derived values ────────────────────────────────────────────────────────
  const safePct = (hp, max) =>
    max > 0 ? Math.max(0, Math.min(100, (hp / max) * 100)) : 0

  const pPct = safePct(player.hp, player.maxHp)
  const ePct = safePct(enemy.hp,  enemy.maxHp)

  const hpColor = pct =>
    pct > 50 ? '#22c55e' : pct > 20 ? '#eab308' : '#ef4444'

  const villains = allChars.filter(c => c.faction === 'villain')
  const canFight = playerCharId && selectedEnemy && !isFighting

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="battle-arena">

      <div className="fighters-row">
        {/* portrait_id is now passed from the player/enemy state objects */}
        <FighterCard
          name={player.name}
          hp={player.hp}
          maxHp={player.maxHp}
          pct={pPct}
          hpColor={hpColor(pPct)}
          side="player"
          label="YOUR HERO"
          portrait_id={player.portrait_id}
        />
        <div className="vs-divider">
          <span className="vs-text">VS</span>
          {isFighting && <div className="pulse-ring" />}
        </div>
        <FighterCard
          name={enemy.name}
          hp={enemy.hp}
          maxHp={enemy.maxHp}
          pct={ePct}
          hpColor={hpColor(ePct)}
          side="enemy"
          label="ENEMY"
          portrait_id={enemy.portrait_id}
        />
      </div>

      {!isFighting && (
        <div className="enemy-picker">
          <p className="picker-label">Choose your opponent:</p>
          <div className="picker-grid">
            {villains.map(c => (
              <button
                key={c.id}
                className={`picker-card ${selectedEnemy === c.id ? 'selected' : ''}`}
                onClick={() => setSelectedEnemy(c.id)}
              >
                <span className="picker-icon">{FACTION_ICON[c.faction]}</span>
                <span className="picker-name">{c.name}</span>
                <span className="picker-rarity" style={{ color: RARITY_COLOR[c.rarity] }}>
                  {c.rarity}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="battle-log" ref={scrollRef}>
        {log.length === 0 && !isFighting && (
          <p className="log-empty">
            {!playerCharId
              ? '⚠ Go to Roster and select a hero first!'
              : 'Pick an enemy above and press Initiate Battle.'}
          </p>
        )}
        <AnimatePresence initial={false}>
          {log.map((entry, i) => <LogEntry key={i} entry={entry} />)}
        </AnimatePresence>
      </div>

      <button
        className={`fight-btn ${isFighting ? 'fighting' : ''} ${!canFight && !isFighting ? 'disabled' : ''}`}
        onClick={startBattle}
        disabled={!canFight}
      >
        {isFighting
          ? <><span className="spin">⚙</span> Simulating…</>
          : status === 'done' ? '⚔ Battle Again' : '⚔ Initiate Battle'}
      </button>

      <AnimatePresence>
        {result && (
          <motion.div
            className={`result-banner ${result.outcome}`}
            initial={{ opacity: 0, scale: 0.8, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8 }}
          >
            <div className="result-outcome">
              {result.outcome === 'win' ? '🏆 VICTORY'
                : result.outcome === 'loss' ? '💀 DEFEAT' : '🤝 DRAW'}
            </div>
            <div className="result-rewards">
              <span>🪙 +{result.coins_earned}</span>
              <span>⭐ +{result.xp_earned} XP</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── FighterCard ───────────────────────────────────────────────────────────────
// portrait_id: string like "swiftbolt" → loads /portraits/swiftbolt.png
// If null, empty, or the image fails to load → falls back to emoji icon.
function FighterCard({ name, hp, maxHp, pct, hpColor, side, label, portrait_id }) {
  const [imgError, setImgError] = useState(false)

  // Reset error state whenever portrait_id changes (new character selected)
  useEffect(() => {
    setImgError(false)
  }, [portrait_id])

  const fallbackIcon = side === 'player' ? '🦸' : '💀'
  const showImage    = portrait_id && portrait_id !== 'default' && !imgError

  return (
    <div className={`fighter-card ${side}`}>
      <div className="fighter-label">{label}</div>
      <div className="fighter-avatar">
        {showImage ? (
          <motion.img
            key={portrait_id}
            src={`/portraits/${portrait_id}.png`}
            alt={name}
            className={`avatar-img ${side === 'enemy' ? 'enemy-flip' : ''}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onError={() => setImgError(true)}
          />
        ) : (
          <span className="fallback-icon">{fallbackIcon}</span>
        )}
      </div>
      <div className="fighter-name">{name}</div>
      <div className="hp-bar-track">
        <motion.div
          className="hp-bar-fill"
          style={{ backgroundColor: hpColor }}
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 80, damping: 18 }}
        />
      </div>
      <div className="hp-text">
        {maxHp > 0 ? `${hp} / ${maxHp} HP` : '— HP'}
      </div>
    </div>
  )
}

// ── LogEntry ──────────────────────────────────────────────────────────────────
function LogEntry({ entry }) {
  const isSystem = entry.actor === 'system'
  const isError  = entry.type  === 'error'
  const cls = isError ? 'log-entry error'
    : isSystem        ? 'log-entry system'
    : entry.action === 'poison' || entry.action === 'passive_heal'
                        ? 'log-entry system'
    :                   'log-entry combat'

  return (
    <motion.div
      className={cls}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.18 }}
    >
      <span className="log-turn">T{String(entry.turn).padStart(2, '0')}</span>
      <span className="log-detail">{entry.detail}</span>
      {entry.damage > 0 && <span className="log-dmg">-{entry.damage}</span>}
      {entry.heal   > 0 && <span className="log-heal">+{entry.heal}</span>}
      {entry.crit   && <span className="log-tag crit">CRIT</span>}
      {entry.evaded && <span className="log-tag evade">EVADE</span>}
    </motion.div>
  )
}