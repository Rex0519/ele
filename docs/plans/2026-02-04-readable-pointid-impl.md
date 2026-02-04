# 仿真数据可读化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将仿真数据中的 UUID point_id 改为可读格式，并增强 MCP 工具支持自然语言查询

**Architecture:** 修改 DeviceProfile 模型增加 display_name/device_type/area_name 字段，改造 init_data.py 从设备名称解析类型和区域，新增/改造 MCP 工具支持名称模糊匹配

**Tech Stack:** Python, SQLAlchemy, MCP SDK, PostgreSQL

---

## Task 1: 设备名称解析器

**Files:**
- Create: `src/db/device_parser.py`
- Test: `tests/test_device_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_device_parser.py
import pytest
from src.db.device_parser import parse_device_name, DEVICE_TYPES, AREA_ABBR


def test_parse_lighting_device():
    result = parse_device_name("F-WS-AT-tlzm-s1-总表")
    assert result["area"] == "西南"
    assert result["device_type"] == "照明"


def test_parse_aircon_device():
    result = parse_device_name("F-EN-AP-kt-s1-1-空调WK3")
    assert result["area"] == "东北"
    assert result["device_type"] == "空调"


def test_parse_escalator_device():
    result = parse_device_name("F-WS-AT-ft-s1-3")
    assert result["area"] == "西南"
    assert result["device_type"] == "扶梯"


def test_parse_layer_device():
    result = parse_device_name("(243-Z1)APgl-7-箱门表")
    assert result["area"] == "243层"
    assert result["device_type"] == "公共照明"


def test_parse_energy_center_device():
    result = parse_device_name("(H3-6)ATz1-WLTD1")
    assert result["area"] == "能源中心"
    assert result["device_type"] == "其他"


def test_parse_unknown_device():
    result = parse_device_name("unknown-device-xyz")
    assert result["area"] == "其他"
    assert result["device_type"] == "其他"


def test_device_types_mapping():
    assert "照明" in DEVICE_TYPES.values()
    assert "空调" in DEVICE_TYPES.values()
    assert "扶梯" in DEVICE_TYPES.values()


def test_area_abbr_mapping():
    assert AREA_ABBR["西北"] == "XBL"
    assert AREA_ABBR["东南"] == "DNL"
    assert AREA_ABBR["243层"] == "243C"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_device_parser.py -v`
Expected: FAIL with "No module named 'src.db.device_parser'"

**Step 3: Write minimal implementation**

```python
# src/db/device_parser.py
import re

DEVICE_TYPES = {
    "tlzm": "照明",
    "kt": "空调",
    "ft": "扶梯",
    "fj": "风机",
    "sy": "水泵",
    "gg": "广告",
    "xx": "消防",
    "gl": "公共照明",
    "py": "配电",
    "pdj": "配电间",
    "wsj": "污水井",
    "rsq": "热水器",
}

AREA_ABBR = {
    "西北": "XBL",
    "西南": "XNL",
    "东北": "DBL",
    "东南": "DNL",
    "中南": "ZNL",
    "中北": "ZBL",
    "243层": "243C",
    "238层": "238C",
    "249层": "249C",
    "能源中心": "NYZX",
    "地下负2层": "DXF2",
    "地下负3层": "DXF3",
    "其他": "QT",
}

AREA_ABBR_REVERSE = {v: k for k, v in AREA_ABBR.items()}
DEVICE_TYPE_ABBR = {
    "照明": "ZM",
    "空调": "KT",
    "扶梯": "FT",
    "风机": "FJ",
    "水泵": "SB",
    "广告": "GG",
    "消防": "XF",
    "公共照明": "GL",
    "配电": "PD",
    "配电间": "PDJ",
    "污水井": "WSJ",
    "热水器": "RSQ",
    "其他": "QT",
}


def parse_device_name(name: str) -> dict:
    """解析设备名称，提取区域和设备类型"""
    area = _extract_area(name)
    device_type = _extract_device_type(name)
    return {"area": area, "device_type": device_type}


def _extract_area(name: str) -> str:
    name_upper = name.upper()
    if re.search(r"F-WS|[-_]WS[-_]", name_upper):
        return "西南"
    if re.search(r"F-WN|[-_]WN[-_]", name_upper):
        return "西北"
    if re.search(r"F-ES|[-_]ES[-_]", name_upper):
        return "东南"
    if re.search(r"F-EN|[-_]EN[-_]", name_upper):
        return "东北"
    if re.search(r"F-CS|[-_]CS[-_]", name_upper):
        return "中南"
    if re.search(r"F-CN|[-_]CN[-_]", name_upper):
        return "中北"
    if "243" in name:
        return "243层"
    if "238" in name:
        return "238层"
    if "249" in name:
        return "249层"
    if re.search(r"H[23][-_]", name_upper):
        return "能源中心"
    return "其他"


def _extract_device_type(name: str) -> str:
    name_lower = name.lower()
    for code, type_name in DEVICE_TYPES.items():
        if code in name_lower:
            return type_name
    if "照明" in name:
        return "照明"
    if "空调" in name:
        return "空调"
    if "热水器" in name:
        return "热水器"
    return "其他"


def generate_point_id(area: str, device_type: str, seq: int) -> str:
    """生成可读的 point_id"""
    area_code = AREA_ABBR.get(area, "QT")
    type_code = DEVICE_TYPE_ABBR.get(device_type, "QT")
    return f"{area_code}-{type_code}-{seq:02d}"


def generate_display_name(area: str, device_type: str, seq: int) -> str:
    """生成中文显示名称"""
    return f"{area}-{device_type}-{seq:02d}号"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_device_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/db/device_parser.py tests/test_device_parser.py
git commit -m "feat: add device name parser for area and type extraction"
```

---

## Task 2: 扩展 DeviceProfile 模型

**Files:**
- Modify: `src/db/models.py:95-104`
- Modify: `scripts/init_db.sql:89-97`
- Modify: `src/db/__init__.py`

**Step 1: Update DeviceProfile model**

```python
# src/db/models.py - Replace DeviceProfile class (lines 95-104)
class DeviceProfile(Base):
    __tablename__ = "device_profile"

    point_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    device_type: Mapped[str | None] = mapped_column(String(20))
    area_name: Mapped[str | None] = mapped_column(String(50))
    original_point_id: Mapped[str | None] = mapped_column(String(50))
    mean_value: Mapped[float | None] = mapped_column(Double)
    std_value: Mapped[float | None] = mapped_column(Double)
    min_value: Mapped[float | None] = mapped_column(Double)
    max_value: Mapped[float | None] = mapped_column(Double)
    last_value: Mapped[float] = mapped_column(Double, default=0)
```

**Step 2: Update init_db.sql**

```sql
-- scripts/init_db.sql - Replace device_profile table (lines 89-97)
-- 设备特征（用于仿真）
CREATE TABLE IF NOT EXISTS device_profile (
    point_id VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100),
    device_type VARCHAR(20),
    area_name VARCHAR(50),
    original_point_id VARCHAR(50),
    mean_value DOUBLE PRECISION,
    std_value DOUBLE PRECISION,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    last_value DOUBLE PRECISION DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_profile_area ON device_profile (area_name);
CREATE INDEX IF NOT EXISTS idx_profile_type ON device_profile (device_type);
```

**Step 3: Update src/db/__init__.py to export DeviceProfile**

Ensure DeviceProfile is exported from `src/db/__init__.py`.

**Step 4: Run existing tests**

Run: `uv run pytest tests/ -v`
Expected: PASS (existing tests should still work)

**Step 5: Commit**

```bash
git add src/db/models.py scripts/init_db.sql src/db/__init__.py
git commit -m "feat: extend DeviceProfile with display_name, device_type, area_name"
```

---

## Task 3: 改造数据初始化逻辑

**Files:**
- Modify: `src/db/init_data.py`
- Modify: `tests/test_init_data.py`

**Step 1: Write the failing test**

```python
# tests/test_init_data.py - Add new test
def test_extract_device_profiles_with_metadata():
    mock_df = pd.DataFrame({
        "point_id": ["uuid1", "uuid1", "uuid2", "uuid2"],
        "value": [100.0, 110.0, 200.0, 220.0],
        "incr": [10.0, 12.0, 20.0, 22.0],
    })
    device_names = {
        "uuid1": "F-WS-AT-tlzm-s1-总表",
        "uuid2": "F-EN-AP-kt-s1-1-空调WK3",
    }

    profiles = extract_device_profiles_v2(mock_df, device_names)

    assert profiles[0]["area_name"] == "西南"
    assert profiles[0]["device_type"] == "照明"
    assert profiles[0]["original_point_id"] == "uuid1"
    assert profiles[0]["point_id"].startswith("XNL-ZM-")

    assert profiles[1]["area_name"] == "东北"
    assert profiles[1]["device_type"] == "空调"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_init_data.py::test_extract_device_profiles_with_metadata -v`
Expected: FAIL with "cannot import name 'extract_device_profiles_v2'"

**Step 3: Write implementation**

```python
# src/db/init_data.py - Add new function and modify load_excel_data
from src.db.device_parser import (
    parse_device_name,
    generate_point_id,
    generate_display_name,
)


def extract_device_profiles_v2(
    df: pd.DataFrame, device_names: dict[str, str]
) -> list[dict]:
    """从电力数据中提取设备特征（包含可读名称）"""
    # 按区域+类型分组计数，用于生成序号
    area_type_seq: dict[tuple[str, str], int] = {}

    profiles = []
    for original_point_id, group in df.groupby("point_id"):
        device_name = device_names.get(original_point_id, "")
        parsed = parse_device_name(device_name)
        area = parsed["area"]
        device_type = parsed["device_type"]

        key = (area, device_type)
        seq = area_type_seq.get(key, 0) + 1
        area_type_seq[key] = seq

        point_id = generate_point_id(area, device_type, seq)
        display_name = generate_display_name(area, device_type, seq)

        profiles.append({
            "point_id": point_id,
            "display_name": display_name,
            "device_type": device_type,
            "area_name": area,
            "original_point_id": original_point_id,
            "mean_value": group["incr"].mean(),
            "std_value": group["incr"].std() if len(group) > 1 else 0,
            "min_value": group["incr"].min(),
            "max_value": group["incr"].max(),
            "last_value": group["value"].iloc[-1] if len(group) > 0 else 0,
        })

    return profiles
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_init_data.py -v`
Expected: PASS

**Step 5: Update load_excel_data to use new function**

```python
# src/db/init_data.py - Modify the profile extraction part in load_excel_data
def load_excel_data(db: Session, data_dir: Path) -> None:
    # ... existing code for areas, items, devices, config_devices ...

    # 提取设备特征（使用新函数）
    electric_df = pd.read_excel(data_dir / "electric.xls")
    device_df = pd.read_excel(data_dir / "devicenfo.xls")

    # 构建 point_id -> device_name 映射
    # 注意：electric.xls 中的 point_id 需要通过某种方式关联到 device_name
    # 由于原数据没有直接关联，这里使用设备名称列表为仿真数据生成可读名称
    device_names = {}
    for _, row in device_df.iterrows():
        # 使用 device_id 的 hash 作为临时映射（与 generator.py 一致）
        pseudo_point_id = str(row["device_id"])
        device_names[pseudo_point_id] = row["device_name"]

    # 为 electric.xls 中的每个 point_id 创建 profile
    # 由于 electric 中的 point_id 是 UUID，无法直接关联设备名
    # 策略：为每个 device 生成一个 profile，而非用 electric.xls 的 UUID
    profiles = []
    area_type_seq: dict[tuple[str, str], int] = {}

    for _, row in device_df.iterrows():
        device_name = row["device_name"]
        parsed = parse_device_name(device_name)
        area = parsed["area"]
        device_type = parsed["device_type"]

        key = (area, device_type)
        seq = area_type_seq.get(key, 0) + 1
        area_type_seq[key] = seq

        point_id = generate_point_id(area, device_type, seq)
        display_name = generate_display_name(area, device_type, seq)

        profiles.append(DeviceProfile(
            point_id=point_id,
            display_name=display_name,
            device_type=device_type,
            area_name=area,
            original_point_id=None,  # 不再关联原 UUID
            mean_value=10.0,  # 默认值，后续可从实际数据计算
            std_value=2.0,
            min_value=0.0,
            max_value=50.0,
            last_value=0,
        ))

    for profile in profiles:
        db.merge(profile)

    db.commit()
```

**Step 6: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/db/init_data.py tests/test_init_data.py
git commit -m "feat: generate readable point_id from device names"
```

---

## Task 4: MCP 工具 - list_areas

**Files:**
- Modify: `src/mcp/server.py`
- Create: `tests/test_mcp_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_mcp_tools.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db():
    return MagicMock()


def test_list_areas_returns_grouped_areas(mock_db):
    from src.mcp.server import _list_areas

    # Mock ConfigArea query
    mock_areas = [
        MagicMock(name="西北楼", config_id="1"),
        MagicMock(name="西南楼", config_id="2"),
        MagicMock(name="243层", config_id="3"),
        MagicMock(name="能源中心", config_id="4"),
    ]
    mock_db.query.return_value.filter.return_value.all.return_value = mock_areas

    import asyncio
    result = asyncio.run(_list_areas(mock_db, {}))

    assert len(result) == 1
    assert "西北楼" in result[0].text
    assert "西南楼" in result[0].text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_tools.py::test_list_areas_returns_grouped_areas -v`
Expected: FAIL with "cannot import name '_list_areas'"

**Step 3: Add list_areas tool to server.py**

```python
# src/mcp/server.py - Add to list_tools() return list
Tool(
    name="list_areas",
    description="列出所有区域",
    inputSchema={
        "type": "object",
        "properties": {},
    },
),

# Add to call_tool()
elif name == "list_areas":
    return await _list_areas(db, arguments)

# Add implementation
async def _list_areas(db, args: dict):
    areas = db.query(ConfigArea).filter(ConfigArea.is_delete == 0).all()

    if not areas:
        return [TextContent(type="text", text="暂无区域数据")]

    # Group by level or parent
    lines = ["系统区域列表:"]
    for area in areas:
        lines.append(f"  • {area.name}")

    return [TextContent(type="text", text="\n".join(lines))]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/mcp/server.py tests/test_mcp_tools.py
git commit -m "feat(mcp): add list_areas tool"
```

---

## Task 5: MCP 工具 - list_devices

**Files:**
- Modify: `src/mcp/server.py`
- Modify: `tests/test_mcp_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_mcp_tools.py - Add test
def test_list_devices_filter_by_area(mock_db):
    from src.mcp.server import _list_devices

    mock_profiles = [
        MagicMock(point_id="XBL-ZM-01", display_name="西北楼-照明-01号", device_type="照明", area_name="西北"),
        MagicMock(point_id="XBL-KT-01", display_name="西北楼-空调-01号", device_type="空调", area_name="西北"),
    ]
    mock_db.query.return_value.filter.return_value.all.return_value = mock_profiles

    import asyncio
    result = asyncio.run(_list_devices(mock_db, {"area": "西北"}))

    assert "西北楼-照明-01号" in result[0].text
    assert "西北楼-空调-01号" in result[0].text


def test_list_devices_filter_by_type(mock_db):
    from src.mcp.server import _list_devices

    mock_profiles = [
        MagicMock(point_id="XBL-ZM-01", display_name="西北楼-照明-01号", device_type="照明", area_name="西北"),
        MagicMock(point_id="DNL-ZM-01", display_name="东南楼-照明-01号", device_type="照明", area_name="东南"),
    ]
    mock_db.query.return_value.filter.return_value.all.return_value = mock_profiles

    import asyncio
    result = asyncio.run(_list_devices(mock_db, {"device_type": "照明"}))

    assert "照明" in result[0].text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_tools.py::test_list_devices_filter_by_area -v`
Expected: FAIL

**Step 3: Add list_devices tool**

```python
# src/mcp/server.py - Add to list_tools()
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

# Add to call_tool()
elif name == "list_devices":
    return await _list_devices(db, arguments)

# Add implementation
from src.db import DeviceProfile

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

    # Group by area
    by_area: dict[str, list] = {}
    for p in profiles:
        by_area.setdefault(p.area_name, []).append(p)

    lines = [f"找到 {len(profiles)} 台设备:"]
    for area_name, devices in by_area.items():
        lines.append(f"\n{area_name}:")
        for d in devices:
            lines.append(f"  • {d.point_id}: {d.display_name} ({d.device_type})")

    return [TextContent(type="text", text="\n".join(lines))]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/mcp/server.py tests/test_mcp_tools.py
git commit -m "feat(mcp): add list_devices tool with area/type filter"
```

---

## Task 6: MCP 工具 - compare_usage

**Files:**
- Modify: `src/mcp/server.py`
- Modify: `tests/test_mcp_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_mcp_tools.py - Add test
def test_compare_usage_day(mock_db):
    from src.mcp.server import _compare_usage

    # Mock aggregation results
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        total=1000.0
    )

    import asyncio
    result = asyncio.run(_compare_usage(mock_db, {"compare_type": "day"}))

    assert "今日" in result[0].text or "用电" in result[0].text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_tools.py::test_compare_usage_day -v`
Expected: FAIL

**Step 3: Add compare_usage tool**

```python
# src/mcp/server.py - Add to list_tools()
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

# Add to call_tool()
elif name == "compare_usage":
    return await _compare_usage(db, arguments)

# Add implementation
async def _compare_usage(db, args: dict):
    compare_type = args.get("compare_type", "day")
    target = args.get("target")

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

        text = f"""今日用电对比:
今日总用电: {today_total:.1f} 度
昨日总用电: {yesterday_total:.1f} 度
变化: {diff:+.1f} 度 ({pct:+.1f}%)"""

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

        text = f"""本周用电对比:
本周总用电: {this_week:.1f} 度
上周总用电: {last_week:.1f} 度
变化: {diff:+.1f} 度 ({pct:+.1f}%)"""

    elif compare_type == "areas":
        # 按区域统计（通过 DeviceProfile.area_name 关联）
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/mcp/server.py tests/test_mcp_tools.py
git commit -m "feat(mcp): add compare_usage tool for day/week/areas comparison"
```

---

## Task 7: 改造现有工具支持名称查询

**Files:**
- Modify: `src/mcp/server.py`
- Modify: `tests/test_mcp_tools.py`

**Step 1: Write the failing test**

```python
# tests/test_mcp_tools.py - Add test
def test_query_electric_data_by_name(mock_db):
    from src.mcp.server import _query_electric_data

    # Mock profile lookup
    mock_profile = MagicMock(point_id="XBL-ZM-01", display_name="西北楼-照明-01号")
    mock_db.query.return_value.filter.return_value.first.return_value = mock_profile
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    import asyncio
    result = asyncio.run(_query_electric_data(mock_db, {"device_name": "西北楼照明"}))

    # Should attempt to find device by name
    assert "西北楼-照明-01号" in result[0].text or "无数据" in result[0].text
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_tools.py::test_query_electric_data_by_name -v`
Expected: FAIL

**Step 3: Modify query_electric_data to support device_name**

```python
# src/mcp/server.py - Modify Tool definition
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

# Modify implementation
async def _query_electric_data(db, args: dict):
    device_id = args.get("device_id")
    device_name = args.get("device_name")
    hours = args.get("hours", 24)
    start = datetime.now() - timedelta(hours=hours)

    point_id = None
    display_name = None

    # 优先使用名称查询
    if device_name:
        profiles = db.query(DeviceProfile).filter(
            DeviceProfile.display_name.ilike(f"%{device_name}%")
        ).limit(5).all()

        if not profiles:
            return [TextContent(type="text", text=f"未找到名称包含 '{device_name}' 的设备")]
        if len(profiles) > 1:
            lines = [f"找到多个匹配设备，请选择:"]
            for p in profiles:
                lines.append(f"  • {p.point_id}: {p.display_name}")
            return [TextContent(type="text", text="\n".join(lines))]

        point_id = profiles[0].point_id
        display_name = profiles[0].display_name
    elif device_id:
        # 通过 device_id 查询
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
        return [TextContent(type="text", text="\n".join(lines))]
    else:
        return [TextContent(type="text", text="请提供 device_id 或 device_name")]

    # 使用 point_id 查询
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
```

**Step 4: Similarly modify get_area_summary and analyze_anomaly**

Apply same pattern: add `area_name` / `device_name` parameter, use `ilike` for fuzzy match.

**Step 5: Run tests**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/mcp/server.py tests/test_mcp_tools.py
git commit -m "feat(mcp): add name-based fuzzy matching to existing tools"
```

---

## Task 8: 更新 Dify 系统提示词

**Files:**
- Modify: `docs/dify-system-prompt.md`

**Step 1: Update prompt content**

```markdown
# docs/dify-system-prompt.md
# Dify Agent 系统提示词

复制以下内容到 Dify Agent 的「系统提示词」设置中：

---

你是电力数据查询助手，服务于企业管理层。

## 回复规范

- 始终使用中文回复
- 回答简洁明了，避免技术术语
- 使用易于理解的数字和比喻
- 主动给出建议或总结

## 查询能力

你可以帮助查询：
- **设备发现**：有哪些区域、某区域有哪些设备、某类型设备列表
- **用电查询**：指定设备或区域的用电数据
- **异常排查**：当前告警、设备异常分析
- **对比分析**：今天vs昨天、本周vs上周、区域排名

## 可用工具

| 工具 | 说明 | 示例问法 |
|------|------|----------|
| list_areas | 列出所有区域 | "有哪些区域？" |
| list_devices | 列出设备（可按区域/类型过滤） | "西北楼有哪些设备？" "有哪些空调？" |
| query_electric_data | 查询设备用电数据 | "西北楼照明用电情况" |
| get_area_summary | 区域用电汇总 | "西北楼今天用了多少电？" |
| compare_usage | 用电对比分析 | "今天比昨天用电多了多少？" "哪个区域用电最多？" |
| list_active_alerts | 当前告警 | "有哪些告警？" |
| analyze_anomaly | 设备异常分析 | "3号空调正常吗？" |

## 回复格式示例

**设备列表：**
> 西北楼共有 12 台设备：
> • 照明：XBL-ZM-01、XBL-ZM-02
> • 空调：XBL-KT-01、XBL-KT-02

**用电查询：**
> 西北楼今日用电 1,234 度，比昨天增加 5%。高峰出现在上午 10 点。

**告警查询：**
> 当前有 2 条告警需要关注：
> 1. [HIGH] 西南楼-扶梯-01 用电量偏高
> 2. [WARNING] 243层-照明-03 超过2小时无数据

**对比分析：**
> 今日总用电 12,450 度，比昨日增加 320 度（+2.6%）。
> 增幅最大：东南楼 +15%

**无数据时：**
> 暂无相关数据。您可以换个时间段或设备再查询。

## 注意事项

- 如果用户问题模糊，主动询问具体设备或区域
- 优先使用设备名称查询（如"西北楼照明"），比 ID 更友好
- 数据异常时主动提醒，但不要危言耸听
- 不要编造数据，如果查不到就如实告知
```

**Step 2: Commit**

```bash
git add docs/dify-system-prompt.md
git commit -m "docs: update Dify system prompt with new tools and examples"
```

---

## Task 9: 更新 README

**Files:**
- Modify: `README.md`

**Step 1: Update MCP tools section**

Add documentation for new tools (list_areas, list_devices, compare_usage) and the name-based query capability.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with new MCP tools"
```

---

## Task 10: 集成测试

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
from unittest.mock import MagicMock, patch


def test_full_workflow_list_then_query():
    """Test: list areas -> list devices -> query device data"""
    # This is a workflow test to ensure tools work together
    pass  # Placeholder - actual implementation depends on test infrastructure
```

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 3: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for MCP workflow"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Device name parser | src/db/device_parser.py, tests/test_device_parser.py |
| 2 | Extend DeviceProfile model | src/db/models.py, scripts/init_db.sql |
| 3 | Update data initialization | src/db/init_data.py, tests/test_init_data.py |
| 4 | MCP: list_areas | src/mcp/server.py |
| 5 | MCP: list_devices | src/mcp/server.py |
| 6 | MCP: compare_usage | src/mcp/server.py |
| 7 | Enhance existing tools | src/mcp/server.py |
| 8 | Update Dify prompt | docs/dify-system-prompt.md |
| 9 | Update README | README.md |
| 10 | Integration test | tests/test_integration.py |
