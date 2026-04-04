"""
seed/seed.py
------------
Creates all game tables and populates them with:
  - 6 starter characters (3 heroes, 3 villains)
  - 1 default player
  - Shop listings for all characters + 2 pack types

Run once before starting the backend:
    python seed/seed.py

Safe to re-run — drops and recreates tables each time.
"""

import sys
import os
import sys, os, json, random, datetime, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

#ORSQL_HOST = "localhost"
# אם המשתנה קיים ב-Railway הוא יקח אותו, אם לא (במחשב שלך) הוא יקח localhost
ORSQL_HOST = os.getenv("ORSQL_HOST", "localhost")
ORSQL_PORT = 5555

# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #
def run_sql(query):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ORSQL_HOST, ORSQL_PORT))
        s.sendall(query.encode())
        s.shutdown(socket.SHUT_WR)
        chunks = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        response = json.loads(b"".join(chunks).decode())
        if response["error"]:
            raise Exception(response["error"])
        return response["result"]

def drop(table: str):
    try:
        run_sql(f"DROP TABLE {table}")
        print(f"  dropped {table}")
    except Exception:
        pass  # didn't exist

def create(sql: str, name: str):
    run_sql(sql)
    print(f"  created {name}")

def insert(sql: str):
    run_sql(sql)

# ------------------------------------------------------------------ #
#  Schema                                                              #
# ------------------------------------------------------------------ #

TABLES = [
    "loadouts",
    "battles",
    "player_characters",
    "shop_items",
    "players",
    "characters",
]

print("\n=== Dropping existing tables ===")
for t in TABLES:
    drop(t)

print("\n=== Creating tables ===")

create("""
CREATE TABLE characters (
    name          TEXT(50),
    faction       TEXT(10),
    rarity        TEXT(2),
    base_hp       INTEGER,
    base_atk      INTEGER,
    base_def      INTEGER,
    base_spd      INTEGER,
    base_crit     INTEGER,
    base_evade    INTEGER,
    passive_name  TEXT(50),
    passive_desc  TEXT(120),
    skill_name    TEXT(50),
    skill_desc    TEXT(120),
    skill_mult    FLOAT,
    skill_cd      INTEGER,
    portrait_id   TEXT(20)
)
""", "characters")

create("""
CREATE TABLE players (
    username   TEXT(30),
    coins      INTEGER,
    gems       INTEGER
)
""", "players")

create("""
CREATE TABLE player_characters (
    player_id  INTEGER,
    char_id    INTEGER,
    level      INTEGER,
    xp         INTEGER,
    stars      INTEGER,
    duplicates INTEGER,
    hp         INTEGER,
    atk        INTEGER,
    def        INTEGER,
    spd        INTEGER,
    crit       INTEGER,
    evade      INTEGER
)
""", "player_characters")

create("""
CREATE TABLE loadouts (
    player_char_id  INTEGER,
    slot            INTEGER,
    ability_type    TEXT(10)
)
""", "loadouts")

create("""
CREATE TABLE battles (
    player_id       INTEGER,
    enemy_char_id   INTEGER,
    player_char_id  INTEGER,
    outcome         TEXT(10),
    turns           INTEGER,
    log             TEXT(500),
    coins_earned    INTEGER,
    xp_earned       INTEGER
)
""", "battles")

create("""
CREATE TABLE shop_items (
    item_type   TEXT(10),
    char_id     INTEGER,
    price       INTEGER,
    currency    TEXT(5),
    available   INTEGER
)
""", "shop_items")

# ------------------------------------------------------------------ #
#  Starter characters                                                  #
# ------------------------------------------------------------------ #
#
#  Stat guide (base values, scale with level):
#    HP:    200–600    DEF: 10–60
#    ATK:   40–120     SPD: 1–10  (higher = goes first)
#    CRIT:  5–30 (%)   EVADE: 0–20 (%)
#
#  skill_mult: damage multiplier (1.0 = same as normal attack)
#  skill_cd:   turns before skill can be used again
#
#  Rarity: C (Common), R (Rare), SR (Super Rare), UR (Ultra Rare)

print("\n=== Seeding characters ===")

characters = [
    # ── HEROES ──────────────────────────────────────────────────────
    {
        "name":         "Ironclad",
        "faction":      "hero",
        "rarity":       "R",
        "base_hp":      520,
        "base_atk":     70,
        "base_def":     55,
        "base_spd":     4,
        "base_crit":    10,
        "base_evade":   5,
        "passive_name": "Steel Skin",
        "passive_desc": "Reduces all incoming damage by 8%",
        "skill_name":   "Shield Slam",
        "skill_desc":   "Deals 1.8x ATK damage and reduces enemy ATK by 15% for 2 turns",
        "skill_mult":   1.8,
        "skill_cd":     3,
        "portrait_id":  "ironclad",
    },
    {
        "name":         "Swiftbolt",
        "faction":      "hero",
        "rarity":       "C",
        "base_hp":      300,
        "base_atk":     95,
        "base_def":     20,
        "base_spd":     9,
        "base_crit":    25,
        "base_evade":   18,
        "passive_name": "Lightning Reflexes",
        "passive_desc": "Gains +5% CRIT chance when going first in a turn",
        "skill_name":   "Thunderstrike",
        "skill_desc":   "Deals 2.2x ATK damage. Always crits if enemy HP is above 80%",
        "skill_mult":   2.2,
        "skill_cd":     4,
        "portrait_id":  "swiftbolt",
    },
    {
        "name":         "Solaris",
        "faction":      "hero",
        "rarity":       "SR",
        "base_hp":      420,
        "base_atk":     85,
        "base_def":     35,
        "base_spd":     6,
        "base_crit":    15,
        "base_evade":   10,
        "passive_name": "Solar Aura",
        "passive_desc": "Heals 5% of max HP at the start of each turn",
        "skill_name":   "Nova Burst",
        "skill_desc":   "Deals 2.0x ATK damage and heals self for 20% of damage dealt",
        "skill_mult":   2.0,
        "skill_cd":     3,
        "portrait_id":  "solaris",
    },
    # ── VILLAINS ────────────────────────────────────────────────────
    {
        "name":         "Venom Shade",
        "faction":      "villain",
        "rarity":       "C",
        "base_hp":      280,
        "base_atk":     100,
        "base_def":     15,
        "base_spd":     8,
        "base_crit":    20,
        "base_evade":   15,
        "passive_name": "Toxic Touch",
        "passive_desc": "Normal attacks apply a 5 damage poison for 3 turns",
        "skill_name":   "Death Coil",
        "skill_desc":   "Deals 1.9x ATK and doubles poison damage this turn",
        "skill_mult":   1.9,
        "skill_cd":     3,
        "portrait_id":  "venomshade",
    },
    {
        "name":         "Graviton",
        "faction":      "villain",
        "rarity":       "SR",
        "base_hp":      480,
        "base_atk":     80,
        "base_def":     45,
        "base_spd":     5,
        "base_crit":    12,
        "base_evade":   8,
        "passive_name": "Gravity Well",
        "passive_desc": "Enemy SPD is reduced by 2 while Graviton is alive",
        "skill_name":   "Singularity",
        "skill_desc":   "Deals 1.6x ATK damage. Ignores 50% of enemy DEF",
        "skill_mult":   1.6,
        "skill_cd":     4,
        "portrait_id":  "graviton",
    },
    {
        "name":         "Void Queen",
        "faction":      "villain",
        "rarity":       "UR",
        "base_hp":      560,
        "base_atk":     110,
        "base_def":     40,
        "base_spd":     7,
        "base_crit":    22,
        "base_evade":   12,
        "passive_name": "Dark Throne",
        "passive_desc": "Gains +10% ATK for every 20% HP lost",
        "skill_name":   "Void Rupture",
        "skill_desc":   "Deals 2.5x ATK damage. Gains 1 charge — 3 charges triggers a free turn",
        "skill_mult":   2.5,
        "skill_cd":     5,
        "portrait_id":  "voidqueen",
    },
]

char_ids = []
for c in characters:
    insert(
        f"INSERT INTO characters "
        f"(name, faction, rarity, base_hp, base_atk, base_def, base_spd, base_crit, base_evade, "
        f"passive_name, passive_desc, skill_name, skill_desc, skill_mult, skill_cd, portrait_id) "
        f"VALUES ("
        f"'{c['name']}', '{c['faction']}', '{c['rarity']}', "
        f"{c['base_hp']}, {c['base_atk']}, {c['base_def']}, {c['base_spd']}, "
        f"{c['base_crit']}, {c['base_evade']}, "
        f"'{c['passive_name']}', '{c['passive_desc']}', "
        f"'{c['skill_name']}', '{c['skill_desc']}', "
        f"{c['skill_mult']}, {c['skill_cd']}, '{c['portrait_id']}')"
    )
    char_ids.append(None)
    print(f"  {c['name']} ({c['faction']}, {c['rarity']})")

# ------------------------------------------------------------------ #
#  Default player                                                      #
# ------------------------------------------------------------------ #

print("\n=== Seeding default player ===")

insert("INSERT INTO players (username, coins, gems) VALUES ('Player1', 500, 10)")
player = run_sql("SELECT * FROM players WHERE username = 'Player1'")[0]
player_id = player["id"]
print(f"  player id={player_id}, username=Player1, coins=500, gems=10")

# ------------------------------------------------------------------ #
#  Give player the 2 Common characters for free                        #
# ------------------------------------------------------------------ #

print("\n=== Giving starter characters to player ===")

# Query back the Common characters by name
starters = ["Swiftbolt", "Venom Shade"]
for name in starters:
    rows = run_sql(f"SELECT * FROM characters WHERE name = '{name}'")
    if not rows:
        print(f"  WARNING: {name} not found")
        continue
    char = rows[0]
    insert(
        f"INSERT INTO player_characters "
        f"(player_id, char_id, level, xp, stars, duplicates, "
        f"hp, atk, def, spd, crit, evade) VALUES ("
        f"{player_id}, {char['id']}, 1, 0, 1, 0, "
        f"{char['base_hp']}, {char['base_atk']}, {char['base_def']}, "
        f"{char['base_spd']}, {char['base_crit']}, {char['base_evade']})"
    )
    print(f"  {name} (char_id={char['id']}) → player")

# ------------------------------------------------------------------ #
#  Shop listings                                                       #
# ------------------------------------------------------------------ #

print("\n=== Seeding shop ===")

rarity_price    = {"C": 200, "R": 400, "SR": 800, "UR": 1500}
rarity_currency = {"C": "coins", "R": "coins", "SR": "gems", "UR": "gems"}

all_chars = run_sql("SELECT * FROM characters")
for char in all_chars:
    price    = rarity_price[char["rarity"]]
    currency = rarity_currency[char["rarity"]]
    insert(
        f"INSERT INTO shop_items (item_type, char_id, price, currency, available) "
        f"VALUES ('direct', {char['id']}, {price}, '{currency}', 1)"
    )
    print(f"  {char['name']} — {price} {currency}")

# Pack listings (char_id=0 means it's a pack, not a specific character)
insert(
    "INSERT INTO shop_items (item_type, char_id, price, currency, available) "
    "VALUES ('pack', 0, 150, 'coins', 1)"
)
print("  Standard Pack — 150 coins (3 random chars, weighted by rarity)")

insert(
    "INSERT INTO shop_items (item_type, char_id, price, currency, available) "
    "VALUES ('pack_premium', 0, 5, 'gems', 1)"
)
print("  Premium Pack — 5 gems (3 random, SR/UR rate boosted)")

print("\n=== Seed complete ===")
print(f"  Characters : {len(characters)}")
print(f"  Players    : 1")
print(f"  Shop items : {len(all_chars) + 2}")
print("\nReady. Start the backend with:  uvicorn backend.main:app --reload")
