from fastapi import FastAPI

app = FastAPI(title="Electric Simulation API")


def setup_routes():
    from src.api import api_router
    app.include_router(api_router)


setup_routes()
