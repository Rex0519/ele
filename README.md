# 电力数据仿真系统

基于真实电力数据的仿真系统，支持自动生成符合实际用电规律的模拟数据，提供 REST API 和 MCP Server 供 AI 查询，并具备智能告警和短信通知能力。通过 Dify 平台提供自然语言对话界面，供管理层直接查询用电数据。

## 功能特性

- **自然语言查询**：通过 Dify Agent 对话界面，用自然语言查询用电数据和告警信息
- **数据仿真**：基于历史数据统计特征，按时段规律（夜间低谷、早晚高峰）自动生成仿真电力数据
- **智能告警**：支持阈值告警、趋势异常检测（同比激增/骤降）、设备离线检测
- **短信通知**：检测到高级别告警时自动发送短信通知（支持接入第三方短信平台）
- **REST API**：完整的设备管理、电力数据查询、告警管理接口
- **MCP Server**：支持 stdio 和 SSE 双传输模式，供 Claude Desktop 和 Dify 等 AI 平台调用
- **定时调度**：每小时自动生成仿真数据并执行告警检测

## 系统架构

```
管理层用户 ──自然语言对话──→ Dify Agent ──MCP/SSE──→ FastAPI + MCP Server ──→ PostgreSQL
                                                            ↑
                                        APScheduler ──告警检测──→ 短信平台 API
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 数据库 | PostgreSQL 16 + TimescaleDB |
| 后端框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 调度器 | APScheduler |
| AI 集成 | MCP SDK (stdio + SSE) |
| AI 前端 | Dify (Docker 自部署) |
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

### 4. 部署 Dify

```bash
# 克隆 Dify
git clone --depth 1 --branch "$(curl -s https://api.github.com/repos/langgenius/dify/releases/latest | jq -r .tag_name)" https://github.com/langgenius/dify.git

# 启动 Dify
cd dify/docker
cp .env.example .env
docker compose up -d
```

访问 http://localhost/install 创建管理员账号，然后：

1. **Tools → MCP → Add MCP Server (HTTP)**
   - URL: `http://host.docker.internal:8000/mcp/sse`
   - Name: `电力仿真系统`
   - ID: `electric-simulation`
2. **创建 Agent 应用** → 添加 MCP 工具 → 粘贴系统提示词（见 `docs/dify-system-prompt.md`）
3. **发布应用** → 管理层通过浏览器访问对话界面

### 5. 访问服务

| 服务 | 地址 |
|------|------|
| Dify 对话界面 | http://localhost |
| API 文档 | http://localhost:8000/docs |
| MCP SSE 端点 | http://localhost:8000/mcp/sse |
| 健康检查 | http://localhost:8000/health |

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

系统提供 MCP Server，支持 stdio 和 SSE 双传输模式。

### 可用工具

| 工具名 | 说明 |
|--------|------|
| `list_areas` | 列出所有区域 |
| `list_devices` | 列出设备，可按区域或类型过滤 |
| `query_electric_data` | 查询指定设备的电力数据（支持名称模糊匹配） |
| `get_area_summary` | 获取区域用电汇总（支持名称模糊匹配） |
| `compare_usage` | 对比用电量（日/周/区域排名） |
| `list_active_alerts` | 列出当前未解决告警 |
| `analyze_anomaly` | 分析设备异常情况（支持名称模糊匹配） |

### SSE 模式（Dify 等 AI 平台）

应用启动后 SSE 端点自动可用：`http://localhost:8000/mcp/sse`

### stdio 模式（Claude Desktop）

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

## 短信通知

系统在检测到 HIGH 或 CRITICAL 级别告警时自动发送短信通知。

### 配置

通过环境变量或 `.env` 文件配置：

```bash
SMS_ENABLED=true
SMS_PHONES='["13800138000","13900139000"]'
```

当前使用占位实现（`DummySmsSender`），仅打印日志。接入真实短信平台时，继承 `SmsSender` 基类实现 `send` 方法即可。

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
│   │   ├── init_data.py    # 数据导入
│   │   └── device_parser.py # 设备名称解析器
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
│   │   ├── rules.py        # 告警规则
│   │   └── sms.py          # 短信发送（抽象层）
│   │
│   └── mcp/                # MCP Server
│       └── server.py       # AI 工具服务（stdio + SSE）
│
├── tests/                  # 测试用例
│
├── data_extracted/         # Excel 数据（需解压）
│
├── docs/
│   ├── dify-system-prompt.md  # Dify Agent 系统提示词
│   └── plans/              # 设计文档
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

# 停止 Dify
cd dify/docker && docker compose down

# 停止数据库
docker-compose down

# 停止并删除数据库数据
docker-compose down -v
```

## License

MIT
