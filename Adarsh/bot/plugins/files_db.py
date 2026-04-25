# (c) adarsh-goel | indexing by RaakRaghu
from motor.motor_asyncio import AsyncIOMotorClient
from Adarsh.vars import Var

class Media:
    def __init__(self):
        self.client = AsyncIOMotorClient(Var.DATABASE_URL)
        self.col = self.client["FileStreamDB"]["Media"]

    async def save_file(self, media: dict):
        existing = await self.col.find_one({
            "file_name": media["file_name"],
            "file_size": media["file_size"]
        })
        if existing:
            return False
        await self.col.insert_one(media)
        return True

    async def get_search_results(self, query, max_results=10, offset=0):
        query = query.strip()
        if not query:
            raw_pattern = "."
        elif " " not in query:
            raw_pattern = r"(\b|[\.\+\-_])" + query + r"(\b|[\.\+\-_])"
        else:
            raw_pattern = query.replace(" ", r".*[\s\.\+\-_]")
        try:
            regex = {"$regex": raw_pattern, "$options": "i"}
        except Exception:
            regex = {"$regex": query, "$options": "i"}
        cursor = self.col.find({"file_name": regex}).skip(offset).limit(max_results)
        return [doc async for doc in cursor]

db = Media()
