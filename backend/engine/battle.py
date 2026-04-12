"""
engine/battle.py
----------------
Pure Python auto-battle simulator. Zero DB dependency.

THE KEY FIX (Gemini was correct):
  Every TurnEvent needs p_hp = player's HP and e_hp = enemy's HP,
  regardless of who is currently the attacker or defender.
  The old code used p_hp=attacker.hp / e_hp=defender.hp, which
  SWAPPED the values every time the enemy took a turn.

  Fix: Fighter gets an `is_player` flag. A single helper `_hp()`
  always resolves the correct player/enemy HP from any two fighters.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Fighter:
    id:            str
    name:          str
    faction:       str
    hp:            int
    max_hp:        int
    atk:           int
    defense:       int
    spd:           int
    crit:          int
    evade:         int
    passive_name:  str
    passive_desc:  str
    skill_name:    str
    skill_desc:    str
    skill_mult:    float
    skill_cd:      int
    skill_current_cd: int  = 0
    is_player:     bool    = False  # THE FIX: marks the human player's fighter
    poison_dmg:       int   = 0
    poison_turns:     int   = 0
    atk_debuff:       float = 0.0
    atk_debuff_turns: int   = 0
    spd_debuff:       int   = 0
    void_charges:     int   = 0
    portrait_id: str= "default"

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        actual = max(1, amount)
        self.hp = max(0, self.hp - actual)
        return actual

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def effective_atk(self) -> int:
        return max(1, int(self.atk * (1.0 - self.atk_debuff)))

    def effective_spd(self) -> int:
        return max(1, self.spd - self.spd_debuff)


@dataclass
class TurnEvent:
    turn:   int
    actor:  str
    action: str
    detail: str
    damage: int  = 0
    heal:   int  = 0
    crit:   bool = False
    evaded: bool = False
    p_hp:   int  = 0   # ALWAYS the human player's HP
    e_hp:   int  = 0   # ALWAYS the enemy's HP


@dataclass
class BattleResult:
    outcome:      Literal["win", "loss", "draw"]
    turns:        int
    log:          list[TurnEvent] = field(default_factory=list)
    coins_earned: int = 0
    xp_earned:    int = 0

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome, "turns": self.turns,
            "coins_earned": self.coins_earned, "xp_earned": self.xp_earned,
            "log": [
                {"turn": e.turn, "actor": e.actor, "action": e.action,
                 "detail": e.detail, "damage": e.damage, "heal": e.heal,
                 "crit": e.crit, "evaded": e.evaded, "p_hp": e.p_hp, "e_hp": e.e_hp}
                for e in self.log
            ],
        }


# ------------------------------------------------------------------ #
#  THE CORE FIX: canonical HP resolver                                #
# ------------------------------------------------------------------ #

def _hp(a: Fighter, b: Fighter) -> tuple[int, int]:
    """
    Given any two fighters (in any order), return (player_hp, enemy_hp).
    
    Before: p_hp=attacker.hp swapped every enemy turn — ROOT CAUSE of the bug.
    After:  this function always finds which fighter has is_player=True
            and returns their HP first, regardless of turn order.
    """
    if a.is_player:
        return a.hp, b.hp
    else:
        return b.hp, a.hp


# ------------------------------------------------------------------ #
#  Fighter factory                                                     #
# ------------------------------------------------------------------ #

def make_fighter(pc: dict | None, char: dict, is_player: bool = False) -> Fighter:
    if pc:
        return Fighter(
            id=str(pc["id"]),
            name=char["name"], faction=char["faction"],
            hp=pc["hp"], max_hp=pc["hp"],
            atk=pc["atk"], defense=pc["def"],
            spd=pc["spd"], crit=pc["crit"], evade=pc["evade"],
            passive_name=char["passive_name"], passive_desc=char["passive_desc"],
            skill_name=char["skill_name"], skill_desc=char["skill_desc"],
            skill_mult=char["skill_mult"], skill_cd=char["skill_cd"],
            is_player=is_player,
            portrait_id=str(char.get("portrait_id", "default")),
            
        )
    else:
        return Fighter(
            id=str(char.get("id", char.get("_id", ""))),
            name=char["name"], faction=char["faction"],
            hp=char["base_hp"], max_hp=char["base_hp"],
            atk=char["base_atk"], defense=char["base_def"],
            spd=char["base_spd"], crit=char["base_crit"], evade=char["base_evade"],
            passive_name=char["passive_name"], passive_desc=char["passive_desc"],
            skill_name=char["skill_name"], skill_desc=char["skill_desc"],
            skill_mult=char["skill_mult"], skill_cd=char["skill_cd"],
            is_player=is_player,
            portrait_id=str(char.get("portrait_id", "default")),
        )


# ------------------------------------------------------------------ #
#  Damage formula                                                      #
# ------------------------------------------------------------------ #

def calc_damage(attacker, defender, mult=1.0, ignore_def_pct=0.0, force_crit=False):
    base_mult = mult
    if attacker.passive_name == "God Complex" and attacker.atk > defender.atk:
        base_mult *= 1.2
    raw     = attacker.effective_atk() * mult
    miti    = defender.defense * (1.0 - ignore_def_pct)
    dmg     = max(1.0, raw - miti)
    is_crit = force_crit or (random.randint(1, 100) <= attacker.crit)
    if is_crit:
        dmg *= 1.5
    return int(dmg), is_crit

def roll_evade(defender: Fighter) -> bool:
    return random.randint(1, 100) <= defender.evade


# ------------------------------------------------------------------ #
#  Passive / start-of-turn effects                                     #
# ------------------------------------------------------------------ #

def apply_start_of_turn(fighter: Fighter, opponent: Fighter, events: list, turn: int):
    if fighter.passive_name == "Solar Aura":
        actual = fighter.heal(max(1, int(fighter.max_hp * 0.05)))
        if actual > 0:
            p_hp, e_hp = _hp(fighter, opponent)
            events.append(TurnEvent(turn=turn, actor=fighter.name, action="passive_heal",
                detail=f"Solar Aura heals {actual} HP", heal=actual, p_hp=p_hp, e_hp=e_hp))
# --- Batman: Prep Time ---
    if fighter.passive_name == "Prep Time" and not getattr(fighter, 'prep_done', False):
        # באטמן מקריב HP בשביל Crit Rate קבוע בתחילת הקרב
        fighter.hp = int(fighter.hp * 0.8)
        fighter.crit += 20
        fighter.prep_done = True
        p_hp, e_hp = _hp(fighter, opponent)
        events.append(TurnEvent(turn=turn, actor=fighter.name, action="passive",
            detail="Prep Time: Traded HP for +20% Crit Rate!", p_hp=p_hp, e_hp=e_hp))
# בתוך לולאת הקרב, לפני או אחרי התור:
    if fighter.passive_name == "Matter Rebirth" and not getattr(fighter, 'passive_triggered', False):
        if fighter.hp < (fighter.max_hp * 0.20):
            heal_amt = int(fighter.max_hp * 0.30)
            fighter.hp = min(fighter.max_hp, fighter.hp + heal_amt)
            fighter.passive_triggered = True  # מבטיח שזה יקרה רק פעם אחת
            
            p_hp, e_hp = _hp(fighter, opponent)
            events.append(TurnEvent(
                turn=turn, actor=fighter.name, action="passive",
                detail=f"Passive {fighter.passive_name}: Eve reformed her molecules! +{heal_amt} HP",
                heal=heal_amt, p_hp=p_hp, e_hp=e_hp
            ))
    if fighter.passive_name == "Zenithian Physiology":
    # מחזק את ההגנה ב-3% באופן קבוע
        fighter.defense = int(fighter.defense * 1.03)
    if fighter.passive_name == "Gravity Well":
        opponent.spd_debuff = max(opponent.spd_debuff, 2)

    if fighter.passive_name == "Dark Throne":
        stacks = int((1.0 - fighter.hp / fighter.max_hp) / 0.20)
        fighter.atk_debuff = -stacks * 0.10  # negative = buff

    if fighter.poison_turns > 0:
        actual = fighter.take_damage(fighter.poison_dmg)
        fighter.poison_turns -= 1
        p_hp, e_hp = _hp(fighter, opponent)
        events.append(TurnEvent(turn=turn, actor=fighter.name, action="poison",
            detail=f"Poison deals {actual} damage ({fighter.poison_turns} turns left)",
            damage=actual, p_hp=p_hp, e_hp=e_hp))

    if fighter.atk_debuff_turns > 0:
        fighter.atk_debuff_turns -= 1
        if fighter.atk_debuff_turns == 0 and fighter.atk_debuff > 0:
            fighter.atk_debuff = 0.0

    if fighter.skill_current_cd > 0:
        fighter.skill_current_cd -= 1


# ------------------------------------------------------------------ #
#  Action resolution — every TurnEvent uses _hp() for correct values  #
# ------------------------------------------------------------------ #

def resolve_skill(attacker: Fighter, defender: Fighter, events: list, turn: int):

    if attacker.skill_name == "Shield Slam":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            defender.atk_debuff = max(defender.atk_debuff, 0.15)
            defender.atk_debuff_turns = max(defender.atk_debuff_turns, 2)
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg, enemy ATK -15% for 2 turns",
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))
    # --- SUPERMAN ---
    elif attacker.skill_name == "Heat Vision":
        # התעלמות מוחלטת מהגנה
        original_def = defender.defense
        defender.defense = 0
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            defender.defense = original_def # החזרת הגנה
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} pure thermal dmg!", damage=taken, p_hp=p_hp, e_hp=e_hp))
        else:
            defender.defense = original_def
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill", detail="Heat Vision missed!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    # --- THE FLASH ---
    elif attacker.skill_name == "Infinite Mass Punch":
        # נזק שמתחזק ככל שהמהירות (spd) גבוהה יותר
        spd_bonus = attacker.spd * 5 
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        dmg += spd_bonus
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg at light speed!", damage=taken, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill", detail="Flash was too fast and missed!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    # --- WONDER WOMAN ---
    elif attacker.skill_name == "Lasso of Truth":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            # אפקט Stun: מוסיף דגל ליריב שידלג על התור הבא
            defender.is_stunned = True 
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg. Target STUNNED by the lasso!", damage=taken, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill", detail="Lasso missed!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    # --- HOMELANDER ---
    elif attacker.skill_name == "Laser Eyes":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            # אפקט ייחודי: אם היריב מת מהמכה, ה-CD מתאפס (Reset)
            p_hp, e_hp = _hp(attacker, defender)
            if e_hp <= 0:
                attacker.skill_cd_current = 0 
                res_msg = " COOLDOWN RESET!"
            else:
                res_msg = ""
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg.{res_msg}", damage=taken, p_hp=p_hp, e_hp=e_hp))
    elif attacker.skill_name == "World-Class Execution":
        # אומני-מן מתעלם מהגנה (Defense Penetration)
        # אנחנו יוצרים "העתק" של הדיפנדר עם 0 הגנה רק לצורך החישוב הזה
        original_defense = defender.defense
        defender.defense = 0
        
        # חישוב נזק בסיסי (בלי הגנה)
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        
        # אפקט "הוצאה להורג": אם לאויב יש פחות מ-40% חיים, הנזק מוכפל ב-1.5
        is_execute = defender.hp < (defender.max_hp * 0.40)
        if is_execute:
            dmg = int(dmg * 1.5)
            
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            # מחזירים את ההגנה המקורית אחרי הפגיעה
            defender.defense = original_defense
            
            p_hp, e_hp = _hp(attacker, defender)
            
            detail_msg = f"{attacker.skill_name}: {taken} pure dmg!"
            if is_execute:
                detail_msg += " (EXECUTE!)"
                
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=detail_msg,
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp
            ))
        else:
            # מחזירים הגנה גם אם הוא התחמק
            defender.defense = original_defense
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: missed!", 
                evaded=True, p_hp=p_hp, e_hp=e_hp
            ))
    elif attacker.skill_name == "Molecular Manipulation":
        # איב משנה את המבנה המולקולרי: נזק לאויב + יצירת מגן
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            
            # אפקט ייחודי: היא מרפאה את עצמה ב-50% מהנזק שגרמה (כמגן)
            heal_amount = int(taken * 0.5)
            attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)
            
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg and restored {heal_amount} HP!",
                damage=taken, heal=heal_amount, crit=is_crit, p_hp=p_hp, e_hp=e_hp
            ))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: Missed!", 
                evaded=True, p_hp=p_hp, e_hp=e_hp
            ))
    elif attacker.skill_name == "Unstoppable Evolution":
        # אלן לומד את היריב ומסתגל
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            
            # אפקט ייחודי: ה-ATK שלו עולה ב-15% בכל פעם שהוא משתמש בסקיל
            atk_buff = int(attacker.atk * 0.15)
            attacker.atk += atk_buff
            
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg. Adaptation complete: ATK +{atk_buff}!",
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp
            ))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill", detail="Missed!", p_hp=p_hp, e_hp=e_hp))
    elif attacker.skill_name == "Inexorable Assault":
        # Conquest נותן 3 מכות רצופות, כל אחת מחלישה את ההגנה
        total_taken = 0
        any_hit = False
        
        for i in range(1, 4):
            # כל מכה חזקה ב-20% מהקודמת (מכה 1: 100%, מכה 2: 120%, מכה 3: 140% מהמולטיפלייר)
            current_mult = attacker.skill_mult * (1 + (i - 1) * 0.2)
            
            # חישוב נזק לכל מכה (משתמש ב-calc_damage הקיים אצלך)
            dmg, is_crit = calc_damage(attacker, defender, current_mult)
            
            if not roll_evade(defender):
                taken = defender.take_damage(dmg)
                total_taken += taken
                any_hit = True
                
                # שבירת הגנה: האפקט הייחודי - כל מכה שפוגעת מורידה 10% הגנה לצמיתות
                defender.defense = max(0, int(defender.defense * 0.90))
        
        p_hp, e_hp = _hp(attacker, defender)
        
        if any_hit:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: 3-hit combo for {total_taken} total dmg! Defense shredded.",
                damage=total_taken, p_hp=p_hp, e_hp=e_hp
            ))
        else:
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: All hits missed!",
                evaded=True, p_hp=p_hp, e_hp=e_hp
            ))
    elif attacker.skill_name == "Nova Burst":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            actual_heal = attacker.heal(int(taken * 0.20))
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg, healed {actual_heal} HP",
                damage=taken, heal=actual_heal, crit=is_crit, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))
            
    elif attacker.skill_name == "Orbital Strike":
        # ססיל קורא למתקפה מהחלל
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            
            # אפקט ייחודי: הלוויין משבש את היריב ומוריד לו את הסיכוי ל-Crit ב-5%
            # (בהנחה שיש לך שדה crit_rate ב-Fighter)
            if hasattr(defender, 'crit_rate'):
                defender.crit_rate = max(0, defender.crit_rate - 0.05)
            
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(
                turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} orbital dmg! Enemy sensors disrupted.",
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp
            ))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill", detail="Satellite missed!", p_hp=p_hp, e_hp=e_hp))
    elif attacker.skill_name == "Death Coil":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            detail = f"{attacker.skill_name}: {taken} dmg"
            if attacker.passive_name == "Toxic Touch" and attacker.poison_dmg:
                extra = defender.take_damage(attacker.poison_dmg * 2)
                detail += f" + {extra} bonus poison"
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=detail, damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    elif attacker.skill_name == "Singularity":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult, ignore_def_pct=0.5)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg (ignores 50% DEF)",
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    elif attacker.skill_name == "Void Rupture":
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            attacker.void_charges += 1
            free_turn = ""
            if attacker.void_charges >= 3:
                attacker.void_charges = 0
                free_turn = " — FREE TURN TRIGGERED!"
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg (charges: {attacker.void_charges}){free_turn}",
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    else:
        dmg, is_crit = calc_damage(attacker, defender, attacker.skill_mult)
        if not roll_evade(defender):
            taken = defender.take_damage(dmg)
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: {taken} dmg",
                damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp))
        else:
            p_hp, e_hp = _hp(attacker, defender)
            events.append(TurnEvent(turn=turn, actor=attacker.name, action="skill",
                detail=f"{attacker.skill_name}: evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))

    attacker.skill_current_cd = attacker.skill_cd


def resolve_default_attack(attacker: Fighter, defender: Fighter, events: list, turn: int):
    apply_poison = attacker.passive_name == "Toxic Touch"
    dmg, is_crit = calc_damage(attacker, defender, 1.0)

    if roll_evade(defender):
        p_hp, e_hp = _hp(attacker, defender)
        events.append(TurnEvent(turn=turn, actor=attacker.name, action="attack",
            detail=f"{attacker.name} attacks — evaded!", evaded=True, p_hp=p_hp, e_hp=e_hp))
        return

    if defender.passive_name == "Steel Skin":
        dmg = max(1, int(dmg * 0.92))

    taken  = defender.take_damage(dmg)
    detail = f"{attacker.name} attacks for {taken} dmg"

    if apply_poison:
        defender.poison_dmg   = max(defender.poison_dmg, 5)
        defender.poison_turns = max(defender.poison_turns, 3)
        detail += " (poisoned!)"
    if is_crit:
        detail += " (CRIT!)"

    p_hp, e_hp = _hp(attacker, defender)
    events.append(TurnEvent(turn=turn, actor=attacker.name, action="attack",
        detail=detail, damage=taken, crit=is_crit, p_hp=p_hp, e_hp=e_hp))


def choose_action(fighter: Fighter, loadout: list[str]) -> str:
    for slot in loadout:
        if slot == "skill" and fighter.skill_current_cd == 0:
            return "skill"
    return "attack"


# ------------------------------------------------------------------ #
#  Main battle loop                                                    #
# ------------------------------------------------------------------ #

MAX_TURNS = 40

def run_battle(
    player_char: dict,
    player_char_master: dict,
    enemy_char_master: dict,
    player_loadout: list[str] | None = None,
) -> BattleResult:
    if player_loadout is None:
        player_loadout = ["skill", "default"]
    enemy_loadout = ["skill", "default"]

    # is_player=True on the human fighter — this is what _hp() uses
    player = make_fighter(player_char, player_char_master, is_player=True)
    enemy  = make_fighter(None,        enemy_char_master,  is_player=False)

    events: list[TurnEvent] = []
    turn = 0

    events.append(TurnEvent(
        turn=0, actor="system", action="start",
        detail=f"Battle start: {player.name} (HP:{player.hp} SPD:{player.spd}) "
               f"vs {enemy.name} (HP:{enemy.hp} SPD:{enemy.spd})",
        p_hp=player.hp, e_hp=enemy.hp,
    ))

    while player.is_alive and enemy.is_alive and turn < MAX_TURNS:
        turn += 1
        p_spd, e_spd = player.effective_spd(), enemy.effective_spd()

        if p_spd > e_spd or (p_spd == e_spd and random.random() < 0.5):
            first, second        = player, enemy
            first_load, sec_load = player_loadout, enemy_loadout
        else:
            first, second        = enemy, player
            first_load, sec_load = enemy_loadout, player_loadout

        apply_start_of_turn(first, second, events, turn)
        if not second.is_alive:
            break

        action = choose_action(first, first_load)
        if action == "skill":
            resolve_skill(first, second, events, turn)
            if first.skill_name == "Void Rupture" and events[-1].detail.endswith("FREE TURN TRIGGERED!"):
                action2 = choose_action(first, first_load)
                if action2 == "skill":
                    resolve_skill(first, second, events, turn)
                else:
                    resolve_default_attack(first, second, events, turn)
        else:
            resolve_default_attack(first, second, events, turn)

        if not second.is_alive:
            break

        apply_start_of_turn(second, first, events, turn)
        if not first.is_alive:
            break

        action = choose_action(second, sec_load)
        if action == "skill":
            resolve_skill(second, first, events, turn)
        else:
            resolve_default_attack(second, first, events, turn)

    if player.is_alive and not enemy.is_alive:
        outcome = "win";  coins = random.randint(30, 80); xp = random.randint(20, 50)
    elif enemy.is_alive and not player.is_alive:
        outcome = "loss"; coins = random.randint(5,  15); xp = random.randint(5,  15)
    else:
        outcome = "draw"; coins = random.randint(10, 25); xp = random.randint(10, 25)

    events.append(TurnEvent(
        turn=turn, actor="system", action="end",
        detail=f"Battle over — {outcome.upper()} after {turn} turns. +{coins} coins, +{xp} XP",
        p_hp=player.hp, e_hp=enemy.hp,
    ))

    return BattleResult(outcome=outcome, turns=turn, log=events, coins_earned=coins, xp_earned=xp)


if __name__ == "__main__":
    pc = {"id": "1", "hp": 300, "atk": 95, "def": 20, "spd": 9, "crit": 25, "evade": 18}
    hero = {"id": "2", "name": "Swiftbolt", "faction": "hero",
            "base_hp": 300, "base_atk": 95, "base_def": 20, "base_spd": 9,
            "base_crit": 25, "base_evade": 18, "passive_name": "Lightning Reflexes",
            "passive_desc": "...", "skill_name": "Thunderstrike", "skill_desc": "...",
            "skill_mult": 2.2, "skill_cd": 4}
    villain = {"id": "3", "name": "Graviton", "faction": "villain",
               "base_hp": 480, "base_atk": 80, "base_def": 45, "base_spd": 5,
               "base_crit": 12, "base_evade": 8, "passive_name": "Gravity Well",
               "passive_desc": "...", "skill_name": "Singularity", "skill_desc": "...",
               "skill_mult": 1.6, "skill_cd": 4}

    result = run_battle(pc, hero, villain)
    print(f"\nOutcome: {result.outcome} in {result.turns} turns")
    print(f"Rewards: +{result.coins_earned} coins, +{result.xp_earned} XP\n")
    for e in result.log:
        print(f"  T{e.turn:02d} [{e.actor:12s}] {e.detail:55s}  P:{e.p_hp:3d}  E:{e.e_hp:3d}")