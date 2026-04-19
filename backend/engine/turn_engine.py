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
    # פסיבי של ת'ראג - כוח עולה כשהחיים יורדים (נבדק בחישוב נזק)
    if fighter.passive_name == "thragg":
        hp_missing_pct = (1 - (fighter.hp / fighter.max_hp)) * 100
        atk_bonus = (hp_missing_pct // 5) * 0.02
        # את הבונוס הזה כדאי להוסיף זמנית ל-atk_mult בחישוב הנזק

    return events


# ── Skill resolution ──────────────────────────────────────────────────────────

def resolve_skill(
    attacker: BattleFighter,
    defender: BattleFighter,
    skill_name: str | None = None,
    skill_mult: float | None = None,
    skill_target: str = "enemy",
    all_targets: list | None = None,
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
# ── Primal Rage (Monster Girl) ──────────────────────────────────────────────
    elif sname == "Primal Rage":
        # 1. חישוב הנזק לפי המולטיפלייר (2.8)
        dmg, is_crit = calc_damage(attacker, defender, _smult)
        
        if not roll_evade(defender):
            # 2. גרימת הנזק לאויב
            taken = _deal(attacker, defender, dmg)
            
            # 3. חישוב הנזק העצמי (חצי מהנזק שנגרם בפועל)
            recoil = int(taken * 0.1)
            attacker.hp -= recoil
            if attacker.hp < 1: attacker.hp = 1  # מונע מוות עצמי
            
            events.append(base_event(
                damage=taken, 
                crit=is_crit, 
                evaded=False,
                detail=f"{sname}:{attacker.name} Deals {taken} dmg to {defender.name}, but {attacker.name} loses {recoil} HP from recoil!"
            ))
        else:
            # אם האויב התחמק, היא לא עושה נזק ולא מקבלת נזק עצמי
            events.append(base_event(
                damage=0, 
                crit=False, 
                evaded=True,
                detail=f"{sname}: Evaded! No damage dealt or taken."
            ))
    # ── World-Class Execution (Omni-Man) ──────────────────────────────────────
    # Ignores all DEF. Below 40% HP → 1.5× execute multiplier.
    elif sname == "World-Class Execution":
        is_execute = defender.hp < defender.max_hp * 0.40
        mult       = attacker.skill_mult * (1.5 if is_execute else 1.0)
        dmg, is_crit = calc_damage(attacker, defender, mult, ignore_def_pct=1.0)
        if not roll_evade(defender):
            taken  = _deal(attacker, defender, dmg)
            detail = f"{sname}: {defender.name} hurts {taken} pure dmg!" + (" (EXECUTE!)" if is_execute else "")
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
    # Damage + restore 150% of damage dealt as HP.
    elif sname == "Molecular Manipulation":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken      = _deal(attacker, defender, dmg)
            healed     = attacker.heal(int(taken * 1.50))
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
        defender.add_effect(StatusEffect("atk_down", -0.50, 2))  # negative = defence buff
        events.append(base_event(damage=0, crit=False, evaded=False,
            detail=f"Molecular Shield: {defender.name} is shielded! (-50% incoming dmg for 2 turns)"))

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
        heal_amt = int(attacker.effective_atk() * 4.0)
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
# ── Grand Regent's Might (Thragg) ──────────────────────────────────────────
    elif sname == "Grand Regent's Might":
        dmg, is_crit = calc_damage(attacker, defender, _smult) # _smult יהיה 3.5 מה-Seed
        
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            
            # סיכוי של 20% לשתק את האויב (Stun)
            import random
            is_stunned = random.random() < 0.2
            if is_stunned:
                defender.add_effect(StatusEffect("stunned", 0, 1))
            
            detail_msg = f"{sname}: Deals {taken} dmg!"
            if is_stunned: detail_msg += " + STUNNED the target!"
            
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=detail_msg
            ))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True, detail=f"{sname}: Evaded!"))
    # ── Unibeam (Iron Man - Single Target Burst) ──────────────────────────────
    elif sname == "Unibeam":
        # נזק עוצמתי מאוד למטרה אחת, מתעלם מחלק מההגנה (Defense Pierce)
        effective_mult = _smult * 1.2 # בונוס פנימי ל-Unibeam
        dmg, is_crit = calc_damage(attacker, defender, effective_mult)
        
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            
            # אפקט משני: צריבה (Burn)
            defender.add_effect(StatusEffect("burned", 0.05, 2))
            
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Unibeam: {attacker.name} fires a massive chest beam at {defender.name}!"
            ))
        else:
            events.append(base_event(attacker, defender, damage=0, crit=False, evaded=True, detail="Unibeam: Missed!"))

    # ── Micro-Missile Barrage (Iron Man) — AoE + ATK-down on all enemies ────────
    elif sname == "Micro-Missile Barrage":
        targets_to_hit = [t for t in (all_targets or [defender]) if t.is_alive]
        total, any_crit = 0, False
        for opp in targets_to_hit:
            dmg, is_c = calc_damage(attacker, opp, _smult or 1.0)
            if not roll_evade(opp):
                taken      = _deal(attacker, opp, dmg)
                total     += taken
                any_crit   = any_crit or is_c
                opp.add_effect(StatusEffect("atk_down", 0.15, 2))
        hit_count = len(targets_to_hit)
        events.append(base_event(
            damage=total, crit=any_crit, evaded=False, is_aoe=True,
            detail=f"Micro-Missile Barrage: {total} dmg across {hit_count} target{'s' if hit_count != 1 else ''}! ATK -15% applied."))
    # ── Mjolnir's Strike (Thor) — primary target full dmg, splash 50% to others ─
        # ── One Punch (Saitama primary) — ignores DEF, cannot miss ─────────────────
    elif sname == "One Punch":
        dmg, is_crit = calc_damage(attacker, defender, _smult, ignore_def_pct=1.0, force_crit=False)
        # Cannot miss — skip roll_evade entirely
        taken = _deal(attacker, defender, dmg)
        events.append(base_event(
            damage=taken, crit=is_crit, evaded=False,
            detail=f"One Punch: {taken} dmg — unstoppable!"))
 
    # ── Serious Series: Serious Punch (Saitama tertiary) — maximum output ─────
    elif sname == "Serious Series: Serious Punch":
        dmg, is_crit = calc_damage(attacker, defender, _smult, ignore_def_pct=1.0, force_crit=True)
        taken = _deal(attacker, defender, dmg)
        events.append(base_event(
            damage=taken, crit=True, evaded=False,
            detail=f"Serious Punch: {taken} dmg — Saitama stopped holding back!"))
 
    # ── Kamehameha (Goku primary) — beam ignoring 40% DEF ────────────────────
    elif sname == "Kamehameha":
        dmg, is_crit = calc_damage(attacker, defender, _smult, ignore_def_pct=0.40)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Kamehameha: {taken} dmg! KA-ME-HA-ME-HA!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Kamehameha: Dodged!"))
 
    # ── Instant Transmission (Goku secondary) — guaranteed crit ──────────────
    elif sname == "Instant Transmission":
        dmg, is_crit = calc_damage(attacker, defender, _smult, force_crit=True)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(
                damage=taken, crit=True, evaded=False,
                detail=f"Instant Transmission: {taken} dmg — Goku teleports in!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True, detail="Too fast!"))
 
    # ── Spirit Bomb (Goku tertiary) — AoE ignoring 30% DEF ───────────────────
    elif sname == "Spirit Bomb":
        targets_to_hit = [t for t in (all_targets or [defender]) if t.is_alive]
        total, any_crit = 0, False
        for opp in targets_to_hit:
            dmg, is_c = calc_damage(attacker, opp, _smult, ignore_def_pct=0.30)
            if not roll_evade(opp):
                taken = _deal(attacker, opp, dmg)
                total += taken; any_crit = any_crit or is_c
        events.append(base_event(
            damage=total, crit=any_crit, evaded=False, is_aoe=True,
            detail=f"Spirit Bomb: {total} dmg across {len(targets_to_hit)} enemies!"))
 
    # ── Magnetic Crush (Magneto primary) — bonus vs Tech ─────────────────────
    elif sname == "Magnetic Crush":
        is_tech      = defender.element == "Tech"
        bonus_mult   = _smult * 1.40 if is_tech else _smult
        dmg, is_crit = calc_damage(attacker, defender, bonus_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("atk_down", 0.20, 2))
            suffix = " (METAL VULNERABILITY!)" if is_tech else ""
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Magnetic Crush: {taken} dmg{suffix} + ATK-down 2 turns!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Magnetic Crush: Evaded!"))
 
    # ── Metal Storm (Magneto secondary) — AoE + stun for Tech enemies ────────
    elif sname == "Metal Storm":
        targets_to_hit = [t for t in (all_targets or [defender]) if t.is_alive]
        total, any_crit = 0, False
        for opp in targets_to_hit:
            is_tech      = opp.element == "Tech"
            bonus_mult   = _smult * 1.40 if is_tech else _smult
            dmg, is_c    = calc_damage(attacker, opp, bonus_mult)
            if not roll_evade(opp):
                taken = _deal(attacker, opp, dmg)
                total += taken; any_crit = any_crit or is_c
                if is_tech:
                    opp.add_effect(StatusEffect("stunned", 1.0, 1))
        events.append(base_event(
            damage=total, crit=any_crit, evaded=False, is_aoe=True,
            detail=f"Metal Storm: {total} dmg! Tech enemies stunned!"))
 
    # ── Magnetic Fortress (Magneto tertiary) — DEF shield for ally ───────────
    elif sname == "Magnetic Fortress":
        # Gives ally a significant DEF boost (modelled as negative atk_down = def up)
        defender.add_effect(StatusEffect("atk_down", -0.30, 2))
        events.append(base_event(
            damage=0, crit=False, evaded=False,
            detail=f"Magnetic Fortress: {defender.name} shielded by metal barrier! +30% DEF for 2 turns."))
 
    # ── Widow's Bite (Black Widow primary) — guaranteed crit + stun ──────────
    elif sname == "Widow's Bite":
        # Red Room Training passive: crits deal 2.0× instead of 1.5×
        # Temporarily patch crit multiplier for this hit
        dmg, is_crit = calc_damage(attacker, defender, _smult, force_crit=True)
        if attacker.passive_name == "Red Room Training":
            # Undo 1.5× crit that calc_damage applied, reapply at 2.0×
            base_dmg = int(dmg / 1.5)
            dmg      = int(base_dmg * 2.0)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("stunned", 1.0, 1))
            events.append(base_event(
                damage=taken, crit=True, evaded=False,
                detail=f"Widow's Bite: {taken} dmg (2× crit)! Target stunned!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Widow's Bite: Evaded!"))
 
    # ── Tactical Takedown (Black Widow secondary) ─────────────────────────────
    elif sname == "Tactical Takedown":
        dmg, is_crit = calc_damage(attacker, defender, _smult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("atk_down", 0.25, 2))
            defender.add_effect(StatusEffect("spd_down", 3,    2))
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Tactical Takedown: {taken} dmg + ATK-down + SPD-down 2 turns!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True,
                detail="Tactical Takedown: Evaded!"))
    elif sname == "Mjolnir's Strike":
        total_dmg = 0
        # Primary target: full 2.8× hit
        dmg, is_crit = calc_damage(attacker, defender, _smult)
        if not roll_evade(defender):
            taken      = _deal(attacker, defender, dmg)
            total_dmg += taken
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False, is_aoe=True,
                detail=f"{sname}: {defender.name} takes {taken} dmg from Mjolnir!"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True, detail=f"{sname}: Evaded!"))
        # Splash: all other alive enemies take 50% dmg (lightning arc)
        splash_targets = [t for t in (all_targets or []) if t.is_alive and t is not defender]
        for opp in splash_targets:
            splash_dmg, _ = calc_damage(attacker, opp, _smult * 0.5)
            if not roll_evade(opp):
                taken      = _deal(attacker, opp, splash_dmg)
                total_dmg += taken
                events.append({
                    "actor":      attacker.name,
                    "actor_team": "player" if attacker.is_player else "enemy",
                    "target":     opp.name,
                    "action":     "skill",
                    "is_aoe":     True,
                    "damage":     taken, "crit": False, "evaded": False,
                    "detail":     f"Lightning Arc: {opp.name} takes {taken} splash dmg!",
                })
    # ── Gamma Slam (Hulk primary) — scales with missing HP ──────────────────────
    elif sname == "Gamma Slam":
        hp_missing_pct = 1.0 - (attacker.hp / attacker.max_hp)
        rage_bonus     = 1.0 + hp_missing_pct  # up to 2× at 0% HP
        effective_mult = _smult * rage_bonus
        dmg, is_crit   = calc_damage(attacker, defender, effective_mult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Gamma Slam: {taken} dmg! ({int(hp_missing_pct*100)}% rage bonus)"))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True, detail="Gamma Slam: Evaded!"))
 
    # ── Thunderclap (Hulk secondary) — AoE stun ──────────────────────────────
    elif sname == "Thunderclap":
        targets_to_hit = [t for t in (all_targets or [defender]) if t.is_alive]
        total, any_crit = 0, False
        for opp in targets_to_hit:
            dmg, is_c = calc_damage(attacker, opp, _smult or 0.8)
            if not roll_evade(opp):
                taken      = _deal(attacker, opp, dmg)
                total     += taken
                any_crit   = any_crit or is_c
                opp.add_effect(StatusEffect("stunned", 1.0, 1))
        events.append(base_event(
            damage=total, crit=any_crit, evaded=False, is_aoe=True,
            detail=f"Thunderclap: {total} dmg to all! All targets STUNNED!"))
 
    # ── Web Shot (Spider-Man primary) — single target + SPD debuff ───────────
    elif sname == "Web Shot":
        dmg, is_crit = calc_damage(attacker, defender, _smult)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("spd_down", 4, 2))
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Web Shot: {taken} dmg, {defender.name} is webbed! SPD -4 for 2 turns."))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True, detail="Web Shot: Evaded!"))
 
    # ── Web Barrage (Spider-Man secondary) — AoE web, SPD-down all ───────────
    elif sname == "Web Barrage":
        targets_to_hit = [t for t in (all_targets or [defender]) if t.is_alive]
        total, any_crit = 0, False
        for opp in targets_to_hit:
            dmg, is_c = calc_damage(attacker, opp, _smult or 0.9)
            if not roll_evade(opp):
                taken      = _deal(attacker, opp, dmg)
                total     += taken
                any_crit   = any_crit or is_c
                opp.add_effect(StatusEffect("spd_down", 3, 2))
        events.append(base_event(
            damage=total, crit=any_crit, evaded=False, is_aoe=True,
            detail=f"Web Barrage: {total} dmg across all! Everyone is webbed (-SPD)!"))
 
    # ── Compound V Blast (Soldier Boy primary) — DEF ignore + ATK shred ──────
    elif sname == "Compound V Blast":
        dmg, is_crit = calc_damage(attacker, defender, _smult, ignore_def_pct=0.6)
        if not roll_evade(defender):
            taken = _deal(attacker, defender, dmg)
            defender.add_effect(StatusEffect("atk_down", 0.25, 2))
            events.append(base_event(
                damage=taken, crit=is_crit, evaded=False,
                detail=f"Compound V Blast: {taken} dmg (60% DEF ignored)! Target ATK -25% for 2 turns."))
        else:
            events.append(base_event(damage=0, crit=False, evaded=True, detail="Compound V Blast: Evaded!"))
 
    # ── Soldier's Fury (Soldier Boy secondary) — 4-hit burst ─────────────────
    elif sname == "Soldier's Fury":
        total, any_crit = 0, False
        for hit in range(1, 5):
            dmg, is_c = calc_damage(attacker, defender, _smult or 0.5)
            if not roll_evade(defender):
                taken      = _deal(attacker, defender, dmg)
                total     += taken
                any_crit   = any_crit or is_c
        events.append(base_event(
            damage=total, crit=any_crit, evaded=total == 0,
            detail=f"Soldier's Fury: 4-hit burst for {total} total dmg!"))
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
 
def _score_target(attacker: BattleFighter, target: BattleFighter) -> float:
    """
    Score how good a target is for the attacker.
    Higher score = better target to attack.
    
    Weights:
      40% — threat elimination  (how much damage can target deal? ATK/max_hp proxy)
      30% — finishing blow      (is target close to dying?)
      20% — element advantage   (does attacker have type advantage?)
      10% — random noise        (prevents perfectly predictable behaviour)
    
    Each component is normalised to [0, 1] before weighting.
    """
    # ── Component 1: finishing blow opportunity (0–1) ─────────────────────────
    hp_pct        = target.hp / target.max_hp          # 0 = almost dead, 1 = full
    finish_score  = 1.0 - hp_pct                       # high when enemy is low HP
 
    # ── Component 2: threat level (0–1) ───────────────────────────────────────
    # A target that has high ATK relative to HP is dangerous — eliminate it first.
    # Normalise ATK to a 0–1 proxy using a soft cap of 300.
    threat_score  = min(1.0, target.effective_atk() / 300.0)
    # Bonus: if target has a skill available (energy >= cost), it's more urgent
    if target.skills and target.energy >= target.skills[0].energy_cost:
        threat_score = min(1.0, threat_score * 1.25)
 
    # ── Component 3: element advantage (0–1) ──────────────────────────────────
    from engine.element_system import element_multiplier
    elem_mult    = element_multiplier(attacker.element, target.element)
    # Map 0.80→0, 1.00→0.5, 1.15→0.75, 1.30→1.0
    elem_score   = max(0.0, (elem_mult - 0.80) / 0.50)
 
    # ── Component 4: random noise (0–1) ───────────────────────────────────────
    noise = random.random()
 
    # ── Weighted sum ──────────────────────────────────────────────────────────
    score = (
        0.30 * finish_score +
        0.40 * threat_score +
        0.20 * elem_score   +
        0.10 * noise
    )
    return score
 
 
def _choose_ai_skill(fighter: BattleFighter, player_team: list[BattleFighter]) -> int:
    """
    Choose which skill index the AI should use.
    
    Logic:
      - If only one skill available, always use it (index 0).
      - If AoE skill is available and multiple targets are alive, prefer it.
      - If an ally-heal skill is available and a teammate is below 40% HP, use it.
      - Otherwise weight skill choice by effectiveness against the situation.
    """
    available = [
        (i, s) for i, s in enumerate(fighter.skills)
        if fighter.energy >= s.energy_cost
    ]
    if not available:
        return 0
 
    # Count alive enemies (for AoE decision)
    alive_enemies_count = sum(1 for f in player_team if f.is_alive)
 
    # Prefer AoE when multiple targets alive
    for i, s in available:
        if s.target == "aoe" and alive_enemies_count >= 2:
            return i
 
    # Use highest-mult damage skill by default (greedy)
    damage_skills = [(i, s) for i, s in available if s.target in ("enemy", "aoe")]
    if damage_skills:
        best_idx, _ = max(damage_skills, key=lambda x: x[1].mult)
        return best_idx
 
    return available[0][0]
 
 
def ai_choose_action(
    fighter: BattleFighter,
    player_team: list[BattleFighter],
) -> tuple[Literal["skill", "attack"], int]:
    """
    Smart AI that scores targets by threat, HP, element advantage, and noise.
    
    Personality is derived from the fighter's passive:
      - Aggressive (God Complex, Dark Throne, Rage Engine):  prioritise finish score more
      - Defensive  (Steel Skin, Zenithian Physiology):       prioritise threat elimination
      - Default:   balanced weights via _score_target
    """
    alive = [(i, f) for i, f in enumerate(player_team) if f.is_alive]
    if not alive:
        return "attack", 0
 
    # Personality modifier: some passives shift priorities
    aggressive_passives = {"God Complex", "Dark Throne", "Rage Engine", "Grand Regent"}
    defensive_passives  = {"Steel Skin", "Zenithian Physiology", "Prep Time"}
 
    if fighter.passive_name in aggressive_passives:
        # Aggressive: weight finish score harder — go for kills
        scores = []
        for i, t in alive:
            hp_pct       = t.hp / t.max_hp
            finish_score = 1.0 - hp_pct
            elem_mult    = element_multiplier(fighter.element, t.element)
            elem_score   = max(0.0, (elem_mult - 0.80) / 0.50)
            noise        = random.random() * 0.15   # less noise = more decisive
            score        = 0.55 * finish_score + 0.25 * elem_score + 0.20 * noise
            scores.append((i, score))
 
    elif fighter.passive_name in defensive_passives:
        # Defensive/tactical: target the highest-threat enemy first
        scores = []
        for i, t in alive:
            threat_score = min(1.0, t.effective_atk() / 300.0)
            elem_score   = max(0.0, (element_multiplier(fighter.element, t.element) - 0.80) / 0.50)
            noise        = random.random() * 0.20
            score        = 0.50 * threat_score + 0.30 * elem_score + 0.20 * noise
            scores.append((i, score))
 
    else:
        # Balanced: use full _score_target
        scores = [(i, _score_target(fighter, t)) for i, t in alive]
 
    # Pick the highest-scoring target
    target_idx, _ = max(scores, key=lambda x: x[1])
 
    # Choose action and skill
    if fighter.can_use_skill():
        skill_idx = _choose_ai_skill(fighter, player_team)
        return "skill", target_idx
    return "attack", target_idx


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
        # For AoE skills pass the entire opposing team so resolve_skill can hit all
        aoe_targets = targets if chosen_skill.target == "aoe" else None
        all_events.extend(resolve_skill(
            actor, target,
            skill_name=chosen_skill.name,
            skill_mult=chosen_skill.mult,
            skill_target=chosen_skill.target,
            all_targets=aoe_targets,
        ))
    else:
        all_events.extend(resolve_basic_attack(actor, target))
 
    # 6. Check over + advance queue
    state.is_over()
    state.advance_queue()
 
    return state, all_events