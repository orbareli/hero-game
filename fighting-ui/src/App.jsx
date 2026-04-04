import React from 'react'
import BattleArena from './components/BattleArena'
import './App.css'

function App() {
  // For now, we hardcode IDs to match your seed.py data
  // Player 1, using their character (ID 1), fighting Villain (ID 4)
  return (
    <div className="App">
      <BattleArena 
        playerId={1} 
        playerCharId={1} 
        enemyCharId={4} 
      />
    </div>
  )
}

export default App