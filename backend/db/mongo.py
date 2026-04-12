import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "fight_game"


class MongoManager:
    def __init__(self):
        self.client = None
        self._db = None  # private to avoid __getattr__ loop

    async def connect(self):
        self.client = AsyncIOMotorClient(MONGO_URL)
        self._db = self.client[DB_NAME]
        print(f"✓ Connected to MongoDB ({DB_NAME})")

    async def close(self):
        if self.client:
            self.client.close()
            print("✓ MongoDB connection closed")

    async def ping(self):
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False

    def __getattr__(self, name: str):
        """
        Proxy attribute access to the underlying Motor database.
        db.players  →  self._db["players"]  (a Motor Collection)
        """
        if name.startswith("_") or name in ("client", "connect", "close", "ping"):
            raise AttributeError(name)
        return getattr(self._db, name)


# Singleton — import this everywhere
db = MongoManager()