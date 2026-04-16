"""
routers/tower.py
----------------
REST API for the Tower of Trials / Campaign mode.

Endpoints:
  POST /tower/start                     — start a new run, pick 3 fighters
  GET  /tower/{session_id}              — get current session state
  GET  /tower/{session_id}/floor        — get floor details + generated enemies
  POST /tower/{session_id}/complete     — record battle result, advance floor
  GET  /tower/{session_id}/buffs        — get 3 random buff choices
  POST /tower/{session_id}/apply-buff   — apply chosen buff
  POST /tower/{session_id}/revive       — use revive node
  GET  /tower/player/{player_id}/active — get player's active run (if any)
  POST /tower/{session_id}/abandon      — abandon the current run

State machine:
  new → active → (per floor: fighting → buff_choice | revive | next_floor) → completed | failed
"""

import uuid
import random
from datetime import datetime
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pydantic import BaseModel

from db.mongo import db
from engine.tower_generator import (
    get_floor_type, is_buff_floor, generate_enemy_team,
    get_random_buffs, apply_buff_to_fighter, BUFF_POOL, TowerBuff,
)

router = APIRouter(prefix="/tower", tags=["Tower"])

TOTAL_FLOORS = 30


# ── Pydantic request schemas ──────────────────────────────────────────────────

class StartRunRequest(BaseModel):
    player_id: str
    pc_ids:    list[str]   # exactly 3 player_character IDs


class CompleteFloorRequest(BaseModel):
    outcome:      str             # "win" | "loss"
    team_state:   list[dict]      # updated HP/energy for each fighter after battle


class ApplyBuffRequest(BaseModel):
    buff_id: str


class ReviveRequest(BaseModel):
    target_pc_id: str   # which dead fighter to revive


# ── Helpers ───────────────────────────────────────────────────────────────────

def _oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid ID: {s}")


async def _get_session(session_id: str) -> dict:
    doc = await db.tower_sessions.find_one({"_id": _oid(session_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Tower session not found")
    return doc


async def _get_active_session(player_id: str) -> dict | None:
    return await db.tower_sessions.find_one({
        "player_id": _oid(player_id),
        "status": "active",
    })


def _build_team_member(pc: dict, char: dict) -> dict:
    """
    Build the persistent team-member dict stored in TowerSession.
    Carries current HP, energy, and stat overrides across floors.
    """
    return {
        "pc_id":             str(pc["_id"]),
        "char_id":           str(char["_id"]),
        "name":              char["name"],
        "portrait_id":       char.get("portrait_id", ""),
        "rarity":            char.get("rarity", "C"),
        "element":           char.get("element", "Power"),
        "faction":           char.get("faction", "hero"),
        # Max stats (base, never decremented except by permanent buffs)
        "max_hp":            pc["hp"],
        "max_atk":           pc["atk"],
        "base_def":          pc["def"],
        "base_spd":          pc["spd"],
        "base_crit":         pc["crit"],
        "base_evade":        pc["evade"],
        # Current state — these persist across floors
        "current_hp":        pc["hp"],   # starts full
        "current_atk":       pc["atk"],
        "current_def":       pc["def"],
        "current_spd":       pc["spd"],
        "current_crit":      pc["crit"],
        "current_evade":     pc["evade"],
        "current_energy":    0,          # starts at 0; buff can change battle_start_energy
        "battle_start_energy": 0,        # floor-start energy (increased by buffs)
        "is_alive":          True,
        # For display
        "skill_name":        char["skill_name"],
        "passive_name":      char["passive_name"],
    }


def _serialise_session(doc: dict) -> dict:
    """Convert ObjectIds to strings for JSON response."""
    doc["id"]        = str(doc.pop("_id"))
    doc["player_id"] = str(doc["player_id"])
    return doc


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_run(req: StartRunRequest):
    """
    Begin a new Tower run. Player selects exactly 3 of their characters.
    Any existing active run is abandoned first.
    """
    p_oid = _oid(req.player_id)

    # Abandon any active run
    await db.tower_sessions.update_many(
        {"player_id": p_oid, "status": "active"},
        {"$set": {"status": "abandoned", "updated_at": datetime.utcnow()}},
    )

    if len(req.pc_ids) < 1 or len(req.pc_ids) > 3:
        raise HTTPException(status_code=400, detail="Select 1–3 fighters")

    # Load each player character + master data
    team = []
    for pc_id in req.pc_ids[:3]:
        pc = await db.player_characters.find_one({"_id": _oid(pc_id), "player_id": p_oid})
        if not pc:
            raise HTTPException(status_code=404, detail=f"Character {pc_id} not in roster")
        char = await db.characters.find_one({"_id": pc["char_id"]})
        if not char:
            raise HTTPException(status_code=500, detail="Master character data missing")
        team.append(_build_team_member(pc, char))

    # Create session document
    session = {
        "player_id":     p_oid,
        "status":        "active",         # active | failed | completed | abandoned
        "current_floor": 1,
        "team":          team,
        "active_buffs":  [],
        "floor_history": [],               # [{floor, outcome, timestamp}]
        "pending_buff":  False,            # True = player must pick a buff before advancing
        "created_at":    datetime.utcnow(),
        "updated_at":    datetime.utcnow(),
    }

    result = await db.tower_sessions.insert_one(session)
    session["_id"] = result.inserted_id
    return _serialise_session(session)


@router.get("/player/{player_id}/active")
async def get_active_run(player_id: str):
    """Return the player's active tower session, or null if none exists."""
    doc = await _get_active_session(player_id)
    if not doc:
        return {"session": None}
    return {"session": _serialise_session(doc)}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Full session state."""
    doc = await _get_session(session_id)
    return _serialise_session(doc)


@router.get("/{session_id}/floor")
async def get_floor_details(session_id: str):
    """
    Return details for the current floor:
      - floor_type (battle | boss | revive)
      - generated enemy team (scaled)
      - whether a buff is pending
    """
    session    = await _get_session(session_id)
    floor      = session["current_floor"]
    floor_type = get_floor_type(floor)

    # If revive or buff pending, return without generating enemies
    if floor_type == "revive":
        return {
            "floor":      floor,
            "floor_type": "revive",
            "enemies":    [],
            "is_boss":    False,
        }

    # Load master characters to generate enemies
    all_chars = await db.characters.find({}).to_list(length=100)
    enemies   = await generate_enemy_team(floor, all_chars)

    # Convert ObjectIds in enemy docs to strings
    for e in enemies:
        if "_id" in e:
            e["id"] = str(e.pop("_id"))

    return {
        "floor":      floor,
        "floor_type": floor_type,
        "is_boss":    floor_type == "boss",
        "enemies":    enemies,   # scaled char docs, used by battle_ws_3v3 to build fighters
        "team_state": session["team"],  # current persistent HP/energy
    }


@router.post("/{session_id}/complete")
async def complete_floor(session_id: str, req: CompleteFloorRequest):
    """
    Called by the frontend after a battle ends.
    - Saves updated HP/energy for each fighter (persistent)
    - Records outcome in history
    - Checks for buff or revive nodes
    - Advances the floor counter
    - Checks win/loss conditions
    """
    session = await _get_session(session_id)

    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    floor = session["current_floor"]

    # ── 1. Update persistent team state ──────────────────────────────────────
    # req.team_state comes from the WebSocket battle result, one dict per fighter
    updated_team = session["team"]
    state_by_pc  = {m["pc_id"]: m for m in req.team_state}

    for member in updated_team:
        if member["pc_id"] in state_by_pc:
            bs = state_by_pc[member["pc_id"]]
            member["current_hp"]     = max(0, bs.get("hp", member["current_hp"]))
            member["current_energy"] = bs.get("energy", 0)
            member["is_alive"]       = member["current_hp"] > 0

    # ── 2. Record floor outcome ───────────────────────────────────────────────
    session["floor_history"].append({
        "floor":     floor,
        "outcome":   req.outcome,
        "timestamp": datetime.utcnow().isoformat(),
    })

    # ── 3. Check loss condition ───────────────────────────────────────────────
    if req.outcome == "loss" or not any(m["is_alive"] for m in updated_team):
        await db.tower_sessions.update_one(
            {"_id": _oid(session_id)},
            {"$set": {
                "status":        "failed",
                "team":          updated_team,
                "floor_history": session["floor_history"],
                "updated_at":    datetime.utcnow(),
            }},
        )
        return {"status": "failed", "floor": floor, "team": updated_team}

    # ── 4. Check win condition ────────────────────────────────────────────────
    if floor >= TOTAL_FLOORS:
        await db.tower_sessions.update_one(
            {"_id": _oid(session_id)},
            {"$set": {
                "status":        "completed",
                "team":          updated_team,
                "floor_history": session["floor_history"],
                "updated_at":    datetime.utcnow(),
            }},
        )
        # Grant completion reward
        await db.players.update_one(
            {"_id": session["player_id"]},
            {"$inc": {"coins": 500, "gems": 5}},
        )
        return {"status": "completed", "floor": floor, "reward": {"coins": 500, "gems": 5}}

    # ── 5. Advance floor ──────────────────────────────────────────────────────
    next_floor     = floor + 1
    next_type      = get_floor_type(next_floor)
    buff_offered   = is_buff_floor(floor)   # buff after clearing this floor

    updates = {
        "current_floor": next_floor,
        "team":          updated_team,
        "floor_history": session["floor_history"],
        "pending_buff":  buff_offered,
        "updated_at":    datetime.utcnow(),
    }

    await db.tower_sessions.update_one({"_id": _oid(session_id)}, {"$set": updates})

    return {
        "status":       "active",
        "floor":        floor,
        "next_floor":   next_floor,
        "next_type":    next_type,
        "buff_offered": buff_offered,
        "team":         updated_team,
    }


@router.get("/{session_id}/buffs")
async def get_buff_choices(session_id: str):
    """Return 3 random buff options for the player to choose from."""
    session    = await _get_session(session_id)
    owned_ids  = [b["id"] for b in session.get("active_buffs", [])]
    choices    = get_random_buffs(3, exclude_ids=owned_ids)
    return {"buffs": [b.to_dict() for b in choices]}


@router.post("/{session_id}/apply-buff")
async def apply_buff(session_id: str, req: ApplyBuffRequest):
    """Apply a chosen buff to the entire team and clear the pending flag."""
    session = await _get_session(session_id)

    buff_obj = next((b for b in BUFF_POOL if b.id == req.buff_id), None)
    if not buff_obj:
        raise HTTPException(status_code=404, detail="Buff not found")

    team = session["team"]

    # Apply buff effects to each alive fighter
    for member in team:
        if member["is_alive"]:
            apply_buff_to_fighter(member, buff_obj)

    # Special case: "hp_one_full" — restore the most injured alive fighter fully
    if "hp_one_full" in buff_obj.stat_delta:
        alive = [m for m in team if m["is_alive"]]
        if alive:
            most_injured = min(alive, key=lambda m: m["current_hp"] / m["max_hp"])
            most_injured["current_hp"] = most_injured["max_hp"]

    # Special case: "revive_one" — revive first dead fighter
    if "revive_one" in buff_obj.stat_delta:
        dead = [m for m in team if not m["is_alive"]]
        if dead:
            dead[0]["current_hp"] = int(dead[0]["max_hp"] * buff_obj.stat_delta["revive_one"])
            dead[0]["is_alive"]   = True

    active_buffs = session.get("active_buffs", []) + [buff_obj.to_dict()]

    await db.tower_sessions.update_one(
        {"_id": _oid(session_id)},
        {"$set": {
            "team":         team,
            "active_buffs": active_buffs,
            "pending_buff": False,
            "updated_at":   datetime.utcnow(),
        }},
    )

    return {"status": "ok", "buff": buff_obj.to_dict(), "team": team}


@router.post("/{session_id}/revive")
async def use_revive_node(session_id: str, req: ReviveRequest):
    """
    Revive node (floors 14, 24): restore one dead fighter to 30% HP.
    Automatically advance past the revive floor.
    """
    session = await _get_session(session_id)
    floor   = session["current_floor"]

    if get_floor_type(floor) != "revive":
        raise HTTPException(status_code=400, detail="Current floor is not a revive node")

    team   = session["team"]
    target = next((m for m in team if m["pc_id"] == req.target_pc_id), None)

    if not target:
        raise HTTPException(status_code=404, detail="Fighter not in team")

    target["current_hp"] = max(target["current_hp"], int(target["max_hp"] * 0.30))
    target["is_alive"]   = True

    next_floor = floor + 1
    await db.tower_sessions.update_one(
        {"_id": _oid(session_id)},
        {"$set": {
            "team":          team,
            "current_floor": next_floor,
            "updated_at":    datetime.utcnow(),
        }},
    )

    return {"status": "ok", "team": team, "next_floor": next_floor}


@router.post("/{session_id}/abandon")
async def abandon_run(session_id: str):
    """Abandon the current run."""
    await db.tower_sessions.update_one(
        {"_id": _oid(session_id)},
        {"$set": {"status": "abandoned", "updated_at": datetime.utcnow()}},
    )
    return {"status": "abandoned"}
