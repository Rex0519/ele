# Dify 前端 + 短信通知 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为电力仿真系统添加 MCP HTTP/SSE 传输支持（供 Dify 连接）和短信通知预留接口。

**Architecture:** MCP Server 新增 SSE 传输层，与现有 FastAPI 应用共用同一进程；短信模块采用抽象基类设计，具体平台实现后替换。

**Tech Stack:** MCP Python SDK (SseServerTransport), Starlette, httpx (短信 HTTP 调用)

---

## Task 1: 添加 SSE 依赖

**Files:**
- Modify: `pyproject.toml`

**Step 1: 添加 sse-starlette 依赖**

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "sqlalchemy>=2.0.0",
    "psycopg[binary]>=3.2.0",
    "pandas>=2.2.0",
    "xlrd>=2.0.0",
    "apscheduler>=3.10.0",
    "pydantic-settings>=2.6.0",
    "mcp>=1.0.0",
    "sse-starlette>=2.0.0",
    "httpx>=0.28.0",
]
```

**Step 2: 同步依赖**

Run: `uv sync`
Expected: 依赖安装成功

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add sse-starlette and httpx dependencies"
```

---

## Task 2: MCP Server 添加 SSE 传输

**Files:**
- Modify: `src/mcp/server.py`

**Step 1: 添加 SSE 传输支持**

在文件顶部添加导入，并新增 `create_sse_routes` 函数：

```python
from datetime import datetime, timedelta

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from sqlalchemy import func
from starlette.routing import Route, Mount
from starlette.responses import Response

from src.db import get_db, ElectricData, Alert, ConfigArea, Device

mcp_server = Server("electric-simulation")

# SSE transport instance
sse_transport = SseServerTransport("/mcp/messages/")


async def handle_sse(request):
    """SSE endpoint handler for MCP connections"""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream, write_stream, mcp_server.create_initialization_options()
        )
    return Response()


def create_sse_routes():
    """Create Starlette routes for MCP SSE transport"""
    return [
        Route("/mcp/sse", endpoint=handle_sse),
        Mount("/mcp/messages/", app=sse_transport.handle_post_message),
    ]
```

保留原有的 `run_mcp_server()` 函数不变（stdio 模式继续支持 Claude Desktop）。

**Step 2: 验证导入无错误**

Run: `uv run python -c "from src.mcp.server import create_sse_routes; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/mcp/server.py
git commit -m "feat: add MCP SSE transport support"
```

---

## Task 3: 将 SSE 路由挂载到 FastAPI

**Files:**
- Modify: `src/main.py`

**Step 1: 挂载 SSE 路由**

```python
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.routing import Mount
import uvicorn

from src.config import settings
from src.db import get_db
from src.db.init_data import load_excel_data
from src.scheduler import start_scheduler
from src.mcp.server import create_sse_routes


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
```

**Step 2: 验证应用可启动（不连数据库，仅检查导入）**

Run: `uv run python -c "from src.main import app; print('Routes:', [r.path for r in app.routes if hasattr(r, 'path')])"`
Expected: 输出包含 `/mcp/sse`

**Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: mount MCP SSE routes to FastAPI app"
```

---

## Task 4: 创建短信发送抽象层

**Files:**
- Create: `src/alert/sms.py`

**Step 1: 创建短信抽象基类**

```python
from abc import ABC, abstractmethod


class SmsSender(ABC):
    """短信发送抽象基类，具体平台实现后继承此类"""

    @abstractmethod
    async def send(self, phones: list[str], message: str) -> bool:
        """发送短信

        Args:
            phones: 接收手机号列表
            message: 短信内容

        Returns:
            是否发送成功
        """
        pass


class DummySmsSender(SmsSender):
    """占位实现，仅打印日志不实际发送"""

    async def send(self, phones: list[str], message: str) -> bool:
        print(f"[SMS] Would send to {phones}: {message}")
        return True
```

**Step 2: 验证模块可导入**

Run: `uv run python -c "from src.alert.sms import DummySmsSender; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/alert/sms.py
git commit -m "feat: add SMS sender abstraction layer"
```

---

## Task 5: 添加短信配置项

**Files:**
- Modify: `src/config.py`

**Step 1: 添加短信相关配置**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://admin:password@localhost:5432/electric"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mcp_port: int = 8001

    # SMS settings
    sms_enabled: bool = False
    sms_phones: list[str] = []

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 2: 验证配置可加载**

Run: `uv run python -c "from src.config import settings; print('sms_enabled:', settings.sms_enabled)"`
Expected: `sms_enabled: False`

**Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add SMS configuration options"
```

---

## Task 6: 在调度器中集成短信通知

**Files:**
- Modify: `src/scheduler.py`

**Step 1: 添加短信通知逻辑**

```python
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.db import get_db
from src.simulator import SimulationGenerator
from src.alert import AlertDetector
from src.alert.sms import DummySmsSender


def run_hourly_tasks():
    """每小时执行的任务"""
    db = next(get_db())
    try:
        generator = SimulationGenerator(db)
        records = generator.generate_hourly_data()
        print(f"Generated {len(records)} records")

        detector = AlertDetector(db)
        alerts = detector.detect_all()
        print(f"Detected {len(alerts)} new alerts")

        # Send SMS for high severity alerts
        if settings.sms_enabled and alerts:
            high_alerts = [a for a in alerts if a.severity in ("HIGH", "CRITICAL")]
            if high_alerts:
                _send_alert_sms(high_alerts)
    finally:
        db.close()


def _send_alert_sms(alerts):
    """Send SMS notification for alerts"""
    if not settings.sms_phones:
        return

    messages = [f"[{a.severity}] {a.message}" for a in alerts[:5]]
    content = f"电力告警 ({len(alerts)}条):\n" + "\n".join(messages)
    if len(alerts) > 5:
        content += f"\n...还有{len(alerts) - 5}条"

    sender = DummySmsSender()
    asyncio.run(sender.send(settings.sms_phones, content))


def start_scheduler() -> BackgroundScheduler:
    """启动调度器"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_hourly_tasks, "cron", minute=0)
    scheduler.start()
    return scheduler
```

**Step 2: 验证模块可导入**

Run: `uv run python -c "from src.scheduler import run_hourly_tasks; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/scheduler.py
git commit -m "feat: integrate SMS notification in scheduler"
```

---

## Task 7: 更新 alert 模块导出

**Files:**
- Modify: `src/alert/__init__.py`

**Step 1: 导出 SmsSender**

读取当前文件内容后，添加 sms 导出：

```python
from src.alert.detector import AlertDetector
from src.alert.rules import AlertType, Severity
from src.alert.sms import SmsSender, DummySmsSender

__all__ = ["AlertDetector", "AlertType", "Severity", "SmsSender", "DummySmsSender"]
```

**Step 2: 验证导出**

Run: `uv run python -c "from src.alert import DummySmsSender; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/alert/__init__.py
git commit -m "feat: export SMS sender from alert module"
```

---

## Task 8: 端到端验证

**Step 1: 启动数据库**

Run: `docker-compose up -d db`
Expected: 数据库容器启动

**Step 2: 等待数据库就绪**

Run: `sleep 5 && docker-compose ps`
Expected: db 容器状态为 healthy

**Step 3: 启动应用验证 MCP SSE**

Run: `timeout 10 uv run python -m src.main || true`
Expected: 输出包含 "MCP SSE endpoint available at"

**Step 4: 停止数据库（可选）**

Run: `docker-compose down`

**Step 5: Final Commit**

```bash
git add -A
git commit -m "feat: complete MCP SSE and SMS notification integration"
```

---

## 后续步骤（不在本计划范围）

1. **部署 Dify** — 使用官方 docker-compose 部署
2. **配置 Dify MCP 连接** — 指向 `http://<host>:8000/mcp/sse`
3. **创建 Dify Agent 应用** — 配置系统提示词，选中 MCP 工具
4. **接入真实短信平台** — 实现 `SmsSender` 子类，替换 `DummySmsSender`
