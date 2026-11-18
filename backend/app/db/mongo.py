from pymongo import AsyncMongoClient
from app.core.config import settings

_client = None


async def connect_to_mongo():
    global _client
    _client = AsyncMongoClient(settings.mongodb_uri)
    await _client.admin.command("ping")


async def close_mongo_connection():
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_database():
    if _client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return _client[settings.mongodb_database]
