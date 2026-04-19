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
        "name": "monster-girl",
        "faction": "villain",          # "hero" or "villain"
        "element": "Power", # הוספת אלמנט
        "rarity": "R",             # "C", "R", "SR", or "UR"
        "base_hp":    1300,
        "base_atk":   95,
        "base_def":   20,
        "base_spd":   2,            # higher = acts first
        "base_crit":  10,           # % chance to crit
        "base_evade": 5,           # % chance to dodge
        "passive_name": "MyPassive",
        "passive_desc": "Omni man s1",
        "skill_name": "Primal Rage",
        "skill_desc": "Deals 2.9x ATK damage but lose o.5x atk life",
        "skill_mult": 2.9,          # damage multiplier (1.0 = basic attack level)
        "skill_cd":   3,            # turns before skill can be used again
        "portrait_id": "omni man",   # used for future portrait images
    },
        {
        "name": "Saitama",
        "faction": "hero",
        "element": "Cosmic",
        "rarity": "UR",
        "base_hp":    2000,
        "base_atk":   300,
        "base_def":   5,
        "base_spd":   7,
        "base_crit":  3,
        "base_evade": 20,
        "passive_name": "Serious Punch",
        "passive_desc": "Once per battle, when Saitama would be KO'd, he survives with 1 HP and next attack crits.",
        "skill_name": "One Punch",
        "skill_desc": "Single devastating punch. Ignores ALL DEF. Cannot miss.",
        "skill_mult": 3.3,
        "skill_cd":   6,
        "portrait_id": "saitama",
    },
    {
        "name": "Goku",
        "faction": "hero",
        "element": "Cosmic",
        "rarity": "UR",
        "base_hp":    2200,
        "base_atk":   220,
        "base_def":   15,
        "base_spd":   10,
        "base_crit":  20,
        "base_evade": 20,
        "passive_name": "Saiyan Pride",
        "passive_desc": "When HP drops below 30%, Goku enters Kaioken: +40% ATK for the rest of the battle.",
        "skill_name": "Kamehameha",
        "skill_desc": "3.0× beam attack, ignores 40% DEF.",
        "skill_mult": 3.0,
        "skill_cd":   4,
        "portrait_id": "goku",
    },
    {
        "name": "Magneto",
        "faction": "villain",
        "element": "Mystic",
        "rarity": "UR",
        "base_hp":    1400,
        "base_atk":   130,
        "base_def":   30,
        "base_spd":   6,
        "base_crit":  18,
        "base_evade": 15,
        "passive_name": "Master of Magnetism",
        "passive_desc": "Tech-element enemies take 40% more damage from Magneto (metal vulnerability).",
        "skill_name": "Magnetic Crush",
        "skill_desc": "2.2× dmg. Tech enemies take 40% bonus damage. Applies ATK-down.",
        "skill_mult": 2.2,
        "skill_cd":   4,
        "portrait_id": "magneto",
    },
    {
        "name": "Black Widow",
        "faction": "hero",
        "element": "Tech",
        "rarity": "SR",
        "base_hp":    1000,
        "base_atk":   110,
        "base_def":   20,
        "base_spd":   10,
        "base_crit":  40,
        "base_evade": 30,
        "passive_name": "Red Room Training",
        "passive_desc": "Critical hits deal 2.0× bonus damage instead of 1.5×. Precision killer.",
        "skill_name": "Widow's Bite",
        "skill_desc": "1.6× dmg, guaranteed crit, stuns target for 1 turn.",
        "skill_mult": 1.6,
        "skill_cd":   3,
        "portrait_id": "black_widow",
    },
    {
        "name": "Thragg",
        "faction": "villain",
        "element": "Power",
        "rarity": "UR",
        "base_hp": 2400,
        "base_atk": 150,
        "base_def": 30,
        "base_spd": 7,
        "base_crit": 25,
        "base_evade": 15,
        "passive_name": "Dark Throne",
        "passive_desc": "Increases ATK by 1% for every 5% HP lost.",
        "skill_name": "Grand Regent's Might",
        "skill_desc": "Unleashes a devastating blow dealing 3.5x damage.",
        "skill_mult": 3.1,
        "skill_cd": 5,
        "portrait_id": "Thragg",
    },
    {
        "name": "Thor",
        "faction": "hero",
        "element": "Power",
        "rarity": "UR",
        "base_hp": 1900,
        "base_atk": 135,
        "base_def": 40,
        "base_spd": 3,
        "base_crit": 15,
        "base_evade": 5,
        "passive_name": "God of Thunder",
        "passive_desc": "Basic attacks have a 25% chance to shock the target.",
        "skill_name": "Mjolnir's Strike",
        "skill_desc": "Strikes with lightning for 2.8x damage.",
        "skill_mult": 2.8,
        "skill_cd": 4,
        "portrait_id": "Thor",
    },
    {
        "name": "Iron Man",
        "faction": "hero",
        "element": "Tech",
        "rarity": "SR",
        "base_hp": 1400,
        "base_atk": 115,
        "base_def": 30,
        "base_spd": 4,
        "base_crit": 12,
        "base_evade": 10,
        "passive_name": "Arc Reactor",
        "passive_desc": "Regenerates 10 energy every turn.",
        "skill_name": "Unibeam",
        "skill_desc": "High precision beam dealing 2.2x damage.",
        "skill_mult": 2.2,
        "skill_cd": 3,
        "portrait_id": "Iron Man",
    },
    {
        "name": "Hulk",
        "faction": "hero",
        "element": "Power",
        "rarity": "UR",
        "base_hp":    3000,
        "base_atk":   110,
        "base_def":   10,
        "base_spd":   3,
        "base_crit":  10,
        "base_evade": 5,
        "passive_name": "Rage Engine",
        "passive_desc": "The angrier Hulk gets (lower HP %), the more damage he deals. Gamma Slam scales with missing HP.",
        "skill_name": "Gamma Slam",
        "skill_desc": "2.5× dmg that grows with rage (missing HP %). The lower his HP, the harder he hits.",
        "skill_mult": 2.5,
        "skill_cd":   3,
        "portrait_id": "Hulk",
    },
    {
        "name": "Spider-Man",
        "faction": "hero",
        "element": "Speed",
        "rarity": "SR",
        "base_hp":    1100,
        "base_atk":   115,
        "base_def":   15,
        "base_spd":   10,
        "base_crit":  20,
        "base_evade": 33,
        "passive_name": "Spider-Sense",
        "passive_desc": "Spidey's danger sense gives him a 20% chance to dodge any incoming attack for free.",
        "skill_name": "Web Shot",
        "skill_desc": "1.8× dmg + webs target, reducing their SPD by 4 for 2 turns.",
        "skill_mult": 1.8,
        "skill_cd":   3,
        "portrait_id": "spiderman",
    },
    {
        "name": "Soldier Boy",
        "faction": "villain",
        "element": "Power",
        "rarity": "SR",
        "base_hp":    1600,
        "base_atk":   125,
        "base_def":   20,
        "base_spd":   6,
        "base_crit":  20,
        "base_evade": 10,
        "passive_name": "Compound V Soldier",
        "passive_desc": "Soldier Boy ignores 15% of enemy defense on all attacks — his shield absorbs punishment.",
        "skill_name": "Compound V Blast",
        "skill_desc": "2.0× dmg ignoring 60% DEF. Target ATK -25% for 2 turns.",
        "skill_mult": 2.0,
        "skill_cd":   4,
        "portrait_id": "soldier_boy",
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
        "base_atk": 75,
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
    print(f"=== indexes ===")
    await db.tower_sessions.create_index([("player_id", 1), ("status", 1)])
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
        "coins": 11500,
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
    import asyncio
    asyncio.run(run_seed())
