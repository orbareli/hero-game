"""
engine/battle.py
----------------
Pure Python auto-battle simulator. Zero DB dependency — takes two
character dicts, runs the fight, returns a structured result.

Battle flow:
  1. Determine turn order by SPD (higher goes first)
  2. Each turn: apply passives → choose action → resolve damage → check win
  3. Action selection uses the equipped loadout (ability_type list)
     - "skill"   → use the skill if not on cooldown, else default attack
     - "passive" → passive is always active, this slot is skipped for action
     - "default" → always basic attack
  4. Returns BattleResult with full turn log

Usage:
    from engine.battle import run_battle
    result = run_battle(player_char, enemy_char, loadout=["skill", "default"])
    print(result.outcome)   # "win" | "loss" | "draw"
    print(result.log)       # list of turn dicts
"""

from __future__ import annotations
import random
import math
from dataclasses import dataclass, field
from typing import Literal


# ------------------------------------------------------------------ #
#  Data classes                                                        #
# ------------------------------------------------------------------ #

@dataclass
class Fighter:
    """
    A combatant in battle. Built from a player_character + character row.
    All stat mutations happen here — original DB rows are never modified.
    """
    id:            int
    name:          str
    faction:       str
    hp:            int
    max_hp:        int
    atk:           int
    defense:       int        # 'def' is a Python keyword
    spd:           int
    crit:          int        # percent (0-100)
    evade:         int        # percent (0-100)

    # Passive
    passive_name:  str
    passive_desc:  str

    # Skill
    skill_name:    str
    skill_desc:    str
    skill_mult:    float
    skill_cd:      int        # base cooldown turns
    skill_current_cd: int = 0 # turns remaining before usable

    # Status effects (applied mid-battle)
    poison_dmg:    int = 0    # damage per turn from poison
    poison_turns:  int = 0    # turns remaining
    atk_debuff:    float = 0.0 # % ATK reduction (0.0–1.0)
    atk_debuff_turns: int = 0
    spd_debuff:    int = 0    # flat SPD reduction

    # Void Queen charge mechanic
    void_charges:  int = 0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage, clamp hp to 0. Returns actual damage taken."""
        actual = max(1, amount)
        self.hp = max(0, self.hp - actual)
        return actual

    def heal(self, amount: int) -> int:
        """Heal up to max_hp. Returns actual healed."""
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def effective_atk(self) -> int:
        mult = 1.0 - self.atk_debuff
        return max(1, int(self.atk * mult))

    def effective_spd(self) -> int:
        return max(1, self.spd - self.spd_debuff)


@dataclass
class TurnEvent:
    turn:      int
    actor:     str   # fighter name
    action:    str   # "skill" | "attack" | "passive_heal" | "poison"
    detail:    str   # human-readable description
    damage:    int = 0
    heal:      int = 0
    crit:      bool = False
    evaded:    bool = False
    p_hp:      int = 0   # player HP after this event
    e_hp:      int = 0   # enemy HP after this event


@dataclass
class BattleResult:
    outcome:      Literal["win", "loss", "draw"]
    turns:        int
    log:          list[TurnEvent] = field(default_factory=list)
    coins_earned: int = 0
    xp_earned:    int = 0

    def to_dict(self) -> dict:
        return {
            "outcome":      self.outcome,
            "turns":        self.turns,
            "coins_earned": self.coins_earned,
            "xp_earned":    self.xp_earned,
            "log": [
                {
                    "turn":    e.turn,
                    "actor":   e.actor,
                    "action":  e.action,
                    "detail":  e.detail,
                    "damage":  e.damage,
                    "heal":    e.heal,
                    "crit":    e.crit,
                    "evaded":  e.evaded,
                    "p_hp":    e.p_hp,
                    "e_hp":    e.e_hp,
                }
                for e in self.log
            ],
        }


# ------------------------------------------------------------------ #
#  Fighter factory                                                     #
# ------------------------------------------------------------------ #

def make_fighter(pc: dict, char: dict) -> Fighter:
    """
    Build a Fighter from a player_character row + character master row.
    If pc is None (enemy with no player_character row), use base stats.
    """
    if pc:
        return Fighter(
            id=pc["id"],
            name=char["name"],
            faction=char["faction"],
            hp=pc["hp"],
            max_hp=pc["hp"],
            atk=pc["atk"],
            defense=pc["def"],
            spd=pc["spd"],
            crit=pc["crit"],
            evade=pc["evade"],
            passive_name=char["passive_name"],
            passive_desc=char["passive_desc"],
            skill_name=char["skill_name"],
            skill_desc=char["skill_desc"],
            skill_mult=char["skill_mult"],
            skill_cd=char["skill_cd"],
        )
    else:
        # Enemy — use base stats directly
        return Fighter(
            id=char["id"],
            name=char["name"],
            faction=char["faction"],
            hp=char["base_hp"],
            max_hp=char["base_hp"],
            atk=char["base_atk"],
            defense=char["base_def"],
            spd=char["base_spd"],
            crit=char["base_crit"],
            evade=char["base_evade"],
            passive_name=char["passive_name"],
            passive_desc=char["passive_desc"],
            skill_name=char["skill_name"],
            skill_desc=char["skill_desc"],
            skill_mult=char["skill_mult"],
            skill_cd=char["skill_cd"],
        )


# ------------------------------------------------------------------ #
#  Damage formula                                                      #
# ------------------------------------------------------------------ #

def calc_damage(
    attacker: Fighter,
    defender: Fighter,
    mult: float = 1.0,
    ignore_def_pct: float = 0.0,
    force_crit: bool = False,
) -> tuple[int, bool]:
    """
    Returns (damage, is_crit).

    Formula:
        raw  = attacker.effective_atk() * mult
        miti = defender.defense * (1 - ignore_def_pct)
        dmg  = max(1, raw - miti)
        crit = random roll against crit%  → *1.5
    """
    raw  = attacker.effective_atk() * mult
    miti = defender.defense * (1.0 - ignore_def_pct)
    dmg  = max(1.0, raw - miti)

    is_crit = force_crit or (random.randint(1, 100) <= attacker.crit)
    if is_crit:
        dmg *= 1.5

    return int(dmg), is_crit


def roll_evade(defender: Fighter) -> bool:
    return random.randint(1, 100) <= defender.evade


# ------------------------------------------------------------------ #
#  Passive effects (applied at start of attacker's turn)              #
# ------------------------------------------------------------------ #

def apply_start_of_turn(fighter: Fighter, opponent: Fighter, events: list, turn: int):
    """Apply any passives / status effects at start of this fighter's turn."""

    # Solar Aura — heal 5% max HP
    if fighter.passive_name == "Solar Aura":
        heal_amt = max(1, int(fighter.max_hp * 0.05))
        actual   = fighter.heal(heal_amt)
        if actual > 0:
            events.append(TurnEvent(
                turn=turn, actor=fighter.name,
                action="passive_heal",
                detail=f"Solar Aura heals {actual} HP",
                heal=actual,
                p_hp=fighter.hp, e_hp=opponent.hp,
            ))

    # Gravity Well — suppress enemy SPD (applied permanently while alive, set once)
    if fighter.passive_name == "Gravity Well":
        opponent.spd_debuff = max(opponent.spd_debuff, 2)

    # Dark Throne — gain ATK for each 20% HP lost
    if fighter.passive_name == "Dark Throne":
        hp_lost_pct = 1.0 - (fighter.hp / fighter.max_hp)
        stacks = int(hp_lost_pct / 0.20)  # 0 stacks at full HP, up to 4
        # Recalculate: base atk + 10% per stack (store on fighter directly)
        # We handle this inline in effective_atk via a multiplier tracked as negative debuff
        fighter.atk_debuff = -stacks * 0.10  # negative = buff

    # Poison tick
    if fighter.poison_turns > 0:
        actual = fighter.take_damage(fighter.poison_dmg)
        fighter.poison_turns -= 1
        events.append(TurnEvent(
            turn=turn, actor=fighter.name,
            action="poison",
            detail=f"Poison deals {actual} damage ({fighter.poison_turns} turns left)",
            damage=actual,
            p_hp=fighter.hp, e_hp=opponent.hp,
        ))

    # ATK debuff countdown
    if fighter.atk_debuff_turns > 0:
        fighter.atk_debuff_turns -= 1
        if fighter.atk_debuff_turns == 0 and fighter.atk_debuff > 0:
            fighter.atk_debuff = 0.0

    # Skill cooldown tick
    if fighter.skill_current_cd > 0:
        fighter.skill_current_cd -= 1


# ------------------------------------------------------------------ #
#  Action resolution                                                   #
# ------------------------------------------------------------------ #

def resolve_skill(attacker: Fighter, defender: Fighter, events: list, turn: int):
    """Execute the attacker's skill against defender."""

    ignore_def = 0.0
    force_crit = False
    extra_events = []

    # Character-specific skill logic
    if attacker.skill_name == "Shield Slam":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            # Apply ATK debuff to defender
            defender.atk_debuff = max(defender.atk_debuff, 0.15)
            defender.atk_debuff_turns = max(defender.atk_debuff_turns, 2)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg, enemy ATK -15% for 2 turns",
                damage=taken, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    elif attacker.skill_name == "Thunderstrike":
        force_crit = defender.hp > (defender.max_hp * 0.80)
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult, force_crit=force_crit)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg" + (" (guaranteed crit!)" if force_crit else ""),
                damage=taken, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    elif attacker.skill_name == "Nova Burst":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            heal_amt = int(taken * 0.20)
            actual_heal = attacker.heal(heal_amt)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg, healed {actual_heal} HP",
                damage=taken, heal=actual_heal, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    elif attacker.skill_name == "Death Coil":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            # Double poison this turn
            poison_bonus = attacker.poison_dmg * 2 if attacker.passive_name == "Toxic Touch" else 0
            if poison_bonus:
                extra = defender.take_damage(poison_bonus)
                detail = f"{attacker.skill_name}: {taken} dmg + {extra} bonus poison"
            else:
                detail = f"{attacker.skill_name}: {taken} dmg"
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=detail, damage=taken, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    elif attacker.skill_name == "Singularity":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult, ignore_def_pct=0.5)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg (ignores 50% DEF)",
                damage=taken, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    elif attacker.skill_name == "Void Rupture":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            attacker.void_charges += 1
            extra = ""
            if attacker.void_charges >= 3:
                attacker.void_charges = 0
                extra = " — FREE TURN TRIGGERED!"
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg (charges: {attacker.void_charges}){extra}",
                damage=taken, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    else:
        # Generic skill fallback
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg",
                damage=taken, crit=is_crit,
                p_hp=attacker.hp, e_hp=defender.hp,
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!",
                evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
            ))

    attacker.skill_current_cd = attacker.skill_cd


def resolve_default_attack(attacker: Fighter, defender: Fighter, events: list, turn: int):
    """Basic attack — 1.0x ATK, respects evade + crit."""

    # Toxic Touch passive: apply poison on hit
    apply_poison = attacker.passive_name == "Toxic Touch"

    dmg, is_crit = calc_damage(attacker, defender, 1.0)
    if roll_evade(defender):
        events.append(TurnEvent(
            turn=turn, actor=attacker.name, action="attack",
            detail=f"{attacker.name} attacks — evaded!",
            evaded=True, p_hp=attacker.hp, e_hp=defender.hp,
        ))
        return

    # Steel Skin passive: reduce incoming damage
    if defender.passive_name == "Steel Skin":
        dmg = max(1, int(dmg * 0.92))

    taken = defender.take_damage(dmg)
    detail = f"{attacker.name} attacks for {taken} dmg"

    if apply_poison:
        defender.poison_dmg   = max(defender.poison_dmg, 5)
        defender.poison_turns = max(defender.poison_turns, 3)
        detail += " (poisoned!)"

    if is_crit:
        detail += " (CRIT!)"

    events.append(TurnEvent(
        turn=turn, actor=attacker.name, action="attack",
        detail=detail, damage=taken, crit=is_crit,
        p_hp=attacker.hp, e_hp=defender.hp,
    ))


def choose_action(fighter: Fighter, loadout: list[str]) -> str:
    """
    Decide action based on loadout.
    loadout is a list of ability_type strings: ["skill", "default"]
    - "skill"   → use skill if off cooldown, else fall back to default
    - "passive" → passive is always-on, skip this slot (use default)
    - "default" → always basic attack
    """
    for slot in loadout:
        if slot == "skill" and fighter.skill_current_cd == 0:
            return "skill"
    return "attack"


# ------------------------------------------------------------------ #
#  Main battle loop                                                    #
# ------------------------------------------------------------------ #

MAX_TURNS = 40  # prevent infinite loops


def run_battle(
    player_char: dict,
    player_char_master: dict,
    enemy_char_master: dict,
    player_loadout: list[str] | None = None,
) -> BattleResult:
    """
    Simulate a full battle.

    Args:
        player_char:        player_characters row (with current stats)
        player_char_master: characters row for the player's character
        enemy_char_master:  characters row for the enemy (base stats used)
        player_loadout:     list of ability_type strings, e.g. ["skill", "default"]
                            defaults to ["skill", "default"] if None

    Returns:
        BattleResult with outcome, turn count, and full event log
    """
    if player_loadout is None:
        player_loadout = ["skill", "default"]

    # Enemy always uses skill when available
    enemy_loadout = ["skill", "default"]

    player = make_fighter(player_char, player_char_master)
    enemy  = make_fighter(None, enemy_char_master)

    events: list[TurnEvent] = []
    turn   = 0

    # Initial state snapshot
    events.append(TurnEvent(
        turn=0, actor="system", action="start",
        detail=f"Battle start: {player.name} (HP:{player.hp} SPD:{player.spd}) "
               f"vs {enemy.name} (HP:{enemy.hp} SPD:{enemy.spd})",
        p_hp=player.hp, e_hp=enemy.hp,
    ))

    while player.is_alive and enemy.is_alive and turn < MAX_TURNS:
        turn += 1

        # Determine who acts first this turn based on effective SPD
        # Ties broken randomly
        p_spd = player.effective_spd()
        e_spd = enemy.effective_spd()

        if p_spd > e_spd or (p_spd == e_spd and random.random() < 0.5):
            first, second   = player, enemy
            first_load, second_load = player_loadout, enemy_loadout
        else:
            first, second   = enemy, player
            first_load, second_load = enemy_loadout, player_loadout

        # ── First fighter acts ──────────────────────────────────────
        apply_start_of_turn(first, second, events, turn)
        if not second.is_alive:
            break

        action = choose_action(first, first_load)
        if action == "skill":
            resolve_skill(first, second, events, turn)
            # Void Queen free turn
            if first.skill_name == "Void Rupture" and first.void_charges == 0:
                if events[-1].detail.endswith("FREE TURN TRIGGERED!"):
                    action2 = choose_action(first, first_load)
                    if action2 == "skill":
                        resolve_skill(first, second, events, turn)
                    else:
                        resolve_default_attack(first, second, events, turn)
        else:
            resolve_default_attack(first, second, events, turn)

        if not second.is_alive:
            break

        # ── Second fighter acts ─────────────────────────────────────
        apply_start_of_turn(second, first, events, turn)
        if not first.is_alive:
            break

        action = choose_action(second, second_load)
        if action == "skill":
            resolve_skill(second, first, events, turn)
        else:
            resolve_default_attack(second, first, events, turn)

    # ── Determine outcome ───────────────────────────────────────────
    if player.is_alive and not enemy.is_alive:
        outcome = "win"
        coins   = random.randint(30, 80)
        xp      = random.randint(20, 50)
    elif enemy.is_alive and not player.is_alive:
        outcome = "loss"
        coins   = random.randint(5, 15)
        xp      = random.randint(5, 15)
    else:
        outcome = "draw"
        coins   = random.randint(10, 25)
        xp      = random.randint(10, 25)

    events.append(TurnEvent(
        turn=turn, actor="system", action="end",
        detail=f"Battle over — {outcome.upper()} after {turn} turns. "
               f"+{coins} coins, +{xp} XP",
        p_hp=player.hp, e_hp=enemy.hp,
    ))

    return BattleResult(
        outcome=outcome,
        turns=turn,
        log=events,
        coins_earned=coins,
        xp_earned=xp,
    )


# ------------------------------------------------------------------ #
#  Quick CLI test                                                      #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    # Fake character data to test the engine standalone
    pc = {
        "id": 1, "hp": 300, "atk": 95, "def": 20,
        "spd": 9, "crit": 25, "evade": 18,
    }
    hero = {
        "id": 2, "name": "Swiftbolt", "faction": "hero",
        "base_hp": 300, "base_atk": 95, "base_def": 20,
        "base_spd": 9, "base_crit": 25, "base_evade": 18,
        "passive_name": "Lightning Reflexes", "passive_desc": "...",
        "skill_name": "Thunderstrike", "skill_desc": "...",
        "skill_mult": 2.2, "skill_cd": 4,
    }
    villain = {
        "id": 3, "name": "Graviton", "faction": "villain",
        "base_hp": 480, "base_atk": 80, "base_def": 45,
        "base_spd": 5, "base_crit": 12, "base_evade": 8,
        "passive_name": "Gravity Well", "passive_desc": "...",
        "skill_name": "Singularity", "skill_desc": "...",
        "skill_mult": 1.6, "skill_cd": 4,
    }

    result = run_battle(pc, hero, villain, player_loadout=["skill", "default"])
    print(f"\nOutcome: {result.outcome} in {result.turns} turns")
    print(f"Rewards: +{result.coins_earned} coins, +{result.xp_earned} XP\n")
    for e in result.log:
        print(f"  T{e.turn:02d} [{e.actor}] {e.detail}  (P:{e.p_hp} E:{e.e_hp})")
