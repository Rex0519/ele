import asyncio
from datetime import datetime, timedelta, timezone

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
            description="对比用电量（支持按设备类型筛选、指定日期对比）",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "区域或设备名称（可选）"},
                    "compare_type": {
                        "type": "string",
                        "enum": ["day", "week", "areas"],
                        "description": "对比类型：day(基准日vs前一日)、week(本周vs上周)、areas(区域排名)",
                        "default": "day",
                    },
                    "device_type": {
                        "type": "string",
                        "description": "设备类型筛选（如：照明、空调、扶梯），不填则统计全部类型",
                    },
                    "date": {
                        "type": "string",
                        "description": "基准日期(YYYY-MM-DD)，默认今天。day模式下对比该日与前一日",
                    },
                },
            },
        ),
        Tool(
            name="usage_ranking",
            description="按区域或设备类型维度统计用电排名",
            inputSchema={
                "type": "object",
                "properties": {
                    "dimension": {
                        "type": "string",
                        "enum": ["area", "device_type"],
                        "description": "聚合维度：area(按区域排名)、device_type(按设备类型排名)",
                    },
                    "device_type": {
                        "type": "string",
                        "description": "设备类型筛选（dimension=area时有用，如只看照明设备）",
                    },
                    "area": {
                        "type": "string",
                        "description": "区域名筛选（dimension=device_type时有用，如只看西北楼）",
                    },
                    "date": {
                        "type": "string",
                        "description": "统计日期(YYYY-MM-DD)，默认今天",
                    },
                },
                "required": ["dimension"],
            },
        ),
    ]


def _execute_tool(name: str, arguments: dict):
    handlers = {
        "query_electric_data": _query_electric_data,
        "get_area_summary": _get_area_summary,
        "list_active_alerts": _list_active_alerts,
        "analyze_anomaly": _analyze_anomaly,
        "list_areas": _list_areas,
        "list_devices": _list_devices,
        "compare_usage": _compare_usage,
        "usage_ranking": _usage_ranking,
    }
    handler = handlers.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    db = next(get_db())
    try:
        return handler(db, arguments)
    finally:
        db.close()


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        return await asyncio.to_thread(_execute_tool, name, arguments)
    except Exception as e:
        return [TextContent(type="text", text=f"工具执行出错: {e}")]


def _query_electric_data(db, args: dict):
    device_id = args.get("device_id")
    device_name = args.get("device_name")
    hours = args.get("hours", 24)
    start = datetime.now(timezone.utc) - timedelta(hours=hours)

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


def _get_area_summary(db, args: dict):
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

    now = datetime.now(timezone.utc)
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
        .join(DeviceProfile, ElectricData.point_id == DeviceProfile.point_id)
        .filter(ElectricData.time >= start, DeviceProfile.area_name == area.name)
        .first()
    )

    text = f"""区域: {area.name}
统计周期: {period}
总用电量: {stats.total or 0:.2f} kWh
平均用电: {stats.avg or 0:.2f} kWh/次
数据条数: {stats.count or 0}"""

    return [TextContent(type="text", text=text)]


def _list_active_alerts(db, args: dict):
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


def _analyze_anomaly(db, args: dict):
    device_id = args.get("device_id")
    device_name = args.get("device_name")

    display = None
    now = datetime.now(timezone.utc)

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
            .order_by(ElectricData.time.desc())
            .all()
        )

        alerts = (
            db.query(Alert)
            .filter(Alert.point_id == point_id, Alert.resolved_at.is_(None))
            .all()
        )

    elif device_id:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            return [TextContent(type="text", text=f"设备 {device_id} 不存在")]
        display = f"{device.device_name} ({device.device_no})"

        profile = db.query(DeviceProfile).filter(DeviceProfile.device_id == device_id).first()
        if profile:
            recent = (
                db.query(ElectricData)
                .filter(ElectricData.point_id == profile.point_id, ElectricData.time >= now - timedelta(hours=24))
                .order_by(ElectricData.time.desc())
                .all()
            )
            alerts = (
                db.query(Alert)
                .filter(Alert.point_id == profile.point_id, Alert.resolved_at.is_(None))
                .all()
            )
        else:
            recent = []
            alerts = []
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


def _list_areas(db, args: dict):
    areas = db.query(ConfigArea).filter(ConfigArea.is_delete == 0).all()

    if not areas:
        return [TextContent(type="text", text="暂无区域数据")]

    lines = ["系统区域列表:"]
    for area in areas:
        lines.append(f"  • {area.name}")

    return [TextContent(type="text", text="\n".join(lines))]


def _list_devices(db, args: dict):
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


def _parse_base_date(date_str: str | None) -> datetime:
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _day_range(base: datetime) -> tuple[datetime, datetime]:
    start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _sum_incr_query(db, start, end, device_type=None):
    q = db.query(func.sum(ElectricData.incr))
    if device_type:
        q = q.join(DeviceProfile, ElectricData.point_id == DeviceProfile.point_id).filter(
            DeviceProfile.device_type == device_type
        )
    return q.filter(ElectricData.time >= start, ElectricData.time < end).scalar() or 0


def _compare_usage(db, args: dict):
    compare_type = args.get("compare_type", "day")
    device_type = args.get("device_type")
    base = _parse_base_date(args.get("date"))

    type_label = f"({device_type})" if device_type else ""

    if compare_type == "day":
        day_start, day_end = _day_range(base)
        prev_start = day_start - timedelta(days=1)

        current_total = _sum_incr_query(db, day_start, day_end, device_type)
        prev_total = _sum_incr_query(db, prev_start, day_start, device_type)

        diff = current_total - prev_total
        pct = (diff / prev_total * 100) if prev_total else 0

        cur_date = day_start.strftime("%m-%d")
        prev_date = prev_start.strftime("%m-%d")
        text = (
            f"用电对比{type_label}:\n"
            f"{cur_date} 总用电: {current_total:.1f} 度\n"
            f"{prev_date} 总用电: {prev_total:.1f} 度\n"
            f"变化: {diff:+.1f} 度 ({pct:+.1f}%)"
        )

    elif compare_type == "week":
        week_start = base - timedelta(days=base.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_start = week_start - timedelta(weeks=1)

        this_week = _sum_incr_query(db, week_start, base, device_type)
        last_week = _sum_incr_query(db, last_week_start, week_start, device_type)

        diff = this_week - last_week
        pct = (diff / last_week * 100) if last_week else 0

        text = (
            f"本周用电对比{type_label}:\n"
            f"本周总用电: {this_week:.1f} 度\n"
            f"上周总用电: {last_week:.1f} 度\n"
            f"变化: {diff:+.1f} 度 ({pct:+.1f}%)"
        )

    elif compare_type == "areas":
        day_start, day_end = _day_range(base)

        q = db.query(
            DeviceProfile.area_name,
            func.sum(ElectricData.incr).label("total")
        ).join(
            ElectricData, ElectricData.point_id == DeviceProfile.point_id
        ).filter(ElectricData.time >= day_start, ElectricData.time < day_end)

        if device_type:
            q = q.filter(DeviceProfile.device_type == device_type)

        results = q.group_by(DeviceProfile.area_name).order_by(
            func.sum(ElectricData.incr).desc()
        ).limit(10).all()

        date_label = day_start.strftime("%m-%d")
        lines = [f"区域用电排名{type_label}（{date_label}）:"]
        total = sum(r.total or 0 for r in results)
        for i, r in enumerate(results, 1):
            pct = (r.total / total * 100) if total else 0
            lines.append(f"  {i}. {r.area_name}: {r.total:.1f} 度 ({pct:.1f}%)")

        text = "\n".join(lines)
    else:
        text = "不支持的对比类型"

    return [TextContent(type="text", text=text)]


def _usage_ranking(db, args: dict):
    dimension = args.get("dimension", "area")
    device_type = args.get("device_type")
    area = args.get("area")
    base = _parse_base_date(args.get("date"))
    day_start, day_end = _day_range(base)

    group_col = DeviceProfile.area_name if dimension == "area" else DeviceProfile.device_type

    q = db.query(
        group_col.label("group_key"),
        func.sum(ElectricData.incr).label("total"),
        func.count(func.distinct(DeviceProfile.point_id)).label("device_count"),
    ).join(
        ElectricData, ElectricData.point_id == DeviceProfile.point_id
    ).filter(ElectricData.time >= day_start, ElectricData.time < day_end)

    if device_type:
        q = q.filter(DeviceProfile.device_type == device_type)
    if area:
        q = q.filter(DeviceProfile.area_name.ilike(f"%{area}%"))

    results = q.group_by(group_col).order_by(func.sum(ElectricData.incr).desc()).all()

    if not results:
        return [TextContent(type="text", text="该条件下无用电数据")]

    date_label = day_start.strftime("%Y-%m-%d")
    dim_label = "区域" if dimension == "area" else "设备类型"
    filters = []
    if device_type:
        filters.append(f"类型={device_type}")
    if area:
        filters.append(f"区域={area}")
    filter_label = f"（{', '.join(filters)}）" if filters else ""

    grand_total = sum(r.total or 0 for r in results)
    lines = [f"{dim_label}用电排名{filter_label}（{date_label}）:"]
    for i, r in enumerate(results, 1):
        pct = (r.total / grand_total * 100) if grand_total else 0
        lines.append(f"  {i}. {r.group_key}: {r.total:.1f} 度 ({pct:.1f}%) [{r.device_count}台设备]")
    lines.append(f"合计: {grand_total:.1f} 度")

    return [TextContent(type="text", text="\n".join(lines))]


async def run_mcp_server():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream)
