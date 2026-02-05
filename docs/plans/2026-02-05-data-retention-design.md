# 数据30天保留与自动补全设计

## 概述

项目不会持续运行，需要在启动时自动补全缺失数据，并清理超过30天的过期数据。

## 目标

- `electric_data` 和 `alert` 表保留最近30天数据
- 启动时自动补全停机期间缺失的 `electric_data`
- 启动时清理过期数据

## 设计

### 数据清理

**`electric_data` 表**

使用 TimescaleDB 原生 retention policy，在 `scripts/init_db.sql` 中添加：

```sql
SELECT add_retention_policy('electric_data', INTERVAL '30 days');
```

TimescaleDB 后台自动清理超过30天的 chunk。

**`alert` 表**

普通表，启动时执行 DELETE：

```sql
DELETE FROM alert WHERE created_at < NOW() - INTERVAL '30 days'
```

### 数据补全

**检测缺失**

查询 `electric_data` 最后一条记录时间，计算到当前时间缺失的小时数。表为空时从30天前开始。

**补全逻辑**

扩展 `SimulationGenerator.generate_hourly_data`，支持指定 `target_time` 参数：

```python
def generate_hourly_data(self, target_time: datetime | None = None) -> list[ElectricData]:
    ts = target_time or datetime.now()
    ...
```

逐小时循环调用补全缺失数据。

### 启动流程

```
1. 加载 Excel 数据（现有）
2. 清理过期 alert
3. 补全缺失 electric_data
4. 启动调度器（现有）
```

## 文件变更

| 文件 | 变更 |
|------|------|
| `scripts/init_db.sql` | 添加 retention policy |
| `src/db/maintenance.py` | 新建 `DataMaintenance` 类 |
| `src/simulator/generator.py` | `generate_hourly_data` 增加 `target_time` 参数 |
| `src/main.py` | lifespan 调用 maintenance |

## 接口设计

```python
class DataMaintenance:
    def __init__(self, db: Session): ...
    def cleanup_expired_alerts(self, days: int = 30) -> int: ...
    def backfill_missing_data(self, days: int = 30) -> int: ...
```
