"""
routers/shop.py
---------------
GET  /shop              — all available shop listings with character details
POST /shop/buy          — direct purchase a specific character
POST /shop/pack         — open a random gacha pack (3 characters)
POST /shop/summon       — spend 100 coins for 1 random character
"""

import random
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from db.mongo import db
from models.schemas import ShopItem, Character, BuyRequest, BuyResponse, PackResult, Player
from services.shop_service import open_pack

router = APIRouter()


# ------------------------------------------------------------------ #
#  Shared helpers                                                    #
# ------------------------------------------------------------------ #

def _doc_to_character(doc: dict) -> Character:
    """Convert a raw characters collection document into a Character model."""
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    return Character(**d)


def _doc_to_player(doc: dict) -> Player:
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    return Player(**d)


async def _add_character_to_player(player_id_str: str, char_doc: dict):
    """
    Add a character to the player's roster.
    If already owned → increment duplicates counter.
    If new           → insert with full base-stat block.
    """
    p_oid = ObjectId(player_id_str)
    c_oid = ObjectId(char_doc["id"]) if "id" in char_doc else char_doc["_id"]

    owned = await db.player_characters.find_one({"player_id": p_oid, "char_id": c_oid})

    if owned:
        await db.player_characters.update_one(
            {"_id": owned["_id"]},
            {"$inc": {"duplicates": 1}},
        )
    else:
        await db.player_characters.insert_one({
            "player_id":  p_oid,
            "char_id":    c_oid,
            "level":      1,
            "xp":         0,
            "stars":      1,
            "duplicates": 0,
            "hp":    char_doc["base_hp"],
            "atk":   char_doc["base_atk"],
            "def":   char_doc["base_def"],
            "spd":   char_doc["base_spd"],
            "crit":  char_doc["base_crit"],
            "evade": char_doc["base_evade"],
        })


# ------------------------------------------------------------------ #
#  Endpoints                                                         #
# ------------------------------------------------------------------ #

@router.get("/shop", response_model=list[ShopItem])
async def get_shop():
    """All available shop listings with embedded character data."""
    items_cursor = db.shop_items.find({"available": True})
    items        = await items_cursor.to_list(length=50)

    all_chars    = await db.characters.find({}).to_list(length=100)
    char_map     = {str(c["_id"]): c for c in all_chars}

    result = []
    for item in items:
        item_id     = str(item["_id"])
        char_id_str = str(item["char_id"]) if item.get("char_id") else None
        char_doc    = char_map.get(char_id_str) if char_id_str else None

        result.append(ShopItem(
            id=item_id,
            item_type=item["item_type"],
            char_id=char_id_str or "",
            price=item["price"],
            currency=item["currency"],
            available=item["available"],
            character=_doc_to_character(char_doc) if char_doc else None,
        ))
    return result


@router.post("/shop/buy", response_model=BuyResponse)
async def buy_direct(req: BuyRequest):
    """Purchase a specific character directly from the shop."""
    try:
        p_oid = ObjectId(req.player_id)
        s_oid = ObjectId(req.shop_item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    player = await db.players.find_one({"_id": p_oid})
    item   = await db.shop_items.find_one({"_id": s_oid})

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    if not item:
        raise HTTPException(status_code=404, detail="Shop item not found")
    if item["item_type"] != "direct":
        raise HTTPException(status_code=400, detail="Use /shop/pack for pack items")

    currency = item["currency"]
    price    = item["price"]

    if player.get(currency, 0) < price:
        return BuyResponse(
            success=False,
            message=f"Not enough {currency}. Need {price}, have {player.get(currency, 0)}.",
        )

    await db.players.update_one({"_id": p_oid}, {"$inc": {currency: -price}})

    char_doc = await db.characters.find_one({"_id": item["char_id"]})
    if not char_doc:
        raise HTTPException(status_code=500, detail="Character data missing")

    char_doc["id"] = str(char_doc["_id"])
    await _add_character_to_player(req.player_id, char_doc)

    updated_player = await db.players.find_one({"_id": p_oid})
    return BuyResponse(
        success=True,
        message=f"{char_doc['name']} added to your roster!",
        player=_doc_to_player(updated_player),
        character=_doc_to_character(char_doc),
    )


@router.post("/shop/pack", response_model=PackResult)
async def open_pack_endpoint(req: BuyRequest):
    """Open a gacha pack and receive 3 random characters."""
    try:
        p_oid = ObjectId(req.player_id)
        s_oid = ObjectId(req.shop_item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    player = await db.players.find_one({"_id": p_oid})
    item   = await db.shop_items.find_one({"_id": s_oid})

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    if not item or item["item_type"] not in ("pack", "pack_premium"):
        raise HTTPException(status_code=400, detail="Not a pack item")

    currency = item["currency"]
    price    = item["price"]

    if player.get(currency, 0) < price:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough {currency}. Need {price}, have {player.get(currency, 0)}.",
        )

    await db.players.update_one({"_id": p_oid}, {"$inc": {currency: -price}})

    drawn = await open_pack(db, item["item_type"])
    for char in drawn:
        char["id"] = str(char["_id"])
        await _add_character_to_player(req.player_id, char)

    updated_player = await db.players.find_one({"_id": p_oid})
    char_objects   = [_doc_to_character(c) for c in drawn]
    names          = ", ".join(c.name for c in char_objects)

    return PackResult(
        characters=char_objects,
        message=f"Pack opened! You got: {names}",
        player=_doc_to_player(updated_player),
    )


@router.post("/shop/summon")
async def summon(player_id: str):
    """
    Spend 100 coins for one random character from the master roster.
    Handles duplicates by incrementing the counter.
    Returns the summoned character and updated player.
    """
    SUMMON_COST = 100

    try:
        p_oid = ObjectId(player_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid player ID")

    player = await db.players.find_one({"_id": p_oid})
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if player.get("coins", 0) < SUMMON_COST:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough coins. Need {SUMMON_COST}, have {player.get('coins', 0)}.",
        )

    # Deduct coins atomically
    await db.players.update_one({"_id": p_oid}, {"$inc": {"coins": -SUMMON_COST}})

    # Pick a random character weighted by rarity
    all_chars = await db.characters.find({}).to_list(length=100)
    if not all_chars:
        raise HTTPException(status_code=500, detail="No characters in database")

    rarity_weights = {"C": 70, "R": 20, "SR": 8, "UR": 2}
    rarities = list(rarity_weights.keys())
    weights  = list(rarity_weights.values())

    selected_rarity = random.choices(rarities, weights=weights, k=1)[0]
    eligible = [c for c in all_chars if c.get("rarity") == selected_rarity] or all_chars
    summoned = random.choice(eligible)

    summoned["id"] = str(summoned["_id"])
    await _add_character_to_player(player_id, summoned)

    updated_player = await db.players.find_one({"_id": p_oid})
    updated_player["id"] = str(updated_player.pop("_id"))

    return {
        "success":   True,
        "character": _doc_to_character(summoned),
        "player":    updated_player,
        "message":   f"Summoned {summoned['name']} ({summoned['rarity']})!",
    }