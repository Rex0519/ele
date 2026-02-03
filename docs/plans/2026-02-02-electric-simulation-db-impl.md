# 电力数据仿真系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建具备仿真数据生成、AI 查询、监控告警能力的电力数据库系统

**Architecture:** PostgreSQL + TimescaleDB 存储时序数据，FastAPI 提供 REST API 和 MCP Server，APScheduler 每小时触发数据生成和告警检测

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, TimescaleDB, APScheduler, MCP SDK

---

## Task 1: 项目基础配置

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/config.py`

**Step 1: 创建 pyproject.toml**

```toml
[project]
name = "electric-simulation"
version = "0.1.0"
requires-python = ">=3.12"
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
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0", "httpx>=0.28.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 2: 创建 .env.example**

```
DATABASE_URL=postgresql://admin:password@localhost:5432/electric
DB_PASSWORD=your_secure_password
```

**Step 3: 创建 src/__init__.py**

```python
```

**Step 4: 创建 src/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://admin:password@localhost:5432/electric"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mcp_port: int = 8001

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 5: 安装依赖**

Run: `uv sync`
Expected: 依赖安装成功

**Step 6: Commit**

```bash
git init
git add pyproject.toml .env.example src/__init__.py src/config.py
git commit -m "chore: init project with dependencies and config"
```

---

## Task 2: Docker 配置

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `.dockerignore`

**Step 1: 创建 docker-compose.yml**

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: electric
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d electric"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://admin:${DB_PASSWORD:-password}@db:5432/electric
    ports:
      - "8000:8000"
      - "8001:8001"
    volumes:
      - ./data_extracted:/app/data_extracted:ro

volumes:
  pgdata:
```

**Step 2: 创建 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY src/ src/

CMD ["uv", "run", "python", "-m", "src.main"]
```

**Step 3: 创建 .dockerignore**

```
.venv
__pycache__
*.pyc
.git
.env
data.zip
```

**Step 4: Commit**

```bash
git add docker-compose.yml Dockerfile .dockerignore
git commit -m "chore: add Docker configuration"
```

---

## Task 3: 数据库初始化脚本

**Files:**
- Create: `scripts/init_db.sql`

**Step 1: 创建 init_db.sql**

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 区域配置
CREATE TABLE IF NOT EXISTS config_area (
    config_id BIGINT PRIMARY KEY,
    parent_id VARCHAR(50),
    name VARCHAR(100),
    level INT,
    energy_type VARCHAR(20),
    park_id INT,
    is_delete INT DEFAULT 0
);

-- 项目配置
CREATE TABLE IF NOT EXISTS config_item (
    config_id BIGINT PRIMARY KEY,
    parent_id VARCHAR(50),
    name VARCHAR(100),
    level INT,
    energy_type VARCHAR(20),
    park_id INT,
    is_delete INT DEFAULT 0
);

-- 设备信息
CREATE TABLE IF NOT EXISTS device (
    device_id BIGINT PRIMARY KEY,
    device_no VARCHAR(50),
    device_name VARCHAR(200),
    point_type_id BIGINT,
    region_id BIGINT,
    building_id BIGINT,
    floor_id BIGINT,
    status INT DEFAULT 1,
    remark TEXT
);

-- 设备-配置关联
CREATE TABLE IF NOT EXISTS config_device (
    config_device_id BIGINT PRIMARY KEY,
    config_id BIGINT,
    device_id BIGINT,
    device_level INT,
    energy_type VARCHAR(20),
    config_type VARCHAR(20)
);

-- 电力数据（时序表）
CREATE TABLE IF NOT EXISTS electric_data (
    time TIMESTAMPTZ NOT NULL,
    device_id BIGINT NOT NULL,
    point_id VARCHAR(50),
    value DOUBLE PRECISION,
    incr DOUBLE PRECISION
);

SELECT create_hypertable('electric_data', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_electric_device ON electric_data (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_electric_point ON electric_data (point_id, time DESC);

-- 告警表
CREATE TABLE IF NOT EXISTS alert (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT,
    alert_type VARCHAR(20) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    message TEXT,
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alert_device ON alert (device_id);
CREATE INDEX IF NOT EXISTS idx_alert_active ON alert (resolved_at) WHERE resolved_at IS NULL;

-- 阈值配置
CREATE TABLE IF NOT EXISTS threshold_config (
    id SERIAL PRIMARY KEY,
    device_id BIGINT,
    metric VARCHAR(20) DEFAULT 'incr',
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    severity VARCHAR(10) DEFAULT 'WARNING'
);

-- 设备特征（用于仿真）
CREATE TABLE IF NOT EXISTS device_profile (
    point_id VARCHAR(50) PRIMARY KEY,
    mean_value DOUBLE PRECISION,
    std_value DOUBLE PRECISION,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    last_value DOUBLE PRECISION DEFAULT 0
);
```

**Step 2: Commit**

```bash
mkdir -p scripts
git add scripts/init_db.sql
git commit -m "feat: add database initialization script"
```

---

## Task 4: 数据库连接与模型

**Files:**
- Create: `src/db/__init__.py`
- Create: `src/db/connection.py`
- Create: `src/db/models.py`

**Step 1: 创建 src/db/__init__.py**

```python
from .connection import get_db, engine
from .models import ConfigArea, ConfigItem, Device, ConfigDevice, ElectricData, Alert, ThresholdConfig, DeviceProfile

__all__ = [
    "get_db",
    "engine",
    "ConfigArea",
    "ConfigItem",
    "Device",
    "ConfigDevice",
    "ElectricData",
    "Alert",
    "ThresholdConfig",
    "DeviceProfile",
]
```

**Step 2: 创建 src/db/connection.py**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 3: 创建 src/db/models.py**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Double, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConfigArea(Base):
    __tablename__ = "config_area"

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str | None] = mapped_column(String(20))
    park_id: Mapped[int | None] = mapped_column(Integer)
    is_delete: Mapped[int] = mapped_column(Integer, default=0)


class ConfigItem(Base):
    __tablename__ = "config_item"

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str | None] = mapped_column(String(20))
    park_id: Mapped[int | None] = mapped_column(Integer)
    is_delete: Mapped[int] = mapped_column(Integer, default=0)


class Device(Base):
    __tablename__ = "device"

    device_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_no: Mapped[str | None] = mapped_column(String(50))
    device_name: Mapped[str | None] = mapped_column(String(200))
    point_type_id: Mapped[int | None] = mapped_column(BigInteger)
    region_id: Mapped[int | None] = mapped_column(BigInteger)
    building_id: Mapped[int | None] = mapped_column(BigInteger)
    floor_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[int] = mapped_column(Integer, default=1)
    remark: Mapped[str | None] = mapped_column(Text)


class ConfigDevice(Base):
    __tablename__ = "config_device"

    config_device_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    config_id: Mapped[int | None] = mapped_column(BigInteger)
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    device_level: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str | None] = mapped_column(String(20))
    config_type: Mapped[str | None] = mapped_column(String(20))


class ElectricData(Base):
    __tablename__ = "electric_data"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    device_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    point_id: Mapped[str | None] = mapped_column(String(50))
    value: Mapped[float | None] = mapped_column(Double)
    incr: Mapped[float | None] = mapped_column(Double)


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    alert_type: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str | None] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Double)
    threshold: Mapped[float | None] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ThresholdConfig(Base):
    __tablename__ = "threshold_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    metric: Mapped[str] = mapped_column(String(20), default="incr")
    min_value: Mapped[float | None] = mapped_column(Double)
    max_value: Mapped[float | None] = mapped_column(Double)
    severity: Mapped[str] = mapped_column(String(10), default="WARNING")


class DeviceProfile(Base):
    __tablename__ = "device_profile"

    point_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    mean_value: Mapped[float | None] = mapped_column(Double)
    std_value: Mapped[float | None] = mapped_column(Double)
    min_value: Mapped[float | None] = mapped_column(Double)
    max_value: Mapped[float | None] = mapped_column(Double)
    last_value: Mapped[float] = mapped_column(Double, default=0)
```

**Step 4: Commit**

```bash
mkdir -p src/db
git add src/db/__init__.py src/db/connection.py src/db/models.py
git commit -m "feat: add database connection and SQLAlchemy models"
```

---

## Task 5: Excel 数据导入

**Files:**
- Create: `src/db/init_data.py`
- Create: `tests/__init__.py`
- Create: `tests/test_init_data.py`

**Step 1: 创建测试文件 tests/test_init_data.py**

```python
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.db.init_data import extract_device_profiles


def test_extract_device_profiles():
    mock_df = pd.DataFrame({
        "point_id": ["p1", "p1", "p2", "p2"],
        "value": [100.0, 110.0, 200.0, 220.0],
        "incr": [10.0, 12.0, 20.0, 22.0],
    })

    profiles = extract_device_profiles(mock_df)

    assert "p1" in profiles
    assert "p2" in profiles
    assert profiles["p1"]["mean_value"] == pytest.approx(11.0, rel=0.1)
    assert profiles["p2"]["mean_value"] == pytest.approx(21.0, rel=0.1)
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_init_data.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 创建 tests/__init__.py**

```python
```

**Step 4: 创建 src/db/init_data.py**

```python
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from src.db.models import ConfigArea, ConfigItem, Device, ConfigDevice, DeviceProfile


def extract_device_profiles(df: pd.DataFrame) -> dict:
    """从电力数据中提取设备特征"""
    profiles = {}
    for point_id, group in df.groupby("point_id"):
        profiles[point_id] = {
            "point_id": point_id,
            "mean_value": group["incr"].mean(),
            "std_value": group["incr"].std() if len(group) > 1 else 0,
            "min_value": group["incr"].min(),
            "max_value": group["incr"].max(),
            "last_value": group["value"].iloc[-1] if len(group) > 0 else 0,
        }
    return profiles


def load_excel_data(db: Session, data_dir: Path) -> None:
    """从 Excel 文件导入数据到数据库"""
    # 导入区域配置
    area_df = pd.read_excel(data_dir / "ene_config_area.xls")
    for _, row in area_df.iterrows():
        if row.get("is_delete") == 1:
            continue
        db.merge(ConfigArea(
            config_id=int(row["config_id"]),
            parent_id=str(row["config_parent_id"]) if pd.notna(row["config_parent_id"]) else None,
            name=row["config_name"],
            level=int(row["config_level"]) if pd.notna(row["config_level"]) else None,
            energy_type=row["energy_type"],
            park_id=int(row["park_id"]) if pd.notna(row["park_id"]) else None,
        ))

    # 导入项目配置
    item_df = pd.read_excel(data_dir / "ene_config_item.xls")
    for _, row in item_df.iterrows():
        if row.get("is_delete") == 1:
            continue
        db.merge(ConfigItem(
            config_id=int(row["config_id"]),
            parent_id=str(row["config_parent_id"]) if pd.notna(row["config_parent_id"]) else None,
            name=row["config_name"],
            level=int(row["config_level"]) if pd.notna(row["config_level"]) else None,
            energy_type=row["energy_type"],
            park_id=int(row["park_id"]) if pd.notna(row["park_id"]) else None,
        ))

    # 导入设备信息
    device_df = pd.read_excel(data_dir / "devicenfo.xls")
    for _, row in device_df.iterrows():
        db.merge(Device(
            device_id=int(row["device_id"]),
            device_no=row["device_no"],
            device_name=row["device_name"],
            point_type_id=int(row["point_type_id"]) if pd.notna(row["point_type_id"]) else None,
            region_id=int(row["region_id"]) if pd.notna(row["region_id"]) else None,
            building_id=int(row["building_id"]) if pd.notna(row["building_id"]) else None,
            floor_id=int(row["floor_id"]) if pd.notna(row["floor_id"]) else None,
            status=int(row["status"]) if pd.notna(row["status"]) else 1,
            remark=row["remark"] if pd.notna(row["remark"]) else None,
        ))

    # 导入设备-配置关联
    config_device_df = pd.read_excel(data_dir / "ene_config_device.xls")
    for _, row in config_device_df.iterrows():
        db.merge(ConfigDevice(
            config_device_id=int(row["config_device_id"]),
            config_id=int(row["config_id"]) if pd.notna(row["config_id"]) else None,
            device_id=int(row["device_id"]) if pd.notna(row["device_id"]) else None,
            device_level=int(row["device_level"]) if pd.notna(row["device_level"]) else None,
            energy_type=row["energy_type"],
            config_type=row["config_type"],
        ))

    # 提取设备特征
    electric_df = pd.read_excel(data_dir / "electric.xls")
    profiles = extract_device_profiles(electric_df)
    for profile in profiles.values():
        db.merge(DeviceProfile(**profile))

    db.commit()
```

**Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_init_data.py -v`
Expected: PASS

**Step 6: Commit**

```bash
mkdir -p tests
git add tests/__init__.py tests/test_init_data.py src/db/init_data.py
git commit -m "feat: add Excel data import with device profile extraction"
```

---

## Task 6: 仿真数据生成器

**Files:**
- Create: `src/simulator/__init__.py`
- Create: `src/simulator/profiles.py`
- Create: `src/simulator/generator.py`
- Create: `tests/test_generator.py`

**Step 1: 创建测试文件 tests/test_generator.py**

```python
import pytest
from src.simulator.profiles import get_time_factor
from src.simulator.generator import generate_increment


def test_time_factor_night():
    factor = get_time_factor(3)
    assert factor == 0.5


def test_time_factor_morning_peak():
    factor = get_time_factor(8)
    assert factor == 1.3


def test_time_factor_work():
    factor = get_time_factor(14)
    assert factor == 1.0


def test_time_factor_evening_peak():
    factor = get_time_factor(19)
    assert factor == 1.4


def test_generate_increment():
    incr = generate_increment(mean=10.0, std=2.0, hour=12)
    assert incr >= 0
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_generator.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 创建 src/simulator/__init__.py**

```python
from .generator import SimulationGenerator

__all__ = ["SimulationGenerator"]
```

**Step 4: 创建 src/simulator/profiles.py**

```python
TIME_FACTORS = {
    (0, 6): 0.5,    # 夜间低谷
    (7, 9): 1.3,    # 早高峰
    (10, 17): 1.0,  # 工作时段
    (18, 21): 1.4,  # 晚高峰
    (22, 23): 0.7,  # 夜间过渡
}


def get_time_factor(hour: int) -> float:
    """根据小时返回时段系数"""
    for (start, end), factor in TIME_FACTORS.items():
        if start <= hour <= end:
            return factor
    return 1.0
```

**Step 5: 创建 src/simulator/generator.py**

```python
import random
from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models import DeviceProfile, ElectricData
from src.simulator.profiles import get_time_factor


def generate_increment(mean: float, std: float, hour: int) -> float:
    """生成符合时段特征的增量"""
    time_factor = get_time_factor(hour)
    noise = random.gauss(0, std * 0.1) if std > 0 else 0
    incr = max(0, mean * time_factor + noise)
    return round(incr, 2)


class SimulationGenerator:
    def __init__(self, db: Session):
        self.db = db

    def generate_hourly_data(self) -> list[ElectricData]:
        """为所有设备生成一小时的数据"""
        now = datetime.now()
        hour = now.hour
        records = []

        profiles = self.db.query(DeviceProfile).all()
        for profile in profiles:
            incr = generate_increment(
                mean=profile.mean_value or 0,
                std=profile.std_value or 0,
                hour=hour,
            )
            new_value = (profile.last_value or 0) + incr

            record = ElectricData(
                time=now,
                device_id=hash(profile.point_id) % (10**18),
                point_id=profile.point_id,
                value=round(new_value, 2),
                incr=incr,
            )
            records.append(record)

            profile.last_value = new_value

        self.db.add_all(records)
        self.db.commit()
        return records
```

**Step 6: 运行测试确认通过**

Run: `uv run pytest tests/test_generator.py -v`
Expected: PASS

**Step 7: Commit**

```bash
mkdir -p src/simulator
git add src/simulator/__init__.py src/simulator/profiles.py src/simulator/generator.py tests/test_generator.py
git commit -m "feat: add simulation data generator with time-based patterns"
```

---

## Task 7: 告警检测系统

**Files:**
- Create: `src/alert/__init__.py`
- Create: `src/alert/rules.py`
- Create: `src/alert/detector.py`
- Create: `tests/test_alert.py`

**Step 1: 创建测试文件 tests/test_alert.py**

```python
import pytest
from src.alert.rules import AlertType, Severity, check_threshold, check_trend


def test_check_threshold_exceed_max():
    result = check_threshold(value=150.0, min_val=0.0, max_val=100.0)
    assert result is not None
    assert result["type"] == AlertType.THRESHOLD
    assert "超过上限" in result["message"]


def test_check_threshold_below_min():
    result = check_threshold(value=-5.0, min_val=0.0, max_val=100.0)
    assert result is not None
    assert "低于下限" in result["message"]


def test_check_threshold_normal():
    result = check_threshold(value=50.0, min_val=0.0, max_val=100.0)
    assert result is None


def test_check_trend_spike():
    result = check_trend(current=180.0, previous=100.0)
    assert result is not None
    assert result["type"] == AlertType.TREND_SPIKE


def test_check_trend_drop():
    result = check_trend(current=20.0, previous=100.0)
    assert result is not None
    assert result["type"] == AlertType.TREND_DROP


def test_check_trend_normal():
    result = check_trend(current=110.0, previous=100.0)
    assert result is None
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alert.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 创建 src/alert/__init__.py**

```python
from .detector import AlertDetector
from .rules import AlertType, Severity

__all__ = ["AlertDetector", "AlertType", "Severity"]
```

**Step 4: 创建 src/alert/rules.py**

```python
from enum import StrEnum


class AlertType(StrEnum):
    THRESHOLD = "THRESHOLD"
    TREND_SPIKE = "TREND_SPIKE"
    TREND_DROP = "TREND_DROP"
    OFFLINE = "OFFLINE"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def check_threshold(
    value: float,
    min_val: float | None,
    max_val: float | None,
    severity: str = Severity.WARNING,
) -> dict | None:
    """检查阈值告警"""
    if max_val is not None and value > max_val:
        return {
            "type": AlertType.THRESHOLD,
            "severity": severity,
            "message": f"数值 {value:.2f} 超过上限 {max_val:.2f}",
            "threshold": max_val,
        }
    if min_val is not None and value < min_val:
        return {
            "type": AlertType.THRESHOLD,
            "severity": severity,
            "message": f"数值 {value:.2f} 低于下限 {min_val:.2f}",
            "threshold": min_val,
        }
    return None


def check_trend(
    current: float,
    previous: float,
    spike_ratio: float = 1.5,
    drop_ratio: float = 0.3,
) -> dict | None:
    """检查趋势异常"""
    if previous <= 0:
        return None

    ratio = current / previous
    if ratio > spike_ratio:
        return {
            "type": AlertType.TREND_SPIKE,
            "severity": Severity.WARNING,
            "message": f"同比增长 {(ratio - 1) * 100:.1f}%",
            "threshold": previous * spike_ratio,
        }
    if ratio < drop_ratio:
        return {
            "type": AlertType.TREND_DROP,
            "severity": Severity.WARNING,
            "message": f"同比下降 {(1 - ratio) * 100:.1f}%",
            "threshold": previous * drop_ratio,
        }
    return None
```

**Step 5: 创建 src/alert/detector.py**

```python
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Alert, ElectricData, ThresholdConfig
from src.alert.rules import AlertType, Severity, check_threshold, check_trend


class AlertDetector:
    def __init__(self, db: Session):
        self.db = db

    def detect_all(self) -> list[Alert]:
        """执行所有告警检测"""
        alerts = []
        alerts.extend(self._detect_threshold_alerts())
        alerts.extend(self._detect_trend_alerts())
        alerts.extend(self._detect_offline_alerts())
        return alerts

    def _detect_threshold_alerts(self) -> list[Alert]:
        """检测阈值告警"""
        alerts = []
        configs = self.db.query(ThresholdConfig).all()

        for config in configs:
            latest = (
                self.db.query(ElectricData)
                .filter(ElectricData.device_id == config.device_id)
                .order_by(ElectricData.time.desc())
                .first()
            )
            if not latest:
                continue

            result = check_threshold(
                value=latest.incr or 0,
                min_val=config.min_value,
                max_val=config.max_value,
                severity=config.severity,
            )
            if result:
                alert = Alert(
                    device_id=config.device_id,
                    alert_type=result["type"],
                    severity=result["severity"],
                    message=result["message"],
                    value=latest.incr,
                    threshold=result["threshold"],
                )
                self.db.add(alert)
                alerts.append(alert)

        self.db.commit()
        return alerts

    def _detect_trend_alerts(self) -> list[Alert]:
        """检测趋势异常"""
        alerts = []
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        subq = (
            self.db.query(
                ElectricData.device_id,
                func.max(ElectricData.time).label("max_time"),
            )
            .filter(ElectricData.time >= hour_ago)
            .group_by(ElectricData.device_id)
            .subquery()
        )

        current_data = (
            self.db.query(ElectricData)
            .join(subq, (ElectricData.device_id == subq.c.device_id) & (ElectricData.time == subq.c.max_time))
            .all()
        )

        for current in current_data:
            previous = (
                self.db.query(ElectricData)
                .filter(
                    ElectricData.device_id == current.device_id,
                    ElectricData.time >= day_ago - timedelta(hours=1),
                    ElectricData.time <= day_ago,
                )
                .order_by(ElectricData.time.desc())
                .first()
            )
            if not previous:
                continue

            result = check_trend(
                current=current.incr or 0,
                previous=previous.incr or 0,
            )
            if result:
                alert = Alert(
                    device_id=current.device_id,
                    alert_type=result["type"],
                    severity=result["severity"],
                    message=result["message"],
                    value=current.incr,
                    threshold=result["threshold"],
                )
                self.db.add(alert)
                alerts.append(alert)

        self.db.commit()
        return alerts

    def _detect_offline_alerts(self) -> list[Alert]:
        """检测设备离线"""
        alerts = []
        threshold = datetime.now() - timedelta(hours=2)

        subq = (
            self.db.query(
                ElectricData.device_id,
                func.max(ElectricData.time).label("last_time"),
            )
            .group_by(ElectricData.device_id)
            .subquery()
        )

        offline_devices = (
            self.db.query(subq.c.device_id)
            .filter(subq.c.last_time < threshold)
            .all()
        )

        for (device_id,) in offline_devices:
            existing = (
                self.db.query(Alert)
                .filter(
                    Alert.device_id == device_id,
                    Alert.alert_type == AlertType.OFFLINE,
                    Alert.resolved_at.is_(None),
                )
                .first()
            )
            if existing:
                continue

            alert = Alert(
                device_id=device_id,
                alert_type=AlertType.OFFLINE,
                severity=Severity.HIGH,
                message="设备超过2小时无数据上报",
            )
            self.db.add(alert)
            alerts.append(alert)

        self.db.commit()
        return alerts
```

**Step 6: 运行测试确认通过**

Run: `uv run pytest tests/test_alert.py -v`
Expected: PASS

**Step 7: Commit**

```bash
mkdir -p src/alert
git add src/alert/__init__.py src/alert/rules.py src/alert/detector.py tests/test_alert.py
git commit -m "feat: add alert detection system with threshold, trend, and offline checks"
```

---

## Task 8: REST API - 设备接口

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/devices.py`
- Create: `tests/test_api_devices.py`

**Step 1: 创建测试文件 tests/test_api_devices.py**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_devices(client):
    with patch("src.api.devices.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.limit.return_value.offset.return_value.all.return_value = []
        mock_get_db.return_value = iter([mock_db])

        response = client.get("/api/devices")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_api_devices.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 创建 src/api/__init__.py**

```python
from fastapi import APIRouter

from .devices import router as devices_router
from .electric import router as electric_router
from .alerts import router as alerts_router

api_router = APIRouter(prefix="/api")
api_router.include_router(devices_router)
api_router.include_router(electric_router)
api_router.include_router(alerts_router)

__all__ = ["api_router"]
```

**Step 4: 创建 src/api/devices.py**

```python
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db, Device, ElectricData

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceResponse(BaseModel):
    device_id: int
    device_no: str | None
    device_name: str | None
    status: int | None

    class Config:
        from_attributes = True


class DeviceDataResponse(BaseModel):
    time: str
    value: float | None
    incr: float | None


@router.get("", response_model=list[DeviceResponse])
def list_devices(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """获取设备列表"""
    devices = db.query(Device).limit(limit).offset(offset).all()
    return devices


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db)):
    """获取单个设备详情"""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/{device_id}/data", response_model=list[DeviceDataResponse])
def get_device_data(
    device_id: int,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    """获取设备历史数据"""
    data = (
        db.query(ElectricData)
        .filter(ElectricData.device_id == device_id)
        .order_by(ElectricData.time.desc())
        .limit(limit)
        .all()
    )
    return [
        DeviceDataResponse(
            time=d.time.isoformat(),
            value=d.value,
            incr=d.incr,
        )
        for d in data
    ]
```

**Step 5: 创建 src/main.py（占位）**

```python
from fastapi import FastAPI

app = FastAPI(title="Electric Simulation API")

# 延迟导入避免循环依赖
def setup_routes():
    from src.api import api_router
    app.include_router(api_router)

setup_routes()
```

**Step 6: 运行测试确认通过**

Run: `uv run pytest tests/test_api_devices.py -v`
Expected: PASS

**Step 7: Commit**

```bash
mkdir -p src/api
git add src/api/__init__.py src/api/devices.py src/main.py tests/test_api_devices.py
git commit -m "feat: add devices REST API endpoints"
```

---

## Task 9: REST API - 电力数据接口

**Files:**
- Create: `src/api/electric.py`
- Create: `tests/test_api_electric.py`

**Step 1: 创建测试文件 tests/test_api_electric.py**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_realtime_data(client):
    with patch("src.api.electric.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_get_db.return_value = iter([mock_db])

        response = client.get("/api/electric/realtime")
        assert response.status_code == 200
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_api_electric.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 创建 src/api/electric.py**

```python
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db import get_db, ElectricData, ConfigArea

router = APIRouter(prefix="/electric", tags=["electric"])


class ElectricDataResponse(BaseModel):
    time: str
    device_id: int
    point_id: str | None
    value: float | None
    incr: float | None


class AreaSummaryResponse(BaseModel):
    area_id: int
    area_name: str | None
    total_value: float
    total_incr: float
    device_count: int


class StatisticsResponse(BaseModel):
    period: str
    total_consumption: float
    avg_hourly: float
    peak_hour: int | None
    peak_value: float | None


@router.get("/realtime", response_model=list[ElectricDataResponse])
def get_realtime_data(
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    """获取实时电力数据"""
    data = (
        db.query(ElectricData)
        .order_by(ElectricData.time.desc())
        .limit(limit)
        .all()
    )
    return [
        ElectricDataResponse(
            time=d.time.isoformat(),
            device_id=d.device_id,
            point_id=d.point_id,
            value=d.value,
            incr=d.incr,
        )
        for d in data
    ]


@router.get("/areas/{area_id}/summary", response_model=AreaSummaryResponse)
def get_area_summary(
    area_id: int,
    period: str = Query("day", regex="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    """获取区域用电汇总"""
    area = db.query(ConfigArea).filter(ConfigArea.config_id == area_id).first()
    if not area:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Area not found")

    now = datetime.now()
    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(weeks=1)
    else:
        start = now - timedelta(days=30)

    stats = (
        db.query(
            func.sum(ElectricData.value).label("total_value"),
            func.sum(ElectricData.incr).label("total_incr"),
            func.count(func.distinct(ElectricData.device_id)).label("device_count"),
        )
        .filter(ElectricData.time >= start)
        .first()
    )

    return AreaSummaryResponse(
        area_id=area_id,
        area_name=area.name,
        total_value=stats.total_value or 0,
        total_incr=stats.total_incr or 0,
        device_count=stats.device_count or 0,
    )


@router.get("/statistics", response_model=StatisticsResponse)
def get_statistics(
    period: str = Query("day", regex="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    """获取统计分析数据"""
    now = datetime.now()
    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(weeks=1)
    else:
        start = now - timedelta(days=30)

    total = (
        db.query(func.sum(ElectricData.incr))
        .filter(ElectricData.time >= start)
        .scalar()
    ) or 0

    hours = (now - start).total_seconds() / 3600
    avg_hourly = total / hours if hours > 0 else 0

    peak = (
        db.query(
            func.extract("hour", ElectricData.time).label("hour"),
            func.sum(ElectricData.incr).label("total"),
        )
        .filter(ElectricData.time >= start)
        .group_by(func.extract("hour", ElectricData.time))
        .order_by(func.sum(ElectricData.incr).desc())
        .first()
    )

    return StatisticsResponse(
        period=period,
        total_consumption=round(total, 2),
        avg_hourly=round(avg_hourly, 2),
        peak_hour=int(peak.hour) if peak else None,
        peak_value=round(peak.total, 2) if peak else None,
    )
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_api_electric.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/electric.py tests/test_api_electric.py
git commit -m "feat: add electric data REST API endpoints"
```

---

## Task 10: REST API - 告警接口

**Files:**
- Create: `src/api/alerts.py`
- Create: `tests/test_api_alerts.py`

**Step 1: 创建测试文件 tests/test_api_alerts.py**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_alerts(client):
    with patch("src.api.alerts.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
        mock_get_db.return_value = iter([mock_db])

        response = client.get("/api/alerts")
        assert response.status_code == 200


def test_list_active_alerts(client):
    with patch("src.api.alerts.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_get_db.return_value = iter([mock_db])

        response = client.get("/api/alerts/active")
        assert response.status_code == 200
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_api_alerts.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: 创建 src/api/alerts.py**

```python
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db, Alert, ThresholdConfig

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertResponse(BaseModel):
    id: int
    device_id: int | None
    alert_type: str
    severity: str
    message: str | None
    value: float | None
    threshold: float | None
    created_at: str
    resolved_at: str | None

    class Config:
        from_attributes = True


class ThresholdConfigResponse(BaseModel):
    id: int
    device_id: int | None
    metric: str
    min_value: float | None
    max_value: float | None
    severity: str

    class Config:
        from_attributes = True


class ThresholdConfigUpdate(BaseModel):
    min_value: float | None = None
    max_value: float | None = None
    severity: str | None = None


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    severity: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """获取告警列表"""
    query = db.query(Alert)
    if severity:
        query = query.filter(Alert.severity == severity)
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).offset(offset).all()
    return [
        AlertResponse(
            id=a.id,
            device_id=a.device_id,
            alert_type=a.alert_type,
            severity=a.severity,
            message=a.message,
            value=a.value,
            threshold=a.threshold,
            created_at=a.created_at.isoformat() if a.created_at else "",
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
        )
        for a in alerts
    ]


@router.get("/active", response_model=list[AlertResponse])
def list_active_alerts(db: Session = Depends(get_db)):
    """获取当前未解决告警"""
    alerts = (
        db.query(Alert)
        .filter(Alert.resolved_at.is_(None))
        .order_by(Alert.created_at.desc())
        .all()
    )
    return [
        AlertResponse(
            id=a.id,
            device_id=a.device_id,
            alert_type=a.alert_type,
            severity=a.severity,
            message=a.message,
            value=a.value,
            threshold=a.threshold,
            created_at=a.created_at.isoformat() if a.created_at else "",
            resolved_at=None,
        )
        for a in alerts
    ]


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """标记告警已解决"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.resolved_at:
        raise HTTPException(status_code=400, detail="Alert already resolved")

    alert.resolved_at = datetime.now()
    db.commit()
    return {"status": "resolved", "alert_id": alert_id}


@router.get("/thresholds", response_model=list[ThresholdConfigResponse])
def list_thresholds(db: Session = Depends(get_db)):
    """获取阈值配置列表"""
    configs = db.query(ThresholdConfig).all()
    return configs


@router.put("/thresholds/{device_id}")
def update_threshold(
    device_id: int,
    update: ThresholdConfigUpdate,
    db: Session = Depends(get_db),
):
    """更新设备阈值配置"""
    config = db.query(ThresholdConfig).filter(ThresholdConfig.device_id == device_id).first()
    if not config:
        config = ThresholdConfig(device_id=device_id)
        db.add(config)

    if update.min_value is not None:
        config.min_value = update.min_value
    if update.max_value is not None:
        config.max_value = update.max_value
    if update.severity is not None:
        config.severity = update.severity

    db.commit()
    return {"status": "updated", "device_id": device_id}
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_api_alerts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/alerts.py tests/test_api_alerts.py
git commit -m "feat: add alerts REST API endpoints"
```

---

## Task 11: MCP Server

**Files:**
- Create: `src/mcp/__init__.py`
- Create: `src/mcp/server.py`

**Step 1: 创建 src/mcp/__init__.py**

```python
from .server import mcp_server

__all__ = ["mcp_server"]
```

**Step 2: 创建 src/mcp/server.py**

```python
from datetime import datetime, timedelta

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from sqlalchemy import func

from src.db import get_db, ElectricData, Alert, ConfigArea, Device

mcp_server = Server("electric-simulation")


@mcp_server.list_tools()
async def list_tools():
    return [
        Tool(
            name="query_electric_data",
            description="查询指定设备的电力数据",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "integer", "description": "设备ID"},
                    "hours": {"type": "integer", "description": "查询最近多少小时", "default": 24},
                },
                "required": ["device_id"],
            },
        ),
        Tool(
            name="get_area_summary",
            description="获取区域用电汇总",
            inputSchema={
                "type": "object",
                "properties": {
                    "area_id": {"type": "integer", "description": "区域ID"},
                    "period": {"type": "string", "enum": ["day", "week", "month"], "default": "day"},
                },
                "required": ["area_id"],
            },
        ),
        Tool(
            name="list_active_alerts",
            description="列出当前未解决的告警",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["INFO", "WARNING", "HIGH", "CRITICAL"]},
                },
            },
        ),
        Tool(
            name="analyze_anomaly",
            description="分析设备异常情况",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "integer", "description": "设备ID"},
                },
                "required": ["device_id"],
            },
        ),
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    db = next(get_db())
    try:
        if name == "query_electric_data":
            return await _query_electric_data(db, arguments)
        elif name == "get_area_summary":
            return await _get_area_summary(db, arguments)
        elif name == "list_active_alerts":
            return await _list_active_alerts(db, arguments)
        elif name == "analyze_anomaly":
            return await _analyze_anomaly(db, arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    finally:
        db.close()


async def _query_electric_data(db, args: dict):
    device_id = args["device_id"]
    hours = args.get("hours", 24)
    start = datetime.now() - timedelta(hours=hours)

    data = (
        db.query(ElectricData)
        .filter(ElectricData.device_id == device_id, ElectricData.time >= start)
        .order_by(ElectricData.time.desc())
        .limit(100)
        .all()
    )

    if not data:
        return [TextContent(type="text", text=f"设备 {device_id} 在最近 {hours} 小时内无数据")]

    lines = [f"设备 {device_id} 最近 {hours} 小时数据 ({len(data)} 条):"]
    for d in data[:10]:
        lines.append(f"  {d.time.strftime('%Y-%m-%d %H:%M')} | 读数: {d.value:.2f} | 增量: {d.incr:.2f}")
    if len(data) > 10:
        lines.append(f"  ... 还有 {len(data) - 10} 条记录")

    return [TextContent(type="text", text="\n".join(lines))]


async def _get_area_summary(db, args: dict):
    area_id = args["area_id"]
    period = args.get("period", "day")

    area = db.query(ConfigArea).filter(ConfigArea.config_id == area_id).first()
    if not area:
        return [TextContent(type="text", text=f"区域 {area_id} 不存在")]

    now = datetime.now()
    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(weeks=1)
    else:
        start = now - timedelta(days=30)

    stats = (
        db.query(
            func.sum(ElectricData.incr).label("total"),
            func.avg(ElectricData.incr).label("avg"),
            func.count().label("count"),
        )
        .filter(ElectricData.time >= start)
        .first()
    )

    text = f"""区域: {area.name}
统计周期: {period}
总用电量: {stats.total or 0:.2f} kWh
平均用电: {stats.avg or 0:.2f} kWh/次
数据条数: {stats.count or 0}"""

    return [TextContent(type="text", text=text)]


async def _list_active_alerts(db, args: dict):
    severity = args.get("severity")

    query = db.query(Alert).filter(Alert.resolved_at.is_(None))
    if severity:
        query = query.filter(Alert.severity == severity)

    alerts = query.order_by(Alert.created_at.desc()).limit(50).all()

    if not alerts:
        return [TextContent(type="text", text="当前无未解决告警")]

    lines = [f"当前未解决告警 ({len(alerts)} 条):"]
    for a in alerts:
        lines.append(f"  [{a.severity}] {a.alert_type}: {a.message} (设备: {a.device_id})")

    return [TextContent(type="text", text="\n".join(lines))]


async def _analyze_anomaly(db, args: dict):
    device_id = args["device_id"]

    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return [TextContent(type="text", text=f"设备 {device_id} 不存在")]

    now = datetime.now()
    recent = (
        db.query(ElectricData)
        .filter(ElectricData.device_id == device_id, ElectricData.time >= now - timedelta(hours=24))
        .all()
    )

    alerts = (
        db.query(Alert)
        .filter(Alert.device_id == device_id, Alert.resolved_at.is_(None))
        .all()
    )

    if not recent:
        status = "离线 (24小时内无数据)"
    else:
        avg_incr = sum(d.incr or 0 for d in recent) / len(recent)
        latest = recent[0]
        if latest.incr and latest.incr > avg_incr * 1.5:
            status = "用电量偏高"
        elif latest.incr and latest.incr < avg_incr * 0.3:
            status = "用电量偏低"
        else:
            status = "正常"

    text = f"""设备: {device.device_name} ({device.device_no})
状态: {status}
24小时数据量: {len(recent)} 条
未解决告警: {len(alerts)} 条"""

    if alerts:
        text += "\n\n告警详情:"
        for a in alerts:
            text += f"\n  [{a.severity}] {a.message}"

    return [TextContent(type="text", text=text)]


async def run_mcp_server():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream)
```

**Step 3: Commit**

```bash
mkdir -p src/mcp
git add src/mcp/__init__.py src/mcp/server.py
git commit -m "feat: add MCP server with electric data tools"
```

---

## Task 12: 调度器与主程序

**Files:**
- Modify: `src/main.py`
- Create: `src/scheduler.py`

**Step 1: 创建 src/scheduler.py**

```python
from apscheduler.schedulers.background import BackgroundScheduler

from src.db import get_db
from src.simulator import SimulationGenerator
from src.alert import AlertDetector


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
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """启动调度器"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_hourly_tasks, "cron", minute=0)
    scheduler.start()
    return scheduler
```

**Step 2: 更新 src/main.py**

```python
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
```

**Step 3: Commit**

```bash
git add src/scheduler.py src/main.py
git commit -m "feat: add scheduler and complete main application"
```

---

## Task 13: 运行全部测试

**Step 1: 运行所有测试**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: 修复任何失败的测试**

如有失败，根据错误信息修复

**Step 3: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: resolve test failures"
```

---

## Task 14: 集成测试

**Step 1: 启动 Docker 服务**

Run: `docker-compose up -d db`
Expected: PostgreSQL 容器启动成功

**Step 2: 等待数据库就绪**

Run: `docker-compose logs -f db`
Expected: 看到 "database system is ready to accept connections"

**Step 3: 运行应用**

Run: `DATABASE_URL=postgresql://admin:password@localhost:5432/electric uv run python -m src.main`
Expected: FastAPI 启动，显示 "Uvicorn running on http://0.0.0.0:8000"

**Step 4: 测试 API**

Run: `curl http://localhost:8000/health`
Expected: `{"status":"healthy"}`

Run: `curl http://localhost:8000/api/devices`
Expected: 返回设备列表 JSON

**Step 5: 停止服务**

Run: `docker-compose down`

**Step 6: Final Commit**

```bash
git add -A
git commit -m "chore: complete electric simulation system"
```

---

## 总结

| Task | 内容 | 预计文件数 |
|------|------|-----------|
| 1 | 项目配置 | 4 |
| 2 | Docker 配置 | 3 |
| 3 | 数据库脚本 | 1 |
| 4 | 数据库模型 | 3 |
| 5 | 数据导入 | 3 |
| 6 | 仿真生成器 | 4 |
| 7 | 告警系统 | 4 |
| 8 | 设备 API | 3 |
| 9 | 电力 API | 2 |
| 10 | 告警 API | 2 |
| 11 | MCP Server | 2 |
| 12 | 调度器/主程序 | 2 |
| 13-14 | 测试验证 | - |

**总计:** 33 个文件，14 个任务
