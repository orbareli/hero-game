"""
ws/battle_ws.py
---------------
WebSocket endpoint — streams a real-time battle to the frontend.

Flow:
  1. Client connects  →  ws://localhost:8000/ws/battle
  2. Client sends     →  { player_id, player_char_id, enemy_char_id }
  3. Server sends     →  { type:"ready", player_char:{name,hp,max_hp}, enemy_char:{…} }
  4. Server streams   →  { type:"event", turn, actor, action, detail,
                                         damage, heal, crit, evaded, p_hp, e_hp }
  5. Server sends     →  { type:"result", outcome, coins_earned, xp_earned,
                                          player:{id,coins}, player_char:{id,level,xp,hp} }
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from bson import ObjectId

from db.mongo import db          # MongoManager singleton — db.players, db.characters, …
from engine.battle import run_battle

router = APIRouter()

TURN_DELAY = 0.9   # seconds between streamed events


# ------------------------------------------------------------------ #
#  Helpers                                                           #
# ------------------------------------------------------------------ #

async def _load_battle_data(player_id: str, player_char_id: str, enemy_char_id: str):
    """
    Load all documents needed to start a battle.
    Returns (player, pc, pc_master_char, enemy_master_char).
    Raises ValueError with a human-readable message on any problem.
    """
    p_id  = ObjectId(player_id)
    pc_id = ObjectId(player_char_id)
    e_id  = ObjectId(enemy_char_id)

    player = await db.players.find_one({"_id": p_id})
    if not player:
        raise ValueError("Player not found")

    pc = await db.player_characters.find_one({"_id": pc_id, "player_id": p_id})
    if not pc:
        raise ValueError("Character not found in your roster")

    pc_char    = await db.characters.find_one({"_id": pc["char_id"]})
    enemy_char = await db.characters.find_one({"_id": e_id})

    if not pc_char:
        raise ValueError("Master character data missing for player's hero")
    if not enemy_char:
        raise ValueError(f"Enemy character {enemy_char_id} not found")

    return player, pc, pc_char, enemy_char


async def _get_loadout(player_char_id: str) -> list[str]:
    """Return saved loadout slots, defaulting to ['skill', 'default']."""
    cursor = db.loadouts.find({"player_char_id": ObjectId(player_char_id)})
    rows   = await cursor.to_list(length=10)
    if not rows:
        return ["skill", "default"]
    rows.sort(key=lambda r: r["slot"])
    return [r["ability_type"] for r in rows]


async def _apply_rewards(
    player_id: str,
    player_char_id: str,
    pc_row: dict,
    coins: int,
    xp: int,
) -> tuple[dict, dict]:
    """
    Persist battle rewards:
      - Increment player coins
      - Add XP to player_character, level up if threshold crossed (100 XP / level, max 50)
    Returns (updated_player, updated_pc).
    """
    p_id  = ObjectId(player_id)
    pc_id = ObjectId(player_char_id)

    # Coins
    await db.players.update_one({"_id": p_id}, {"$inc": {"coins": coins}})

    # XP + leveling
    new_xp    = pc_row.get("xp", 0) + xp
    new_level = pc_row.get("level", 1)
    xp_per_level = 100

    while new_xp >= xp_per_level and new_level < 50:
        new_xp    -= xp_per_level
        new_level += 1

    levels_gained = new_level - pc_row.get("level", 1)
    stat_updates  = {"xp": new_xp, "level": new_level}

    if levels_gained > 0:
        mult = 1.05 ** levels_gained
        stat_updates.update({
            "hp":    int(pc_row.get("hp",    0) * mult),
            "atk":   int(pc_row.get("atk",   0) * mult),
            "def":   int(pc_row.get("def",   0) * mult),
            "spd":   min(10, pc_row.get("spd",   1) + levels_gained),
            "crit":  min(60, pc_row.get("crit",   0) + levels_gained),
            "evade": min(40, pc_row.get("evade",  0) + levels_gained),
        })

    await db.player_characters.update_one({"_id": pc_id}, {"$set": stat_updates})

    updated_player = await db.players.find_one({"_id": p_id})
    updated_pc     = await db.player_characters.find_one({"_id": pc_id})
    return updated_player, updated_pc


def _event_to_dict(event) -> dict:
    """Convert a TurnEvent dataclass to a plain JSON-serializable dict."""
    return {
        "type":   "event",
        "turn":   event.turn,
        "actor":  event.actor,
        "action": event.action,
        "detail": event.detail,
        "damage": event.damage,
        "heal":   event.heal,
        "crit":   bool(event.crit),
        "evaded": bool(event.evaded),
        "p_hp":   event.p_hp,
        "e_hp":   event.e_hp,
    }


# ------------------------------------------------------------------ #
#  WebSocket Endpoint                                                #
# ------------------------------------------------------------------ #

@router.websocket("/ws/battle")
async def battle_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        # ── 1. Parse incoming request ───────────────────────────────
        raw = await websocket.receive_text()
        req = json.loads(raw)

        player_id      = req["player_id"]
        player_char_id = req["player_char_id"]
        enemy_char_id  = req["enemy_char_id"]

        # ── 2. Load data from MongoDB ───────────────────────────────
        try:
            player, pc, pc_char, enemy_char = await _load_battle_data(
                player_id, player_char_id, enemy_char_id
            )
        except ValueError as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            return

        loadout = await _get_loadout(player_char_id)

        # ── 3. Send "ready" with max_hp so the UI can init HP bars ──
        await websocket.send_json({
            "type":    "ready",
            "message": f"{pc_char['name']} vs {enemy_char['name']} — FIGHT!",
            "player_char": {
                "name":       pc_char["name"],
                "hp":         pc["hp"],
                "max_hp":     pc["hp"],        # current stats = max at battle start
                "portrait_id": pc_char.get("portrait_id", ""),
            },
            "enemy_char": {
                "name":       enemy_char["name"],
                "hp":         enemy_char["base_hp"],
                "max_hp":     enemy_char["base_hp"],
                "portrait_id": enemy_char.get("portrait_id", ""),
            },
        })

        # ── 4. Run the battle engine (pure Python, no DB calls) ─────
        # Normalize the MongoDB doc for the engine:
        #   - engine reads pc["id"]  but Mongo stores "_id"
        #   - engine reads pc["def"] which Mongo stores as "def" (fine)
        #   - master char fields use "base_*" keys (no change needed)
        pc_for_engine = dict(pc)
        pc_for_engine["id"] = str(pc_for_engine["_id"])

        pc_char_for_engine = dict(pc_char)
        pc_char_for_engine["id"] = str(pc_char_for_engine["_id"])

        enemy_char_for_engine = dict(enemy_char)
        enemy_char_for_engine["id"] = str(enemy_char_for_engine["_id"])

        result = run_battle(
            player_char=pc_for_engine,
            player_char_master=pc_char_for_engine,
            enemy_char_master=enemy_char_for_engine,
            player_loadout=loadout,
        )

        # ── 5. Stream each turn event with a delay ──────────────────
        for event in result.log:
            ev_dict = _event_to_dict(event)
                # הדפסה לטרמינל כדי לראות אם השרת משתגע
            print(f"TURN {ev_dict['turn']} | Action: {ev_dict['action']} | P_HP: {ev_dict['p_hp']} | E_HP: {ev_dict['e_hp']}")
                
            await websocket.send_json(ev_dict)
            await asyncio.sleep(TURN_DELAY)

        # ── 6. Apply rewards and fetch updated documents ─────────────
        updated_player, updated_pc = await _apply_rewards(
            player_id, player_char_id, pc,
            result.coins_earned, result.xp_earned,
        )

        # ── 7. Send final result ────────────────────────────────────
        await websocket.send_json({
            "type":         "result",
            "outcome":      result.outcome,
            "turns":        result.turns,
            "coins_earned": result.coins_earned,
            "xp_earned":    result.xp_earned,
            "player": {
                "id":    str(updated_player["_id"]),
                "coins": updated_player["coins"],
                "gems":  updated_player.get("gems", 0),
            },
            "player_char": {
                "id":    str(updated_pc["_id"]),
                "level": updated_pc["level"],
                "xp":    updated_pc["xp"],
                "hp":    updated_pc["hp"],
                "atk":   updated_pc["atk"],
            },
        })

    except WebSocketDisconnect:
        pass   # client navigated away — nothing to do
    except Exception as exc:
        # Attempt to notify the client before the socket dies
        try:
            await websocket.send_json({
                "type":    "error",
                "message": f"Server error: {exc}",
            })
        except Exception:
            pass