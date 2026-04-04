"""
main.py
-------
FastAPI application entry point.

Run with:
    uvicorn backend.main:app --reload --port 8000

API docs auto-generated at:
    http://localhost:8000/docs


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import characters, player, shop, loadout
from ws.battle_ws import router as battle_ws_router
from db.client import get_db

app = FastAPI(
    title="Superhero Battle Game API",
    version="1.0.0",
    description="Backend for the superhero card collection & battle game.",
)

# ------------------------------------------------------------------ #
#  CORS — allow React dev server (port 5173) and production           #
# ------------------------------------------------------------------ #

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
#  Routers                                                             #
# ------------------------------------------------------------------ #

app.include_router(characters.router, tags=["Characters"])
app.include_router(player.router,     tags=["Player"])
app.include_router(shop.router,       tags=["Shop"])
app.include_router(loadout.router,    tags=["Loadout"])
app.include_router(battle_ws_router,  tags=["Battle"])

# ------------------------------------------------------------------ #
#  Health check                                                        #
# ------------------------------------------------------------------ #

@app.get("/health")
def health():
    db = get_db()
    db_ok = db.ping()
    return {
        "status": "ok" if db_ok else "db_unreachable",
        "db":     db_ok,
    }


@app.get("/")
def root():
    return {"message": "Superhero Battle API — see /docs for endpoints"}
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# New MongoDB Imports
from db.mongo import db
from routers import characters, player, shop, loadout
from ws.battle_ws import router as battle_ws_router

# ------------------------------------------------------------------ #
#  Lifespan Management                                               #
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events.
    Replaces manual get_db() initialization.
    """
    # Startup: Connect to MongoDB
    await db.connect()
    yield
    # Shutdown: Close connection pool
    await db.close()

# ------------------------------------------------------------------ #
#  App Initialization                                                #
# ------------------------------------------------------------------ #

app = FastAPI(
    title="Superhero Battle Game API",
    version="2.0.0 (MongoDB)",
    description="Backend for the superhero card collection & battle game.",
    lifespan=lifespan
)

# ------------------------------------------------------------------ #
#  CORS — allow React dev server                                     #
# ------------------------------------------------------------------ #

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------------------------------------------ #
#  Health & Root                                                     #
# ------------------------------------------------------------------ #

@app.get("/health")
async def health():
    """Check if the API and MongoDB are up."""
    db_ok = await db.ping()
    return {
        "status": "ok" if db_ok else "db_unreachable",
        "database": "mongodb",
        "connected": db_ok,
    }


@app.get("/")
def root():
    return {"message": "Superhero Battle API (Mongo Edition) — see /docs"}

# ------------------------------------------------------------------ #
#  Routers                                                           #
# ------------------------------------------------------------------ #

app.include_router(characters.router, tags=["Characters"])
app.include_router(player.router,     tags=["Player"])
app.include_router(shop.router,       tags=["Shop"])
app.include_router(loadout.router,    tags=["Loadout"])
app.include_router(battle_ws_router,  tags=["Battle"])

