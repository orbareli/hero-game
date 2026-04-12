"""
routers/loadout.py
------------------
GET  /loadout/{player_char_id}  — fetch saved loadout (or default)
POST /loadout                   — save / replace loadout (max 2 slots)
"""

from fastapi import APIRouter, HTTPException
from bson import ObjectId

from db.mongo import db
from models.schemas import LoadoutRequest, LoadoutResponse, LoadoutSlot

router = APIRouter()


def _doc_to_slot(doc: dict) -> LoadoutSlot:
    return LoadoutSlot(
        player_char_id=str(doc["player_char_id"]),
        slot=doc["slot"],
        ability_type=doc["ability_type"],
    )


@router.get("/loadout/{player_char_id}", response_model=LoadoutResponse)
async def get_loadout(player_char_id: str):
    """Fetch the saved loadout for a player character, or return default."""
    try:
        pc_oid = ObjectId(player_char_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    cursor = db.loadouts.find({"player_char_id": pc_oid})
    rows   = await cursor.to_list(length=10)
    rows.sort(key=lambda r: r["slot"])

    slots = [_doc_to_slot(r) for r in rows]

    if not slots:
        slots = [
            LoadoutSlot(player_char_id=player_char_id, slot=0, ability_type="skill"),
            LoadoutSlot(player_char_id=player_char_id, slot=1, ability_type="default"),
        ]

    return LoadoutResponse(player_char_id=player_char_id, slots=slots)


@router.post("/loadout", response_model=LoadoutResponse)
async def save_loadout(req: LoadoutRequest):
    """Replace all loadout slots for a player character."""
    if len(req.slots) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 loadout slots")

    try:
        pc_oid = ObjectId(req.player_char_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    pc = await db.player_characters.find_one({"_id": pc_oid})
    if not pc:
        raise HTTPException(status_code=404, detail="Player character not found")

    # Atomic replace
    await db.loadouts.delete_many({"player_char_id": pc_oid})

    if req.slots:
        await db.loadouts.insert_many([
            {"player_char_id": pc_oid, "slot": s.slot, "ability_type": s.ability_type}
            for s in req.slots
        ])

    cursor    = db.loadouts.find({"player_char_id": pc_oid})
    saved     = await cursor.to_list(length=10)
    saved.sort(key=lambda r: r["slot"])

    return LoadoutResponse(
        player_char_id=req.player_char_id,
        slots=[_doc_to_slot(r) for r in saved],
    )