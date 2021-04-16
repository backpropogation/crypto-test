from collections import defaultdict, namedtuple
from enum import Enum
from pprint import pprint

from pydantic import BaseModel

api_key, api_secret = 'PEwXfwuWep5l44SEUUIG7wpNLR0iVSMe0Sj6dHfEw37Zerj7UcCrnFq1x3G1O5AZ', 'e7aE7DNDMhSfl9BHpHbpadDmfwWSta32WaUFEJC9wr84LD4VURRzSiQXp90ILUAL'


class AssetsToBuy(Enum):
    BTC = 'BTC'
    ETH = 'ETH'
    USDT = 'USDT'


class Order(BaseModel):
    asset_to: str
    asset_from: AssetsToBuy


def get_balances_by_user():
    balances = client.get_account()['balances']
    res_dict = {}
    for balance in balances:
        if float(balance['free']) or float(balance['locked']):
            res_dict[balance['asset']] = {'free': float(balance['free']), 'locked': float(balance['locked'])}
    orders = []
    print(res_dict)
    Order = namedtuple('Order', ['asset', 'price', 'spent', 'amount', 'side', 'time'])
    for symbol in res_dict:
        if symbol == 'USDT':
            continue
        orders_by_symbol = client.get_all_orders(symbol=f'{symbol}USDT', limit=1000)

        for order in orders_by_symbol:
            orders.append(
                Order(symbol, order['price'], order['cummulativeQuoteQty'], order['executedQty'], order['side'],
                      order['time']))
    orders.sort(key=lambda x: x.time)
    pprint(orders)
    prices = client.get_all_tickers()
    my_symbols = set(f'{o.asset}USDT' for o in orders)
    for coin in res_dict.keys():
        my_symbols.add(f'{coin}USDT')
    print(my_symbols)
    my_prices = {}
    for price in prices:
        if price['symbol'] not in my_symbols:
            continue
        symbol = price['symbol'].replace('USDT', '')
        my_prices[symbol] = float(price['price'])

    dynamic = defaultdict(float)
    for order in orders:
        now_price = my_prices[order.asset] * float(order.amount)
        if order.side == 'BUY':
            dynamic[order.asset] += now_price - float(order.spent)
        else:
            test = now_price - float(order.spent)
            dynamic[order.asset] -= test
    my_prices['USDT'] = 1
    for coin, amount in res_dict.items():
        if coin not in dynamic:
            dynamic[coin] += my_prices[coin] * float(amount)

    return dynamic
