from datetime import datetime, timedelta

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from sqlalchemy import func
from starlette.routing import Route, Mount
from starlette.responses import Response

from src.db import get_db, ElectricData, Alert, ConfigArea, Device, DeviceProfile

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
            description="查询指定设备的电力数据（支持设备名称模糊匹配）",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "integer", "description": "设备ID"},
                    "device_name": {"type": "string", "description": "设备名称（支持模糊匹配）"},
                    "hours": {"type": "integer", "description": "查询最近多少小时", "default": 24},
                },
            },
        ),
        Tool(
            name="get_area_summary",
            description="获取区域用电汇总（支持区域名称模糊匹配）",
            inputSchema={
                "type": "object",
                "properties": {
                    "area_id": {"type": "integer", "description": "区域ID"},
                    "area_name": {"type": "string", "description": "区域名称（支持模糊匹配）"},
                    "period": {"type": "string", "enum": ["day", "week", "month"], "default": "day"},
                },
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
            description="分析设备异常情况（支持设备名称模糊匹配）",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "integer", "description": "设备ID"},
                    "device_name": {"type": "string", "description": "设备名称（支持模糊匹配）"},
                },
            },
        ),
        Tool(
            name="list_areas",
            description="列出所有区域",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="list_devices",
            description="列出设备，可按区域或类型过滤",
            inputSchema={
                "type": "object",
                "properties": {
                    "area": {"type": "string", "description": "区域名称（支持模糊匹配）"},
                    "device_type": {"type": "string", "description": "设备类型：照明/空调/扶梯/风机/水泵/广告"},
                },
            },
        ),
        Tool(
            name="compare_usage",
            description="对比用电量",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "区域或设备名称（可选）"},
                    "compare_type": {
                        "type": "string",
                        "enum": ["day", "week", "areas"],
                        "description": "对比类型：day(今天vs昨天)、week(本周vs上周)、areas(区域排名)",
                        "default": "day",
                    },
                },
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
        elif name == "list_areas":
            return await _list_areas(db, arguments)
        elif name == "list_devices":
            return await _list_devices(db, arguments)
        elif name == "compare_usage":
            return await _compare_usage(db, arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    finally:
        db.close()


async def _query_electric_data(db, args: dict):
    device_id = args.get("device_id")
    device_name = args.get("device_name")
    hours = args.get("hours", 24)
    start = datetime.now() - timedelta(hours=hours)

    point_id = None
    display_name = None

    if device_name:
        profiles = db.query(DeviceProfile).filter(
            DeviceProfile.display_name.ilike(f"%{device_name}%")
        ).limit(5).all()

        if not profiles:
            return [TextContent(type="text", text=f"未找到名称包含 '{device_name}' 的设备")]
        if len(profiles) > 1:
            lines = ["找到多个匹配设备，请选择:"]
            for p in profiles:
                lines.append(f"  • {p.point_id}: {p.display_name}")
            return [TextContent(type="text", text="\n".join(lines))]

        point_id = profiles[0].point_id
        display_name = profiles[0].display_name

        data = (
            db.query(ElectricData)
            .filter(ElectricData.point_id == point_id, ElectricData.time >= start)
            .order_by(ElectricData.time.desc())
            .limit(100)
            .all()
        )

        if not data:
            return [TextContent(type="text", text=f"{display_name} 在最近 {hours} 小时内无数据")]

        lines = [f"{display_name} 最近 {hours} 小时数据 ({len(data)} 条):"]
        for d in data[:10]:
            lines.append(f"  {d.time.strftime('%Y-%m-%d %H:%M')} | 读数: {d.value:.2f} | 增量: {d.incr:.2f}")
        if len(data) > 10:
            lines.append(f"  ... 还有 {len(data) - 10} 条记录")

        return [TextContent(type="text", text="\n".join(lines))]

    elif device_id:
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

    return [TextContent(type="text", text="请提供 device_id 或 device_name")]


async def _get_area_summary(db, args: dict):
    area_id = args.get("area_id")
    area_name = args.get("area_name")
    period = args.get("period", "day")

    area = None
    if area_name:
        area = db.query(ConfigArea).filter(
            ConfigArea.name.ilike(f"%{area_name}%"),
        ).first()
        if not area:
            return [TextContent(type="text", text=f"未找到名称包含 '{area_name}' 的区域")]
    elif area_id:
        area = db.query(ConfigArea).filter(ConfigArea.config_id == area_id).first()
        if not area:
            return [TextContent(type="text", text=f"区域 {area_id} 不存在")]
    else:
        return [TextContent(type="text", text="请提供 area_id 或 area_name")]

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
    device_id = args.get("device_id")
    device_name = args.get("device_name")

    display = None
    now = datetime.now()

    if device_name:
        profiles = db.query(DeviceProfile).filter(
            DeviceProfile.display_name.ilike(f"%{device_name}%")
        ).limit(5).all()

        if not profiles:
            return [TextContent(type="text", text=f"未找到名称包含 '{device_name}' 的设备")]
        if len(profiles) > 1:
            lines = ["找到多个匹配设备，请选择:"]
            for p in profiles:
                lines.append(f"  • {p.point_id}: {p.display_name}")
            return [TextContent(type="text", text="\n".join(lines))]

        profile = profiles[0]
        display = profile.display_name
        point_id = profile.point_id

        recent = (
            db.query(ElectricData)
            .filter(ElectricData.point_id == point_id, ElectricData.time >= now - timedelta(hours=24))
            .all()
        )

        alerts = (
            db.query(Alert)
            .filter(Alert.device_id == hash(point_id) % (10**18), Alert.resolved_at.is_(None))
            .all()
        )

    elif device_id:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            return [TextContent(type="text", text=f"设备 {device_id} 不存在")]
        display = f"{device.device_name} ({device.device_no})"

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
    else:
        return [TextContent(type="text", text="请提供 device_id 或 device_name")]

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

    text = (
        f"设备: {display}\n"
        f"状态: {status}\n"
        f"24小时数据量: {len(recent)} 条\n"
        f"未解决告警: {len(alerts)} 条"
    )

    if alerts:
        text += "\n\n告警详情:"
        for a in alerts:
            text += f"\n  [{a.severity}] {a.message}"

    return [TextContent(type="text", text=text)]


async def _list_areas(db, args: dict):
    areas = db.query(ConfigArea).filter(ConfigArea.is_delete == 0).all()

    if not areas:
        return [TextContent(type="text", text="暂无区域数据")]

    lines = ["系统区域列表:"]
    for area in areas:
        lines.append(f"  • {area.name}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _list_devices(db, args: dict):
    area = args.get("area")
    device_type = args.get("device_type")

    query = db.query(DeviceProfile)
    if area:
        query = query.filter(DeviceProfile.area_name.ilike(f"%{area}%"))
    if device_type:
        query = query.filter(DeviceProfile.device_type == device_type)

    profiles = query.limit(50).all()

    if not profiles:
        return [TextContent(type="text", text="未找到匹配的设备")]

    by_area: dict[str, list] = {}
    for p in profiles:
        by_area.setdefault(p.area_name, []).append(p)

    lines = [f"找到 {len(profiles)} 台设备:"]
    for area_name, devices in by_area.items():
        lines.append(f"\n{area_name}:")
        for d in devices:
            lines.append(f"  • {d.point_id}: {d.display_name} ({d.device_type})")

    return [TextContent(type="text", text="\n".join(lines))]


async def _compare_usage(db, args: dict):
    compare_type = args.get("compare_type", "day")

    now = datetime.now()

    if compare_type == "day":
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)

        today_total = db.query(func.sum(ElectricData.incr)).filter(
            ElectricData.time >= today_start
        ).scalar() or 0

        yesterday_total = db.query(func.sum(ElectricData.incr)).filter(
            ElectricData.time >= yesterday_start,
            ElectricData.time < today_start
        ).scalar() or 0

        diff = today_total - yesterday_total
        pct = (diff / yesterday_total * 100) if yesterday_total else 0

        text = (
            f"今日用电对比:\n"
            f"今日总用电: {today_total:.1f} 度\n"
            f"昨日总用电: {yesterday_total:.1f} 度\n"
            f"变化: {diff:+.1f} 度 ({pct:+.1f}%)"
        )

    elif compare_type == "week":
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_start = week_start - timedelta(weeks=1)

        this_week = db.query(func.sum(ElectricData.incr)).filter(
            ElectricData.time >= week_start
        ).scalar() or 0

        last_week = db.query(func.sum(ElectricData.incr)).filter(
            ElectricData.time >= last_week_start,
            ElectricData.time < week_start
        ).scalar() or 0

        diff = this_week - last_week
        pct = (diff / last_week * 100) if last_week else 0

        text = (
            f"本周用电对比:\n"
            f"本周总用电: {this_week:.1f} 度\n"
            f"上周总用电: {last_week:.1f} 度\n"
            f"变化: {diff:+.1f} 度 ({pct:+.1f}%)"
        )

    elif compare_type == "areas":
        results = db.query(
            DeviceProfile.area_name,
            func.sum(ElectricData.incr).label("total")
        ).join(
            ElectricData, ElectricData.point_id == DeviceProfile.point_id
        ).filter(
            ElectricData.time >= now - timedelta(days=1)
        ).group_by(DeviceProfile.area_name).order_by(
            func.sum(ElectricData.incr).desc()
        ).limit(10).all()

        lines = ["区域用电排名（今日）:"]
        total = sum(r.total or 0 for r in results)
        for i, r in enumerate(results, 1):
            pct = (r.total / total * 100) if total else 0
            lines.append(f"  {i}. {r.area_name}: {r.total:.1f} 度 ({pct:.1f}%)")

        text = "\n".join(lines)
    else:
        text = "不支持的对比类型"

    return [TextContent(type="text", text=text)]


async def run_mcp_server():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream)
