"""
engine/element_system.py
------------------------
Power > Speed > Tech > Power triangle.
Returns a damage multiplier given attacker and defender elements.
"""

# Who beats whom
STRONG_AGAINST: dict[str, str] = {
    "Power": "Speed",
    "Speed": "Tech",
    "Tech":  "Power",
}

ADVANTAGE_MULT  = 1.25
DISADVANTAGE_MULT = 0.85   # optional: weak against gives a penalty too
NEUTRAL_MULT    = 1.0


def element_multiplier(attacker_element: str, defender_element: str) -> float:
    """
    Return the damage multiplier for attacker's element vs defender's element.
      Power vs Speed → 1.25x
      Speed vs Power → 0.85x
      Same element   → 1.0x
    """
    if not attacker_element or not defender_element:
        return NEUTRAL_MULT
    if STRONG_AGAINST.get(attacker_element) == defender_element:
        return ADVANTAGE_MULT
    if STRONG_AGAINST.get(defender_element) == attacker_element:
        return DISADVANTAGE_MULT
    return NEUTRAL_MULT


def element_color(element: str) -> str:
    """CSS colour for UI badges."""
    return {
        "Power": "#ef4444",
        "Speed": "#22c55e",
        "Tech":  "#60a5fa",
    }.get(element, "#94a3b8")


def element_icon(element: str) -> str:
    return {"Power": "⚡", "Speed": "💨", "Tech": "⚙"}.get(element, "○")
