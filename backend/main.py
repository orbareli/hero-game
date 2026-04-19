"""
main.py
-------
FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.mongo import db
from routers import characters, player, shop, loadout
from ws.battle_ws import router as battle_ws_router


# ------------------------------------------------------------------ #
#  Lifespan — connect/disconnect MongoDB                             #
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()


# ------------------------------------------------------------------ #
#  App                                                               #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Fight Game API",
    version="2.0.0",
    description="Hero battle RPG backend — MongoDB edition",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
#  Routes                                                            #
# ------------------------------------------------------------------ #

app.include_router(characters.router, tags=["Characters"])
app.include_router(player.router,     tags=["Player"])
app.include_router(shop.router,       tags=["Shop"])
app.include_router(loadout.router,    tags=["Loadout"])
app.include_router(battle_ws_router,  tags=["Battle"])


# ── Dev convenience: get the first player in the DB ────────────────
# The React app calls this on first visit to discover the player_id
# (In production, replace with real auth)
@app.get("/player/first", tags=["Player"])
async def get_first_player():
    """Return the first player document — used by the UI on first load."""
    player = await db.players.find_one({})
    if not player:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No players found — run db/seed2.py first")
    player["id"] = str(player.pop("_id"))
    return player


# ── Health ─────────────────────────────────────────────────────────
@app.get("/health", tags=["Meta"])
async def health():
    ok = await db.ping()
    return {"status": "ok" if ok else "db_unreachable", "db": "mongodb", "connected": ok}


@app.get("/", tags=["Meta"])
def root():
    return {"message": "Fight Game API — visit /docs for the full API reference"}

# ── 3v3 interactive battle ──────────────────────────────────────────
from ws.battle_ws_3v3 import router as battle_3v3_router
app.include_router(battle_3v3_router, tags=["Battle 3v3"])

# ── Tower of Trials ─────────────────────────────────────────────────
from routers.tower import router as tower_router
from ws.tower_battle_ws import router as tower_battle_router

app.include_router(tower_router,        tags=["Tower"])
app.include_router(tower_battle_router, tags=["Tower Battle"])
