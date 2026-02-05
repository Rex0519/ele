import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.routing import Mount
import uvicorn

from src.config import settings
from src.db import get_db
from src.db.init_data import load_excel_data
from src.db.maintenance import DataMaintenance
from src.scheduler import start_scheduler
from src.mcp.server import create_sse_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_dir = Path("data_extracted")
    if data_dir.exists():
        db = next(get_db())
        try:
            load_excel_data(db, data_dir)
            print("Data loaded from Excel files")
        except Exception as e:
            print(f"Data load error: {e}")
        finally:
            db.close()

    db = next(get_db())
    try:
        maintenance = DataMaintenance(db)
        deleted = maintenance.cleanup_expired_alerts()
        if deleted:
            print(f"Cleaned up {deleted} expired alerts")
        backfilled = maintenance.backfill_missing_data()
        if backfilled:
            print(f"Backfilled {backfilled} hours of missing data")
    finally:
        db.close()

    scheduler = start_scheduler()
    print("Scheduler started")
    print(f"MCP SSE endpoint available at http://{settings.api_host}:{settings.api_port}/mcp/sse")

    yield

    scheduler.shutdown()


app = FastAPI(title="Electric Simulation API", lifespan=lifespan)

# Mount MCP SSE routes
for route in create_sse_routes():
    app.routes.append(route)


def setup_routes():
    from src.api import api_router
    app.include_router(api_router)


setup_routes()


@app.get("/health")
def health_check():
    return {"status": "healthy"}


def main():
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
