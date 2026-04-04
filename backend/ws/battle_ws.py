"""
ws/battle_ws.py
---------------
WebSocket endpoint that runs a battle and streams each turn event
to the frontend in real time.

Flow:
  1. Client connects: ws://localhost:8000/ws/battle
  2. Client sends JSON:  { player_id, player_char_id, enemy_char_id }
  3. Server validates, loads data from DB
  4. Server runs battle turn-by-turn, sending each TurnEvent as JSON
  5. Server sends final "result" message with rewards + updated state
  6. Connection closes

Message types sent by server:
  { type: "ready",  message: "..." }
  { type: "event",  turn: N, actor: "...", action: "...", detail: "...",
                    damage: N, heal: N, crit: bool, evaded: bool,
                    p_hp: N, e_hp: N }
  { type: "result", outcome: "win|loss|draw", coins_earned: N,
                    xp_earned: N, player: {...}, player_char: {...} }
  { type: "error",  message: "..." }


import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from db.client import get_db, DBError
from engine.battle import run_battle, make_fighter
from routers.characters import _row_to_character, _row_to_player_character

router = APIRouter()

# How long to pause between streaming each turn event (seconds)
# Gives the frontend time to animate before the next event arrives
TURN_DELAY = 0.6


def _load_battle_data(db, player_id: int, player_char_id: int, enemy_char_id: int):
    ""Load all DB rows needed for a battle. Returns (player, pc, pc_char, enemy_char).""

    player_rows = db.query(f"SELECT * FROM players WHERE id = {player_id}")
    if not player_rows:
        raise ValueError(f"Player {player_id} not found")

    pc_rows = db.query(
        f"SELECT * FROM player_characters "
        f"WHERE id = {player_char_id} AND player_id = {player_id}"
    )
    if not pc_rows:
        raise ValueError("Player character not found in your roster")

    pc = pc_rows[0]

    pc_char_rows = db.query(f"SELECT * FROM characters WHERE id = {pc['char_id']}")
    if not pc_char_rows:
        raise ValueError("Character master data missing")

    enemy_char_rows = db.query(f"SELECT * FROM characters WHERE id = {enemy_char_id}")
    if not enemy_char_rows:
        raise ValueError(f"Enemy character {enemy_char_id} not found")

    return player_rows[0], pc, pc_char_rows[0], enemy_char_rows[0]


def _get_loadout(db, player_char_id: int) -> list[str]:
    ""Fetch the player's saved loadout, or return default.""
    rows = db.query(f"SELECT * FROM loadouts WHERE player_char_id = {player_char_id}")
    if not rows:
        return ["skill", "default"]
    rows.sort(key=lambda r: r["slot"])
    return [r["ability_type"] for r in rows]


def _apply_rewards(db, player_id: int, player_char_id: int, player_char: dict,
                   coins: int, xp: int) -> tuple[dict, dict]:
    ""
    Apply battle rewards to DB:
      - Add coins to player
      - Add XP to player_character, level up if threshold crossed

    Returns (updated_player_row, updated_pc_row).
    ""
    # Update coins
    player_rows = db.query(f"SELECT * FROM players WHERE id = {player_id}")
    player = player_rows[0]
    new_coins = player["coins"] + coins
    db.execute(f"UPDATE players SET coins = {new_coins} WHERE id = {player_id}")

    # Update XP + level
    new_xp    = player_char["xp"] + xp
    new_level = player_char["level"]

    # Simple leveling curve: level up every 100 XP, max level 50
    xp_per_level = 100
    while new_xp >= xp_per_level and new_level < 50:
        new_xp    -= xp_per_level
        new_level += 1

    # On level up, boost stats by 5% (rounded)
    levels_gained = new_level - player_char["level"]
    hp    = player_char["hp"]
    atk   = player_char["atk"]
    def_  = player_char["def"]
    spd   = player_char["spd"]
    crit  = player_char["crit"]
    evade = player_char["evade"]

    if levels_gained > 0:
        mult  = 1.05 ** levels_gained
        hp    = int(hp  * mult)
        atk   = int(atk * mult)
        def_  = int(def_ * mult)
        # SPD, CRIT, EVADE grow slower
        spd   = min(10, spd + levels_gained)
        crit  = min(60, crit + levels_gained)
        evade = min(40, evade + levels_gained)

    db.execute(
        f"UPDATE player_characters SET "
        f"xp = {new_xp}, level = {new_level}, "
        f"hp = {hp}, atk = {atk}, def = {def_}, "
        f"spd = {spd}, crit = {crit}, evade = {evade} "
        f"WHERE id = {player_char_id}"
    )

    # Fetch updated rows
    updated_player = db.query(f"SELECT * FROM players WHERE id = {player_id}")[0]
    updated_pc     = db.query(f"SELECT * FROM player_characters WHERE id = {player_char_id}")[0]

    return updated_player, updated_pc


def _save_battle_record(db, player_id: int, player_char_id: int, enemy_char_id: int,
                        outcome: str, turns: int, log_events: list,
                        coins: int, xp: int):
    ""Persist a battle record to the battles table.""
    # Truncate log to fit TEXT(500)
    log_summary = f"{outcome} in {turns} turns | " + " | ".join(
        e["detail"] for e in log_events[:6]
    )
    log_summary = log_summary[:498]

    db.execute(
        f"INSERT INTO battles "
        f"(player_id, enemy_char_id, player_char_id, outcome, turns, log, coins_earned, xp_earned) "
        f"VALUES ("
        f"{player_id}, {enemy_char_id}, {player_char_id}, "
        f"'{outcome}', {turns}, '{log_summary}', {coins}, {xp})"
    )


@router.websocket("/ws/battle")
async def battle_websocket(websocket: WebSocket):
    await websocket.accept()
    db = get_db()

    try:
        # ── Receive battle request ──────────────────────────────────
        raw = await websocket.receive_text()
        req = json.loads(raw)

        player_id      = int(req["player_id"])
        player_char_id = int(req["player_char_id"])
        enemy_char_id  = int(req["enemy_char_id"])

        # ── Load data from DB ───────────────────────────────────────
        try:
            player_row, pc_row, pc_char_row, enemy_char_row = _load_battle_data(
                db, player_id, player_char_id, enemy_char_id
            )
        except ValueError as e:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
            return

        loadout = _get_loadout(db, player_char_id)

        await websocket.send_text(json.dumps({
            "type":    "ready",
            "message": f"{pc_char_row['name']} vs {enemy_char_row['name']} — FIGHT!",
            "player_char": {
                "name": pc_char_row["name"],
                "hp":   pc_row["hp"],
                "atk":  pc_row["atk"],
                "portrait_id": pc_char_row["portrait_id"],
            },
            "enemy_char": {
                "name": enemy_char_row["name"],
                "hp":   enemy_char_row["base_hp"],
                "atk":  enemy_char_row["base_atk"],
                "portrait_id": enemy_char_row["portrait_id"],
            },
        }))

        # ── Run battle ──────────────────────────────────────────────
        # pc_row uses 'def' as key — pass as-is, battle engine handles it
        result = run_battle(
            player_char=pc_row,
            player_char_master=pc_char_row,
            enemy_char_master=enemy_char_row,
            player_loadout=loadout,
        )

        # ── Stream events ───────────────────────────────────────────
        for event in result.log:
            await websocket.send_text(json.dumps({
                "type":   "event",
                "turn":   event.turn,
                "actor":  event.actor,
                "action": event.action,
                "detail": event.detail,
                "damage": event.damage,
                "heal":   event.heal,
                "crit":   event.crit,
                "evaded": event.evaded,
                "p_hp":   event.p_hp,
                "e_hp":   event.e_hp,
            }))
            await asyncio.sleep(TURN_DELAY)

        # ── Apply rewards ───────────────────────────────────────────
        updated_player, updated_pc = _apply_rewards(
            db, player_id, player_char_id, pc_row,
            result.coins_earned, result.xp_earned
        )

        # Save battle to history
        log_dicts = result.to_dict()["log"]
        _save_battle_record(
            db, player_id, player_char_id, enemy_char_id,
            result.outcome, result.turns, log_dicts,
            result.coins_earned, result.xp_earned
        )

        # Fetch master char for response
        pc_char_rows = db.query(f"SELECT * FROM characters WHERE id = {updated_pc['char_id']}")
        pc_char      = pc_char_rows[0] if pc_char_rows else pc_char_row

        # ── Send final result ───────────────────────────────────────
        await websocket.send_text(json.dumps({
            "type":    "result",
            "outcome": result.outcome,
            "turns":   result.turns,
            "coins_earned": result.coins_earned,
            "xp_earned":    result.xp_earned,
            "player": {
                "id":       updated_player["id"],
                "username": updated_player["username"],
                "coins":    updated_player["coins"],
                "gems":     updated_player["gems"],
            },
            "player_char": {
                "id":       updated_pc["id"],
                "level":    updated_pc["level"],
                "xp":       updated_pc["xp"],
                "hp":       updated_pc["hp"],
                "atk":      updated_pc["atk"],
                "defense":  updated_pc["def"],
                "spd":      updated_pc["spd"],
                "crit":     updated_pc["crit"],
                "evade":    updated_pc["evade"],
                "character": {
                    "name":       pc_char["name"],
                    "portrait_id": pc_char["portrait_id"],
                },
            },
        }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type":    "error",
                "message": f"Server error: {str(e)}",
            }))
        except Exception:
            pass
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from bson import ObjectId
from db.mongo import db  # Your motor manager
from engine.battle import run_battle

router = APIRouter()

TURN_DELAY = 0.6

# ------------------------------------------------------------------ #
#  Data Loading Helpers                                              #
# ------------------------------------------------------------------ #

async def _load_battle_data(player_id: str, player_char_id: str, enemy_char_id: str):
    p_id = ObjectId(player_id)
    pc_id = ObjectId(player_char_id)
    e_id = ObjectId(enemy_char_id)

    player = await db.db.players.find_one({"_id": p_id})
    if not player: raise ValueError("Player not found")

    pc = await db.db.player_characters.find_one({"_id": pc_id, "player_id": p_id})
    if not pc: raise ValueError("Character not found in roster")

    pc_char = await db.db.characters.find_one({"_id": pc["char_id"]})
    enemy_char = await db.db.characters.find_one({"_id": e_id})
    
    if not pc_char or not enemy_char: raise ValueError("Character data missing")

    return player, pc, pc_char, enemy_char

async def _get_loadout(player_char_id: str) -> list[str]:
    cursor = db.db.loadouts.find({"player_char_id": ObjectId(player_char_id)})
    rows = await cursor.to_list(length=10)
    if not rows: return ["skill", "default"]
    rows.sort(key=lambda r: r["slot"])
    return [r["ability_type"] for r in rows]

# ------------------------------------------------------------------ #
#  Reward & History Logic                                            #
# ------------------------------------------------------------------ #

async def _apply_rewards(player_id: str, player_char_id: str, pc_row: dict, coins: int, xp: int):
    p_id = ObjectId(player_id)
    pc_id = ObjectId(player_char_id)

    # 1. Update Player Coins
    await db.db.players.update_one({"_id": p_id}, {"$inc": {"coins": coins}})

    # 2. Calculate Level Up Logic
    new_xp = pc_row["xp"] + xp
    new_level = pc_row["level"]
    xp_per_level = 100

    while new_xp >= xp_per_level and new_level < 50:
        new_xp -= xp_per_level
        new_level += 1

    # 3. Stat Growth
    levels_gained = new_level - pc_row["level"]
    updates = {"xp": new_xp, "level": new_level}

    if levels_gained > 0:
        mult = 1.05 ** levels_gained
        updates.update({
            "hp": int(pc_row["hp"] * mult),
            "atk": int(pc_row["atk"] * mult),
            "def": int(pc_row["def"] * mult),
            "spd": min(10, pc_row["spd"] + levels_gained),
            "crit": min(60, pc_row["crit"] + levels_gained),
            "evade": min(40, pc_row["evade"] + levels_gained)
        })

    await db.db.player_characters.update_one({"_id": pc_id}, {"$set": updates})
    
    # Return fresh copies
    up = await db.db.players.find_one({"_id": p_id})
    uc = await db.db.player_characters.find_one({"_id": pc_id})
    return up, uc

# ------------------------------------------------------------------ #
#  WebSocket Router                                                  #
# ------------------------------------------------------------------ #

@router.websocket("/ws/battle")
async def battle_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        raw = await websocket.receive_text()
        req = json.loads(raw)

        # Load data (Async)
        p_row, pc_row, pcm_row, ecm_row = await _load_battle_data(
            req["player_id"], req["player_char_id"], req["enemy_char_id"]
        )
        loadout = await _get_loadout(req["player_char_id"])

        await websocket.send_json({
            "type": "ready",
            "message": f"{pcm_row['name']} vs {ecm_row['name']} — FIGHT!",
            "player_char": {"name": pcm_row["name"], "hp": pc_row["hp"]},
            "enemy_char": {"name": ecm_row["name"], "hp": ecm_row["base_hp"]}
        })

        # Run Battle Engine
        result = run_battle(
            player_char=pc_row,
            player_char_master=pcm_row,
            enemy_char_master=ecm_row,
            player_loadout=loadout,
        )

        # Stream turns
        for event in result.log:
            await websocket.send_json({"type": "event", **event.__dict__})
            await asyncio.sleep(TURN_DELAY)

        # Finalize
        up, uc = await _apply_rewards(
            req["player_id"], req["player_char_id"], pc_row,
            result.coins_earned, result.xp_earned
        )

        await websocket.send_json({
            "type": "result",
            "outcome": result.outcome,
            "coins_earned": result.coins_earned,
            "xp_earned": result.xp_earned,
            "player": {
                "id": str(up["_id"]),
                "coins": up["coins"]
            },
            "player_char": {
                "id": str(uc["_id"]),
                "level": uc["level"],
                "xp": uc["xp"],
                "hp": uc["hp"]
            }
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})