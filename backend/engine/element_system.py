"""
engine/element_system.py
------------------------
6-element system with a full advantage/disadvantage web.

Elements: Power · Speed · Tech · Mystic · Bio · Cosmic

Chart (attacker → defender):
  Power  > Speed, Bio
  Speed  > Tech,  Mystic
  Tech   > Power, Cosmic
  Mystic > Bio,   Power
  Bio    > Cosmic, Speed
  Cosmic > Mystic, Tech

Visual:
  Power  ──beats──► Speed  ──beats──► Tech
    ▲                                   │
    │           (Mystic)                │
   Bio  ◄──beats── Cosmic ──beats──► Mystic
    │                                   ▲
    └──────────────beats────────────────┘

Multipliers:
  Strong advantage:    1.30×
  Weak advantage:      1.15×  (second-element bonus)
  Neutral:             1.00×
  Disadvantage:        0.80×
"""

from __future__ import annotations

# ── Advantage table ───────────────────────────────────────────────────────────
# Each element has a STRONG target and a WEAK target.
# Strong: 1.30×  |  Weak: 1.15×  |  Neutral: 1.00×  |  Disadvantaged: 0.80×

STRONG_AGAINST: dict[str, list[str]] = {
    "Power":  ["Speed", "Bio"],
    "Speed":  ["Tech",  "Mystic"],
    "Tech":   ["Power", "Cosmic"],
    "Mystic": ["Bio",   "Power"],
    "Bio":    ["Cosmic","Speed"],
    "Cosmic": ["Mystic","Tech"],
}

# Precompute reverse: who is strong against me?
WEAK_AGAINST: dict[str, list[str]] = {}
for attacker, defenders in STRONG_AGAINST.items():
    for d in defenders:
        WEAK_AGAINST.setdefault(d, []).append(attacker)

STRONG_MULT       = 1.30
WEAK_MULT         = 1.15   # second advantage (softer bonus)
NEUTRAL_MULT      = 1.00
DISADVANTAGE_MULT = 0.80


def element_multiplier(attacker_element: str, defender_element: str) -> float:
    """
    Return the damage multiplier for attacker's element vs defender's element.

    Priority:
      1. Is defender in attacker's STRONG_AGAINST list?   → 1.30× (index 0) or 1.15× (index 1)
      2. Is attacker in defender's STRONG_AGAINST list?   → 0.80×
      3. Neither                                          → 1.00×
    """
    if not attacker_element or not defender_element:
        return NEUTRAL_MULT

    targets = STRONG_AGAINST.get(attacker_element, [])
    if defender_element in targets:
        # Both targets get the full advantage (1.30×)
        # The second target entry just gives narrative variety, not a weaker bonus
        return STRONG_MULT

    # Disadvantage: defender has attacker in its strong list
    if attacker_element in STRONG_AGAINST.get(defender_element, []):
        return DISADVANTAGE_MULT

    return NEUTRAL_MULT


def element_advantage_label(attacker: str, defender: str) -> str:
    """Human-readable matchup label for UI tooltips."""
    mult = element_multiplier(attacker, defender)
    if mult >= STRONG_MULT:
        return "STRONG"
    if mult >= WEAK_MULT:
        return "EFFECTIVE"
    if mult <= DISADVANTAGE_MULT:
        return "WEAK"
    return ""


# ── UI helpers ────────────────────────────────────────────────────────────────

ELEMENT_COLORS: dict[str, str] = {
    "Power":  "#ef4444",   # red
    "Speed":  "#22c55e",   # green
    "Tech":   "#60a5fa",   # blue
    "Mystic": "#c084fc",   # purple
    "Bio":    "#86efac",   # light green
    "Cosmic": "#fbbf24",   # gold
}

ELEMENT_ICONS: dict[str, str] = {
    "Power":  "⚡",
    "Speed":  "💨",
    "Tech":   "⚙",
    "Mystic": "🔮",
    "Bio":    "🌿",
    "Cosmic": "✨",
}


def element_color(element: str) -> str:
    return ELEMENT_COLORS.get(element, "#94a3b8")


def element_icon(element: str) -> str:
    return ELEMENT_ICONS.get(element, "○")


def all_elements() -> list[str]:
    return list(ELEMENT_COLORS.keys())


# ── Character affinity / synergy system ──────────────────────────────────────
#
# When specific characters fight alongside each other, they gain bonuses.
# Checked once per battle in build_synergy_bonuses() and applied to fighters.
#
# Format: { frozenset({name_a, name_b}): SynergyBonus }

from dataclasses import dataclass, field

@dataclass
class SynergyBonus:
    name:        str
    description: str
    atk_pct:     float = 0.0    # multiplicative ATK bonus (0.15 = +15%)
    def_pct:     float = 0.0
    crit_flat:   int   = 0
    energy_start: int  = 0      # extra starting energy

# pairs (frozenset) → bonus
SYNERGY_TABLE: dict[frozenset, SynergyBonus] = {
    # Invincible Universe bonds
    frozenset({"omni-man",    "invincible"}): SynergyBonus(
        "Father & Son",  "Viltrumite blood: +20% ATK each",  atk_pct=0.20),
    frozenset({"invincible",  "Atom Eve"}): SynergyBonus(
        "Young Love",    "Fighting for each other: +15% ATK, +10 CRIT", atk_pct=0.15, crit_flat=10),
    frozenset({"omni-man",    "Thragg"}): SynergyBonus(
        "Grand Regents", "Viltrumite rivalry: +25% ATK",  atk_pct=0.25),
    frozenset({"Allen the Alien", "invincible"}): SynergyBonus(
        "Best Friends",  "Tested together: +15% DEF, +10 CRIT", def_pct=0.15, crit_flat=10),
    frozenset({"conquest",    "Thragg"}): SynergyBonus(
        "Viltrum Vanguard","Relentless conquerors: +20% ATK", atk_pct=0.20),

    # DC/Marvel crossover synergy
    frozenset({"Superman",    "Wonder Woman"}): SynergyBonus(
        "Justice League", "Heroes united: +15% ATK, +15% DEF", atk_pct=0.15, def_pct=0.15),
    frozenset({"Superman",    "The Flash"}): SynergyBonus(
        "Speed & Power",  "League combo: +20 starting energy each", energy_start=20),
    frozenset({"Batman",      "The Flash"}): SynergyBonus(
        "Dark Speedster",  "+10 CRIT, +15% DEF", crit_flat=10, def_pct=0.15),
    frozenset({"Iron Man",    "Thor"}): SynergyBonus(
        "Avengers Assemble", "+20% ATK, +10 CRIT", atk_pct=0.20, crit_flat=10),
    frozenset({"Iron Man",    "Hulk"}): SynergyBonus(
        "Science Bros",   "Tech meets Gamma: +15% ATK, +20 start energy", atk_pct=0.15, energy_start=20),
    frozenset({"Thor",        "Hulk"}): SynergyBonus(
        "Strongest Avengers", "+25% ATK each", atk_pct=0.25),
    frozenset({"Spider-Man",  "Iron Man"}): SynergyBonus(
        "Mentorship",     "Stark mentored Spidey: +15 CRIT, +15% ATK", crit_flat=15, atk_pct=0.15),
    frozenset({"Spider-Man",  "Black Widow"}): SynergyBonus(
        "Street Level",   "Tactical pair: +20% DEF, +15 CRIT", def_pct=0.20, crit_flat=15),
    frozenset({"Black Widow", "Soldier Boy"}): SynergyBonus(
        "Cold War Agents","Spy partners: +15% ATK, +20 start energy", atk_pct=0.15, energy_start=20),

    # The Boys
    frozenset({"Homelander",  "Soldier Boy"}): SynergyBonus(
        "Supe Rivals",    "Hatred fuels power: +30% ATK each", atk_pct=0.30),

    # Cross-universe
    frozenset({"Goku",        "Superman"}): SynergyBonus(
        "Ultimate Rivals", "Power levels clash: +25% ATK", atk_pct=0.25),
    frozenset({"Saitama",     "Goku"}): SynergyBonus(
        "One Punch vs Saiyan", "Who's stronger? +30% ATK each", atk_pct=0.30),
    frozenset({"Magneto",     "Iron Man"}): SynergyBonus(
        "Metal vs Machine", "Magneto controls iron: +20% ATK to Magneto, +20 energy", atk_pct=0.20, energy_start=20),
}


def get_synergies_for_team(team_names: list[str]) -> list[dict]:
    """
    Given a list of character names on one team, return all active synergies.
    Used at battle start to display and apply bonuses.
    """
    active = []
    names_set = set(n.lower() for n in team_names)
    for pair, bonus in SYNERGY_TABLE.items():
        pair_lower = frozenset(n.lower() for n in pair)
        if pair_lower.issubset(names_set):
            active.append({
                "pair":        list(pair),
                "name":        bonus.name,
                "description": bonus.description,
                "bonus":       bonus,
            })
    return active


def apply_synergy_bonus(fighter_name: str, bonus: SynergyBonus, fighter) -> list[str]:
    """
    Apply a synergy bonus to a BattleFighter instance.
    Returns list of human-readable strings describing what changed.
    """
    changes = []
    name = fighter_name

    if bonus.atk_pct:
        gain = int(fighter.atk * bonus.atk_pct)
        fighter.atk += gain
        changes.append(f"+{gain} ATK")

    if bonus.def_pct:
        gain = int(fighter.defense * bonus.def_pct)
        fighter.defense += gain
        changes.append(f"+{gain} DEF")

    if bonus.crit_flat:
        fighter.crit = min(100, fighter.crit + bonus.crit_flat)
        changes.append(f"+{bonus.crit_flat} CRIT")

    if bonus.energy_start:
        fighter.energy = min(100, fighter.energy + bonus.energy_start)
        changes.append(f"+{bonus.energy_start} energy")

    return changes