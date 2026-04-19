"""
engine/skill_definitions.py
---------------------------
Centralised skill catalogue.
Each character name maps to a list of skill dicts.
Index 0 = primary (all rarities have this).
Index 1 = secondary (SR and UR only, costs 60 energy).
Index 2 = tertiary  (UR only, costs 80 energy).

This file is the single source of truth — imported by the builder in
battle_ws_3v3.py to construct SkillDef objects on each BattleFighter.
Keeping it separate from seed2.py means you can tune skills without
re-seeding the database.
"""

from engine.battle_state import SkillDef

# ── Rarity → how many skills ──────────────────────────────────────────────────
RARITY_SKILL_COUNT = {"C": 1, "R": 1, "SR": 2, "UR": 3}

# Primary skill energy cost (same for everyone — the secondary/tertiary costs
# are defined per-skill below)
PRIMARY_COST   = 50
SECONDARY_COST = 60
TERTIARY_COST  = 80

# ── Master catalogue ─────────────────────────────────────────────────────────
# skill_name, skill_desc, skill_mult, energy_cost, target
SKILL_CATALOGUE: dict[str, list[SkillDef]] = {

    "omni-man": [
        SkillDef("World-Class Execution",
                 "Ignore all DEF. Execute bonus at <40% HP.",
                 1.8, PRIMARY_COST, "enemy"),
        SkillDef("Rallying Cry",
                 "Grant an ally +30 energy so they can act sooner.",
                 0.0, SECONDARY_COST, "ally"),
    ],

    "invincible": [
        SkillDef("viltrumaite",
                 "2.8× ATK damage — Viltrumite brute force.",
                 2.8, PRIMARY_COST, "enemy"),
        SkillDef("Viltrumite Rush",
                 "1.2× ATK to all enemies (AoE).",
                 1.2, SECONDARY_COST, "enemy"),
    ],
    "monster-girl": [
        SkillDef("Primal Rage",
                 "2.8× ATK and lose 0.1 hp.",
                 2.8, PRIMARY_COST, "enemy"),

    ],
    "conquest": [
        SkillDef("Inexorable Assault",
                 "3-hit combo, each hit shreds 10% enemy DEF permanently.",
                 0.7, PRIMARY_COST, "enemy"),
    ],

    "Atom Eve": [
        SkillDef("Molecular Manipulation",
                 "1.3× damage + restore 150% of dmg as HP.",
                 1.3, PRIMARY_COST, "enemy"),
        SkillDef("Healing Touch",
                 "Restore 200% ATK as HP to one ally.",
                 2.0, SECONDARY_COST, "ally"),
        SkillDef("Molecular Shield",
                 "Shield an ally: reduce their incoming damage by 50% for 2 turns.",
                 0.0, TERTIARY_COST, "ally"),
    ],
    "Thragg":[
        SkillDef("Grand Regent's Might",
                 "2.9 dmg .",
                 2.9, PRIMARY_COST, "enemy"),
    ],
        "Saitama": [
        SkillDef("One Punch",
                 "5.0× dmg, ignores ALL DEF. Cannot miss (no evade check).",
                 5.0, PRIMARY_COST, "enemy"),
        SkillDef("Serious Series: Serious Punch",
                 "8.0× dmg, ignores ALL DEF. Costs 80 energy — the real one.",
                 8.0, TERTIARY_COST, "enemy"),
    ],
 
    "Goku": [
        SkillDef("Kamehameha",
                 "3.0× beam, ignores 40% DEF.",
                 3.0, PRIMARY_COST, "enemy"),
        SkillDef("Instant Transmission",
                 "Teleport strike: 2.0× dmg + guaranteed crit + untargetable this round.",
                 2.0, SECONDARY_COST, "enemy"),
        SkillDef("Spirit Bomb",
                 "2.5× AoE dmg to ALL enemies, ignores 30% DEF.",
                 2.5, TERTIARY_COST, "aoe"),
    ],
 
    "Magneto": [
        SkillDef("Magnetic Crush",
                 "2.2× dmg. Tech enemies take 40% more. ATK-down applied.",
                 2.2, PRIMARY_COST, "enemy"),
        SkillDef("Metal Storm",
                 "1.5× AoE dmg. Tech enemies also stunned for 1 turn.",
                 1.5, SECONDARY_COST, "aoe"),
        SkillDef("Magnetic Fortress",
                 "Raise a magnetic shield: apply DEF +30% to an ally for 2 turns.",
                 0.0, TERTIARY_COST, "ally"),
    ],
 
    "Black Widow": [
        SkillDef("Widow's Bite",
                 "1.6× dmg, guaranteed crit (2.0× crit bonus), stuns target.",
                 1.6, PRIMARY_COST, "enemy"),
        SkillDef("Tactical Takedown",
                 "1.0× dmg + apply ATK-down and SPD-down for 2 turns.",
                 1.0, SECONDARY_COST, "enemy"),
    ],
    "Thor": [
    
        SkillDef("Mjolnir's Strike",
                 "2.8× dmg .",
                 2.8, PRIMARY_COST, "enemy"),
    ],
    "Iron Man": [        
        SkillDef("Unibeam",
                 "High precision beam dealing 2.2x damage",
                 2.2, PRIMARY_COST, "enemy"),
        SkillDef("Micro-Missile Barrage",
                 "High precision beam dealing 2.2x damage to all.",
                 1, SECONDARY_COST, "enemy"),
    ],
    "Hulk": [
        SkillDef("Gamma Slam",
                 "2.5× dmg scaling with rage (missing HP %). More damage the angrier he is.",
                 2.5, PRIMARY_COST, "enemy"),
        SkillDef("Thunderclap",
                 "0.8× AoE dmg to ALL enemies + stuns everyone for 1 turn.",
                 0.8, SECONDARY_COST, "aoe"),
        SkillDef("Hulk Smash",
                 "4.0× single target — pure destruction. Ignores 50% DEF.",
                 4.0, TERTIARY_COST, "enemy"),
    ],
 
    "Spider-Man": [
        SkillDef("Web Shot",
                 "1.8× dmg + webs target, reducing their SPD by 4 for 2 turns.",
                 1.8, PRIMARY_COST, "enemy"),
        SkillDef("Web Barrage",
                 "0.9× AoE web covering ALL enemies. SPD -3 for 2 turns each.",
                 0.9, SECONDARY_COST, "aoe"),
    ],
 
    "Soldier Boy": [
        SkillDef("Compound V Blast",
                 "2.0× dmg ignoring 60% DEF. Target ATK -25% for 2 turns.",
                 2.0, PRIMARY_COST, "enemy"),
        SkillDef("Soldier's Fury",
                 "4-hit burst at 0.5× each — 2.0× total dmg.",
                 0.5, SECONDARY_COST, "enemy"),
    ],

    "Allen the Alien": [
        SkillDef("Unstoppable Evolution",
                 "1.4× dmg + permanently gain +15% ATK.",
                 1.4, PRIMARY_COST, "enemy"),
        SkillDef("Speed Aura",
                 "Boost an ally's SPD by +3 permanently.",
                 0.0, SECONDARY_COST, "ally"),
    ],

    "Cecil Stedman": [
        SkillDef("Orbital Strike",
                 "1.7× dmg + reduce target SPD for 2 turns.",
                 1.7, PRIMARY_COST, "enemy"),
        SkillDef("Satellite Network",
                 "Medical drone heals most-injured ally for 400% of Cecil's ATK.",
                 4.0, SECONDARY_COST, "ally"),
        SkillDef("Black-Site Dossier",
                 "Apply ATK-down and SPD-down to an enemy for 2 turns.",
                 0.6, TERTIARY_COST, "enemy"),
    ],

    "Superman": [
        SkillDef("Heat Vision",
                 "1.8× pure damage, ignores all DEF.",
                 1.8, PRIMARY_COST, "enemy"),
        SkillDef("Heat Burst",
                 "Thermal burst hits target for 1.0× ignoring 50% DEF.",
                 1.0, SECONDARY_COST, "enemy"),
        SkillDef("Super Breath",
                 "Freeze an enemy: SPD-down and ATK-down for 2 turns.",
                 0.7, TERTIARY_COST, "enemy"),
    ],

    "The Flash": [
        SkillDef("Infinite Mass Punch",
                 "1.5× dmg + SPD×5 bonus damage.",
                 1.5, PRIMARY_COST, "enemy"),
        SkillDef("Speed Boost",
                 "Grant an ally +3 SPD and +70 energy.",
                 0.0, TERTIARY_COST, "ally"),
    ],

    "Wonder Woman": [
        SkillDef("Lasso of Truth",
                 "1.4× dmg + stuns target for 1 turn.",
                 1.4, PRIMARY_COST, "enemy"),
        SkillDef("Wonder Block",
                 "Heal an ally for 80% ATK and clear any stun on them.",
                 0.8, SECONDARY_COST, "ally"),
        SkillDef("Divine Smite",
                 "2.0× dmg, ignores 30% DEF.",
                 2.0, TERTIARY_COST, "enemy"),
    ],

    "Batman": [
        SkillDef("Explosive Batarang",
                 "1.2× dmg + enemy ATK -20% for 2 turns.",
                 1.2, PRIMARY_COST, "enemy"),
        SkillDef("Batarang Storm",
                 "3 rapid throws at 0.6× each with independent crits.",
                 0.6, SECONDARY_COST, "enemy"),
    ],

    "Homelander": [
        SkillDef("Laser Eyes",
                 "1.6× dmg. Kill resets skill energy cost.",
                 1.6, PRIMARY_COST, "enemy"),
        SkillDef("Fear Aura",
                 "0.8× dmg + intimidate reduces target ATK -10% for 2 turns.",
                 0.8, SECONDARY_COST, "enemy"),
        SkillDef("Reign of Terror",
                 "2.2× dmg to lowest-HP enemy.",
                 2.2, TERTIARY_COST, "enemy"),
    ],

    "Swiftbolt": [
        SkillDef("Thunderstrike",
                 "2.2× ATK. Guaranteed crit when enemy HP > 80%.",
                 2.2, PRIMARY_COST, "enemy"),
    ],

    "Void Queen": [
        SkillDef("Void Rupture",
                 "2.5× dmg. 3 charges → free energy refund.",
                 2.5, PRIMARY_COST, "enemy"),
        SkillDef("Dark Pact",
                 "Sacrifice 10% HP to instantly gain +40 energy.",
                 0.0, SECONDARY_COST, "self"),
        SkillDef("Void Collapse",
                 "2.0× dmg, ignore 40% DEF. Costs 80 energy.",
                 2.0, TERTIARY_COST, "enemy"),
    ],

    "Graviton": [
        SkillDef("Singularity",
                 "1.6× dmg, ignores 50% DEF.",
                 1.6, PRIMARY_COST, "enemy"),
        SkillDef("Gravity Crush",
                 "0.9× dmg + SPD-down and ATK-down to target for 2 turns.",
                 0.9, SECONDARY_COST, "enemy"),
    ],
}


def get_skills_for(char_name: str, rarity: str, primary_name: str,
                   primary_desc: str, primary_mult: float) -> list[SkillDef]:
    """
    Return the SkillDef list for a character.
    Falls back to a single generic skill using the DB values if not in catalogue.
    Respects RARITY_SKILL_COUNT so C/R always get exactly 1 skill.
    """
    max_skills = RARITY_SKILL_COUNT.get(rarity, 1)
    catalogue  = SKILL_CATALOGUE.get(char_name)

    if catalogue:
        return catalogue[:max_skills]

    # Fallback: one primary skill from DB fields
    return [SkillDef(primary_name, primary_desc, primary_mult, PRIMARY_COST, "enemy")]
