"""
engine/tower_generator.py
-------------------------
Procedural enemy generation and floor layout for the Tower of Trials.

Design:
  - 30 floors total. Every 5th floor is a Boss (3v1). Others are 3v3.
  - Enemy stats scale by +8% per floor.
  - Every 3rd floor clears, player is offered 3 random buffs.
  - Floors 14 and 24 are Revive nodes (no combat).
  - Boss floors use a single character pulled from the villain pool,
    with stats scaled much higher and a larger HP multiplier.

Enemy pool is loaded from MongoDB at runtime so new characters added
via seed automatically appear in the tower without code changes.
"""

from __future__ import annotations
import random
import math
from dataclasses import dataclass, field
from typing import Literal


# ── Floor type definitions ────────────────────────────────────────────────────

FloorType = Literal["battle", "boss", "revive", "buff", "start"]

FLOOR_LAYOUT: dict[int, FloorType] = {}
for f in range(1, 31):
    if f in (14, 24):
        FLOOR_LAYOUT[f] = "revive"
    elif f % 5 == 0:
        FLOOR_LAYOUT[f] = "boss"
    else:
        FLOOR_LAYOUT[f] = "battle"
FLOOR_LAYOUT[0] = "start"


def get_floor_type(floor: int) -> FloorType:
    return FLOOR_LAYOUT.get(floor, "battle")


def is_buff_floor(floor: int) -> bool:
    """Player is offered buffs after clearing floors 3, 6, 9, 12 …"""
    return floor > 0 and floor % 3 == 0 and get_floor_type(floor) not in ("revive",)


# ── Stat scaling ──────────────────────────────────────────────────────────────

def scale_stat(base: int, floor: int, is_boss: bool = False) -> int:
    """
    Linear scaling: +8% per floor for normal, +15% for boss.
    Floors are 1-indexed.
    """
    multiplier = 1.0 + (floor - 1) * (0.15 if is_boss else 0.08)
    return max(1, int(base * multiplier))


def scale_enemy(char_doc: dict, floor: int, is_boss: bool = False) -> dict:
    """
    Return a new dict with stats scaled for the current floor.
    Does NOT mutate the original DB document.
    """
    scaled = dict(char_doc)
    for stat in ("base_hp", "base_atk", "base_def"):
        scaled[stat] = scale_stat(char_doc[stat], floor, is_boss)
    if is_boss:
        scaled["base_hp"] = int(scaled["base_hp"] * 2.5)  # boss HP pool
    return scaled


# ── Buff catalogue ────────────────────────────────────────────────────────────

@dataclass
class TowerBuff:
    id:          str
    name:        str
    description: str
    category:    Literal["atk", "hp", "energy", "crit", "def", "utility"]
    # Applied to each fighter in the team when selected
    # Values are relative (0.10 = +10%) or absolute (+20 energy)
    stat_delta:  dict  = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "description": self.description,
            "category": self.category,
            "stat_delta": self.stat_delta,
        }


BUFF_POOL: list[TowerBuff] = [
    TowerBuff("atk_10",     "Warrior's Edge",    "+10% ATK to all fighters",        "atk",     {"atk_pct": 0.10}),
    TowerBuff("atk_20",     "Berserker's Rage",  "+20% ATK to all fighters",        "atk",     {"atk_pct": 0.20}),
    TowerBuff("hp_20",      "Iron Will",         "Restore 20% max HP to all",       "hp",      {"hp_pct":  0.20}),
    TowerBuff("hp_full",    "Second Wind",       "Fully restore one fighter's HP",   "hp",      {"hp_one_full": True}),
    TowerBuff("energy_20",  "Battle Rush",       "Start next battle with +20 energy","energy",  {"energy_flat": 20}),
    TowerBuff("energy_full","Overdrive",         "Start next battle at 50 energy",   "energy",  {"energy_set": 50}),
    TowerBuff("crit_15",    "Sharpened Instinct","+15% CRIT to all fighters",       "crit",    {"crit_flat": 15}),
    TowerBuff("def_20",     "Fortress",          "+20% DEF to all fighters",        "def",     {"def_pct":   0.20}),
    TowerBuff("spd_2",      "Swift Stride",      "+2 SPD to all fighters",          "utility", {"spd_flat":  2}),
    TowerBuff("evade_10",   "Ghost Step",        "+10% Evade to all fighters",      "utility", {"evade_flat": 10}),
    TowerBuff("revive_30",  "Phoenix Ember",     "Revive one dead fighter at 30% HP","utility", {"revive_one": 0.30}),
    TowerBuff("poison_all", "Toxic Fangs",       "All attacks inflict 3-turn poison","utility", {"passive_poison": True}),
]


def get_random_buffs(count: int = 3, exclude_ids: list[str] | None = None) -> list[TowerBuff]:
    """Return `count` distinct random buffs, excluding already-owned ones."""
    exclude = set(exclude_ids or [])
    pool    = [b for b in BUFF_POOL if b.id not in exclude]
    return random.sample(pool, min(count, len(pool)))


# ── Apply buffs to a team member dict ─────────────────────────────────────────

def apply_buff_to_fighter(fighter: dict, buff: TowerBuff) -> dict:
    """
    Mutate a TowerSession team-member dict in place with buff effects.
    Returns the modified dict.
    """
    d = fighter  # operating on the session's team list dicts

    if "atk_pct" in buff.stat_delta:
        d["current_atk"] = int(d.get("current_atk", d["max_atk"]) * (1 + buff.stat_delta["atk_pct"]))
        d["max_atk"]     = d["current_atk"]

    if "hp_pct" in buff.stat_delta:
        restore = int(d["max_hp"] * buff.stat_delta["hp_pct"])
        d["current_hp"] = min(d["max_hp"], d.get("current_hp", d["max_hp"]) + restore)

    if "hp_one_full" in buff.stat_delta:
        # Restore the most injured alive fighter — caller handles selection
        pass  # handled in the router

    if "energy_flat" in buff.stat_delta:
        d["battle_start_energy"] = min(100, d.get("battle_start_energy", 0) + buff.stat_delta["energy_flat"])

    if "energy_set" in buff.stat_delta:
        d["battle_start_energy"] = buff.stat_delta["energy_set"]

    if "crit_flat" in buff.stat_delta:
        d["current_crit"] = min(100, d.get("current_crit", d.get("base_crit", 10)) + buff.stat_delta["crit_flat"])

    if "def_pct" in buff.stat_delta:
        base = d.get("base_def", 20)
        d["current_def"] = int(base * (1 + buff.stat_delta["def_pct"]))

    if "spd_flat" in buff.stat_delta:
        d["current_spd"] = min(12, d.get("current_spd", d.get("base_spd", 5)) + buff.stat_delta["spd_flat"])

    if "evade_flat" in buff.stat_delta:
        d["current_evade"] = min(90, d.get("current_evade", d.get("base_evade", 5)) + buff.stat_delta["evade_flat"])

    if "revive_one" in buff.stat_delta:
        # Handled in router — revive first dead fighter
        pass

    return d


# ── Enemy team generator ───────────────────────────────────────────────────────

async def generate_enemy_team(floor: int, all_chars: list[dict]) -> list[dict]:
    """
    Given the floor number and the full master character list from MongoDB,
    return a list of scaled enemy character dicts.

    Floor type determines team size:
      - boss:   1 villain (heavily scaled, 2.5× HP)
      - battle: 2–3 villains (scaled normally)
    """
    floor_type = get_floor_type(floor)
    villains   = [c for c in all_chars if c.get("faction") == "villain"]

    if not villains:
        # Fallback: use any characters as enemies
        villains = all_chars

    if floor_type == "boss":
        # Pick the highest-rarity villain available, prefer UR > SR > R > C
        rarity_order = {"UR": 4, "SR": 3, "R": 2, "C": 1}
        boss_char    = max(villains, key=lambda c: rarity_order.get(c.get("rarity", "C"), 0))
        return [scale_enemy(boss_char, floor, is_boss=True)]

    # Normal battle: 2 fighters on floors 1–4, 3 fighters from floor 5+
    team_size = 2 if floor <= 4 else 3

    # Weight selection toward harder enemies as floors increase
    # Early floors: favour C/R. Late floors: favour SR/UR.
    if floor <= 8:
        pool = [c for c in villains if c.get("rarity") in ("C", "R", "SR")] or villains
    elif floor <= 16:
        pool = [c for c in villains if c.get("rarity") in ("R", "SR", "UR")] or villains
    else:
        pool = [c for c in villains if c.get("rarity") in ("SR", "UR")] or villains

    chosen = random.choices(pool, k=team_size)
    return [scale_enemy(c, floor) for c in chosen]
