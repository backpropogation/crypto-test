from fastapi import FastAPI
from httpx import Request
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.responses import JSONResponse

from proj.errors import ApiError
from proj.config import config
from proj.views import router


def on_startup_handler(app: FastAPI):
    async def on_startup():
        setup_mongo_client(app)

    return on_startup


def setup_mongo_client(app: FastAPI):
    client = AsyncIOMotorClient(config.mongo_uri)
    app.state.client = client
    app.state.db = client.get_default_database()
    # try:
    #     asyncio.run(ensure_indexes(app.state.db))
    # except RuntimeError:
    #     loop = asyncio.get_running_loop()
    #     loop.create_task(ensure_indexes(app.state.db))


async def unknown_exception_handler(request: Request, exc: Exception):
    data = {
        "status": "failure",
        "error": {"code": '0', "message": f'Internal Server Error: {exc}'},
    }
    return JSONResponse(status_code=500, content=data, )


async def api_exception_handler(request: Request, exc: ApiError):
    data = {
        "status": "failure",
        "error": {"code": exc.code, "message": exc.message},
    }
    return JSONResponse(status_code=exc.status, content=data)


def create_app():
    app = FastAPI()

    # End Setup
    app.add_event_handler("startup", on_startup_handler(app))
    app.add_exception_handler(Exception, unknown_exception_handler)
    app.add_exception_handler(ApiError, api_exception_handler)
    app.include_router(router)
    return app
