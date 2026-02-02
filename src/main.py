import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import uvicorn

from src.config import settings
from src.db import get_db
from src.db.init_data import load_excel_data
from src.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
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

    scheduler = start_scheduler()
    print("Scheduler started")

    yield

    scheduler.shutdown()


app = FastAPI(title="Electric Simulation API", lifespan=lifespan)


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
