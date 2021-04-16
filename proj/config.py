from pydantic import BaseSettings


class Config(BaseSettings):
    mongo_uri: str
    secret: str

    class Config:
        env_file = '.env'


config = Config()
