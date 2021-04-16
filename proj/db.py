from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from proj.models import UserDb, Rate, Order, UserCreate


class Storage:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def find_user_by_id(self, telegram_id):
        res = await self._db[UserDb.Meta.collection].find_one({'telegram_id': telegram_id})
        return UserDb(**res) if res else None

    async def mark_user_updated(self, telegram_id):
        await self._db[UserDb.Meta.collection].update_one(
            {'telegram_id': telegram_id},
            {"$set": {"is_full_updating": False}})

    async def get_users(self):
        res = [UserDb(**doc) async for doc in self._db[UserDb.Meta.collection].find()]
        return res

    async def get_users_full_updated(self):
        res = [UserDb(**doc) async for doc in self._db[UserDb.Meta.collection].find({'is_full_updating': False})]
        return res if res else None

    async def create_user(self, user_data):
        await self._db[UserDb.Meta.collection].insert_one(user_data)

    async def save_order(self, user_id, order):
        await self._db[Order.Meta.collection].insert_one({'user_id': user_id, **order.dict()})

    async def get_orders(self, user_id, symbol=None):
        filter_kwargs = {'user_id': user_id, 'amount': {"$ne": 0}}
        if symbol:
            filter_kwargs.update({'asset_from': symbol})
        return [Order(**doc) async for doc in self._db[Order.Meta.collection].find(filter_kwargs)]

    async def update_rates(self, rates):
        await self._db[Rate.Meta.collection].bulk_write(rates)

    async def get_rates(self):
        return {doc['symbol']: doc['price'] async for doc in self._db[Rate.Meta.collection].find()}

    async def find_rates_by_symbols(self, symbols):
        return {doc['symbol']: Rate(**doc) async for doc in
                self._db[Rate.Meta.collection].find({'symbol': {"$in": symbols}})}

    async def update_users_balances(self, telegram_id, balances):
        await self._db[UserDb.Meta.collection].update_one(
            {'telegram_id': telegram_id}, {"$set": {"spot_wallet": balances}})

    async def insert_orders(self, orders: List[Dict[str, Any]]):
        if not orders:
            return
        await self._db[Order.Meta.collection].insert_many(orders)
