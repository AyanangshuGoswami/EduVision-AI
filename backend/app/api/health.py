from fastapi import APIRouter
from app.db.mongo import get_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    await get_database().command("ping")
    return {"status": "ok", "database": "connected"}
