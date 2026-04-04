"""
routers/characters.py
---------------------
GET  /characters              — full master roster (all chars in the game)
GET  /characters/{id}         — single character by id
GET  /roster/{player_id}      — characters the player owns (with current stats)
GET  /roster/{player_id}/{pc_id} — single owned character with full detail


from fastapi import APIRouter, HTTPException
from db.client import get_db
from models.schemas import Character, PlayerCharacter

router = APIRouter()


def _row_to_character(row: dict) -> Character:
    return Character(
        id=row["id"],
        name=row["name"],
        faction=row["faction"],
        rarity=row["rarity"],
        base_hp=row["base_hp"],
        base_atk=row["base_atk"],
        base_def=row["base_def"],
        base_spd=row["base_spd"],
        base_crit=row["base_crit"],
        base_evade=row["base_evade"],
        passive_name=row["passive_name"],
        passive_desc=row["passive_desc"],
        skill_name=row["skill_name"],
        skill_desc=row["skill_desc"],
        skill_mult=row["skill_mult"],
        skill_cd=row["skill_cd"],
        portrait_id=row["portrait_id"],
    )


def _row_to_player_character(pc_row: dict, char_row: dict | None = None) -> PlayerCharacter:
    return PlayerCharacter(
        id=pc_row["id"],
        player_id=pc_row["player_id"],
        char_id=pc_row["char_id"],
        level=pc_row["level"],
        xp=pc_row["xp"],
        stars=pc_row["stars"],
        duplicates=pc_row["duplicates"],
        hp=pc_row["hp"],
        atk=pc_row["atk"],
        defense=pc_row["def"],
        spd=pc_row["spd"],
        crit=pc_row["crit"],
        evade=pc_row["evade"],
        character=_row_to_character(char_row) if char_row else None,
    )


# ------------------------------------------------------------------ #
#  Master roster                                                       #
# ------------------------------------------------------------------ #

@router.get("/characters", response_model=list[Character])
def get_all_characters():
    "All characters in the game — used for enemy selection and shop display."
    db = get_db()
    rows = db.query("SELECT * FROM characters")
    return [_row_to_character(r) for r in rows]


@router.get("/characters/{char_id}", response_model=Character)
def get_character(char_id: int):
    db = get_db()
    rows = db.query(f"SELECT * FROM characters WHERE id = {char_id}")
    if not rows:
        raise HTTPException(status_code=404, detail=f"Character {char_id} not found")
    return _row_to_character(rows[0])


# ------------------------------------------------------------------ #
#  Player roster                                                       #
# ------------------------------------------------------------------ #

@router.get("/roster/{player_id}", response_model=list[PlayerCharacter])
def get_player_roster(player_id: int):
    "All characters owned by a player, joined with master character data."
    db = get_db()

    pc_rows = db.query(
        f"SELECT * FROM player_characters WHERE player_id = {player_id}"
    )
    if not pc_rows:
        return []

    # Build a char_id → character map to avoid N+1 queries
    all_chars = db.query("SELECT * FROM characters")
    char_map  = {c["id"]: c for c in all_chars}

    result = []
    for pc in pc_rows:
        char_row = char_map.get(pc["char_id"])
        result.append(_row_to_player_character(pc, char_row))

    return result


@router.get("/roster/{player_id}/{pc_id}", response_model=PlayerCharacter)
def get_player_character(player_id: int, pc_id: int):
    db = get_db()

    pc_rows = db.query(
        f"SELECT * FROM player_characters WHERE id = {pc_id} AND player_id = {player_id}"
    )
    if not pc_rows:
        raise HTTPException(status_code=404, detail="Character not found in roster")

    pc = pc_rows[0]
    char_rows = db.query(f"SELECT * FROM characters WHERE id = {pc['char_id']}")
    char_row  = char_rows[0] if char_rows else None

    return _row_to_player_character(pc, char_row)
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from db.mongo import db  # Ensure this is your motor client instance
from models.schemas import Character, PlayerCharacter

router = APIRouter()

# ------------------------------------------------------------------ #
#  Helpers to convert Mongo Documents to Pydantic Models             #
# ------------------------------------------------------------------ #

def _doc_to_character(doc: dict) -> Character:
    # MongoDB uses _id, Pydantic expects id
    doc["id"] = str(doc.pop("_id"))
    return Character(**doc)


def _doc_to_player_character(pc_doc: dict, char_doc: dict | None = None) -> PlayerCharacter:
    pc_doc["id"] = str(pc_doc.pop("_id"))
    pc_doc["player_id"] = str(pc_doc["player_id"])
    pc_doc["char_id"] = str(pc_doc["char_id"])
    
    # Map 'def' from Mongo to 'defense' for the Pydantic schema
    if "def" in pc_doc:
        pc_doc["defense"] = pc_doc.pop("def")
        
    character_data = _doc_to_character(char_doc) if char_doc else None
    return PlayerCharacter(**pc_doc, character=character_data)


# ------------------------------------------------------------------ #
#  Master roster                                                     #
# ------------------------------------------------------------------ #

@router.get("/characters", response_model=list[Character])
async def get_all_characters():
    """All characters in the game — used for enemy selection and shop display."""
    cursor = db.characters.find({})
    rows = await cursor.to_list(length=100)
    return [_doc_to_character(r) for r in rows]


@router.get("/characters/{char_id}", response_model=Character)
async def get_character(char_id: str):
    """Fetch a single master character by its Hex String ID."""
    try:
        doc = await db.characters.find_one({"_id": ObjectId(char_id)})
        if not doc:
            raise HTTPException(status_code=404, detail=f"Character {char_id} not found")
        return _doc_to_character(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


# ------------------------------------------------------------------ #
#  Player roster                                                     #
# ------------------------------------------------------------------ #

@router.get("/roster/{player_id}", response_model=list[PlayerCharacter])
async def get_player_roster(player_id: str):
    """All characters owned by a player, joined with master character data."""
    try:
        # 1. Find all characters belonging to the player
        cursor = db.player_characters.find({"player_id": ObjectId(player_id)})
        pc_rows = await cursor.to_list(length=100)
        
        if not pc_rows:
            return []

        # 2. To avoid N+1 queries, fetch all master characters at once
        all_chars_cursor = db.characters.find({})
        all_chars = await all_chars_cursor.to_list(length=100)
        # Create a map of string_id -> doc
        char_map = {str(c["_id"]): c for c in all_chars}

        result = []
        for pc in pc_rows:
            char_doc = char_map.get(str(pc["char_id"]))
            result.append(_doc_to_player_character(pc, char_doc))

        return result
    except Exception as e:
        print(f"Error fetching roster: {e}")
        return []


@router.get("/roster/{player_id}/{pc_id}", response_model=PlayerCharacter)
async def get_player_character(player_id: str, pc_id: str):
    """Single owned character with full detail."""
    try:
        # Find the specific player-character instance
        pc = await db.player_characters.find_one({
            "_id": ObjectId(pc_id), 
            "player_id": ObjectId(player_id)
        })
        
        if not pc:
            raise HTTPException(status_code=404, detail="Character not found in roster")

        # Find the master data for that character
        char_doc = await db.characters.find_one({"_id": ObjectId(pc["char_id"])})
        
        return _doc_to_player_character(pc, char_doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
