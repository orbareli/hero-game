import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "fight_game"

class MongoManager:
    def __init__(self):
        self.client = None
        self.db = None

    # This MUST be named 'connect' to match your main.py call
    async def connect(self):
        self.client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.client[DB_NAME]
        print("Successfully connected to MongoDB.")

    async def close(self):
        if self.client:
            self.client.close()

    async def ping(self):
        try:
            await self.db.command("ping")
            return True
        except:
            return False
    def __getattr__(self, name):
        return getattr(self.db, name)

# Instantiate the singleton
db = MongoManager()