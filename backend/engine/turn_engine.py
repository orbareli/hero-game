"""
engine/turn_engine.py
---------------------
Resolves a single action in a 3v3 interactive battle.
Synced with all skills and passives from battle.py (updated seed2 characters).
"""

from __future__ import annotations
import random
from typing import Literal

from engine.battle_state import (
    BattleState, BattleFighter, StatusEffect,
    ENERGY_ON_DEAL,
)
ENERGY_SKILL_COST = 50  # default fallback (individual skills have their own cost)
from engine.element_system import element_multiplier


# ── Damage formula ────────────────────────────────────────────────────────────

def calc_damage(
    attacker: BattleFighter,
    defender: BattleFighter,
    mult: float = 1.0,
    ignore_def_pct: float = 0.0,
    force_crit: bool = False,
) -> tuple[int, bool]:
    elem_mult = element_multiplier(attacker.element, defender.element)

    # God Complex: +20% damage when attacker ATK > defender ATK
    god_mult = 1.2 if (attacker.passive_name == "God Complex" and attacker.atk > defender.atk) else 1.0

    raw     = attacker.effective_atk() * mult * elem_mult * god_mult
    miti    = defender.defense * (1.0 - ignore_def_pct)
    dmg     = max(1.0, raw - miti)
    is_crit = force_crit or (random.randint(1, 100) <= attacker.crit)
    if is_crit:
        dmg *= 1.5
    return int(dmg), is_crit


def roll_evade(defender: BattleFighter) -> bool:
    return random.randint(1, 100) <= defender.evade


# ── Start-of-turn passives ────────────────────────────────────────────────────

def apply_start_of_turn_passives(
    fighter: BattleFighter,
    opponent_team: list[BattleFighter],
) -> list[dict]:
    """
    Apply all passive effects and tick status effects at the start of a fighter's turn.
    Returns a list of event dicts.
    """
    events: list[dict] = []

    def evt(**kwargs) -> dict:
        return {
            "actor":      fighter.name,
            "actor_team": "player" if fighter.is_player else "enemy",
            **kwargs,
        }

    # ── Tick active status effects (poison etc.) ──────────────────────────────
    for te in fighter.tick_effects():
        events.append(evt(
            action="effect_tick",
            detail=f"Poison: {te['damage']} dmg to {te['target']}",
            damage=te["damage"],
        ))

    if not fighter.is_alive:
        return events

    # ── Solar Aura (original) — heal 5% max HP ────────────────────────────────
    if fighter.passive_name == "Solar Aura":
        healed = fighter.heal(max(1, int(fighter.max_hp * 0.05)))
        if healed > 0:
            events.append(evt(action="passive_heal",
                detail=f"Solar Aura: healed {healed} HP", heal=healed))

    # ── Solar Absorption (Superman) — heal 5% when HP > 50% ──────────────────
    if fighter.passive_name == "Solar Absorption":
        if fighter.hp > fighter.max_hp * 0.50:
            healed = fighter.heal(max(1, int(fighter.max_hp * 0.05)))
            if healed > 0:
                events.append(evt(action="passive_heal",
                    detail=f"Solar Absorption: Sun heals {healed} HP", heal=healed))

    # ── Matter Rebirth (Atom Eve) — one-time revive below 20% HP ─────────────
    if fighter.passive_name == "Matter Rebirth":
        if (fighter.hp < fighter.max_hp * 0.20
                and not getattr(fighter, '_matter_rebirth_used', False)):
            heal_amt = int(fighter.max_hp * 0.30)
            fighter.heal(heal_amt)
            fighter._matter_rebirth_used = True
            events.append(evt(action="passive_heal",
                detail=f"Matter Rebirth: Eve reforms! +{heal_amt} HP", heal=heal_amt))

    # ── Prep Time (Batman) — one-time HP trade for crit ──────────────────────
    if fighter.passive_name == "Prep Time":
        if not getattr(fighter, '_prep_done', False):
            penalty = int(fighter.hp * 0.20)
            fighter.hp = max(1, fighter.hp - penalty)
            fighter.crit = min(100, fighter.crit + 20)
            fighter._prep_done = True
            events.append(evt(action="passive",
                detail=f"Prep Time: -{penalty} HP for +20% Crit Rate!"))

    # ── Zenithian Physiology (Allen) — permanent 15% damage reduction ─────────
    # Implemented as a defense multiplier applied once per turn via effect tracking.
    # We handle it inline in resolve_basic_attack / resolve_skill via the
    # defender passive check — see _apply_zenithian below.

    # ── Gravity Well — reduce all opposing fighters' SPD by 2 ─────────────────
    if fighter.passive_name == "Gravity Well":
        for opp in opponent_team:
            if opp.is_alive:
                opp.add_effect(StatusEffect("spd_down", 2, 1))

    # ── Dark Throne (Void Queen) — gain ATK as HP drops ──────────────────────
    if fighter.passive_name == "Dark Throne":
        hp_lost = 1.0 - (fighter.hp / fighter.max_hp)
        stacks  = int(hp_lost / 0.20)
        # Clear old Dark Throne buff then re-apply at current stack count
        fighter.effects = [e for e in fighter.effects
                           if not (e.name == "atk_down" and e.value < 0)]
        if stacks > 0:
            fighter.add_effect(StatusEffect("atk_down", -stacks * 0.10, 1))

    # ── Global Agency (Cecil) — start battle with +20 evade (applied once) ───
    if fighter.passive_name == "Global Agency":
        if not getattr(fighter, '_global_agency_applied', False):
            fighter.evade = min(95, fighter.evade + 20)
            fighter._global_agency_applied = True

    return events


# ── Skill resolution ──────────────────────────────────────────────────────────

def resolve_skill(
    attacker: BattleFighter,
    defender: BattleFighter,
    skill_name: str | None = None,
    skill_mult: float | None = None,
    skill_target: str = "enemy",
) -> list[dict]:
    """
    Execute attacker's named skill against defender.
    Energy is already spent by the caller.
    Returns list of JSON-serialisable event dicts.
    """
    events: list[dict] = []

    def base_event(**kwargs) -> dict:
        return {
            "actor":      attacker.name,
            "actor_team": "player" if attacker.is_player else "enemy",
            "target":     defender.name,
            "action":     "skill",
            "skill_name": attacker.skill_name,
            "element":    attacker.element,
            **kwargs,
        }

    sname = skill_name if skill_name is not None else (attacker.skills[0].name if attacker.skills else attacker.skill_name)
    # Use passed mult, or fall back to attacker primary skill mult
    _smult = skill_mult if skill_mult is not None else (attacker.skills[0].mult if attacker.skills else attacker.skill_mult)
    # Patch attacker.skill_mult for all calc_damage calls that use attacker.skill_mult
    _orig_mult = attacker.skill_mult
    attacker.skill_mult = _smult

    # ── Shield Slam ────────────────────────────────────────────────────────────
    if sname == "Shield Slam":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("atk_down", 0.15, 2))
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg + ATK -15% for 2 turns"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── Thunderstrike (Swiftbolt) ──────────────────────────────────────────────
    elif sname == "Thunderstrike":
        force_crit = defender.hp > defender.max_hp * 0.80
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult, force_crit=force_crit)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            suffix = " (guaranteed crit!)" if force_crit else ""
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg{suffix}"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── World-Class Execution (Omni-Man) ──────────────────────────────────────
    # Ignores all DEF. Below 40% HP → 1.5× execute multiplier.
    elif sname == "World-Class Execution":
        is_execute = defender.hp < defender.max_hp * 0.40
        mult       = attacker.skill_mult * (1.5 if is_execute else 1.0)
        dmg, is_crit = calc_damage(attacker, defender, mult, ignore_def_pct=1.0)
        if not roll_evade(defender):
            taken  = _deal(attacker, defender, dmg)
            detail = f"{sname}: {taken} pure dmg!" + (" (EXECUTE!)" if is_execute else "")
            events.append(base_event(damage=taken, crit=is_crit, evaded=False, detail=detail))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: missed!"))

    # ── viltrumaite (Invincible) ───────────────────────────────────────────────
    elif sname == "viltrumaite":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg — Viltrumite power!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── Inexorable Assault (Conquest) ─────────────────────────────────────────
    # 3-hit combo, each hit 20% stronger. Every hit that lands shreds 10% DEF.
    elif sname == "Inexorable Assault":
        total_taken, any_hit, any_crit = 0, False, False
        for i in range(1, 4):
            current_mult = attacker.skill_mult * (1 + (i - 1) * 0.2)
            dmg, is_crit  = calc_damage(attacker, defender, current_mult)
            if not roll_evade(defender):
                taken        = _deal(attacker, defender, dmg)
                total_taken += taken
                any_hit      = True
                any_crit     = any_crit or is_crit
                defender.defense = max(0, int(defender.defense * 0.90))
        if any_hit:
            events.append(base_event(damage=total_taken, crit=any_crit, evaded=False,
                detail=f"{sname}: 3-hit combo for {total_taken} dmg! Defense shredded."))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: All hits missed!"))

    # ── Molecular Manipulation (Atom Eve) ─────────────────────────────────────
    # Damage + restore 50% of damage dealt as HP.
    elif sname == "Molecular Manipulation":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken      = _deal(attacker, defender, dmg)
            healed     = attacker.heal(int(taken * 0.50))
            events.append(base_event(damage=taken, heal=healed, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg, restored {healed} HP!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: Missed!"))

    # ── Unstoppable Evolution (Allen the Alien) ────────────────────────────────
    # Damage + permanently increases own ATK by 15%.
    elif sname == "Unstoppable Evolution":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken    = _deal(attacker, defender, dmg)
            atk_buff = int(attacker.atk * 0.15)
            attacker.atk += atk_buff
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg. Adaptation: ATK +{atk_buff}!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: Missed!"))

    # ── Orbital Strike (Cecil) ────────────────────────────────────────────────
    # Damage + applies SPD debuff (sensor disruption).
    elif sname == "Orbital Strike":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("spd_down", 3, 2))
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} orbital dmg! Enemy sensors disrupted (-SPD 2 turns)."))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Satellite missed!"))

    # ── Heat Vision (Superman) ────────────────────────────────────────────────
    # Ignores 100% of DEF.
    elif sname == "Heat Vision":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult, ignore_def_pct=1.0)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} pure thermal dmg!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Heat Vision missed!"))

    # ── Infinite Mass Punch (Flash) ───────────────────────────────────────────
    # Base damage + bonus equal to SPD × 5.
    elif sname == "Infinite Mass Punch":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        spd_bonus    = attacker.spd * 5
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg + spd_bonus)
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg at light speed! (+{spd_bonus} SPD bonus)"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Flash was too fast and missed!"))

    # ── Lasso of Truth (Wonder Woman) ─────────────────────────────────────────
    # Damage + stuns target for 1 turn.
    elif sname == "Lasso of Truth":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("stunned", 1.0, 1))
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg. Target STUNNED for 1 turn!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Lasso missed!"))

    # ── Explosive Batarang (Batman) ────────────────────────────────────────────
    # Damage + ATK debuff for 2 turns.
    elif sname == "Explosive Batarang":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("atk_down", 0.20, 2))
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg + enemy ATK -20% for 2 turns!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: missed!"))

    # ── Laser Eyes (Homelander) ────────────────────────────────────────────────
    # Damage. If target dies, refund full skill energy cost.
    elif sname == "Laser Eyes":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken   = _deal(attacker, defender, dmg)
            res_msg = ""
            if not defender.is_alive:
                attacker.gain_energy(ENERGY_SKILL_COST)
                res_msg = " COOLDOWN RESET!"
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg.{res_msg}"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Laser Eyes missed!"))

    # ── Nova Burst ────────────────────────────────────────────────────────────
    elif sname == "Nova Burst":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken  = _deal(attacker, defender, dmg)
            healed = attacker.heal(int(taken * 0.25))
            events.append(base_event(damage=taken, heal=healed, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg, healed {healed} HP"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── Singularity (Graviton) ─────────────────────────────────────────────────
    elif sname == "Singularity":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult, ignore_def_pct=0.5)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg (ignores 50% DEF)"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── Void Rupture (Void Queen) ──────────────────────────────────────────────
    # Builds void charges. At 3 charges → free skill (full energy refund).
    elif sname == "Void Rupture":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            attacker.void_charges += 1
            free_skill = attacker.void_charges >= 3
            if free_skill:
                attacker.void_charges = 0
                attacker.gain_energy(ENERGY_SKILL_COST)
            suffix = " — VOID SURGE! Energy restored!" if free_skill else f" ({attacker.void_charges}/3)"
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg{suffix}"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── Death Coil ────────────────────────────────────────────────────────────
    elif sname == "Death Coil":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken  = _deal(attacker, defender, dmg)
            detail = f"{sname}: {taken} dmg"
            if attacker.passive_name == "Toxic Touch":
                extra   = defender.take_damage(20)
                detail += f" + {extra} bonus poison"
            events.append(base_event(damage=taken, crit=is_crit, evaded=False, detail=detail))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    # ── Healing Touch (Atom Eve secondary) ───────────────────────────────────────
    # Targets an ally. Heals them for a % of Eve's ATK. No damage.
    elif sname == "Healing Touch":
        # When targeting an ally, defender IS the ally
        heal_amt = int(attacker.effective_atk() * (_smult if _smult else 1.5))
        actual   = defender.heal(heal_amt)
        events.append(base_event(damage=0, crit=False, evaded=False, heal=actual,
            detail=f"Healing Touch: {attacker.name} restores {actual} HP to {defender.name}!"))

    # ── Molecular Shield (Atom Eve tertiary) ──────────────────────────────────
    # Gives ally a damage-reduction effect for 2 turns.
    elif sname == "Molecular Shield":
        defender.add_effect(StatusEffect("atk_down", -0.20, 2))  # negative = defence buff
        events.append(base_event(damage=0, crit=False, evaded=False,
            detail=f"Molecular Shield: {defender.name} is shielded! (-20% incoming dmg for 2 turns)"))

    # ── Speed Aura (Allen secondary) ──────────────────────────────────────────
    # Boosts an ally's SPD for 2 turns.
    elif sname == "Speed Aura":
        defender.spd = min(12, defender.spd + 3)
        events.append(base_event(damage=0, crit=False, evaded=False,
            detail=f"Speed Aura: {defender.name} gains +3 SPD for this battle!"))

    # ── Rallying Cry (Omni-Man secondary) ─────────────────────────────────────
    # Grants energy to an ally so they can use their skill sooner.
    elif sname == "Rallying Cry":
        energy_grant = 30
        defender.gain_energy(energy_grant)
        events.append(base_event(damage=0, crit=False, evaded=False,
            detail=f"Rallying Cry: {defender.name} gains {energy_grant} energy!"))

    # ── Satellite Network (Cecil secondary) ───────────────────────────────────
    # Heals the most injured ally.
    elif sname == "Satellite Network":
        heal_amt = int(attacker.effective_atk() * 1.0)
        actual   = defender.heal(heal_amt)
        events.append(base_event(damage=0, crit=False, evaded=False, heal=actual,
            detail=f"Satellite Network: Medical drone heals {defender.name} for {actual} HP!"))

    # ── Fear Aura (Homelander secondary) ──────────────────────────────────────
    # ATK debuff on ALL enemies (targets one, aura hits all).
    elif sname == "Fear Aura":
        # defender is the primary target but we also affect attacker's team's opponents
        dmg, is_crit = calc_damage(attacker, defender, _smult or 0.8)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"Fear Aura: {taken} dmg + ATK -10% (intimidated)"))
        defender.add_effect(StatusEffect("atk_down", 0.10, 2))

    # ── Heat Burst (Superman secondary) ──────────────────────────────────────
    # AoE — hits all enemies for reduced damage.
    elif sname == "Heat Burst":
        total = 0
        for opp in ([defender] if skill_target != "aoe" else []):
            dmg, _ = calc_damage(attacker, opp, _smult or 1.0, ignore_def_pct=0.5)
            taken  = _deal(attacker, opp, dmg)
            total += taken
        events.append(base_event(damage=total, crit=False, evaded=False,
            detail=f"Heat Burst: {total} thermal dmg!"))

    # ── Wonder Block (Wonder Woman secondary) ─────────────────────────────────
    # Gives ally a stun-immunity shield and heals them.
    elif sname == "Wonder Block":
        heal_amt = int(attacker.effective_atk() * 0.8)
        actual   = defender.heal(heal_amt)
        # Immunity implemented as removing any stunned effect
        defender.effects = [e for e in defender.effects if e.name != "stunned"]
        events.append(base_event(damage=0, crit=False, evaded=False, heal=actual,
            detail=f"Wonder Block: {defender.name} healed {actual} HP + stun cleared!"))

    # ── Dark Pact (Void Queen secondary) ──────────────────────────────────────
    # Self-drains HP to gain a massive energy burst.
    elif sname == "Dark Pact":
        cost_hp = int(attacker.max_hp * 0.10)
        attacker.hp = max(1, attacker.hp - cost_hp)
        attacker.gain_energy(40)
        events.append(base_event(damage=0, crit=False, evaded=False,
            detail=f"Dark Pact: {attacker.name} sacrifices {cost_hp} HP for +40 energy!"))

    # ── Batarang Storm (Batman secondary) ─────────────────────────────────────
    # Multi-hit lower damage, each hit has independent crit roll.
    elif sname == "Batarang Storm":
        total, any_crit = 0, False
        for _ in range(3):
            dmg, is_c = calc_damage(attacker, defender, (_smult or 0.6))
            if not roll_evade(defender):
                taken  = _deal(attacker, defender, dmg)
                total += taken
                any_crit = any_crit or is_c
        events.append(base_event(damage=total, crit=any_crit, evaded=total == 0,
            detail=f"Batarang Storm: {total} total dmg from 3 throws!"))

    # ── Generic fallback (any unrecognised skill name) ─────────────────────────
    else:
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(damage=taken, crit=is_crit, evaded=False,
                detail=f"{sname}: {taken} dmg"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail=f"{sname}: evaded!"))

    attacker.skill_mult = _orig_mult  # restore
    return events


# ── Basic attack ──────────────────────────────────────────────────────────────

def resolve_basic_attack(
    attacker: BattleFighter,
    defender: BattleFighter,
) -> list[dict]:
    """1.0× attack with passive effects applied."""
    events: list[dict] = []

    def base_event(**kwargs) -> dict:
        return {
            "actor":      attacker.name,
            "actor_team": "player" if attacker.is_player else "enemy",
            "target":     defender.name,
            "action":     "attack",
            **kwargs,
        }

    dmg, is_crit = calc_damage(attacker, defender, 1.0)

    if roll_evade(defender):
        events.append(base_event(damage=0, crit=False, evaded=True,
            detail=f"{attacker.name} attacks — evaded!"))
        return events

    # Steel Skin: -8% incoming damage
    if defender.passive_name == "Steel Skin":
        dmg = max(1, int(dmg * 0.92))

    # Zenithian Physiology (Allen): -15% incoming damage
    if defender.passive_name == "Zenithian Physiology":
        dmg = max(1, int(dmg * 0.85))

    # Bracelets of Submission (Wonder Woman): attacker takes 20% of dmg back
    reflect_dmg = 0
    if defender.passive_name == "Bracelets of Submission":
        reflect_dmg = max(1, int(dmg * 0.20))

    taken  = _deal(attacker, defender, dmg)
    detail = f"{attacker.name} attacks for {taken} dmg"

    # Toxic Touch: poison on hit
    if attacker.passive_name == "Toxic Touch":
        defender.add_effect(StatusEffect("poisoned", 5, 3))
        detail += " (poisoned!)"

    if is_crit:
        detail += " (CRIT!)"

    events.append(base_event(damage=taken, crit=is_crit, evaded=False, detail=detail))

    # Speed Force (Flash): 20% chance to act twice — grant bonus energy to simulate
    if attacker.passive_name == "Speed Force" and random.randint(1, 100) <= 20:
        attacker.gain_energy(ENERGY_SKILL_COST)
        events.append(base_event(damage=0, crit=False, evaded=False,
            detail=f"Speed Force: {attacker.name} moves again! (energy restored)"))

    # Bracelets reflect
    if reflect_dmg > 0 and attacker.is_alive:
        attacker.hp = max(0, attacker.hp - reflect_dmg)
        if attacker.hp == 0:
            attacker.is_alive = False
        events.append({
            "actor":      defender.name,
            "actor_team": "player" if defender.is_player else "enemy",
            "target":     attacker.name,
            "action":     "passive",
            "damage":     reflect_dmg,
            "detail":     f"Bracelets of Submission: {reflect_dmg} reflected back!",
        })

    return events


# ── Internal helper ───────────────────────────────────────────────────────────

def _deal(attacker: BattleFighter, defender: BattleFighter, dmg: int) -> int:
    """
    Apply damage to defender, grant energy to attacker, return actual damage taken.
    Single helper so energy gain is never forgotten.
    """
    taken = defender.take_damage(dmg)
    attacker.gain_energy(ENERGY_ON_DEAL)
    return taken


# ── AI decision ───────────────────────────────────────────────────────────────

def ai_choose_action(
    fighter: BattleFighter,
    player_team: list[BattleFighter],
) -> tuple[Literal["skill", "attack"], int]:
    """
    Focus-fire the lowest HP% player fighter.
    Uses skill when energy allows.
    """
    alive = [(i, f) for i, f in enumerate(player_team) if f.is_alive]
    if not alive:
        return "attack", 0
    target_idx, _ = min(alive, key=lambda t: t[1].hp / t[1].max_hp)
    action = "skill" if fighter.can_use_skill() else "attack"
    return action, target_idx


# ── Main entry point ──────────────────────────────────────────────────────────

def resolve_action(
    state: BattleState,
    actor_team: str,
    actor_idx: int,
    action_type: Literal["skill", "attack"],
    target_idx: int,
    skill_index: int = 0,
) -> tuple[BattleState, list[dict]]:
    """
    Resolve one fighter's full turn.
    skill_index selects which skill to use (0 = primary, 1 = secondary, 2 = tertiary).
    target_idx selects target in the opposing team.
    For ally-targeting skills, target_idx refers to the friendly team instead.
    """
    all_events: list[dict] = []

    actor   = state.player_team[actor_idx] if actor_team == "player" else state.enemy_team[actor_idx]
    targets = state.enemy_team             if actor_team == "player" else state.player_team

    if not actor.is_alive:
        state.advance_queue()
        return state, []

    # 1. Start-of-turn passives
    opp_team = state.enemy_team if actor_team == "player" else state.player_team
    all_events.extend(apply_start_of_turn_passives(actor, opp_team))

    if not actor.is_alive:
        state.advance_queue()
        return state, all_events

    # 2. Stun check
    if actor.is_stunned():
        all_events.append({
            "actor":      actor.name,
            "actor_team": actor_team,
            "action":     "stunned",
            "detail":     f"{actor.name} is stunned and loses their turn!",
            "damage":     0,
        })
        state.advance_queue()
        return state, all_events

    # 3. Validate & fix target index
    alive_targets = [f for f in targets if f.is_alive]
    if not alive_targets:
        state.advance_queue()
        return state, all_events

    target_idx = min(target_idx, len(targets) - 1)
    if not targets[target_idx].is_alive:
        target_idx = next(i for i, f in enumerate(targets) if f.is_alive)
    target = targets[target_idx]

    # 4. Resolve skill selection and energy check
    chosen_skill = None
    if action_type == "skill":
        # Clamp skill_index to available skills
        skill_index = max(0, min(skill_index, len(actor.skills) - 1))
        if actor.skills:
            chosen_skill = actor.skills[skill_index]
        if not actor.can_use_skill(skill_index):
            action_type = "attack"
            sname = chosen_skill.name if chosen_skill else actor.skill_name
            all_events.append({
                "actor":      actor.name,
                "actor_team": actor_team,
                "action":     "info",
                "detail":     f"Not enough energy for {sname} — basic attack instead.",
                "damage":     0,
            })
            chosen_skill = None

    # 5. Handle ally-targeting skills (target is friendly team, not enemy)
    if action_type == "skill" and chosen_skill and chosen_skill.target == "ally":
        friendly_team = state.player_team if actor_team == "player" else state.enemy_team
        ally_idx  = min(target_idx, len(friendly_team) - 1)
        # If chosen ally is dead, pick first alive friendly
        if not friendly_team[ally_idx].is_alive:
            alive_allies = [i for i, f in enumerate(friendly_team) if f.is_alive]
            ally_idx = alive_allies[0] if alive_allies else ally_idx
        ally_target = friendly_team[ally_idx]
        actor.spend_energy(chosen_skill.energy_cost)
        all_events.extend(resolve_skill(
            actor, ally_target,
            skill_name=chosen_skill.name,
            skill_mult=chosen_skill.mult,
            skill_target=chosen_skill.target,
        ))
    # 5b. Normal skill (enemy target) or basic attack
    elif action_type == "skill" and chosen_skill:
        actor.spend_energy(chosen_skill.energy_cost)
        all_events.extend(resolve_skill(
            actor, target,
            skill_name=chosen_skill.name,
            skill_mult=chosen_skill.mult,
            skill_target=chosen_skill.target,
        ))
    else:
        all_events.extend(resolve_basic_attack(actor, target))

    # 6. Check over + advance queue
    state.is_over()
    state.advance_queue()

    return state, all_events