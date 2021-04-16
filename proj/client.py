from typing import Optional, Dict, Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from proj.errors import ApiError
from proj.models import UserBase, Order


class AsyncApiClientBase:
    def __init__(self, base_url: str, http_client: Optional[httpx.AsyncClient] = None, timeout: int = 60):
        self._base_url: str = base_url
        self._http = http_client
        self._timeout = timeout

    async def _post(self, url: str, **kwargs):
        if self._http:
            return await self._http.post(url, timeout=self._timeout, **kwargs)

        async with httpx.AsyncClient() as http:
            return await http.post(url, timeout=self._timeout, **kwargs)

    async def _get(self, url: str, **kwargs):
        if self._http:
            return await self._http.get(url, timeout=self._timeout, **kwargs)

        async with httpx.AsyncClient() as http:
            return await http.get(url, timeout=self._timeout, **kwargs)

    async def _delete(self, url: str, **kwargs):
        if self._http:
            return await self._http.delete(url, timeout=self._timeout, **kwargs)

        async with httpx.AsyncClient() as http:
            return await http.delete(url, timeout=self._timeout, **kwargs)


class BalanceData(BaseModel):
    balances: Dict[str, Any]
    profit_total: float


class Client(AsyncApiClientBase):
    @classmethod
    def get_data_from_response(cls, response: httpx.Response):
        response_data: Dict[str, Any] = response.json()
        if response_data['status'] == 'success':
            return response_data['data']
        raise ApiError

    def url_for(self, url):
        return urljoin(self._base_url, url)

    async def auth_user(self, user_id):
        params = {'user_id': user_id}
        response = await self._post(self.url_for('/api/users/authorize'), json=params)
        if response.status_code == 403:
            return
        self.get_data_from_response(response)
        return True

    async def get_account_info(self, user_id):
        params = {'user_id': user_id}
        response = await self._post(self.url_for('/api/authorize'), json=params)
        self.get_data_from_response(response)

    async def register(self, telegram_id, username, secret, api_key):
        data = {'telegram_id': telegram_id, 'telegram_username': username, 'secret_token': secret,
                'secret_api_key': api_key}
        response = await self._post(self.url_for('/api/users/'), json=data)
        data = self.get_data_from_response(response)
        return UserBase(**data)

    async def get_balance(self, telegram_id, symbol=None):
        url = f'/api/users/{telegram_id}/balance?symbol={symbol}' if symbol else f'/api/users/{telegram_id}/balance'
        response = await self._get(self.url_for(url))
        data = self.get_data_from_response(response)
        return data

    async def get_orders(self, telegram_id, symbol=None):
        url = f'/api/users/{telegram_id}/orders?symbol={symbol}' if symbol else f'/api/users/{telegram_id}/orders'
        response = await self._get(self.url_for(url))
        data = self.get_data_from_response(response)
        return [Order(**doc) for doc in data['orders']]

    async def get_profit(self, telegram_id):
        response = await self._get(self.url_for(f'/api/users/{telegram_id}/profit'))
        data = self.get_data_from_response(response)
        return data

    async def get_rate(self, symbol):
        response = await self._get(self.url_for(f'/api/rates?symbol={symbol}'))
        data = self.get_data_from_response(response)
        if data.get('value'):
            return data['value']
        return None