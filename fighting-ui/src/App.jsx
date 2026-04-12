import React, { useState, useEffect } from 'react'
import BattleArena from './components/BattleArena'
import Roster from './components/Roster'
import Shop from './components/Shop'
import './App.css'

const API = 'http://localhost:8000'

// ── Top-level app shell ──────────────────────────────────────────────────────
// On first load we call GET /player/{id} to verify the player exists.
// The player_id comes from localStorage so a returning user keeps their session.
// If nothing is stored we fall back to the seeded Player1 id by fetching the
// first player record (dev convenience — in production you'd have real auth).

export default function App() {
  const [tab, setTab]           = useState('battle')
  const [player, setPlayer]     = useState(null)
  const [error, setError]       = useState(null)

  // The IDs the BattleArena needs (chosen in Roster / hardcoded for now)
  const [playerCharId, setPlayerCharId] = useState(null)
  const [enemyCharId,  setEnemyCharId]  = useState(null)

  // ── Load player on mount ─────────────────────────────────────────
  useEffect(() => {
    async function loadPlayer() {
      try {
        // Try localStorage first (player already played before)
        let pid = localStorage.getItem('player_id')

        if (!pid) {
          // Dev fallback: grab the first player from a known endpoint
          // In production replace this with real auth
          const res = await fetch(`${API}/player/first`)
          if (!res.ok) throw new Error('No player found — did you run seed2.py?')
          const data = await res.json()
          pid = data.id
          localStorage.setItem('player_id', pid)
        }

        const res = await fetch(`${API}/player/${pid}`)
        if (!res.ok) {
          localStorage.removeItem('player_id')
          throw new Error('Saved player not found — re-seeding may be needed')
        }
        const data = await res.json()
        setPlayer(data)

        // Also load roster to pick a default battle character
        const rosterRes = await fetch(`${API}/player/${pid}/roster`)
        if (rosterRes.ok) {
          const roster = await rosterRes.json()
          if (roster.length > 0) setPlayerCharId(roster[0].id)
        }
      } catch (e) {
        setError(e.message)
      }
    }
    loadPlayer()
  }, [])

  const refreshPlayer = async () => {
    if (!player?.id) return
    const res  = await fetch(`${API}/player/${player.id}`)
    if (res.ok) setPlayer(await res.json())
  }

  if (error) {
    return (
      <div className="app-error">
        <div className="error-box">
          <h2>⚠ Setup Required</h2>
          <p>{error}</p>
          <code>cd backend && python -m db.seed2</code>
          <p>Then refresh this page.</p>
        </div>
      </div>
    )
  }

  if (!player) {
    return (
      <div className="app-loading">
        <div className="loading-spinner" />
        <p>Connecting to server…</p>
      </div>
    )
  }

  return (
    <div className="app-shell">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-brand">
          <span className="brand-icon">⚔</span>
          <span className="brand-name">FIGHT GAME</span>
        </div>
        <nav className="header-nav">
          {['battle', 'roster', 'shop'].map(t => (
            <button
              key={t}
              className={`nav-btn ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}
            >
              {t === 'battle' ? '⚔ Battle' : t === 'roster' ? '🧑‍🤝‍🧑 Roster' : '🏪 Shop'}
            </button>
          ))}
        </nav>
        <div className="header-currency">
          <span className="coin">🪙 {player.coins}</span>
          <span className="gem">💎 {player.gems}</span>
        </div>
      </header>

      {/* ── Content ── */}
      <main className="app-main">
        {tab === 'battle' && (
          <BattleArena
            playerId={player.id}
            playerCharId={playerCharId}
            enemyCharId={enemyCharId}
            onSetEnemyCharId={setEnemyCharId}
            onBattleEnd={refreshPlayer}
          />
        )}
        {tab === 'roster' && (
          <Roster
            playerId={player.id}
            onSelectFighter={(pcId) => {
              setPlayerCharId(pcId)
              setTab('battle')
            }}
          />
        )}
        {tab === 'shop' && (
          <Shop
            playerId={player.id}
            playerCoins={player.coins}
            onPurchase={refreshPlayer}
          />
        )}
      </main>
    </div>
  )
}