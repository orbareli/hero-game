"""
engine/battle_state.py
----------------------
All dataclasses for the 3v3 interactive battle system.

Multi-skill update:
  - BattleFighter now holds a `skills` list (SkillDef objects) instead of
    a single skill_name/skill_mult pair.
  - Each SkillDef has its own energy_cost, so skills are individually balanced.
  - Index 0 is always the "primary" skill (backward compat with 1v1 engine).
  - C/R characters have one skill; SR characters have two; UR characters have three.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

# ── Energy constants ──────────────────────────────────────────────────────────
ENERGY_MAX        = 100
ENERGY_ON_DEAL    = 20
ENERGY_ON_RECEIVE = 10
ENERGY_SKILL_COST  = 50
Status = Literal["poisoned", "atk_down", "spd_down", "stunned"]


@dataclass
class StatusEffect:
    name:  Status
    value: float
    turns: int


@dataclass
class SkillDef:
    """One skill a fighter can use."""
    name:         str
    desc:         str
    mult:         float
    energy_cost:  int    # how much energy it costs to activate
    target:       str = "enemy"   # "enemy" | "ally" | "self"


@dataclass
class BattleFighter:
    # Identity
    pc_id:       str
    char_id:     str
    name:        str
    faction:     str
    element:     str
    rarity:      str
    portrait_id: str
    is_player:   bool

    # Stats
    hp:      int
    max_hp:  int
    atk:     int
    defense: int
    spd:     int
    crit:    int
    evade:   int
    energy:  int

    # Skills list — index 0 is primary
    skills:      list[SkillDef] = field(default_factory=list)

    # Legacy single-skill fields (kept for 1v1 engine compatibility)
    skill_name:  str   = ""
    skill_desc:  str   = ""
    skill_mult:  float = 1.0
    passive_name: str  = ""

    # State
    effects:      list[StatusEffect] = field(default_factory=list)
    void_charges: int  = 0
    is_alive:     bool = True

    # ── Computed ──────────────────────────────────────────────────────────────

    def effective_atk(self) -> int:
        debuff = sum(e.value for e in self.effects if e.name == "atk_down")
        return max(1, int(self.atk * (1.0 - debuff)))

    def effective_spd(self) -> int:
        debuff = sum(int(e.value) for e in self.effects if e.name == "spd_down")
        return max(1, self.spd - debuff)

    def can_use_skill(self, skill_index: int = 0) -> bool:
        if not self.is_alive or skill_index >= len(self.skills):
            return False
        return self.energy >= self.skills[skill_index].energy_cost

    def is_stunned(self) -> bool:
        return any(e.name == "stunned" for e in self.effects)

    def take_damage(self, amount: int) -> int:
        actual = max(1, amount)
        self.hp = max(0, self.hp - actual)
        if self.hp == 0:
            self.is_alive = False
        self.energy = min(ENERGY_MAX, self.energy + ENERGY_ON_RECEIVE)
        return actual

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def gain_energy(self, amount: int):
        self.energy = min(ENERGY_MAX, self.energy + amount)

    def spend_energy(self, cost: int):
        self.energy = max(0, self.energy - cost)

    def tick_effects(self) -> list[dict]:
        triggered = []
        remaining = []
        for e in self.effects:
            if e.name == "poisoned":
                dmg = self.take_damage(int(e.value))
                triggered.append({"effect": "poison", "damage": dmg, "target": self.name})
            e.turns -= 1
            if e.turns > 0:
                remaining.append(e)
        self.effects = remaining
        return triggered

    def add_effect(self, effect: StatusEffect):
        for existing in self.effects:
            if existing.name == effect.name:
                existing.turns = max(existing.turns, effect.turns)
                existing.value = max(existing.value, effect.value)
                return
        self.effects.append(effect)

    def skills_for_client(self) -> list[dict]:
        """JSON-serialisable skill list with affordability flag."""
        return [
            {
                "index":       i,
                "name":        s.name,
                "desc":        s.desc,
                "mult":        s.mult,
                "energy_cost": s.energy_cost,
                "target":      s.target,
                "can_afford":  self.energy >= s.energy_cost,
            }
            for i, s in enumerate(self.skills)
        ]

    def to_dict(self) -> dict:
        return {
            "pc_id":       self.pc_id,
            "char_id":     self.char_id,
            "name":        self.name,
            "faction":     self.faction,
            "element":     self.element,
            "rarity":      self.rarity,
            "portrait_id": self.portrait_id,
            "is_player":   self.is_player,
            "hp":          self.hp,
            "max_hp":      self.max_hp,
            "atk":         self.atk,
            "defense":     self.defense,
            "spd":         self.spd,
            "crit":        self.crit,
            "evade":       self.evade,
            "energy":      self.energy,
            "skills":      self.skills_for_client(),
            # Legacy field for 1v1 compatibility
            "skill_name":  self.skills[0].name if self.skills else self.skill_name,
            "skill_desc":  self.skills[0].desc if self.skills else self.skill_desc,
            "skill_mult":  self.skills[0].mult if self.skills else self.skill_mult,
            "passive_name": self.passive_name,
            "is_alive":    self.is_alive,
            "void_charges": self.void_charges,
            "effects":     [{"name": e.name, "value": e.value, "turns": e.turns}
                            for e in self.effects],
        }


@dataclass
class BattleState:
    battle_id:   str
    round:       int
    phase:       Literal["player_input", "enemy_turn", "battle_end"]
    player_team: list[BattleFighter]
    enemy_team:  list[BattleFighter]
    turn_queue:  list[tuple[str, int]] = field(default_factory=list)
    queue_pos:   int = 0
    outcome:     str = ""
    round_events: list[dict] = field(default_factory=list)

    def current_fighter(self) -> tuple[str, int] | None:
        alive_queue = [
            (team, idx) for team, idx in self.turn_queue[self.queue_pos:]
            if self._get_fighter(team, idx).is_alive
        ]
        return alive_queue[0] if alive_queue else None

    def _get_fighter(self, team: str, idx: int) -> BattleFighter:
        return self.player_team[idx] if team == "player" else self.enemy_team[idx]

    def advance_queue(self):
        self.queue_pos += 1
        while self.queue_pos < len(self.turn_queue):
            team, idx = self.turn_queue[self.queue_pos]
            if self._get_fighter(team, idx).is_alive:
                break
            self.queue_pos += 1

    def rebuild_turn_queue(self):
        entries = []
        for i, f in enumerate(self.player_team):
            if f.is_alive:
                entries.append(("player", i, f.effective_spd(), 0))
        for i, f in enumerate(self.enemy_team):
            if f.is_alive:
                entries.append(("enemy", i, f.effective_spd(), 1))
        entries.sort(key=lambda e: (-e[2], e[3]))
        self.turn_queue = [(e[0], e[1]) for e in entries]
        self.queue_pos  = 0

    def is_over(self) -> bool:
        player_alive = any(f.is_alive for f in self.player_team)
        enemy_alive  = any(f.is_alive for f in self.enemy_team)
        if not player_alive or not enemy_alive:
            self.outcome = "win" if player_alive else ("loss" if enemy_alive else "draw")
            self.phase   = "battle_end"
            return True
        return False

    def alive_player_fighters(self) -> list[BattleFighter]:
        return [f for f in self.player_team if f.is_alive]

    def alive_enemy_fighters(self) -> list[BattleFighter]:
        return [f for f in self.enemy_team if f.is_alive]

    def to_dict(self) -> dict:
        return {
            "battle_id":   self.battle_id,
            "round":       self.round,
            "phase":       self.phase,
            "player_team": [f.to_dict() for f in self.player_team],
            "enemy_team":  [f.to_dict() for f in self.enemy_team],
            "queue_pos":   self.queue_pos,
            "turn_queue":  self.turn_queue,
            "outcome":     self.outcome,
        }