import asyncio
from asyncio import sleep
from collections import defaultdict

from binance.client import Client as BinanceClient
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from pymongo import UpdateOne

from proj.celery import app
from proj.config import config
from proj.data import ASSETS_TO, ALL_COINS
from proj.db import Storage
from proj.models import Rate, Order, Balance


async def get_storage() -> Storage:
    return Storage(AsyncIOMotorClient(config.mongo_uri).get_default_database())


async def _update_rates():
    client = BinanceClient()
    rates = []
    prices = client.get_all_tickers()
    for price in prices:
        rate = Rate(symbol=price['symbol'], price=price['price'])
        upd = UpdateOne({'symbol': rate.symbol}, {"$set": rate.dict()}, upsert=True)
        rates.append(upd)
    storage = await get_storage()

    await storage.update_rates(rates)


async def _update_balances():
    storage = await get_storage()

    users = await storage.get_users()

    for user in users:
        user_balance = {}
        client = BinanceClient(user.secret_api_key, user.secret_token)
        balances = [Balance(**doc, user_id=user.telegram_id) for doc in client.get_account()['balances']]
        for balance in balances:
            if balance.locked or balance.free:
                user_balance[balance.asset] = balance.dict(exclude={'asset'})

        await storage.update_users_balances(user.telegram_id, user_balance)


# celery worker src.tasks -l info -Q test-queue -c 1


# async def _update_orders():
#     storage = await get_storage()
#     users = await storage.get_users()
#     for user in users:
#         client = BinanceClient(user.secret_api_key, user.secret_token)
#
#         orders = await storage.get_orders(user.telegram_id)
#         orders.sort(key=lambda x: x.order_id)
#         orders_by_symbol = defaultdict(list)
#         for order in orders:
#             orders_by_symbol[order.symbol].append(orders)
#         latest_order = orders[-1] if orders else None
#         print(orders_by_symbol.keys())
#         for symbol, orders in orders_by_symbol.items():
#             latest_order = orders[-1] if orders else None
#             latest_order = orders[-1] if orders else None
#
#             api_orders = client.get_all_orders(symbol=symbol, orderId=latest_order.order_id, limit=1000)
#             res_orders = []
#             for order in api_orders:
#
#                 res_orders = []
#                 db_order = Order(
#                     symbol=symbol,
#                     price=order['price'],
#                     spent=order['cummulativeQuoteQty'],
#                     amount=order['executedQty'],
#                     side=order['side'],
#                     time=order['time'],
#                     asset_from=latest_order.asset_from,
#                     asset_to=latest_order.asset_to,
#                     order_id=order['orderId'],
#                     user_id=user.telegram_id
#                 )
#                 if db_order.order_id == latest_order.order_id:
#                     continue
#                 res_orders.append(db_order.dict())
#             await storage.insert_orders(res_orders)


@app.task()
async def _full_update_orders(user_id):
    storage = await get_storage()
    user = await storage.find_user_by_id(user_id)
    rates = await storage.get_rates()
    client = BinanceClient(user.secret_api_key, user.secret_token)
    print(f'full updating user {user.telegram_id} {user.telegram_username}')
    for asset_to in ALL_COINS:
        for asset_from in ASSETS_TO:
            symbol = f'{asset_to}{asset_from}'
            if symbol not in rates:
                continue
            orders_by_symbol = client.get_all_orders(symbol=symbol, limit=1000)
            print(f'got {len(orders_by_symbol)} for {symbol} {user.telegram_id}')

            res_orders = []
            for order in orders_by_symbol:
                db_order = Order(
                    symbol=symbol,
                    price=order['price'],
                    spent=order['cummulativeQuoteQty'],
                    amount=order['executedQty'],
                    side=order['side'],
                    time=order['time'],
                    asset_from=asset_to,
                    asset_to=asset_from,
                    order_id=order['orderId'],
                    user_id=user.telegram_id
                )
                res_orders.append(db_order.dict())
            await storage.insert_orders(res_orders)
    await storage.mark_user_updated(user.telegram_id)
    print(f'user {user.telegram_id} successfully updated')


@app.task()
def update_rates():
    asyncio.run(_update_rates())


@app.task()
def update_balances():
    asyncio.run(_update_balances())


@app.task()
def full_update_orders(user_id):
    asyncio.run(_full_update_orders(user_id))

# "secret_token": "0q2Tzs9BDSVoNqtprL7A4rIR9e45XFqNLxoQbBt1rPiXcLFnQmt0hNgyUHghkMQV"
# "secret_api_key": "NdWhYrhPFCnCbtFSajDZR4lFjDtzE9zckZQm7cRaZBV9OawoKxQ6hQvZU8pJTyGP"
