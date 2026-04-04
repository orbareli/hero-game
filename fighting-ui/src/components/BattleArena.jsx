import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const BattleArena = ({ playerId, playerCharId, enemyCharId }) => {
  const [log, setLog] = useState([]);
  const [battleResult, setBattleResult] = useState(null);
  const [fighterStats, setFighterStats] = useState({ p_hp: 100, p_max: 100, e_hp: 100, e_max: 100 });
  const [isFighting, setIsFighting] = useState(false);
  const scrollRef = useRef(null);

  const startBattle = () => {
    setLog([]);
    setBattleResult(null);
    setIsFighting(true);

    const ws = new WebSocket(`ws://localhost:8000/ws/battle`);

    ws.onopen = () => {
      ws.send(JSON.stringify({
        player_id: playerId,
        player_char_id: playerCharId,
        enemy_char_id: enemyCharId
      }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'ready') {
        // Initialize HP bars if max_hp is provided in a 'ready' or first event
      } else if (data.type === 'event') {
        setLog(prev => [...prev, data]);
        setFighterStats({
          p_hp: data.p_hp,
          e_hp: data.e_hp,
          // Assuming we store max_hp elsewhere or first event provides it
          p_max: fighterStats.p_max || data.p_hp, 
          e_max: fighterStats.e_max || data.e_hp
        });
      } else if (data.type === 'result') {
        setBattleResult(data);
        setIsFighting(false);
        ws.close();
      }
    };
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [log]);

  return (
    <div className="flex flex-col items-center p-6 bg-slate-900 min-h-screen text-white">
      <h2 className="text-3xl font-bold mb-8 text-blue-400">Combat Simulator</h2>

      {/* Battlefield */}
      <div className="flex justify-between w-full max-w-4xl mb-10">
        <FighterDisplay name="Player Hero" hp={fighterStats.p_hp} maxHp={fighterStats.p_max} side="left" />
        <div className="flex items-center text-4xl font-black text-red-600">VS</div>
        <FighterDisplay name="Villain" hp={fighterStats.e_hp} maxHp={fighterStats.e_max} side="right" />
      </div>

      {/* Battle Feed */}
      <div className="w-full max-w-2xl bg-slate-800 rounded-lg p-4 h-64 overflow-y-auto border border-slate-700" ref={scrollRef}>
        <AnimatePresence>
          {log.map((entry, i) => (
            <motion.div 
              key={i} 
              initial={{ opacity: 0, x: -10 }} 
              animate={{ opacity: 1, x: 0 }}
              className={`mb-2 p-2 rounded ${entry.actor === 'player' ? 'bg-blue-900/30 border-l-4 border-blue-500' : 'bg-red-900/30 border-r-4 border-red-500 text-right'}`}
            >
              <span className="font-bold">{entry.actor}:</span> {entry.detail}
              {entry.damage > 0 && <span className="text-red-400 font-bold ml-2">-{entry.damage}</span>}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <button 
        onClick={startBattle} 
        disabled={isFighting}
        className="mt-8 px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 rounded-full font-bold transition-all"
      >
        {isFighting ? "Simulating..." : "Initiate Battle"}
      </button>

      {battleResult && (
        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="mt-6 p-4 bg-yellow-600 rounded-lg text-center">
          <h3 className="text-2xl font-bold uppercase">{battleResult.outcome}!</h3>
          <p>Earned: {battleResult.coins_earned} Coins | {battleResult.xp_earned} XP</p>
        </motion.div>
      )}
    </div>
  );
};

const FighterDisplay = ({ name, hp, maxHp, side }) => {
  const percentage = Math.max(0, (hp / maxHp) * 100);
  return (
    <div className={`flex flex-col ${side === 'right' ? 'items-end' : 'items-start'} w-1/3`}>
      <div className="text-xl font-bold mb-2">{name}</div>
      <div className="w-full bg-slate-700 h-6 rounded-full overflow-hidden border-2 border-slate-600">
        <motion.div 
          animate={{ width: `${percentage}%` }}
          className={`h-full ${percentage > 50 ? 'bg-green-500' : percentage > 20 ? 'bg-yellow-500' : 'bg-red-500'}`}
        />
      </div>
      <div className="mt-1 text-sm text-slate-400">{hp} / {maxHp} HP</div>
    </div>
  );
};

export default BattleArena;