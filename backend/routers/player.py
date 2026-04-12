"""
routers/player.py
-----------------
GET /player/{player_id}         — player profile (coins, gems, username)
GET /player/{player_id}/roster  — owned characters joined with master data
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from db.mongo import db

router = APIRouter(prefix="/player")


def _str_id(doc: dict) -> dict:
    """Convert _id → id (string) in-place and return the doc."""
    doc["id"] = str(doc.pop("_id"))
    return doc
@router.get("/first")
async def get_first_player():
    """
    Dev Helper: Returns the first player in the DB.
    Used by the frontend when localStorage is empty.
    """
    player = await db.players.find_one({})
    if not player:
        raise HTTPException(status_code=404, detail="No players found in DB. Run seed script!")
    
    return _str_id(player)

@router.get("/{player_id}")
async def get_player_profile(player_id: str):
    """Return the player document with id as a string."""
    try:
        player = await db.players.find_one({"_id": ObjectId(player_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid player ID format")

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return _str_id(player)


@router.get("/{player_id}/roster")
async def get_player_roster(player_id: str):
    """
    Return all characters the player owns, joined with master character data.
    Each item includes the full master character under 'master_data'.
    """
    try:
        p_id = ObjectId(player_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid player ID format")

    cursor = db.player_characters.find({"player_id": p_id})
    roster = await cursor.to_list(length=50)

    # Batch-load master characters to avoid N+1
    all_chars_cursor = db.characters.find({})
    all_chars = await all_chars_cursor.to_list(length=100)
    char_map = {str(c["_id"]): c for c in all_chars}

    result = []
    for item in roster:
        item["id"]        = str(item.pop("_id"))
        item["player_id"] = str(item["player_id"])
        char_id_str       = str(item["char_id"])
        item["char_id"]   = char_id_str

        # Rename "def" → "defense" for frontend consistency
        if "def" in item:
            item["defense"] = item.pop("def")

        master = char_map.get(char_id_str)
        if master:
            master_copy = dict(master)
            master_copy["id"] = str(master_copy.pop("_id"))
            item["master_data"] = master_copy

        result.append(item)

    return result