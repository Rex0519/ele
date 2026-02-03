# Dify 前端 + 短信通知 设计方案

## 需求

- 3-5 个非技术管理层通过自然语言查询用电数据，返回文字摘要
- 异常告警通过短信单向通知，短信平台待定

## 架构

```
管理层用户
    ↓ 自然语言对话
Dify Agent (Docker 自部署)
    ↓ MCP over HTTP/SSE
MCP Server (新增 HTTP 传输)
    ↓ SQL
PostgreSQL + TimescaleDB
```

```
APScheduler (每小时)
    → AlertDetector.detect_all()
    → 新告警 → SmsSender (短信平台 API)
```

查询和通知两条路径完全独立。

## 改动清单

### 1. MCP Server 增加 HTTP/SSE 传输

**文件**: `src/mcp/server.py`

当前仅支持 stdio 传输。新增 HTTP/SSE 传输入口，与 stdio 共存：

- 使用 MCP Python SDK 的 `StreamableHTTPServer` 或 SSE transport
- 新增启动函数 `run_mcp_http(host, port)`
- 在 `src/main.py` 的 lifespan 中启动 HTTP MCP Server
- 原有 stdio 模式保留，供 Claude Desktop 等客户端继续使用

Dify 连接地址: `http://<host>:<mcp_port>/mcp`

### 2. 短信通知模块

**新增文件**: `src/alert/sms.py`

```python
class SmsSender:
    """短信发送抽象层，具体平台实现后替换"""

    async def send(self, phones: list[str], message: str) -> bool:
        raise NotImplementedError
```

**修改文件**: `src/scheduler.py`

在 `run_hourly_tasks()` 中，`detect_all()` 返回新告警后调用 `SmsSender.send()`。

**配置**: `src/config.py` 新增短信相关配置项（平台、密钥、接收手机号列表），默认禁用。

### 3. Dify Docker 部署

在项目根目录或独立目录部署 Dify：

- 使用 Dify 官方 `docker-compose.yml`
- 与现有数据库服务独立（Dify 有自己的 PostgreSQL 和 Redis）
- 通过 Docker 网络访问 MCP Server 的 HTTP 端口

### 4. Dify 应用配置（无代码）

- 添加 MCP Server 连接：指向 MCP HTTP 端口
- 创建 Agent 类型应用
- 系统提示词要求 LLM：用中文回复、返回简洁摘要、面向非技术人员
- 发布为 Web App，管理层通过浏览器访问

## 不做的事

- 不做图表可视化
- 不做短信回复交互
- 不通过 Dify 发短信（直接在后端处理）
- 不改现有 REST API 和数据库结构
