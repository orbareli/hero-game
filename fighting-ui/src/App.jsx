import React, { useState, useEffect } from 'react'
import BattleArena from './components/BattleArena'
import BattleArena3v3 from './components/BattleArena3v3'
import TeamBuilder from './components/TeamBuilder'
import Roster from './components/Roster'
import Shop from './components/Shop'
import TowerMode from './components/TowerMode'
import './App.css'

const API = 'http://localhost:8000'

// Battle mode: '1v1' | 'setup3v3' | '3v3'
export default function App() {
  const [tab,          setTab]          = useState('battle')
  const [battleMode,   setBattleMode]   = useState('1v1')
  const [player,       setPlayer]       = useState(null)
  const [allChars,     setAllChars]     = useState([])
  const [roster,       setRoster]       = useState([])   // player-owned characters
  const [error,        setError]        = useState(null)
  const [playerCharId, setPlayerCharId] = useState(null)
  const [enemyCharId,  setEnemyCharId]  = useState(null)

  // 3v3 team state
  const [playerTeam3,  setPlayerTeam3]  = useState([])
  const [enemyTeam3,   setEnemyTeam3]   = useState([])

  // Load player on mount
  useEffect(() => {
    async function load() {
      try {
        let pid = localStorage.getItem('player_id')
        if (!pid) {
          const r = await fetch(`${API}/player/first`)
          if (!r.ok) throw new Error('No player found — run db/seed2.py first')
          const d = await r.json()
          pid = d.id
          localStorage.setItem('player_id', pid)
        }
        const r = await fetch(`${API}/player/${pid}`)
        if (!r.ok) { localStorage.removeItem('player_id'); throw new Error('Player not found') }
        setPlayer(await r.json())

        // Pre-load master chars
        const cr = await fetch(`${API}/characters`)
        if (cr.ok) setAllChars(await cr.json())

        // Load roster — used by TowerMode picker, Roster tab, and default 1v1 char
        const rr = await fetch(`${API}/player/${pid}/roster`)
        if (rr.ok) {
          const rosterData = await rr.json()
          setRoster(rosterData)
          if (rosterData.length > 0) setPlayerCharId(rosterData[0].id)
        }
      } catch (e) { setError(e.message) }
    }
    load()
  }, [])

  const refreshPlayer = async () => {
    if (!player?.id) return
    const [pr, rr] = await Promise.all([
      fetch(`${API}/player/${player.id}`),
      fetch(`${API}/player/${player.id}/roster`),
    ])
    if (pr.ok) setPlayer(await pr.json())
    if (rr.ok) setRoster(await rr.json())
  }

  if (error) return (
    <div className="app-error">
      <div className="error-box">
        <h2>⚠ Setup Required</h2>
        <p>{error}</p>
        <code>cd backend && python -m db.seed2</code>
        <p>Then refresh this page.</p>
      </div>
    </div>
  )

  if (!player) return (
    <div className="app-loading">
      <div className="loading-spinner" />
      <p>Connecting…</p>
    </div>
  )

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <span className="brand-icon">⚔</span>
          <span className="brand-name">FIGHT GAME</span>
        </div>
        <nav className="header-nav">
          {['battle', 'roster', 'shop', 'tower'].map(t => (
            <button key={t} className={`nav-btn ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}>
              {t === 'battle' ? '⚔ Battle' : t === 'roster' ? '🧑‍🤝‍🧑 Roster' : t === 'shop' ? '🏪 Shop' : '🗼 Tower'}
            </button>
          ))}
        </nav>
        <div className="header-currency">
          <span className="coin">🪙 {player.coins}</span>
          <span className="gem">💎 {player.gems}</span>
        </div>
      </header>

      <main className="app-main">
        {/* ── BATTLE TAB ── */}
        {tab === 'battle' && (
          <>
            {/* Mode toggle */}
            {(battleMode === '1v1' || battleMode === 'setup3v3') && (
              <div className="mode-toggle">
                <button
                  className={`mode-btn ${battleMode === '1v1' ? 'active' : ''}`}
                  onClick={() => setBattleMode('1v1')}
                >1v1 Classic</button>
                <button
                  className={`mode-btn ${battleMode === 'setup3v3' ? 'active' : ''}`}
                  onClick={() => setBattleMode('setup3v3')}
                >⚔ 3v3 Squad</button>
              </div>
            )}

            {battleMode === '1v1' && (
              <BattleArena
                playerId={player.id}
                playerCharId={playerCharId}
                enemyCharId={enemyCharId}
                onSetEnemyCharId={setEnemyCharId}
                onBattleEnd={refreshPlayer}
              />
            )}

            {battleMode === 'setup3v3' && (
              <TeamBuilder
                playerId={player.id}
                allChars={allChars}
                onTeamReady={(pTeam, eTeam) => {
                  setPlayerTeam3(pTeam)
                  setEnemyTeam3(eTeam)
                  setBattleMode('3v3')
                }}
              />
            )}

            {battleMode === '3v3' && (
              <BattleArena3v3
                playerId={player.id}
                playerTeam={playerTeam3}
                enemyTeam={enemyTeam3}
                onBattleEnd={(outcome) => { refreshPlayer() }}
                onBack={() => setBattleMode('setup3v3')}
              />
            )}
          </>
        )}

        {tab === 'roster' && (
          <Roster
            playerId={player.id}
            onSelectFighter={(pcId) => { setPlayerCharId(pcId); setTab('battle') }}
          />
        )}

        {tab === 'tower' && (
          <TowerMode
            playerId={player.id}
            allChars={allChars}
            roster={roster}
            onBack={() => setTab('battle')}
          />
        )}

        {tab === 'shop' && (
          <Shop playerId={player.id} playerCoins={player.coins} onPurchase={refreshPlayer} />
        )}
      </main>
    </div>
  )
}