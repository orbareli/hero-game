"""
routers/shop.py
---------------
GET  /shop                   — all shop listings with character detail
POST /shop/buy               — direct purchase a specific character
POST /shop/pack              — open a random pack


from fastapi import APIRouter, HTTPException
from db.client import get_db
from models.schemas import (
    ShopItem, Character, BuyRequest, BuyResponse, PackResult, Player
)
from services.shop_service import open_pack
from routers.characters import _row_to_character

router = APIRouter()


def _row_to_player(row: dict) -> Player:
    return Player(
        id=row["id"],
        username=row["username"],
        coins=row["coins"],
        gems=row["gems"],
    )


def _add_character_to_player(db, player_id: int, char: dict):
    "
    Add a character to player's roster.
    If already owned, increment duplicates instead.
    "
    owned = db.query(
        f"SELECT * FROM player_characters "
        f"WHERE player_id = {player_id} AND char_id = {char['id']}"
    )
    if owned:
        pc = owned[0]
        new_dups = pc["duplicates"] + 1
        db.execute(
            f"UPDATE player_characters SET duplicates = {new_dups} "
            f"WHERE id = {pc['id']}"
        )
    else:
        db.execute(
            f"INSERT INTO player_characters "
            f"(player_id, char_id, level, xp, stars, duplicates, "
            f"hp, atk, def, spd, crit, evade) VALUES ("
            f"{player_id}, {char['id']}, 1, 0, 1, 0, "
            f"{char['base_hp']}, {char['base_atk']}, {char['base_def']}, "
            f"{char['base_spd']}, {char['base_crit']}, {char['base_evade']})"
        )


# ------------------------------------------------------------------ #
#  Endpoints                                                           #
# ------------------------------------------------------------------ #

@router.get("/shop", response_model=list[ShopItem])
def get_shop():
    ""All shop listings. Direct purchases include the full character object.""
    db = get_db()

    items     = db.query("SELECT * FROM shop_items WHERE available = 1")
    all_chars = db.query("SELECT * FROM characters")
    char_map  = {c["id"]: c for c in all_chars}

    result = []
    for item in items:
        char = char_map.get(item["char_id"])
        result.append(ShopItem(
            id=item["id"],
            item_type=item["item_type"],
            char_id=item["char_id"],
            price=item["price"],
            currency=item["currency"],
            available=item["available"],
            character=_row_to_character(char) if char else None,
        ))
    return result


@router.post("/shop/buy", response_model=BuyResponse)
def buy_direct(req: BuyRequest):
    ""
    Purchase a specific character directly.
    Deducts currency, adds character to roster (or increments duplicates).
    ""
    db = get_db()

    # Validate player
    player_rows = db.query(f"SELECT * FROM players WHERE id = {req.player_id}")
    if not player_rows:
        raise HTTPException(status_code=404, detail="Player not found")
    player = player_rows[0]

    # Validate shop item
    item_rows = db.query(f"SELECT * FROM shop_items WHERE id = {req.shop_item_id}")
    if not item_rows:
        raise HTTPException(status_code=404, detail="Shop item not found")
    item = item_rows[0]

    if item["item_type"] not in ("direct",):
        raise HTTPException(status_code=400, detail="Use /shop/pack for pack purchases")

    # Check funds
    currency = item["currency"]
    balance  = player[currency]
    price    = item["price"]

    if balance < price:
        return BuyResponse(
            success=False,
            message=f"Not enough {currency}. Need {price}, have {balance}.",
        )

    # Deduct currency
    new_balance = balance - price
    db.execute(
        f"UPDATE players SET {currency} = {new_balance} WHERE id = {req.player_id}"
    )

    # Add character to roster
    char_rows = db.query(f"SELECT * FROM characters WHERE id = {item['char_id']}")
    if not char_rows:
        raise HTTPException(status_code=500, detail="Character data missing")
    char = char_rows[0]

    _add_character_to_player(db, req.player_id, char)

    # Return updated player
    updated_player_rows = db.query(f"SELECT * FROM players WHERE id = {req.player_id}")
    updated_player = _row_to_player(updated_player_rows[0])

    return BuyResponse(
        success=True,
        message=f"{char['name']} added to your roster!",
        player=updated_player,
        character=_row_to_character(char),
    )


@router.post("/shop/pack", response_model=PackResult)
def open_pack_endpoint(req: BuyRequest):
    ""
    Open a pack (standard or premium).
    req.shop_item_id must point to a pack or pack_premium shop item.
    Returns 3 characters.
    "
    db = get_db()

    # Validate player
    player_rows = db.query(f"SELECT * FROM players WHERE id = {req.player_id}")
    if not player_rows:
        raise HTTPException(status_code=404, detail="Player not found")
    player = player_rows[0]

    # Validate shop item
    item_rows = db.query(f"SELECT * FROM shop_items WHERE id = {req.shop_item_id}")
    if not item_rows:
        raise HTTPException(status_code=404, detail="Shop item not found")
    item = item_rows[0]

    if item["item_type"] not in ("pack", "pack_premium"):
        raise HTTPException(status_code=400, detail="Not a pack item")

    # Check funds
    currency = item["currency"]
    balance  = player[currency]
    price    = item["price"]

    if balance < price:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough {currency}. Need {price}, have {balance}."
        )

    # Deduct currency
    new_balance = balance - price
    db.execute(
        f"UPDATE players SET {currency} = {new_balance} WHERE id = {req.player_id}"
    )

    # Open the pack
    drawn_chars = open_pack(db, item["item_type"])

    for char in drawn_chars:
        _add_character_to_player(db, req.player_id, char)

    # Updated player
    updated_player_rows = db.query(f"SELECT * FROM players WHERE id = {req.player_id}")
    updated_player = _row_to_player(updated_player_rows[0])

    char_objects = [_row_to_character(c) for c in drawn_chars]
    names = ", ".join(c.name for c in char_objects)

    return PackResult(
        characters=char_objects,
        message=f"Pack opened! You got: {names}",
        player=updated_player,
    )
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from db.mongo import db  # Assuming your motor client is here
from models.schemas import (
    ShopItem, Character, BuyRequest, BuyResponse, PackResult, Player
)
from services.shop_service import open_pack
from routers.characters import _doc_to_character

router = APIRouter()

# ------------------------------------------------------------------ #
#  Helpers                                                           #
# ------------------------------------------------------------------ #

def _doc_to_player(doc: dict) -> Player:
    doc["id"] = str(doc.pop("_id"))
    return Player(**doc)

async def _add_character_to_player(player_id: str, char: dict):
    """
    Add a character to player's roster.
    If already owned, increment duplicates instead.
    """
    p_id = ObjectId(player_id)
    c_id = ObjectId(char["id"])

    # Check if already owned
    owned = await db.db.player_characters.find_one({
        "player_id": p_id, 
        "char_id": c_id
    })

    if owned:
        # Atomic increment of duplicates
        await db.db.player_characters.update_one(
            {"_id": owned["_id"]},
            {"$inc": {"duplicates": 1}}
        )
    else:
        # Fresh insert - MongoDB doesn't care about the number of columns!
        new_pc = {
            "player_id": p_id,
            "char_id": c_id,
            "level": 1,
            "xp": 0,
            "stars": 1,
            "duplicates": 0,
            "hp": char["base_hp"],
            "atk": char["base_atk"],
            "def": char["base_def"],
            "spd": char["base_spd"],
            "crit": char["base_crit"],
            "evade": char["base_evade"]
        }
        await db.db.player_characters.insert_one(new_pc)

# ------------------------------------------------------------------ #
#  Endpoints                                                         #
# ------------------------------------------------------------------ #

@router.get("/shop", response_model=list[ShopItem])
async def get_shop():
    """All shop listings with character details."""
    # 1. Fetch available items
    items_cursor = db.db.shop_items.find({"available": True})
    items = await items_cursor.to_list(length=50)
    
    # 2. Fetch all characters to map details
    chars_cursor = db.db.characters.find({})
    all_chars = await chars_cursor.to_list(length=100)
    char_map = {str(c["_id"]): c for c in all_chars}

    result = []
    for item in items:
        char_doc = char_map.get(str(item["char_id"]))
        
        # Format for Pydantic
        item_id = str(item.pop("_id"))
        char_id_str = str(item["char_id"])
        
        result.append(ShopItem(
            id=item_id,
            item_type=item["item_type"],
            char_id=char_id_str,
            price=item["price"],
            currency=item["currency"],
            available=item["available"],
            character=_doc_to_character(char_doc) if char_doc else None,
        ))
    return result

@router.post("/shop/buy", response_model=BuyResponse)
async def buy_direct(req: BuyRequest):
    p_id = ObjectId(req.player_id)
    s_id = ObjectId(req.shop_item_id)

    # 1. Validate player and shop item
    player = await db.db.players.find_one({"_id": p_id})
    item = await db.db.shop_items.find_one({"_id": s_id})

    if not player or not item:
        raise HTTPException(status_code=404, detail="Player or Item not found")

    if item["item_type"] != "direct":
        raise HTTPException(status_code=400, detail="Use /shop/pack for packs")

    # 2. Check funds
    currency = item["currency"]
    price = item["price"]
    if player.get(currency, 0) < price:
        return BuyResponse(success=False, message=f"Insufficient {currency}")

    # 3. Atomic Deduction
    await db.db.players.update_one(
        {"_id": p_id},
        {"$inc": {currency: -price}}
    )

    # 4. Get Character and Add to Roster
    char_doc = await db.db.characters.find_one({"_id": ObjectId(item["char_id"])})
    # Convert _id to string for the helper
    char_doc["id"] = str(char_doc["_id"])
    
    await _add_character_to_player(req.player_id, char_doc)

    # 5. Return updated state
    updated_player = await db.db.players.find_one({"_id": p_id})
    
    return BuyResponse(
        success=True,
        message=f"{char_doc['name']} purchased!",
        player=_doc_to_player(updated_player),
        character=_doc_to_character(char_doc)
    )

@router.post("/shop/pack", response_model=PackResult)
async def open_pack_endpoint(req: BuyRequest):
    p_id = ObjectId(req.player_id)
    s_id = ObjectId(req.shop_item_id)

    player = await db.db.players.find_one({"_id": p_id})
    item = await db.db.shop_items.find_one({"_id": s_id})

    if not item or item["item_type"] not in ("pack", "pack_premium"):
        raise HTTPException(status_code=400, detail="Invalid pack item")

    # Check and deduct funds
    currency = item["currency"]
    if player.get(currency, 0) < item["price"]:
        raise HTTPException(status_code=400, detail="Insufficient funds")

    await db.db.players.update_one({"_id": p_id}, {"$inc": {currency: -item["price"]}})

    # Open the pack (Update your service to be async if needed)
    drawn_chars = await open_pack(db, item["item_type"])

    for char in drawn_chars:
        char["id"] = str(char["_id"]) # ensure ID string exists for helper
        await _add_character_to_player(req.player_id, char)

    updated_player = await db.db.players.find_one({"_id": p_id})
    char_objects = [_doc_to_character(c) for c in drawn_chars]

    return PackResult(
        characters=char_objects,
        message=f"Pack opened! You got {len(char_objects)} heroes.",
        player=_doc_to_player(updated_player)
    )