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
