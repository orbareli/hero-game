"""
models/schemas.py
-----------------
Pydantic models for request/response validation.
These are the contracts between frontend and backend.


from __future__ import annotations
from pydantic import BaseModel
from typing import Literal, Optional


# ------------------------------------------------------------------ #
#  Character                                                           #
# ------------------------------------------------------------------ #

class Character(BaseModel):
    id:            int
    name:          str
    faction:       Literal["hero", "villain"]
    rarity:        Literal["C", "R", "SR", "UR"]
    base_hp:       int
    base_atk:      int
    base_def:      int
    base_spd:      int
    base_crit:     int
    base_evade:    int
    passive_name:  str
    passive_desc:  str
    skill_name:    str
    skill_desc:    str
    skill_mult:    float
    skill_cd:      int
    portrait_id:   str


class PlayerCharacter(BaseModel):
    ""A character the player owns, with current leveled stats.""
    id:         int
    player_id:  int
    char_id:    int
    level:      int
    xp:         int
    stars:      int
    duplicates: int
    hp:         int
    atk:        int
    defense:    int      # mapped from 'def' (Python keyword)
    spd:        int
    crit:       int
    evade:      int
    # Joined from characters table
    character:  Optional[Character] = None


# ------------------------------------------------------------------ #
#  Player                                                              #
# ------------------------------------------------------------------ #

class Player(BaseModel):
    id:       int
    username: str
    coins:    int
    gems:     int


# ------------------------------------------------------------------ #
#  Loadout                                                             #
# ------------------------------------------------------------------ #

class LoadoutSlot(BaseModel):
    player_char_id: int
    slot:           int                              # 0 or 1
    ability_type:   Literal["skill", "default", "passive"]


class LoadoutRequest(BaseModel):
    player_char_id: int
    slots:          list[LoadoutSlot]                # max 2


class LoadoutResponse(BaseModel):
    player_char_id: int
    slots:          list[LoadoutSlot]


# ------------------------------------------------------------------ #
#  Shop                                                                #
# ------------------------------------------------------------------ #

class ShopItem(BaseModel):
    id:        int
    item_type: str
    char_id:   int
    price:     int
    currency:  Literal["coins", "gems"]
    available: int
    character: Optional[Character] = None


class BuyRequest(BaseModel):
    player_id:    int
    shop_item_id: int


class BuyResponse(BaseModel):
    success:   bool
    message:   str
    player:    Optional[Player] = None
    character: Optional[Character] = None


class PackResult(BaseModel):
    characters: list[Character]
    message:    str
    player:     Player


# ------------------------------------------------------------------ #
#  Battle                                                              #
# ------------------------------------------------------------------ #

class BattleRequest(BaseModel):
    player_id:      int
    player_char_id: int   # player_characters.id
    enemy_char_id:  int   # characters.id (base char, not owned)


class TurnEvent(BaseModel):
    turn:   int
    actor:  str
    action: str
    detail: str
    damage: int = 0
    heal:   int = 0
    crit:   bool = False
    evaded: bool = False
    p_hp:   int = 0
    e_hp:   int = 0


class BattleResponse(BaseModel):
    battle_id:    int
    outcome:      Literal["win", "loss", "draw"]
    turns:        int
    coins_earned: int
    xp_earned:    int
    log:          list[TurnEvent]
    player:       Player              # updated currency
    player_char:  PlayerCharacter     # updated xp/level
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional

# ------------------------------------------------------------------ #
#  Character                                                         #
# ------------------------------------------------------------------ #

class Character(BaseModel):
    # MongoDB IDs come as strings to the frontend
    id:           str  
    name:          str
    faction:       Literal["hero", "villain"]
    rarity:        Literal["C", "R", "SR", "UR"]
    base_hp:       int
    base_atk:      int
    base_def:      int
    base_spd:      int
    base_crit:     int
    base_evade:    int
    passive_name:  str
    passive_desc:  str
    skill_name:    str
    skill_desc:    str
    skill_mult:    float
    skill_cd:      int
    portrait_id:   str


class PlayerCharacter(BaseModel):
    """A character the player owns, with current leveled stats."""
    id:         str
    player_id:  str
    char_id:    str
    level:      int
    xp:         int
    stars:      int
    duplicates: int
    hp:         int
    atk:        int
    defense:    int      # We map 'def' from Mongo to this in the router
    spd:        int
    crit:       int
    evade:      int
    character:  Optional[Character] = None


# ------------------------------------------------------------------ #
#  Player                                                            #
# ------------------------------------------------------------------ #

class Player(BaseModel):
    id:       str
    username: str
    coins:    int
    gems:     int


# ------------------------------------------------------------------ #
#  Loadout                                                           #
# ------------------------------------------------------------------ #

class LoadoutSlot(BaseModel):
    player_char_id: str
    slot:           int
    ability_type:   Literal["skill", "default", "passive"]


class LoadoutRequest(BaseModel):
    player_char_id: str
    slots:          list[LoadoutSlot]


class LoadoutResponse(BaseModel):
    player_char_id: str
    slots:          list[LoadoutSlot]


# ------------------------------------------------------------------ #
#  Shop                                                              #
# ------------------------------------------------------------------ #

class ShopItem(BaseModel):
    id:        str
    item_type: str
    char_id:   str
    price:     int
    currency:  Literal["coins", "gems"]
    available: bool  # Changed from int to bool for cleaner Mongo logic
    character: Optional[Character] = None


class BuyRequest(BaseModel):
    player_id:    str
    shop_item_id: str


class BuyResponse(BaseModel):
    success:   bool
    message:   str
    player:    Optional[Player] = None
    character: Optional[Character] = None


class PackResult(BaseModel):
    characters: list[Character]
    message:    str
    player:     Player


# ------------------------------------------------------------------ #
#  Battle                                                            #
# ------------------------------------------------------------------ #

class BattleRequest(BaseModel):
    player_id:      str
    player_char_id: str 
    enemy_char_id:  str 


class TurnEvent(BaseModel):
    turn:   int
    actor:  str
    action: str
    detail: str
    damage: int = 0
    heal:   int = 0
    crit:   bool = False
    evaded: bool = False
    p_hp:   int = 0
    e_hp:   int = 0


class BattleResponse(BaseModel):
    battle_id:    str
    outcome:      Literal["win", "loss", "draw"]
    turns:        int
    coins_earned: int
    xp_earned:    int
    log:          list[TurnEvent]
    player:       Player 
    player_char:  PlayerCharacter