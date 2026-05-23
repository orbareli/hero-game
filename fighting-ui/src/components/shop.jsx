import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

//const API = 'http://localhost:8000'
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const RARITY_COLOR = { C: '#94a3b8', R: '#60a5fa', SR: '#c084fc', UR: '#fbbf24' }

const SUMMON_COST = 100

export default function Shop({ playerId, playerCoins, onPurchase }) {
  const [shopItems,  setShopItems]  = useState([])
  const [loading,    setLoading]    = useState(true)
  const [summoning,  setSummoning]  = useState(false)
  const [summonResult, setSummonResult] = useState(null)
  const [error,      setError]      = useState(null)

  useEffect(() => {
    fetch(`${API}/shop`)
      .then(r => r.json())
      .then(setShopItems)
      .catch(() => setError('Failed to load shop'))
      .finally(() => setLoading(false))
  }, [])

  const handleSummon = async () => {
    if (playerCoins < SUMMON_COST || summoning) return
    setSummoning(true)
    setSummonResult(null)
    try {
      const res = await fetch(`${API}/shop/summon?player_id=${playerId}`, {
        method: 'POST',
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Summon failed')
      }
      const data = await res.json()
      setSummonResult(data)
      if (onPurchase) onPurchase()
    } catch (e) {
      setError(e.message)
    } finally {
      setSummoning(false)
    }
  }

  const directItems = shopItems.filter(i => i.item_type === 'direct' && i.character)

  if (loading) return <div className="section-loading">Loading shop…</div>

  return (
    <div className="shop-page">
      <div className="section-header">
        <h2>Shop</h2>
        <p className="section-subtitle">Your coins: 🪙 {playerCoins}</p>
      </div>

      {/* ── Summon banner ── */}
      <div className="summon-banner">
        <div className="summon-text">
          <h3>🎲 Random Summon</h3>
          <p>Spend {SUMMON_COST} coins for a chance at any character</p>
          <p className="rarity-odds">
            <span style={{ color: RARITY_COLOR.C }}>C 70%</span> ·{' '}
            <span style={{ color: RARITY_COLOR.R }}>R 20%</span> ·{' '}
            <span style={{ color: RARITY_COLOR.SR }}>SR 8%</span> ·{' '}
            <span style={{ color: RARITY_COLOR.UR }}>UR 2%</span>
          </p>
        </div>
        <button
          className={`summon-btn ${playerCoins < SUMMON_COST ? 'disabled' : ''} ${summoning ? 'loading' : ''}`}
          onClick={handleSummon}
          disabled={playerCoins < SUMMON_COST || summoning}
        >
          {summoning ? '✨ Summoning…' : `Summon — 🪙 ${SUMMON_COST}`}
        </button>

        {/* Summon result pop-up */}
        <AnimatePresence>
          {summonResult && (
            <motion.div
              className="summon-result"
              style={{ '--rarity-color': RARITY_COLOR[summonResult.character?.rarity] }}
              initial={{ opacity: 0, scale: 0.7, y: -10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.7 }}
            >
              <div className="sr-label">YOU GOT</div>
              <div className="sr-name">{summonResult.character?.name}</div>
              <div className="sr-rarity" style={{ color: RARITY_COLOR[summonResult.character?.rarity] }}>
                {summonResult.character?.rarity}
              </div>
              <div className="sr-msg">{summonResult.message}</div>
              <button className="sr-close" onClick={() => setSummonResult(null)}>✕</button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Direct purchase roster ── */}
      <div className="shop-section-title">Direct Purchase</div>
      <div className="shop-grid">
        {directItems.map((item, i) => (
          <ShopCard key={item.id} item={item} playerId={playerId} playerCoins={playerCoins} onPurchase={onPurchase} index={i} />
        ))}
      </div>

      {error && <div className="section-error">{error}</div>}
    </div>
  )
}

function ShopCard({ item, playerId, playerCoins, onPurchase, index }) {
  const [buying,  setBuying]  = useState(false)
  const [bought,  setBought]  = useState(false)
  const [message, setMessage] = useState(null)

  const char      = item.character
  const rarity    = char?.rarity || 'C'
  const canAfford = playerCoins >= item.price

  const handleBuy = async () => {
    if (buying || !canAfford) return
    setBuying(true)
    try {
      const res = await fetch(`${API}/shop/buy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_id: playerId, shop_item_id: item.id }),
      })
      const data = await res.json()
      setMessage(data.message)
      if (data.success) {
        setBought(true)
        if (onPurchase) onPurchase()
      }
    } catch {
      setMessage('Purchase failed')
    } finally {
      setBuying(false)
    }
  }

  return (
    <motion.div
      className="shop-card"
      style={{ '--rarity-color': RARITY_COLOR[rarity] }}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
    >
      <div className="sc-rarity" style={{ color: RARITY_COLOR[rarity] }}>{rarity}</div>
      <div className="sc-avatar">{char?.faction === 'villain' ? '💀' : '🦸'}</div>
      <div className="sc-name">{char?.name || 'Unknown'}</div>
      <div className="sc-faction">{char?.faction}</div>

      {char?.skill_name && (
        <div className="sc-skill">✦ {char.skill_name}</div>
      )}

      <div className="sc-stats">
        <span>HP {char?.base_hp}</span>
        <span>ATK {char?.base_atk}</span>
      </div>

      <div className="sc-price">🪙 {item.price}</div>

      {message && <div className="sc-message">{message}</div>}

      <button
        className={`sc-buy-btn ${!canAfford ? 'poor' : ''} ${bought ? 'owned' : ''}`}
        onClick={handleBuy}
        disabled={buying || !canAfford}
      >
        {bought ? '✓ Owned' : buying ? 'Buying…' : canAfford ? 'Purchase' : 'Need more coins'}
      </button>
    </motion.div>
  )
}