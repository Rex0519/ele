# 数据完整性检查报告

> 检查日期: 2026-02-06

## CRITICAL

### 1. `device_id` 体系断裂

**文件**: `src/simulator/generator.py:39`

```python
device_id=hash(profile.point_id) % (10**18)
```

仿真生成器用 `hash(point_id)` 生成 `device_id`，而 `Device` 表存储的是 Excel 导入的真实设备 ID。两套 ID 体系完全不互通。

**影响范围**:

- `GET /api/devices/{device_id}/data` — 真实 device_id 在 electric_data 中不存在，永远查不到数据
- `AlertDetector._detect_threshold_alerts()` (`src/alert/detector.py:26-30`) — `ThresholdConfig.device_id` 匹配不到 electric_data 记录，阈值告警形同虚设
- Python `hash()` 受 `PYTHONHASHSEED` 随机化影响，每次进程重启生成的 device_id 可能不同，历史数据与新数据的 device_id 会错位

### 2. 区域汇总未按区域过滤

**文件**: `src/api/electric.py:75-83`, `src/mcp/server.py:242-250`

两处区域汇总查询都接收了 `area_id` / `area_name` 参数，但实际 SQL 查询未做区域过滤，返回的是全部设备的汇总数据。

---

## MODERATE

### 3. `electric_data` 表无主键约束

**文件**: `scripts/init_db.sql:50-56`

建表语句未定义 PRIMARY KEY。SQLAlchemy 模型声明了 `(time, device_id)` 复合主键，但 TimescaleDB hypertable 不强制此约束。

**影响**: 应用崩溃后重启执行 `backfill_missing_data` 可能插入重复时间点数据，无法在数据库层面防止重复记录。

### 4. naive/aware datetime 混用

数据库列为 `TIMESTAMPTZ`（时区感知），但代码广泛使用 `datetime.now()`（naive datetime）:

| 文件 | 行号 | 场景 |
|------|------|------|
| `src/db/maintenance.py` | 14, 27 | cleanup / backfill |
| `src/alert/detector.py` | 58, 117 | 趋势检测 / 离线检测 |
| `src/api/electric.py` | 70, 99 | API 统计查询 |
| `src/api/alerts.py` | 89 | resolve alert |
| `src/mcp/server.py` | 152, 234, 285, 407 | MCP 工具 |

PostgreSQL 会隐式使用服务器时区解析 naive datetime，跨时区部署或 DST 切换时可能产生数据偏差。

### 5. 异常分析使用未排序查询结果

**文件**: `src/mcp/server.py:304-308`

```python
recent = (
    db.query(ElectricData)
    .filter(ElectricData.point_id == point_id, ElectricData.time >= now - timedelta(hours=24))
    .all()
)
```

查询未加 `ORDER BY`，但 `server.py:340` 直接取 `recent[0]` 作为最新数据进行异常判断。数据库返回顺序不保证，可能导致误判。

---

## LOW

### 6. `backfill_missing_data` 不回填当前小时

**文件**: `src/db/maintenance.py:41`

```python
while current < target:
```

使用严格小于，当前整点时段永远不会被回填。

### 7. `DeviceProfile.original_point_id` 始终为 None

**文件**: `src/db/init_data.py:52`

该字段硬编码为 `None`，从未被赋值或使用。

### 8. `extract_device_profiles` 为死代码

**文件**: `src/db/init_data.py:14-26`

标注为"旧方法，保留向后兼容"，但从未被调用。
