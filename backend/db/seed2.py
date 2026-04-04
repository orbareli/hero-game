import asyncio
import motor.motor_asyncio
from datetime import datetime

# Connection setup
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "fight_game"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ------------------------------------------------------------------ #
#  Data Definitions                                                  #
# ------------------------------------------------------------------ #

characters = [
    {
        "name": "Ironclad",
        "faction": "hero",
        "rarity": "R",
        "base_hp": 520,
        "base_atk": 70,
        "base_def": 55,
        "base_spd": 4,
        "base_crit": 10,
        "base_evade": 5,
        "passive_name": "Steel Skin",
        "passive_desc": "Reduces all incoming damage by 8%.",
        "skill_name": "Shield Slam",
        "skill_desc": "Deals 1.8x ATK damage and reduces enemy ATK by 15% for 2 turns.",
        "skill_mult": 1.8,
        "skill_cd": 3,
        "portrait_id": "ironclad",
    },
    {
        "name": "Swiftbolt",
        "faction": "hero",
        "rarity": "C",
        "base_hp": 300,
        "base_atk": 95,
        "base_def": 20,
        "base_spd": 9,
        "base_crit": 25,
        "base_evade": 18,
        "passive_name": "Lightning Reflexes",
        "passive_desc": "Gains +5% CRIT chance when going first in a turn.",
        "skill_name": "Thunderstrike",
        "skill_desc": "Deals 2.2x ATK damage. Always crits if enemy HP is above 80%.",
        "skill_mult": 2.2,
        "skill_cd": 4,
        "portrait_id": "swiftbolt",
    },
    {
        "name": "Void Queen",
        "faction": "villain",
        "rarity": "UR",
        "base_hp": 560,
        "base_atk": 110,
        "base_def": 40,
        "base_spd": 7,
        "base_crit": 22,
        "base_evade": 12,
        "passive_name": "Dark Throne",
        "passive_desc": "Gains +10% ATK for every 20% HP lost.",
        "skill_name": "Void Rupture",
        "skill_desc": "Deals 2.5x ATK damage. Gains 1 charge — 3 charges triggers a free turn.",
        "skill_mult": 2.5,
        "skill_cd": 5,
        "portrait_id": "voidqueen",
    }
]

# ------------------------------------------------------------------ #
#  Seeding Logic                                                     #
# ------------------------------------------------------------------ #

async def run_seed():
    print(f"=== Connecting to MongoDB at {MONGO_URL} ===")
    
    # 1. Clear existing data (Equivalent to Drop Tables)
    await db.characters.drop()
    await db.players.drop()
    await db.player_characters.drop()
    await db.shop_items.drop()
    print("  Cleared all existing collections.")

    # 2. Seed Characters
    print("\n=== Seeding Characters ===")
    result = await db.characters.insert_many(characters)
    # Map names to the new MongoDB ObjectIDs for later use
    char_map = {}
    cursor = db.characters.find({})
    async for char in cursor:
        char_map[char["name"]] = char["_id"]
        print(f"  Inserted: {char['name']} (ID: {char['_id']})")

    # 3. Seed Default Player
    print("\n=== Seeding Default Player ===")
    player_data = {
        "username": "Player1",
        "coins": 500,
        "gems": 10,
        "created_at": datetime.utcnow()
    }
    player_result = await db.players.insert_one(player_data)
    player_id = player_result.inserted_id
    print(f"  Created Player1 (ID: {player_id})")

    # 4. Give Starter Characters to Player
    print("\n=== Giving Starters to Player ===")
    starters = ["Swiftbolt"]
    for name in starters:
        if name in char_map:
            char_id = char_map[name]
            master_data = next(c for c in characters if c["name"] == name)
            
            # In Mongo, we can store the character's current stats directly
            pc_data = {
                "player_id": player_id,
                "char_id": char_id,
                "level": 1,
                "xp": 0,
                "hp": master_data["base_hp"],
                "atk": master_data["base_atk"],
                "def": master_data["base_def"],
                "spd": master_data["base_spd"]
            }
            await db.player_characters.insert_one(pc_data)
            print(f"  Linked {name} to Player1")

    # 5. Seed Shop
    print("\n=== Seeding Shop ===")
    shop_items = []
    for name, cid in char_map.items():
        shop_items.append({
            "item_type": "direct",
            "char_id": cid,
            "price": 400,
            "currency": "coins",
            "available": True
        })
    
    if shop_items:
        await db.shop_items.insert_many(shop_items)
        print(f"  Added {len(shop_items)} items to the shop.")

    print("\n=== Seed Complete! ===")
    print("You can now restart your backend with the MongoDB drivers.")

if __name__ == "__main__":
    asyncio.run(run_seed())