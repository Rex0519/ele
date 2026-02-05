# 数据30天保留与自动补全 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 启动时自动补全缺失的 electric_data，清理超过30天的 alert，并通过 TimescaleDB retention policy 自动清理过期时序数据。

**Architecture:** 在 `scripts/init_db.sql` 添加 TimescaleDB retention policy 处理 `electric_data` 的自动清理；新建 `src/db/maintenance.py` 封装 alert 清理和数据补全逻辑；扩展 `SimulationGenerator` 支持指定时间生成；在 `main.py` lifespan 中调用 maintenance。

**Tech Stack:** Python, SQLAlchemy, TimescaleDB, APScheduler, pytest

---

## Task 1: 添加 TimescaleDB retention policy

**Files:**
- Modify: `scripts/init_db.sql:58-61`

**Step 1: 在 hypertable 创建后添加 retention policy**

在 `scripts/init_db.sql` 的 `create_hypertable` 语句之后、索引创建之前，添加：

```sql
SELECT add_retention_policy('electric_data', INTERVAL '30 days', if_not_exists => TRUE);
```

**Step 2: Commit**

```bash
git add scripts/init_db.sql
git commit -m "feat: add 30-day retention policy for electric_data"
```

---

## Task 2: 扩展 SimulationGenerator 支持 target_time

**Files:**
- Modify: `src/simulator/generator.py:22-50`
- Modify: `tests/test_generator.py`

**Step 1: 写失败测试**

在 `tests/test_generator.py` 末尾添加：

```python
from unittest.mock import MagicMock
from datetime import datetime
from src.simulator.generator import SimulationGenerator
from src.db.models import DeviceProfile, ElectricData


def test_generate_hourly_data_with_target_time():
    """generate_hourly_data 使用 target_time 而非 now()"""
    mock_db = MagicMock()
    profile = DeviceProfile(
        point_id="test-device-001",
        mean_value=10.0,
        std_value=2.0,
        last_value=100.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    target = datetime(2026, 1, 15, 14, 0, 0)
    gen = SimulationGenerator(mock_db)
    records = gen.generate_hourly_data(target_time=target)

    assert len(records) == 1
    assert records[0].time == target
    assert records[0].point_id == "test-device-001"
    assert records[0].value > 100.0


def test_generate_hourly_data_default_uses_now():
    """不传 target_time 时行为不变"""
    mock_db = MagicMock()
    profile = DeviceProfile(
        point_id="test-device-002",
        mean_value=5.0,
        std_value=1.0,
        last_value=50.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    gen = SimulationGenerator(mock_db)
    records = gen.generate_hourly_data()

    assert len(records) == 1
    now = datetime.now()
    assert abs((records[0].time - now).total_seconds()) < 5
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_generator.py::test_generate_hourly_data_with_target_time -v`
Expected: FAIL - `TypeError: generate_hourly_data() got an unexpected keyword argument 'target_time'`

**Step 3: 修改 generate_hourly_data 支持 target_time**

将 `src/simulator/generator.py` 中的 `generate_hourly_data` 改为：

```python
def generate_hourly_data(self, target_time: datetime | None = None) -> list[ElectricData]:
    """为所有设备生成一小时的数据"""
    ts = target_time or datetime.now()
    hour = ts.hour
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
            time=ts,
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

变更点：`now` → `ts`，方法签名增加 `target_time` 参数。

**Step 4: 运行测试确认通过**

Run: `pytest tests/test_generator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/simulator/generator.py tests/test_generator.py
git commit -m "feat: add target_time parameter to generate_hourly_data"
```

---

## Task 3: 创建 DataMaintenance 类

**Files:**
- Create: `src/db/maintenance.py`
- Create: `tests/test_maintenance.py`

**Step 1: 写失败测试 - cleanup_expired_alerts**

创建 `tests/test_maintenance.py`：

```python
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call

from src.db.maintenance import DataMaintenance


def test_cleanup_expired_alerts():
    """清理超过30天的 alert 记录"""
    mock_db = MagicMock()
    mock_db.execute.return_value.rowcount = 5

    m = DataMaintenance(mock_db)
    count = m.cleanup_expired_alerts(days=30)

    assert count == 5
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
    sql_text = str(mock_db.execute.call_args[0][0])
    assert "alert" in sql_text
    assert "created_at" in sql_text
```

**Step 2: 运行测试确认失败**

Run: `pytest tests/test_maintenance.py::test_cleanup_expired_alerts -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'src.db.maintenance'`

**Step 3: 实现 cleanup_expired_alerts**

创建 `src/db/maintenance.py`：

```python
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.models import ElectricData
from src.simulator.generator import SimulationGenerator


class DataMaintenance:
    def __init__(self, db: Session):
        self.db = db

    def cleanup_expired_alerts(self, days: int = 30) -> int:
        result = self.db.execute(
            text("DELETE FROM alert WHERE created_at < NOW() - INTERVAL ':days days'"),
            {"days": days},
        )
        self.db.commit()
        return result.rowcount
```

注意：先只实现 `cleanup_expired_alerts`，`backfill` 在下一步。

**Step 4: 运行测试确认通过**

Run: `pytest tests/test_maintenance.py::test_cleanup_expired_alerts -v`
Expected: PASS

**Step 5: 写失败测试 - backfill_missing_data**

在 `tests/test_maintenance.py` 添加：

```python
def test_backfill_missing_data_detects_gap():
    """检测到数据空缺时逐小时补全"""
    mock_db = MagicMock()

    # 模拟 MAX(time) 返回3小时前
    three_hours_ago = datetime.now() - timedelta(hours=3)
    mock_result = MagicMock()
    mock_result.scalar.return_value = three_hours_ago
    mock_db.execute.return_value = mock_result

    # 模拟 query(DeviceProfile).all() 返回一个 profile
    from src.db.models import DeviceProfile
    profile = DeviceProfile(
        point_id="test-001", mean_value=10.0, std_value=1.0, last_value=100.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=30)

    # 应该补全 2 个小时（3小时前到1小时前，当前小时由调度器负责）
    assert count == 2


def test_backfill_missing_data_empty_table():
    """表为空时从30天前开始补全"""
    mock_db = MagicMock()

    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute.return_value = mock_result

    from src.db.models import DeviceProfile
    profile = DeviceProfile(
        point_id="test-001", mean_value=10.0, std_value=1.0, last_value=0.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=30)

    # 30天 × 24小时 - 1（当前小时由调度器负责）
    assert count == 30 * 24 - 1


def test_backfill_no_gap():
    """无数据缺口时不补全"""
    mock_db = MagicMock()

    recent = datetime.now() - timedelta(minutes=30)
    mock_result = MagicMock()
    mock_result.scalar.return_value = recent
    mock_db.execute.return_value = mock_result

    m = DataMaintenance(mock_db)
    count = m.backfill_missing_data(days=30)

    assert count == 0
```

**Step 6: 运行测试确认失败**

Run: `pytest tests/test_maintenance.py::test_backfill_missing_data_detects_gap -v`
Expected: FAIL - `AttributeError: 'DataMaintenance' object has no attribute 'backfill_missing_data'`

**Step 7: 实现 backfill_missing_data**

更新 `src/db/maintenance.py`，在 `DataMaintenance` 类中添加 `backfill_missing_data`：

```python
def backfill_missing_data(self, days: int = 30) -> int:
    result = self.db.execute(text("SELECT MAX(time) FROM electric_data"))
    last_time = result.scalar()

    now = datetime.now()
    if last_time is None:
        start = now - timedelta(days=days)
    else:
        start = last_time

    start = start.replace(minute=0, second=0, microsecond=0)
    current = start + timedelta(hours=1)
    target = now.replace(minute=0, second=0, microsecond=0)

    if current > target:
        return 0

    generator = SimulationGenerator(self.db)
    count = 0
    while current < target:
        generator.generate_hourly_data(target_time=current)
        count += 1
        current += timedelta(hours=1)

    return count
```

**Step 8: 运行所有 maintenance 测试确认通过**

Run: `pytest tests/test_maintenance.py -v`
Expected: ALL PASS

**Step 9: Commit**

```bash
git add src/db/maintenance.py tests/test_maintenance.py
git commit -m "feat: add DataMaintenance for alert cleanup and data backfill"
```

---

## Task 4: 集成到 lifespan 启动流程

**Files:**
- Modify: `src/main.py:16-36`

**Step 1: 在 lifespan 中调用 maintenance**

修改 `src/main.py` 的 `lifespan` 函数，在 Excel 数据加载之后、调度器启动之前添加 maintenance 调用：

```python
from src.db.maintenance import DataMaintenance
```

在 lifespan 中，Excel 加载完成后添加：

```python
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
```

完整的 lifespan 函数：

```python
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
```

**Step 2: 运行全部测试确认无回归**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: integrate data maintenance into startup lifecycle"
```
