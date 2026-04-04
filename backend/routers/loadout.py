"""
routers/loadout.py
------------------
GET  /loadout/{player_char_id}   — get current loadout for a player character
POST /loadout                    — save a loadout (replaces existing)


from fastapi import APIRouter, HTTPException
from db.client import get_db
from models.schemas import LoadoutRequest, LoadoutResponse, LoadoutSlot

router = APIRouter()


@router.get("/loadout/{player_char_id}", response_model=LoadoutResponse)
def get_loadout(player_char_id: int):
    db = get_db()

    rows = db.query(
        f"SELECT * FROM loadouts WHERE player_char_id = {player_char_id}"
    )

    # Sort by slot so order is always consistent
    rows.sort(key=lambda r: r["slot"])

    slots = [
        LoadoutSlot(
            player_char_id=r["player_char_id"],
            slot=r["slot"],
            ability_type=r["ability_type"],
        )
        for r in rows
    ]

    # Default loadout if nothing saved yet
    if not slots:
        slots = [
            LoadoutSlot(player_char_id=player_char_id, slot=0, ability_type="skill"),
            LoadoutSlot(player_char_id=player_char_id, slot=1, ability_type="default"),
        ]

    return LoadoutResponse(player_char_id=player_char_id, slots=slots)


@router.post("/loadout", response_model=LoadoutResponse)
def save_loadout(req: LoadoutRequest):
    "
    Save a loadout for a player character.
    Replaces all existing slots for that character.
    Max 2 slots. Valid ability_type values: skill, default, passive.
    "
    db = get_db()

    if len(req.slots) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 loadout slots")

    # Verify the player_character exists
    pc_rows = db.query(
        f"SELECT * FROM player_characters WHERE id = {req.player_char_id}"
    )
    if not pc_rows:
        raise HTTPException(status_code=404, detail="Player character not found")

    # Delete existing loadout for this character
    db.execute(f"DELETE FROM loadouts WHERE player_char_id = {req.player_char_id}")

    # Insert new slots
    for slot in req.slots:
        db.execute(
            f"INSERT INTO loadouts (player_char_id, slot, ability_type) "
            f"VALUES ({req.player_char_id}, {slot.slot}, '{slot.ability_type}')"
        )

    # Return the saved loadout
    saved = db.query(
        f"SELECT * FROM loadouts WHERE player_char_id = {req.player_char_id}"
    )
    saved.sort(key=lambda r: r["slot"])

    return LoadoutResponse(
        player_char_id=req.player_char_id,
        slots=[
            LoadoutSlot(
                player_char_id=r["player_char_id"],
                slot=r["slot"],
                ability_type=r["ability_type"],
            )
            for r in saved
        ],
    )
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from db.mongo import db  # Your motor client instance
from models.schemas import LoadoutRequest, LoadoutResponse, LoadoutSlot

router = APIRouter()

# ------------------------------------------------------------------ #
#  Helpers                                                           #
# ------------------------------------------------------------------ #

def _doc_to_slot(doc: dict) -> LoadoutSlot:
    return LoadoutSlot(
        player_char_id=str(doc["player_char_id"]),
        slot=doc["slot"],
        ability_type=doc["ability_type"]
    )

# ------------------------------------------------------------------ #
#  Endpoints                                                         #
# ------------------------------------------------------------------ #

@router.get("/loadout/{player_char_id}", response_model=LoadoutResponse)
async def get_loadout(player_char_id: str):
    """Fetch the saved loadout for a specific character instance."""
    try:
        cursor = db.db.loadouts.find({"player_char_id": ObjectId(player_char_id)})
        rows = await cursor.to_list(length=10)
        
        # Sort by slot index
        rows.sort(key=lambda r: r["slot"])
        
        slots = [_doc_to_slot(r) for r in rows]

        # Default loadout if nothing saved yet
        if not slots:
            slots = [
                LoadoutSlot(player_char_id=player_char_id, slot=0, ability_type="skill"),
                LoadoutSlot(player_char_id=player_char_id, slot=1, ability_type="default"),
            ]

        return LoadoutResponse(player_char_id=player_char_id, slots=slots)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


@router.post("/loadout", response_model=LoadoutResponse)
async def save_loadout(req: LoadoutRequest):
    """
    Save a loadout for a player character.
    Replaces all existing slots for that character.
    """
    try:
        p_char_id = ObjectId(req.player_char_id)
        
        if len(req.slots) > 2:
            raise HTTPException(status_code=400, detail="Maximum 2 loadout slots")

        # 1. Verify the player_character exists
        pc = await db.db.player_characters.find_one({"_id": p_char_id})
        if not pc:
            raise HTTPException(status_code=404, detail="Player character not found")

        # 2. Delete existing loadout (Cleanup)
        await db.db.loadouts.delete_many({"player_char_id": p_char_id})

        # 3. Prepare new slots
        new_slots = []
        for s in req.slots:
            new_slots.append({
                "player_char_id": p_char_id,
                "slot": s.slot,
                "ability_type": s.ability_type
            })

        # 4. Insert new slots if any provided
        if new_slots:
            await db.db.loadouts.insert_many(new_slots)

        # 5. Return the newly saved state
        cursor = db.db.loadouts.find({"player_char_id": p_char_id})
        saved_rows = await cursor.to_list(length=10)
        saved_rows.sort(key=lambda r: r["slot"])

        return LoadoutResponse(
            player_char_id=req.player_char_id,
            slots=[_doc_to_slot(r) for r in saved_rows]
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error saving loadout: {str(e)}")