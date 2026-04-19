"""
engine/tactical_moves.py
------------------------
Maps each character to their unique tactical move.
Imported by battle_ws_3v3 and tower_battle_ws to stamp
tactical_move onto each BattleFighter at build time.
"""

# ── Tactical move assignment ──────────────────────────────────────────────────
# Maps character name (lowercase) → tactical move type.
# Set at battle-build time so the frontend always knows what button to show.

TACTICAL_MOVES: dict[str, str] = {
    # FOCUS — precision / analytical characters
    "iron man":      "focus",
    "spider-man":    "focus",
    "batman":        "focus",
    "black widow":   "focus",
    "goku":          "focus",
    "saitama":       "focus",
    "Cecil Stedman": "focus",

    # GUARD — defensive / tank characters
    "ironclad":      "guard",
    "wonder woman":  "guard",
    "superman":      "guard",
    "allen the alien": "guard",
    "hulk":          "guard",
    "thor":          "guard",
    "Atom Eve":      "guard",

    # TAUNT — intimidating / aggro-magnet characters
    "thragg":        "taunt",
    "homelander":    "taunt",
    "conquest":      "taunt",
    "graviton":      "taunt",
    "magneto":       "taunt",
    "soldier boy":   "taunt",
    "void queen":    "taunt",
}

TACTICAL_ICONS: dict[str, str] = {
    "focus": "🎯",
    "guard": "🛡",
    "taunt": "😤",
}

TACTICAL_LABELS: dict[str, str] = {
    "focus": "Focus",
    "guard": "Guard",
    "taunt": "Taunt",
}

TACTICAL_DESCS: dict[str, str] = {
    "focus": "Concentrate — next attack is a guaranteed Critical Hit.",
    "guard": "Brace for impact — reduce incoming damage by 50% this turn.",
    "taunt": "Challenge enemies — force all foes to target you next turn.",
}


def get_tactical_move(char_name: str) -> str | None:
    """Return the tactical move type for a character, or None if unassigned."""
    return TACTICAL_MOVES.get(char_name.lower()) or TACTICAL_MOVES.get(char_name)
