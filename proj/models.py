from datetime import datetime
from typing import Any, Dict

import pytz
from bson import ObjectId
from pydantic import Field, validator, BaseModel


class ObjectID(ObjectId):
    @classmethod
    def __modify_schema__(cls, field_schema) -> None:
        field_schema.update(type='ObjectId', format='ObjectId')

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        if ObjectId.is_valid(value):
            return ObjectId(value)

        raise ValueError


class MongoDbModel(BaseModel):
    id: ObjectID = Field(None, alias='_id')
    created: datetime = None

    @validator("created", pre=True, always=True)
    def set_created_now(cls, v: datetime) -> datetime:
        if v:
            return v
        return datetime.now(pytz.utc)

    def dict(
            self,
            *,
            include: Any = None,
            exclude: Any = None,
            by_alias: bool = False,
            skip_defaults: bool = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
    ):
        return super().dict(by_alias=True, exclude=exclude, exclude_none=exclude_none, exclude_unset=True)


class UserBase(MongoDbModel):
    telegram_id: int
    telegram_username: str

    class Meta:
        collection = "users"

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: lambda x: str(x)}


class UserCreate(UserBase):
    secret_token: str
    secret_api_key: str


class UserDb(UserCreate):
    spot_wallet: Dict = None
    stacking_wallet: Any = None
    is_full_updating: Any = None


class Order(MongoDbModel):
    asset_from: str
    asset_to: str
    symbol: str
    spent: float
    price: float
    amount: float
    side: str
    time: float
    order_id: int
    user_id: int

    class Meta:
        collection = "orders"


class Rate(MongoDbModel):
    symbol: str
    price: float

    class Meta:
        collection = "rates"


class Balance(MongoDbModel):
    asset: str
    free: float
    locked: float

    class Meta:
        collection = "balances"
