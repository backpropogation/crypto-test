from collections import defaultdict
from pprint import pprint
from typing import Any, List

import orjson
from binance.client import Client
from binance.exceptions import BinanceAPIException
from fastapi import APIRouter, Depends, Body, Query
from pydantic import BaseModel
from starlette.responses import JSONResponse

from proj.binance_api import get_balances_by_user
from proj.db import Storage
from proj.dependencies import get_storage
from proj.errors import AlreadyRegistered, NotAuthorized, WrongKeys
from proj.models import Order, UserCreate, UserBase, Balance
from proj.tasks import full_update_orders

router = APIRouter()


class OrjsonResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        data = {
            'status': 'success',
            'data': content
        }
        return orjson.dumps(data, default=str)


@router.get(
    "/api/users/{user_id}/balance",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {"balance": 10.100, }
                }
            },
        }}
)
async def get_balance(
        user_id: int,
        symbol: str = Query(None),
        storage: Storage = Depends(get_storage),
):
    user = await storage.find_user_by_id(user_id)
    user_pairs = [f'{asset}BTC' for asset in user.spot_wallet.keys() if asset != 'USDT']
    user_pairs.extend(['BTCUSDT'])
    user_pairs.extend([f'BTC{symbol}'])
    user_rates = await storage.find_rates_by_symbols(user_pairs)
    sum_btc = 0
    resp = {}
    for coin, coin_info in user.spot_wallet.items():

        if coin == 'BTC':
            sum_btc += coin_info['free'] + coin_info['locked']
        elif coin == 'USDT':
            sum_btc += coin_info['free'] / user_rates[f'BTCUSDT'].price
        else:
            rate = user_rates[f'{coin}BTC']
            sum_btc += coin_info['free'] * rate.price + coin_info['locked'] * rate.price
        resp[coin] = coin_info['free'] + coin_info['locked']
    if symbol:
        rate = user_rates.get(f'BTC{symbol}')
        if not rate:
            rate = await storage.find_rates_by_symbols([f'{symbol}USDT'])
            btc_in_usdt = sum_btc * user_rates['BTCUSDT'].price
            sum_btc = btc_in_usdt / rate[f'{symbol}USDT'].price
        else:
            sum_btc = sum_btc * rate.price

    return OrjsonResponse({'balances': resp, 'sum': float('{:010.9f}'.format(sum_btc))})


class OrderList(BaseModel):
    orders: List[Order]


@router.get(
    "/api/users/{user_id}/orders/",
    responses={
        200: {
            "description": "Success",
            "model": OrderList, "description": "Successful Response"
            ,
        }}
)
async def get_orders(
        user_id: int,
        symbol: str = Query(None),
        storage: Storage = Depends(get_storage)
):
    orders = [o.dict() for o in await storage.get_orders(user_id, symbol)]
    return OrjsonResponse({'orders': orders})


@router.get(
    "/api/users/{user_id}/profit/",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {"BTC": 10.100, 'ETH': 100, "total_profit": 100}
                }
            },
        }}
)
async def profit(
        user_id: int,
        storage: Storage = Depends(get_storage)
):
    orders = await storage.get_orders(user_id)
    user = await storage.find_user_by_id(user_id)
    balance = user.spot_wallet
    orders.sort(key=lambda x: x.time)
    rates = await storage.get_rates()
    res = defaultdict(float)
    orders.sort(key=lambda x: x.order_id, reverse=True)
    for o in orders:
        if not o.asset_from in balance.keys():
            continue
        now_rate = rates[o.symbol]
        now_price = now_rate * float(o.amount)
        if o.side == 'BUY':
            res[o.asset_from] += now_price - float(o.spent)
        else:
            res[o.asset_from] -= now_price - float(o.spent)
    final = {k: float('{:010.4f}'.format(v)) for k, v in res.items()}
    return OrjsonResponse({'profit': final, 'total_profit': sum(final.values())})


@router.post(
    '/api/users/',
    responses={
        200: {"model": UserBase, "description": "Successful Response"}
    }
)
async def create_user(
        user_data: UserCreate,
        storage: Storage = Depends(get_storage),
):
    user = await storage.find_user_by_id(user_data.telegram_id)
    if user:
        raise AlreadyRegistered
    try:
        client = Client(api_key=user_data.secret_api_key, api_secret=user_data.secret_token)
        balances = [Balance(**doc) for doc in client.get_account()['balances']]
        user_balance = {}
        for balance in balances:
            if balance.locked or balance.free:
                user_balance[balance.asset] = balance.dict(exclude={'asset'})
        data = user_data.dict(exclude_none=True)
        data['spot_wallet'] = user_balance
        await storage.create_user(data)
        full_update_orders.apply_async(args=(user_data.telegram_id,))
        return OrjsonResponse(UserBase(**user_data.dict()).dict())
    except BinanceAPIException:
        raise WrongKeys


@router.post(
    "/api/users/authorize",
    description='Authorization',
    responses={
        200: {
            "description": "Authorized successfully",
            "content": {
                "application/json": {
                    "example": {"success": True, }
                }
            },
        },

        403: {
            "description": "Not authorized ",
            "content": {
                "application/json": {
                    "example": {"success": False}
                }
            },
        },
    }
)
async def read_user(
        user_id: int = Body(None, embed=True),
        storage: Storage = Depends(get_storage),
):
    user = await storage.find_user_by_id(telegram_id=user_id)
    if not user:
        raise NotAuthorized
    return OrjsonResponse({})


@router.get(
    "/api/rates",
    responses={200
    : {
            "description": "Success response",
            "content": {
                "application/json": {
                    "example": {"rate": 10.100}
                }
            }}}

)
async def get_rate(
        symbol: str = Query(None, description='Pair of currencies without spaces like BTCUSDT', ),
        storage: Storage = Depends(get_storage),
):
    symbol_db = await storage.find_rates_by_symbols([symbol])
    if symbol_db:
        return OrjsonResponse({'value': symbol_db[symbol].price})
    return None
