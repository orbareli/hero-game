/**
 * PvPLobby.jsx
 * ------------
 * Entry screen for local multiplayer.
 *
 * Flow:
 *   Player 1 clicks "Create Room"
 *     → connects to ws/pvp/create
 *     → receives room_code (e.g. "X4R9KZ")
 *     → shown a big code to share with friend
 *     → selects their team
 *
 *   Player 2 types the code, clicks "Join Room"
 *     → connects to ws/pvp/join/{code}
 *     → selects their team
 *
 *   Both teams confirmed → battle starts → PvPBattle component renders
 */

import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const WS_BASE = 'ws://localhost:8000'

const RARITY_COLOR = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }

export default function PvPLobby({ playerId, roster, onBattleReady, onBack }) {
  // 'menu' | 'creating' | 'joining' | 'waiting_opponent' | 'team_select' | 'waiting_start'
  const [phase,       setPhase]      = useState('menu')
  const [roomCode,    setRoomCode]   = useState('')
  const [joinInput,   setJoinInput]  = useState('')
  const [status,      setStatus]     = useState('')
  const [role,        setRole]       = useState(null)    // 'player1' | 'player2'
  const [selectedTeam, setSelectedTeam] = useState([])  // pc_ids
  const [teamLocked,  setTeamLocked] = useState(false)
  const [error,       setError]      = useState(null)
  const wsRef = useRef(null)

  // Clean up WS on unmount
  useEffect(() => () => wsRef.current?.close(), [])

  const connect = (url) => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      handleServerMessage(msg)
    }
    ws.onerror = () => setError('Connection failed — is the backend running?')
    ws.onclose = () => {
      if (phase !== 'menu') setError('Disconnected from server')
    }
    return ws
  }

  const handleServerMessage = (msg) => {
    switch (msg.type) {
      case 'room_created':
        setRoomCode(msg.room_code)
        setRole('player1')
        setPhase('waiting_opponent')
        setStatus(msg.message)
        break

      case 'room_joined':
        setRole('player2')
        setPhase('team_select')
        setStatus(msg.message)
        break

      case 'opponent_joined':
        // P1 gets this when P2 connects
        setPhase('team_select')
        setStatus('Opponent connected! Select your team.')
        break

      case 'team_confirmed':
        setTeamLocked(true)
        setStatus(msg.message)
        setPhase('waiting_start')
        break

      case 'status':
        setStatus(msg.message)
        break

      case 'battle_start':
        // Hand off to the battle component
        onBattleReady({ ws: wsRef.current, role, initialState: msg.state })
        break

      case 'error':
        setError(msg.message)
        break
    }
  }

  const createRoom = () => {
    setError(null)
    setPhase('creating')
    const ws = connect(`${WS_BASE}/ws/pvp/create`)
    ws.onopen = () => setStatus('Creating room…')
  }

  const joinRoom = () => {
    const code = joinInput.trim().toUpperCase()
    if (!code || code.length < 4) { setError('Enter a valid room code'); return }
    setError(null)
    setPhase('joining')
    const ws = connect(`${WS_BASE}/ws/pvp/join/${code}`)
    ws.onopen = () => setStatus(`Joining room ${code}…`)
  }

  const lockTeam = () => {
    if (selectedTeam.length === 0) { setError('Select at least 1 character'); return }
    if (!wsRef.current) return
    wsRef.current.send(JSON.stringify({
      type:      'team_ready',
      player_id: playerId,
      pc_ids:    selectedTeam,
    }))
  }

  const toggleChar = (pcId) => {
    setSelectedTeam(prev =>
      prev.includes(pcId) ? prev.filter(id => id !== pcId)
        : prev.length < 3  ? [...prev, pcId]
        : prev
    )
  }

  return (
    <div className="pvp-lobby">
      <AnimatePresence mode="wait">

        {/* ── Main menu ── */}
        {phase === 'menu' && (
          <motion.div key="menu" className="pvp-menu"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="pvp-hero-icon">⚔️</div>
            <h2 className="pvp-title">Local PvP</h2>
            <p className="pvp-subtitle">
              Play 3v3 against a friend on the same network.<br/>
              One player creates a room, the other joins with the code.
            </p>

            <div className="pvp-menu-buttons">
              <motion.button className="pvp-btn primary" onClick={createRoom}
                whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                🏠 Create Room
              </motion.button>

              <div className="pvp-join-row">
                <input
                  className="pvp-code-input"
                  placeholder="Room code (e.g. X4R9KZ)"
                  value={joinInput}
                  onChange={e => setJoinInput(e.target.value.toUpperCase())}
                  maxLength={6}
                  onKeyDown={e => e.key === 'Enter' && joinRoom()}
                />
                <motion.button className="pvp-btn secondary" onClick={joinRoom}
                  whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                  🔗 Join Room
                </motion.button>
              </div>
            </div>

            {error && <div className="pvp-error">{error}</div>}
            <button className="back-btn" onClick={onBack}>← Back</button>
          </motion.div>
        )}

        {/* ── Creating / joining spinner ── */}
        {(phase === 'creating' || phase === 'joining') && (
          <motion.div key="connecting" className="pvp-center"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="loading-spinner" />
            <p>{status || 'Connecting…'}</p>
          </motion.div>
        )}

        {/* ── Waiting for opponent (Player 1 after room created) ── */}
        {phase === 'waiting_opponent' && (
          <motion.div key="waiting" className="pvp-waiting"
            initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
            <p className="pvp-role-badge">You are Player 1</p>
            <p className="pvp-wait-label">Share this code with your opponent:</p>
            <motion.div
              className="pvp-room-code"
              animate={{ boxShadow: ['0 0 0 0 rgba(249,115,22,0)', '0 0 0 12px rgba(249,115,22,0.25)', '0 0 0 0 rgba(249,115,22,0)'] }}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              {roomCode}
            </motion.div>
            <div className="loading-spinner" style={{ marginTop: 24 }} />
            <p className="pvp-wait-sub">Waiting for opponent to join…</p>
            {error && <div className="pvp-error">{error}</div>}
          </motion.div>
        )}

        {/* ── Team selection ── */}
        {phase === 'team_select' && (
          <motion.div key="team" className="pvp-team-select"
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <p className="pvp-role-badge">
              {role === 'player1' ? '👤 You are Player 1' : '👤 You are Player 2'}
            </p>
            <h3 className="pvp-section-title">Select Your Team ({selectedTeam.length}/3)</h3>
            <p className="pvp-subtitle">{status}</p>

            <div className="pvp-char-grid">
              {roster.map(pc => {
                const m   = pc.master_data || {}
                const sel = selectedTeam.includes(pc.id)
                return (
                  <motion.button
                    key={pc.id}
                    className={`pvp-char-card ${sel ? 'selected' : ''} ${selectedTeam.length >= 3 && !sel ? 'maxed' : ''}`}
                    onClick={() => !teamLocked && toggleChar(pc.id)}
                    whileHover={!teamLocked ? { scale: 1.04 } : {}}
                    whileTap={!teamLocked ? { scale: 0.97 } : {}}
                    disabled={teamLocked}
                  >
                    <div className="pvp-card-rarity" style={{ color: RARITY_COLOR[m.rarity] }}>{m.rarity}</div>
                    <div className="pvp-card-avatar">🦸</div>
                    <div className="pvp-card-name">{m.name || 'Unknown'}</div>
                    <div className="pvp-card-stats">
                      <span>HP {pc.hp}</span>
                      <span>ATK {pc.atk}</span>
                    </div>
                    {sel && <div className="pvp-card-check">✓</div>}
                  </motion.button>
                )
              })}
            </div>

            {!teamLocked && (
              <motion.button
                className={`pvp-btn primary ${selectedTeam.length === 0 ? 'disabled' : ''}`}
                onClick={lockTeam}
                disabled={selectedTeam.length === 0}
                whileHover={selectedTeam.length > 0 ? { scale: 1.04 } : {}}
              >
                ✓ Lock In Team ({selectedTeam.length} hero{selectedTeam.length !== 1 ? 'es' : ''})
              </motion.button>
            )}

            {error && <div className="pvp-error">{error}</div>}
          </motion.div>
        )}

        {/* ── Waiting for battle to start ── */}
        {phase === 'waiting_start' && (
          <motion.div key="waiting_start" className="pvp-center"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="pvp-team-locked-icon">✓</div>
            <h3>Team Locked!</h3>
            <div className="loading-spinner" style={{ marginTop: 16 }} />
            <p>{status || 'Waiting for opponent to lock in their team…'}</p>
            {error && <div className="pvp-error">{error}</div>}
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  )
}
