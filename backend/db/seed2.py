"""
db/seed2.py
-----------
Run once to populate the fight_game database with starter data.
    python -m db.seed2
"""
import asyncio
import motor.motor_asyncio
from datetime import datetime

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "fight_game"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ------------------------------------------------------------------ #
#  Master Character Definitions                                       #
# ------------------------------------------------------------------ #

characters = [
    {
        "name": "omni-man",
        "faction": "hero",          # "hero" or "villain"
        "element": "Power", # הוספת אלמנט
        "rarity": "SR",             # "C", "R", "SR", or "UR"
        "base_hp":    1600,
        "base_atk":   100,
        "base_def":   25,
        "base_spd":   8,            # higher = acts first
        "base_crit":  35,           # % chance to crit
        "base_evade": 15,           # % chance to dodge
        "passive_name": "MyPassive",
        "passive_desc": "Omni man s1",
        "skill_name": "World-Class Execution",
        "skill_desc": "Deals 2.8x ATK damage for 2 turns",
        "skill_mult": 1.8,          # damage multiplier (1.0 = basic attack level)
        "skill_cd":   4,            # turns before skill can be used again
        "portrait_id": "omni man",   # used for future portrait images
    },
    {
        "name": "invincible",
        "faction": "hero",          # "hero" or "villain"
        "element": "Power", # הוספת אלמנט
        "rarity": "SR",             # "C", "R", "SR", or "UR"
        "base_hp":    1250,
        "base_atk":   100,
        "base_def":   15,
        "base_spd":   6,            # higher = acts first
        "base_crit":  20,           # % chance to crit
        "base_evade": 20,           # % chance to dodge
        "passive_name": "MyPassive",
        "passive_desc": "invincible s1",
        "skill_name": "viltrumaite",
        "skill_desc": "Deals 2.8x ATK damage for 2 turns",
        "skill_mult": 2.8,          # damage multiplier (1.0 = basic attack level)
        "skill_cd":   4,            # turns before skill can be used again
        "portrait_id": "invincible",   # used for future portrait images
    },
        {
        "name": "conquest",
        "faction": "villain",          # "hero" or "villain"
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",             # "C", "R", "SR", or "UR"
        "base_hp":    2000,
        "base_atk":   160,
        "base_def":   20,
        "base_spd":   4,            # higher = acts first
        "base_crit":  15,           # % chance to crit
        "base_evade": 15,           # % chance to dodge
        "passive_name": "MyPassive",
        "passive_desc": "invincible s1",
        "skill_name": "Inexorable Assault",
        "skill_desc": "smash you with 3 attacks",
        "skill_mult": 0.7,          # damage multiplier (1.0 = basic attack level)
        "skill_cd":   4,            # turns before skill can be used again
        "portrait_id": "conquest",   # used for future portrait images
    },
    {
        "name": "Atom Eve",
        "faction": "hero",
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 1000,
        "base_atk": 70,
        "base_def": 20,
        "base_spd": 4,
        "base_crit": 12,
        "base_evade": 15,
        "passive_name": "Matter Rebirth",
        "passive_desc": "When HP falls below 20%, instantly heals 30% HP (once per battle).",
        "skill_name": "Molecular Manipulation",
        "skill_desc": "Deals 130% damage and restores HP based on damage dealt.",
        "skill_mult": 1.3,
        "skill_cd": 3,
        "portrait_id": "atom_eve"
    },
    {
        "name": "Allen the Alien",
        "faction": "hero",
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 1700,
        "base_atk": 95,
        "base_def": 35,
        "base_spd": 4,
        "base_crit": 7,
        "base_evade": 10,
        "passive_name": "Zenithian Physiology",
        "passive_desc": "Reduces incoming damage by 15%.",
        "skill_name": "Unstoppable Evolution",
        "skill_desc": "Deals 140% damage and permanently increases ATK for the rest of the battle.",
        "skill_mult": 1.4,
        "skill_cd": 4,
        "portrait_id": "allen_alien"
    },
    {
        "name": "Cecil Stedman",
        "faction": "villain",
        "element": "Tech", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 750,
        "base_atk": 75,
        "base_def": 30,
        "base_spd": 7,
        "base_crit": 15,
        "base_evade": 45,
        "passive_name": "Global Agency",
        "passive_desc": "Start the battle with a 20% Evade buff.",
        "skill_name": "Orbital Strike",
        "skill_desc": "High damage orbital laser that disrupts enemy sensors, reducing their Crit chance.",
        "skill_mult": 1.7,
        "skill_cd": 5,
        "portrait_id": "cecil"
    },
    {
        "name": "Superman",
        "faction": "villain",
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 2500,
        "base_atk": 200,
        "base_def": 23,
        "base_spd": 6,
        "base_crit": 15,
        "base_evade": 5,
        "passive_name": "Solar Absorption",
        "passive_desc": "Heals 5% of max HP every turn while HP is above 50%.",
        "skill_name": "Heat Vision",
        "skill_desc": "Deals 180% pure damage, ignoring enemy defense.",
        "skill_mult": 1.8,
        "skill_cd": 4,
        "portrait_id": "superman"
    },
    {
        "name": "The Flash",
        "faction": "villain",
        "element": "Speed", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 900,
        "base_atk": 110,
        "base_def": 10,
        "base_spd": 12,
        "base_crit": 25,
        "base_evade": 45,
        "passive_name": "Speed Force",
        "passive_desc": "Has a 20% chance to act twice in a single turn.",
        "skill_name": "Infinite Mass Punch",
        "skill_desc": "Deals 150% damage. Damage increases based on Flash's Speed.",
        "skill_mult": 1.5,
        "skill_cd": 3,
        "portrait_id": "flash"
    },
    {
        "name": "Wonder Woman",
        "faction": "villain",
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 1600,
        "base_atk": 160,
        "base_def": 30,
        "base_spd": 5,
        "base_crit": 20,
        "base_evade": 15,
        "passive_name": "Bracelets of Submission",
        "passive_desc": "Reflects 20% of incoming damage back to the attacker.",
        "skill_name": "Lasso of Truth",
        "skill_desc": "Deals 140% damage and stuns the enemy for 1 turn.",
        "skill_mult": 1.4,
        "skill_cd": 5,
        "portrait_id": "wonder_woman"
    },
    {
        "name": "Batman",
        "faction": "villain",
        "element": "Tech", # הוספת אלמנט
        "rarity": "SR",
        "base_hp": 1100,
        "base_atk": 130,
        "base_def": 15,
        "base_spd": 8,
        "base_crit": 30,
        "base_evade": 30,
        "passive_name": "Prep Time",
        "passive_desc": "Increases Crit Damage by 50% but reduces Base HP.",
        "skill_name": "Explosive Batarang",
        "skill_desc": "Deals 120% damage and reduces enemy Attack for 2 turns.",
        "skill_mult": 1.2,
        "skill_cd": 3,
        "portrait_id": "batman"
    },
    {
        "name": "Homelander",
        "faction": "villain",
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 1900,
        "base_atk": 170,
        "base_def": 5,
        "base_spd": 5,
        "base_crit": 10,
        "base_evade": 5,
        "passive_name": "God Complex",
        "passive_desc": "Deals 20% more damage against enemies with lower ATK than him.",
        "skill_name": "Laser Eyes",
        "skill_desc": "Deals 160% damage. If it kills the target, resets cooldown.",
        "skill_mult": 1.6,
        "skill_cd": 4,
        "portrait_id": "homelander"
    },
    {
        "name": "Swiftbolt",
        "faction": "hero",
        "element": "Power", # הוספת אלמנט
        "rarity": "C",
        "base_hp": 1300,
        "base_atk": 95,
        "base_def": 10,
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
        "element": "Power", # הוספת אלמנט
        "rarity": "UR",
        "base_hp": 1560,
        "base_atk": 110,
        "base_def": 15,
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
    },
    {
        "name": "Graviton",
        "faction": "villain",
        "element": "Power", # הוספת אלמנט
        "rarity": "SR",
        "base_hp": 480,
        "base_atk": 80,
        "base_def": 45,
        "base_spd": 5,
        "base_crit": 12,
        "base_evade": 8,
        "passive_name": "Gravity Well",
        "passive_desc": "Reduces enemy SPD by 2 permanently.",
        "skill_name": "Singularity",
        "skill_desc": "Deals 1.6x ATK damage, ignores 50% of enemy DEF.",
        "skill_mult": 1.6,
        "skill_cd": 4,
        "portrait_id": "graviton",
    },
]

# ------------------------------------------------------------------ #
#  Seeding Logic                                                      #
# ------------------------------------------------------------------ #

async def run_seed():
    print(f"=== Connecting to MongoDB ({DB_NAME}) ===")

    # 1. Drop existing collections for a clean slate
    await db.characters.drop()
    await db.players.drop()
    await db.player_characters.drop()
    await db.shop_items.drop()
    await db.loadouts.drop()
    print("  ✓ Cleared all collections")

    # 2. Insert master characters
    print("\n=== Seeding Characters ===")
    await db.characters.insert_many(characters)
    char_map = {}
    async for char in db.characters.find({}):
        char_map[char["name"]] = char
        print(f"  + {char['name']} ({char['rarity']})  id={char['_id']}")

    # 3. Create default player
    print("\n=== Seeding Player ===")
    player_doc = {
        "username": "Player1",
        "coins": 1500,
        "gems": 10,
        "created_at": datetime.utcnow(),
    }
    player_result = await db.players.insert_one(player_doc)
    player_id = player_result.inserted_id
    print(f"  + Player1  id={player_id}")

    # 4. Give starter character — full stat block required by engine + schemas
    print("\n=== Giving Starters ===")
    starters = ["Swiftbolt"]
    for name in starters:
        if name not in char_map:
            continue
        master = char_map[name]
        pc_doc = {
            "player_id": player_id,
            "char_id":   master["_id"],
            "level":     1,
            "xp":        0,
            "stars":     1,
            "duplicates": 0,
            # Current stats (start at base values)
            "hp":    master["base_hp"],
            "atk":   master["base_atk"],
            "def":   master["base_def"],   # engine reads "def"
            "spd":   master["base_spd"],
            "crit":  master["base_crit"],
            "evade": master["base_evade"],
        }
        await db.player_characters.insert_one(pc_doc)
        print(f"  + {name} → Player1")

    # 5. Populate shop (one listing per character)
    print("\n=== Seeding Shop ===")
    shop_items = [
        {
            "item_type": "direct",
            "char_id":   char["_id"],
            "price":     400,
            "currency":  "coins",
            "available": True,
        }
        for char in char_map.values()
    ]
    # Add a gacha pack option
    shop_items.append({
        "item_type": "pack",
        "char_id":   None,   # packs don't have a single char_id
        "price":     100,
        "currency":  "coins",
        "available": True,
    })
    await db.shop_items.insert_many(shop_items)
    print(f"  + {len(shop_items)} shop items")

    # 6. Create indexes for common query patterns
    await db.player_characters.create_index([("player_id", 1)])
    await db.loadouts.create_index([("player_char_id", 1)])
    print("\n  ✓ Indexes created")

    print("\n=== Seed complete! ===")
    print(f"Player ID (use this in the UI): {player_id}")


if __name__ == "__main__":
    asyncio.run(run_seed())