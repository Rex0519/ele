# 电力数据仿真系统

基于真实电力数据的仿真系统，支持自动生成符合实际用电规律的模拟数据，提供 REST API 和 MCP Server 供 AI 查询，并具备智能告警能力。

## 功能特性

- **数据仿真**：基于历史数据统计特征，按时段规律（夜间低谷、早晚高峰）自动生成仿真电力数据
- **智能告警**：支持阈值告警、趋势异常检测（同比激增/骤降）、设备离线检测
- **REST API**：完整的设备管理、电力数据查询、告警管理接口
- **MCP Server**：为 AI 提供电力数据查询工具，支持 Claude 等 AI 直接调用
- **定时调度**：每小时自动生成仿真数据并执行告警检测

## 技术栈

| 组件 | 技术 |
|------|------|
| 数据库 | PostgreSQL 16 + TimescaleDB |
| 后端框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 调度器 | APScheduler |
| AI 集成 | MCP SDK |
| 部署 | Docker Compose |

## 快速开始

### 环境要求

- Python 3.12+
- Docker & Docker Compose
- uv（Python 包管理器）

### 1. 安装依赖

```bash
# 克隆项目后进入目录
cd ele

# 安装依赖
uv sync
```

### 2. 准备数据

确保 `data_extracted/` 目录包含以下 Excel 文件（从 `data.zip` 解压）：

```
data_extracted/
├── ene_config_area.xls    # 区域配置
├── ene_config_item.xls    # 项目配置
├── ene_config_device.xls  # 设备-配置关联
├── devicenfo.xls          # 设备信息
└── electric.xls           # 历史电力数据
```

解压命令：
```bash
unzip data.zip -d data_extracted
```

### 3. 启动服务

```bash
# 启动数据库
docker-compose up -d db

# 等待数据库就绪（约 10 秒）
docker-compose ps  # 确认状态为 healthy

# 启动应用
uv run python -m src.main
```

应用启动时会自动：
1. 导入 Excel 数据到数据库
2. 提取设备特征用于仿真
3. 启动定时调度器（每小时整点执行）

### 4. 访问服务

- **API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health

## 数据库连接

| 参数 | 值 |
|------|-----|
| Host | localhost |
| Port | 5432 |
| Database | electric |
| User | admin |
| Password | password |

命令行连接：
```bash
docker exec -it ele-db-1 psql -U admin -d electric
```

## API 接口

### 设备管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/devices` | 获取设备列表 |
| GET | `/api/devices/{device_id}` | 获取设备详情 |
| GET | `/api/devices/{device_id}/data` | 获取设备历史电力数据 |

### 电力数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/electric/realtime` | 获取实时电力数据 |
| GET | `/api/electric/areas/{area_id}/summary` | 获取区域用电汇总 |
| GET | `/api/electric/statistics` | 获取统计分析数据 |

### 告警管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts` | 获取告警列表 |
| GET | `/api/alerts/active` | 获取未解决告警 |
| POST | `/api/alerts/{alert_id}/resolve` | 标记告警已解决 |
| GET | `/api/alerts/thresholds` | 获取阈值配置 |
| PUT | `/api/alerts/thresholds/{device_id}` | 更新设备阈值 |

### 示例请求

```bash
# 获取设备列表
curl http://localhost:8000/api/devices

# 获取实时数据
curl http://localhost:8000/api/electric/realtime?limit=10

# 获取统计数据（按天/周/月）
curl "http://localhost:8000/api/electric/statistics?period=day"

# 获取未解决告警
curl http://localhost:8000/api/alerts/active

# 设置设备告警阈值
curl -X PUT http://localhost:8000/api/alerts/thresholds/123456 \
  -H "Content-Type: application/json" \
  -d '{"min_value": 0, "max_value": 100, "severity": "WARNING"}'
```

## MCP Server

系统提供 MCP Server，可供 Claude 等 AI 直接调用查询电力数据。

### 可用工具

| 工具名 | 说明 |
|--------|------|
| `query_electric_data` | 查询指定设备的电力数据 |
| `get_area_summary` | 获取区域用电汇总 |
| `list_active_alerts` | 列出当前未解决告警 |
| `analyze_anomaly` | 分析设备异常情况 |

### Claude Desktop 配置

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "electric-simulation": {
      "command": "uv",
      "args": ["run", "python", "-c", "import asyncio; from src.mcp.server import run_mcp_server; asyncio.run(run_mcp_server())"],
      "cwd": "/path/to/ele",
      "env": {
        "DATABASE_URL": "postgresql+psycopg://admin:password@localhost:5432/electric"
      }
    }
  }
}
```

## 数据仿真原理

### 时段系数

系统根据实际用电规律，为不同时段设置系数：

| 时段 | 系数 | 说明 |
|------|------|------|
| 0:00 - 6:00 | 0.5 | 夜间低谷 |
| 7:00 - 9:00 | 1.3 | 早高峰 |
| 10:00 - 17:00 | 1.0 | 工作时段 |
| 18:00 - 21:00 | 1.4 | 晚高峰 |
| 22:00 - 23:00 | 0.7 | 夜间过渡 |

### 生成算法

```
增量 = max(0, 历史均值 × 时段系数 + 随机波动)
累计值 = 上次累计值 + 增量
```

随机波动服从正态分布，标准差为历史标准差的 10%。

## 告警规则

### 1. 阈值告警

当电力增量超出配置的阈值范围时触发。

```sql
-- 配置示例：设备 123 的增量超过 100 时告警
INSERT INTO threshold_config (device_id, min_value, max_value, severity)
VALUES (123, 0, 100, 'WARNING');
```

### 2. 趋势异常

- **同比激增**：当前增量 > 昨日同时段 × 1.5
- **同比骤降**：当前增量 < 昨日同时段 × 0.3

### 3. 设备离线

设备超过 2 小时无数据上报时触发 `HIGH` 级别告警。

## 数据库结构

### 核心表

| 表名 | 说明 |
|------|------|
| `config_area` | 区域配置 |
| `config_item` | 项目配置（充电桩、照明、空调等） |
| `device` | 设备信息 |
| `config_device` | 设备-配置关联 |
| `electric_data` | 电力时序数据（TimescaleDB hypertable） |
| `alert` | 告警记录 |
| `threshold_config` | 阈值配置 |
| `device_profile` | 设备特征（用于仿真） |

### 查询示例

```sql
-- 查看设备数量
SELECT count(*) FROM device;

-- 查看最近的电力数据
SELECT * FROM electric_data ORDER BY time DESC LIMIT 10;

-- 查看未解决的告警
SELECT * FROM alert WHERE resolved_at IS NULL;

-- 查看设备特征
SELECT point_id, mean_value, std_value FROM device_profile LIMIT 10;
```

## 项目结构

```
ele/
├── docker-compose.yml      # Docker 编排
├── Dockerfile              # 应用镜像
├── pyproject.toml          # 项目依赖
├── README.md               # 本文档
│
├── scripts/
│   └── init_db.sql         # 数据库初始化
│
├── src/
│   ├── main.py             # 应用入口
│   ├── config.py           # 配置管理
│   ├── scheduler.py        # 定时调度
│   │
│   ├── db/                 # 数据库层
│   │   ├── models.py       # ORM 模型
│   │   ├── connection.py   # 连接管理
│   │   └── init_data.py    # 数据导入
│   │
│   ├── api/                # REST API
│   │   ├── devices.py      # 设备接口
│   │   ├── electric.py     # 电力数据接口
│   │   └── alerts.py       # 告警接口
│   │
│   ├── simulator/          # 仿真引擎
│   │   ├── generator.py    # 数据生成器
│   │   └── profiles.py     # 时段系数
│   │
│   ├── alert/              # 告警系统
│   │   ├── detector.py     # 告警检测器
│   │   └── rules.py        # 告警规则
│   │
│   └── mcp/                # MCP Server
│       └── server.py       # AI 工具服务
│
├── tests/                  # 测试用例
│
├── data_extracted/         # Excel 数据（需解压）
│
└── docs/plans/             # 设计文档
```

## 开发

### 运行测试

```bash
uv run pytest tests/ -v
```

### 手动触发仿真

```python
from src.db import get_db
from src.simulator import SimulationGenerator
from src.alert import AlertDetector

db = next(get_db())

# 生成仿真数据
generator = SimulationGenerator(db)
records = generator.generate_hourly_data()
print(f"Generated {len(records)} records")

# 执行告警检测
detector = AlertDetector(db)
alerts = detector.detect_all()
print(f"Detected {len(alerts)} alerts")

db.close()
```

## 停止服务

```bash
# 停止应用（Ctrl+C）

# 停止并删除容器
docker-compose down

# 停止并删除容器及数据
docker-compose down -v
```

## License

MIT
