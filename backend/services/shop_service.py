"""import random
from db.client import DBClient

def open_pack(db: DBClient, pack_type: str) -> list[dict]:
    "
    Logic for opening a character pack.
    Returns a list of 3 character dictionaries from the master 'characters' table.
    "
    # 1. Fetch all available characters from the master table
    all_chars = db.query("SELECT * FROM characters")
    
    if not all_chars:
        return []

    # 2. Define rarity weights (adjust these for game balance)
    # C: 70%, R: 20%, SR: 8%, UR: 2%
    rarity_map = {
        "C": 70,
        "R": 20,
        "SR": 8,
        "UR": 2
    }

    # 3. Draw 3 characters
    drawn_characters = []
    
    # If it's a premium pack, we could boost the odds here
    if pack_type == "pack_premium":
        rarity_map = {"C": 40, "R": 40, "SR": 15, "UR": 5}

    for _ in range(3):
        # Pick a rarity based on weights
        rarities = list(rarity_map.keys())
        weights = list(rarity_map.values())
        selected_rarity = random.choices(rarities, weights=weights, k=1)[0]

        # Filter all_chars for that rarity
        eligible = [c for c in all_chars if c["rarity"] == selected_rarity]
        
        # Fallback: if no UR exists, just pick from all
        if not eligible:
            eligible = all_chars
            
        drawn_characters.append(random.choice(eligible))

    return drawn_characters"""
import random
from motor.motor_asyncio import AsyncIOMotorClient

async def open_pack(db_manager, pack_type: str) -> list[dict]:
    """
    Logic for opening a character pack using MongoDB.
    Returns a list of 3 character documents.
    """
    # 1. Access the characters collection
    collection = db_manager.db.characters

    # 2. Define rarity weights (adjust these for game balance)
    # Standard: C: 70%, R: 20%, SR: 8%, UR: 2%
    rarity_weights = {
        "C": 70,
        "R": 20,
        "SR": 8,
        "UR": 2
    }

    # If it's a premium pack, boost the odds
    if pack_type == "pack_premium":
        rarity_weights = {"C": 40, "R": 40, "SR": 15, "UR": 5}

    drawn_characters = []
    rarities = list(rarity_weights.keys())
    weights = list(rarity_weights.values())

    for _ in range(3):
        # A. Pick a rarity based on weights
        selected_rarity = random.choices(rarities, weights=weights, k=1)[0]

        # B. Query MongoDB for characters with that rarity
        # We use an aggregation or find to get a random one efficiently
        cursor = collection.find({"rarity": selected_rarity})
        eligible = await cursor.to_list(length=100)

        # C. Fallback: If no characters of that rarity exist in DB yet, pick any
        if not eligible:
            cursor = collection.find({})
            eligible = await cursor.to_list(length=100)

        if eligible:
            drawn_characters.append(random.choice(eligible))

    return drawn_characters