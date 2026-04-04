"""from fastapi import APIRouter, HTTPException
from db.client import get_db
from models.schemas import Player

router = APIRouter()

def _row_to_player(row: dict) -> Player:
    return Player(
        id=row["id"],
        username=row["username"],
        coins=row["coins"],
        gems=row["gems"]
    )

@router.get("/player/{player_id}", response_model=Player)
def get_player(player_id: int):
    db = get_db()
    rows = db.query(f"SELECT * FROM players WHERE id = {player_id}")
    if not rows:
        raise HTTPException(status_code=404, detail="Player not found")
    return _row_to_player(rows[0])"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from db.mongo import db

router = APIRouter()

@router.get("/{player_id}")
async def get_player_profile(player_id: str):
    player = await db.db.players.find_one({"_id": ObjectId(player_id)})
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    player["id"] = str(player.pop("_id"))
    return player

@router.get("/{player_id}/roster")
async def get_player_roster(player_id: str):
    # Find all player_characters belonging to this player
    cursor = db.player_characters.find({"player_id": ObjectId(player_id)})
    roster = await cursor.to_list(length=50)
    
    for item in roster:
        item["id"] = str(item.pop("_id"))
        item["player_id"] = str(item["player_id"])
        item["char_id"] = str(item["char_id"])
        
        # Optional: Join with master character data
        master = await db.chars.find_one({"_id": ObjectId(item["char_id"])})
        if master:
            item["master_data"] = master
            item["master_data"]["id"] = str(item["master_data"].pop("_id"))

    return roster