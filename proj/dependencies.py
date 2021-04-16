from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.requests import Request

from proj.db import Storage


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


def get_storage(request: Request, db: AsyncIOMotorDatabase = Depends(get_db)) -> Storage:
    return Storage(db)
