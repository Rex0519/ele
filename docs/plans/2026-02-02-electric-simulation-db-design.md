# 电力数据仿真系统设计方案

## 概述

基于 `data.zip` 中的真实电力数据，构建具备仿真数据生成、AI 查询、监控告警能力的电力数据库系统。

## 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| 数据库 | PostgreSQL + TimescaleDB | 关系型 + 时序扩展 |
| 后端 | FastAPI | REST API + MCP Server |
| 调度 | APScheduler | 每小时数据生成/告警检测 |
| 部署 | Docker Compose | 容器化部署 |

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ PostgreSQL  │  │   App       │  │   Scheduler     │  │
│  │ + Timescale │◄─┤  (FastAPI)  │  │   (APScheduler) │  │
│  └─────────────┘  └──────┬──────┘  └────────┬────────┘  │
│                          │                   │           │
│                    ┌─────┴─────┐      ┌─────┴─────┐     │
│                    │ REST API  │      │ 数据生成器 │     │
│                    │ MCP Server│      │ 告警检测器 │     │
│                    └───────────┘      └───────────┘     │
└─────────────────────────────────────────────────────────┘
```

## 数据库设计

### 配置表（普通表）

```sql
-- 区域配置
CREATE TABLE config_area (
    config_id BIGINT PRIMARY KEY,
    parent_id VARCHAR(50),
    name VARCHAR(100),
    level INT,
    energy_type VARCHAR(20),
    park_id INT
);

-- 项目配置
CREATE TABLE config_item (
    config_id BIGINT PRIMARY KEY,
    parent_id VARCHAR(50),
    name VARCHAR(100),
    level INT,
    energy_type VARCHAR(20),
    park_id INT
);

-- 设备信息
CREATE TABLE device (
    device_id BIGINT PRIMARY KEY,
    device_no VARCHAR(50),
    device_name VARCHAR(200),
    point_type_id BIGINT,
    region_id BIGINT,
    building_id BIGINT,
    floor_id BIGINT,
    status INT
);

-- 设备-配置关联
CREATE TABLE config_device (
    config_device_id BIGINT PRIMARY KEY,
    config_id BIGINT,
    device_id BIGINT,
    device_level INT,
    energy_type VARCHAR(20),
    config_type VARCHAR(20)
);
```

### 时序表（TimescaleDB hypertable）

```sql
CREATE TABLE electric_data (
    time TIMESTAMPTZ NOT NULL,
    device_id BIGINT NOT NULL,
    point_id VARCHAR(50),
    value DOUBLE PRECISION,
    incr DOUBLE PRECISION,
    PRIMARY KEY (time, device_id)
);

SELECT create_hypertable('electric_data', 'time');
```

### 告警表

```sql
CREATE TABLE alert (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT,
    alert_type VARCHAR(20),
    severity VARCHAR(10),
    message TEXT,
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE threshold_config (
    id SERIAL PRIMARY KEY,
    device_id BIGINT,
    metric VARCHAR(20),
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    severity VARCHAR(10)
);
```

## 仿真数据生成

### 设备特征提取

从 `electric.xls` 提取每个 `point_id` 的统计特征：
- 基准值范围（min, max, mean, std）
- 时段模式（白天/夜间/高峰差异）
- 增量分布特征

### 生成算法

```python
def generate_value(point_id: str, hour: int) -> tuple[float, float]:
    profile = device_profiles[point_id]

    # 基础值 = 历史均值
    base = profile.mean

    # 时段系数
    time_factor = get_time_factor(hour, profile.pattern)

    # 随机波动（正态分布）
    noise = random.gauss(0, profile.std * 0.1)

    # 增量计算
    incr = max(0, base * time_factor + noise)
    value = last_value[point_id] + incr

    return value, incr
```

### 时段系数

| 时段 | 系数 | 说明 |
|------|------|------|
| 0-6时 | 0.5 | 夜间低谷 |
| 7-9时 | 1.3 | 早高峰 |
| 10-17时 | 1.0 | 工作时段 |
| 18-21时 | 1.4 | 晚高峰 |
| 22-23时 | 0.7 | 夜间过渡 |

## 告警检测

### 告警类型

**1. 阈值告警**
- 当前值超出配置的 min/max 范围

**2. 趋势异常**
- 同比增长超过 50%：`TREND_SPIKE`
- 同比下降超过 70%：`TREND_DROP`

**3. 设备离线**
- 超过 2 小时无数据上报

### 告警级别

`INFO` → `WARNING` → `HIGH` → `CRITICAL`

## API 设计

### REST API

```
GET  /api/devices                    # 设备列表
GET  /api/devices/{id}/data          # 设备历史数据
GET  /api/areas/{id}/summary         # 区域用电汇总
GET  /api/electric/realtime          # 实时数据
GET  /api/electric/statistics        # 统计分析

GET  /api/alerts                     # 告警列表
GET  /api/alerts/active              # 当前未解决告警
POST /api/alerts/{id}/resolve        # 标记告警已解决

GET  /api/thresholds                 # 阈值配置
PUT  /api/thresholds/{device_id}     # 更新阈值
```

### MCP Server Tools

```python
@tool
def query_electric_data(device_id, start_time, end_time):
    """查询指定设备的电力数据"""

@tool
def get_area_summary(area_id, period='day'):
    """获取区域用电汇总"""

@tool
def list_active_alerts(severity=None):
    """列出当前告警"""

@tool
def analyze_anomaly(device_id):
    """分析设备异常情况"""
```

## 项目结构

```
ele/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
│
├── src/
│   ├── main.py
│   ├── config.py
│   │
│   ├── db/
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── init_data.py
│   │
│   ├── api/
│   │   ├── devices.py
│   │   ├── electric.py
│   │   └── alerts.py
│   │
│   ├── mcp/
│   │   └── server.py
│   │
│   ├── simulator/
│   │   ├── generator.py
│   │   └── profiles.py
│   │
│   └── alert/
│       ├── detector.py
│       └── rules.py
│
└── scripts/
    └── init_db.sql
```

## Docker Compose

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: electric
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  app:
    build: .
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://admin:${DB_PASSWORD}@db:5432/electric
    ports:
      - "8000:8000"
      - "8001:8001"
    command: python -m src.main

volumes:
  pgdata:
```

## 启动流程

1. `docker-compose up -d` 启动服务
2. 应用自动执行：建表 → 导入 Excel 数据 → 提取设备特征
3. APScheduler 每小时触发：生成数据 → 检测告警
