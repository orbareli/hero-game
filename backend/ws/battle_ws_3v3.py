"""
ws/battle_ws_3v3.py
-------------------
Interactive 3v3 WebSocket battle endpoint.

URL: ws://localhost:8000/ws/battle3

Protocol:
  Client → { type:"start",  player_team:[pc_id, pc_id, pc_id], enemy_team:[char_id, char_id, char_id] }
  Server → { type:"state",  state:{...} }           # full battle state
  Server → { type:"input_required", actor:{...}, valid_targets:[...], can_use_skill:bool }
  Client → { type:"action", action:"skill"|"attack", target_index:0|1|2 }
  Server → { type:"events", events:[...] }           # what just happened
  Server → { type:"state",  state:{...} }            # updated state
  Server → { type:"battle_end", outcome:"win"|"loss"|"draw", rewards:{...} }
  Server → { type:"error",  message:"..." }
"""

import asyncio
import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from bson import ObjectId

from db.mongo import db
from engine.battle_state import BattleState, BattleFighter, ENERGY_SKILL_COST
from engine.skill_definitions import get_skills_for
from engine.turn_engine   import resolve_action, ai_choose_action

router = APIRouter()

# Delay between AI actions so the frontend can animate them
AI_ACTION_DELAY = 1.2


# ── Fighter builder ───────────────────────────────────────────────────────────

def _build_player_fighter(pc: dict, char: dict) -> BattleFighter:
    skills = get_skills_for(
        char_name=char["name"],
        rarity=char.get("rarity", "C"),
        primary_name=char["skill_name"],
        primary_desc=char["skill_desc"],
        primary_mult=char["skill_mult"],
    )
    return BattleFighter(
        pc_id       = str(pc["_id"]),
        char_id     = str(char["_id"]),
        name        = char["name"],
        faction     = char["faction"],
        element     = char.get("element", "Power"),
        rarity      = char.get("rarity", "C"),
        portrait_id = char.get("portrait_id", ""),
        is_player   = True,
        hp          = pc["hp"],
        max_hp      = pc["hp"],
        atk         = pc["atk"],
        defense     = pc["def"],
        spd         = pc["spd"],
        crit        = pc["crit"],
        evade       = pc["evade"],
        energy      = pc.get("energy", 0),
        skills      = skills,
        skill_name  = skills[0].name if skills else char["skill_name"],
        skill_desc  = skills[0].desc if skills else char["skill_desc"],
        skill_mult  = skills[0].mult if skills else char["skill_mult"],
        passive_name= char["passive_name"],
    )


def _build_enemy_fighter(char: dict) -> BattleFighter:
    skills = get_skills_for(
        char_name=char["name"],
        rarity=char.get("rarity", "R"),
        primary_name=char["skill_name"],
        primary_desc=char["skill_desc"],
        primary_mult=char["skill_mult"],
    )
    return BattleFighter(
        pc_id       = "",
        char_id     = str(char["_id"]),
        name        = char["name"],
        faction     = char["faction"],
        element     = char.get("element", "Speed"),
        rarity      = char.get("rarity", "R"),
        portrait_id = char.get("portrait_id", ""),
        is_player   = False,
        hp          = char["base_hp"],
        max_hp      = char["base_hp"],
        atk         = char["base_atk"],
        defense     = char["base_def"],
        spd         = char["base_spd"],
        crit        = char["base_crit"],
        evade       = char["base_evade"],
        energy      = 0,
        skills      = skills,
        skill_name  = skills[0].name if skills else char["skill_name"],
        skill_desc  = skills[0].desc if skills else char["skill_desc"],
        skill_mult  = skills[0].mult if skills else char["skill_mult"],
        passive_name= char["passive_name"],
    )


# ── Reward calculation ────────────────────────────────────────────────────────

async def _apply_rewards(
    player_id: str,
    player_team_docs: list[dict],  # original pc docs
    outcome: str,
    rounds: int,
) -> dict:
    """Apply XP and coins based on outcome. Returns reward summary."""
    import random

    base_coins = {"win": random.randint(60, 120), "loss": random.randint(10, 25), "draw": random.randint(20, 40)}
    base_xp    = {"win": random.randint(40, 80),  "loss": random.randint(8,  20), "draw": random.randint(15, 35)}
    coins = base_coins.get(outcome, 10)
    xp    = base_xp.get(outcome, 5)

    await db.players.update_one({"_id": ObjectId(player_id)}, {"$inc": {"coins": coins}})

    # Apply XP to each player character
    for pc in player_team_docs:
        new_xp    = pc.get("xp", 0) + xp
        new_level = pc.get("level", 1)
        while new_xp >= 100 and new_level < 50:
            new_xp    -= 100
            new_level += 1
        levels_gained = new_level - pc.get("level", 1)
        updates = {"xp": new_xp, "level": new_level}
        if levels_gained > 0:
            mult = 1.05 ** levels_gained
            updates.update({
                "hp": int(pc["hp"] * mult), "atk": int(pc["atk"] * mult),
                "def": int(pc["def"] * mult),
                "spd": min(10, pc["spd"] + levels_gained),
                "crit": min(60, pc["crit"] + levels_gained),
                "evade": min(40, pc["evade"] + levels_gained),
            })
        await db.player_characters.update_one({"_id": pc["_id"]}, {"$set": updates})

    return {"coins": coins, "xp": xp, "outcome": outcome}


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/battle3")
async def battle_3v3(websocket: WebSocket):
    await websocket.accept()

    try:
        # ── 1. Wait for "start" message ───────────────────────────────────────
        raw = await websocket.receive_text()
        req = json.loads(raw)

        if req.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected {type:'start'}"})
            return

        player_id       = req["player_id"]
        pc_ids          = req["player_team"]   # list of 1–3 player_character id strings
        enemy_char_ids  = req["enemy_team"]    # list of 1–3 character id strings

        # ── 2. Load player team from DB ───────────────────────────────────────
        p_oid = ObjectId(player_id)
        player_fighters: list[BattleFighter] = []
        player_pc_docs:  list[dict]          = []

        for pc_id in pc_ids[:3]:
            pc = await db.player_characters.find_one({
                "_id": ObjectId(pc_id), "player_id": p_oid
            })
            if not pc:
                await websocket.send_json({"type": "error", "message": f"Character {pc_id} not in roster"})
                return
            char = await db.characters.find_one({"_id": pc["char_id"]})
            if not char:
                await websocket.send_json({"type": "error", "message": "Master character data missing"})
                return
            player_fighters.append(_build_player_fighter(pc, char))
            player_pc_docs.append(pc)

        # ── 3. Load enemy team ────────────────────────────────────────────────
        enemy_fighters: list[BattleFighter] = []

        for char_id in enemy_char_ids[:3]:
            char = await db.characters.find_one({"_id": ObjectId(char_id)})
            if not char:
                await websocket.send_json({"type": "error", "message": f"Enemy {char_id} not found"})
                return
            enemy_fighters.append(_build_enemy_fighter(char))

        # ── 4. Build initial state ────────────────────────────────────────────
        state = BattleState(
            battle_id    = str(uuid.uuid4()),
            round        = 1,
            phase        = "player_input",
            player_team  = player_fighters,
            enemy_team   = enemy_fighters,
        )
        state.rebuild_turn_queue()

        await websocket.send_json({"type": "state", "state": state.to_dict()})

        # ── 5. Main battle loop ───────────────────────────────────────────────
        while not state.is_over():
            current = state.current_fighter()

            # Turn queue exhausted → start new round
            if current is None:
                state.round += 1
                state.rebuild_turn_queue()
                await websocket.send_json({
                    "type":  "round_start",
                    "round": state.round,
                    "state": state.to_dict(),
                })
                if state.is_over():
                    break
                continue

            actor_team, actor_idx = current
            actor = (state.player_team if actor_team == "player" else state.enemy_team)[actor_idx]

            if not actor.is_alive:
                state.advance_queue()
                continue

            # ── Player's turn ─────────────────────────────────────────────────
            if actor_team == "player":
                # Compute valid targets for each skill
                enemy_targets = [
                    {"index": i, "name": f.name, "hp": f.hp, "max_hp": f.max_hp,
                     "element": f.element, "rarity": f.rarity}
                    for i, f in enumerate(state.enemy_team) if f.is_alive
                ]
                ally_targets = [
                    {"index": i, "name": f.name, "hp": f.hp, "max_hp": f.max_hp,
                     "element": f.element, "rarity": f.rarity}
                    for i, f in enumerate(state.player_team) if f.is_alive
                ]

                await websocket.send_json({
                    "type":          "input_required",
                    "actor":         actor.to_dict(),
                    "actor_team":    "player",
                    "actor_index":   actor_idx,
                    "enemy_targets": enemy_targets,
                    "ally_targets":  ally_targets,
                    "skills":        actor.skills_for_client(),
                    "energy":        actor.energy,
                })

                # Wait for player's action
                try:
                    raw_action = await asyncio.wait_for(
                        websocket.receive_text(), timeout=120.0
                    )
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "error", "message": "Timed out waiting for action"})
                    return

                action_req  = json.loads(raw_action)
                action_type = action_req.get("action", "attack")
                target_idx  = int(action_req.get("target_index", 0))
                skill_index = int(action_req.get("skill_index", 0))

            # ── Enemy's turn (AI) ─────────────────────────────────────────────
            else:
                await asyncio.sleep(AI_ACTION_DELAY)
                action_type, target_idx = ai_choose_action(actor, state.player_team)
                await websocket.send_json({
                    "type":        "enemy_acting",
                    "actor":       actor.to_dict(),
                    "actor_index": actor_idx,
                    "action":      action_type,
                    "target_index": target_idx,
                })

            # ── Resolve action ────────────────────────────────────────────────
            _skill_idx = skill_index if actor_team == "player" else 0
            state, events = resolve_action(
                state, actor_team, actor_idx, action_type, target_idx, _skill_idx
            )

            # Send events + updated state
            await websocket.send_json({"type": "events",  "events": events})
            await websocket.send_json({"type": "state",   "state":  state.to_dict()})

            if state.is_over():
                break

        # ── 6. Battle over ────────────────────────────────────────────────────
        rewards = await _apply_rewards(
            player_id, player_pc_docs, state.outcome, state.round
        )

        await websocket.send_json({
            "type":    "battle_end",
            "outcome": state.outcome,
            "rounds":  state.round,
            "rewards": rewards,
            "state":   state.to_dict(),
        })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass