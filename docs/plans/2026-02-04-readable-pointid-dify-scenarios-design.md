# 仿真数据可读化 + Dify 交互场景设计

## 背景

当前仿真数据中的 `point_id` 使用 UUID 格式（如 `002927e560a34a13b2f76cad8cd278be`），用户在 Dify 中交互时难以理解和使用。需要改造为可读格式，并增强 MCP 工具以支持自然语言查询场景。

## 设计目标

1. 将 point_id 改为可读格式：`{区域简称}-{设备类型}-{序号}`
2. MCP 返回数据时自动关联设备名称/区域信息
3. 支持按名称模糊查询和列表选择
4. 覆盖用电查询、异常排查、对比分析、设备发现四类场景

---

## 第一部分：数据模型改造

### 1.1 设备类型映射

从现有设备名称中提取类型，建立中文映射：

| 代码 | 中文名称 | 示例设备 |
|------|----------|----------|
| tlzm | 照明 | F-WS-AT-tlzm-s1-总表 |
| kt | 空调 | F-EN-AP-kt-s1-1-空调WK3 |
| ft | 扶梯 | F-WS-AT-ft-s1-3 |
| fj | 风机 | F-CS-AP-fj-s1-2 |
| sy | 水泵 | F-CS-AL-sy-s2-总表 |
| gg | 广告 | F-WN-AL-gg-S2-总表 |
| rsq | 热水器 | F-CN-AP-Kt-s1-7-热水器1 |
| other | 其他 | 未匹配的设备 |

### 1.2 区域简称映射

| 区域名称 | 简称 |
|----------|------|
| 西北楼 | XBL |
| 西南楼 | XNL |
| 东北楼 | DBL |
| 东南楼 | DNL |
| 243层 | 243C |
| 238层 | 238C |
| 249层 | 249C |
| 能源中心 | NYZX |
| 能源中心1层 | NYZX1 |
| 能源中心2层 | NYZX2 |
| 能源中心屋面层 | NYZXWM |
| 地下负2层 | DXF2 |
| 地下负3层 | DXF3 |

### 1.3 point_id 格式

新格式：`{区域简称}-{设备类型代码}-{两位序号}`

示例：
- `XBL-ZM-01` → 西北楼-照明-01
- `DNL-KT-03` → 东南楼-空调-03
- `243C-FT-02` → 243层-扶梯-02

### 1.4 DeviceProfile 表结构变更

```python
class DeviceProfile(Base):
    __tablename__ = "device_profile"

    point_id: Mapped[str]           # 新格式：XBL-ZM-01
    display_name: Mapped[str]       # 中文显示名：西北楼-照明-01号
    device_type: Mapped[str]        # 设备类型：照明
    area_name: Mapped[str]          # 所属区域：西北楼
    original_point_id: Mapped[str]  # 原 UUID（保留用于数据关联）

    # 原有统计字段
    mean_value: Mapped[float | None]
    std_value: Mapped[float | None]
    min_value: Mapped[float | None]
    max_value: Mapped[float | None]
    last_value: Mapped[float]
```

---

## 第二部分：MCP 工具增强

### 2.1 新增工具

#### list_areas - 列出所有区域

```python
Tool(
    name="list_areas",
    description="列出所有区域",
    inputSchema={
        "type": "object",
        "properties": {},
    },
)
```

返回示例：
```
系统共有 15 个区域：
• 枢纽：西北楼、西南楼、东北楼、东南楼
• 楼层：243层、238层、249层
• 能源中心：能源中心、能源中心1层、能源中心2层、能源中心屋面层
• 地下：地下负2层、地下负3层
```

#### list_devices - 列出设备

```python
Tool(
    name="list_devices",
    description="列出设备，可按区域或类型过滤",
    inputSchema={
        "type": "object",
        "properties": {
            "area": {"type": "string", "description": "区域名称（可选，支持模糊匹配）"},
            "device_type": {"type": "string", "description": "设备类型（可选）：照明/空调/扶梯/风机/水泵/广告/热水器"},
        },
    },
)
```

返回示例：
```
西北楼共有 12 台设备：
• 照明：XBL-ZM-01(总表)、XBL-ZM-02
• 空调：XBL-KT-01、XBL-KT-02
• 广告：XBL-GG-01(总表)
```

#### compare_usage - 对比分析

```python
Tool(
    name="compare_usage",
    description="对比用电量",
    inputSchema={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "区域或设备名称（可选，不填则查全部）"},
            "compare_type": {
                "type": "string",
                "enum": ["day", "week", "areas"],
                "description": "对比类型：day(今天vs昨天)、week(本周vs上周)、areas(区域排名)",
                "default": "day",
            },
        },
    },
)
```

### 2.2 改造现有工具

| 工具 | 原参数 | 新增参数 | 变更说明 |
|------|--------|----------|----------|
| query_electric_data | device_id (必填) | device_name (可选) | 支持名称模糊匹配 |
| get_area_summary | area_id (必填) | area_name (可选) | 支持名称模糊匹配 |
| analyze_anomaly | device_id (必填) | device_name (可选) | 支持名称模糊匹配 |
| list_active_alerts | severity (可选) | area (可选) | 支持按区域过滤 |

### 2.3 模糊匹配逻辑

```python
def find_by_name(db, name: str, model) -> list:
    """模糊匹配，返回匹配结果列表"""
    return db.query(model).filter(
        model.name.ilike(f"%{name}%")
    ).all()

# 使用逻辑：
# - 匹配到 1 个：直接查询
# - 匹配到多个：返回列表让用户选择
# - 匹配到 0 个：提示未找到，建议使用 list_areas/list_devices
```

---

## 第三部分：Dify 交互场景

### 场景1：设备/区域发现

```
用户：有哪些区域？
助手：系统共有 15 个区域：
      • 枢纽：西北楼、西南楼、东北楼、东南楼
      • 楼层：243层、238层、249层
      • 其他：能源中心、能源中心1层...

用户：西北楼有哪些设备？
助手：西北楼共有 12 台设备：
      • 照明：XBL-ZM-01(总表)、XBL-ZM-02
      • 空调：XBL-KT-01、XBL-KT-02
      • 广告：XBL-GG-01(总表)

用户：有哪些空调？
助手：系统共有 8 台空调设备：
      • 西北楼：XBL-KT-01、XBL-KT-02
      • 东南楼：DNL-KT-01、DNL-KT-02、DNL-KT-03
      • 东北楼：DBL-KT-01、DBL-KT-02、DBL-KT-03
```

### 场景2：用电查询

```
用户：西北楼今天用了多少电？
助手：西北楼今日用电 1,234 度，比昨天增加 5%。
      用电高峰出现在 10:00-11:00。

用户：3号空调最近用电情况
助手：东北楼-空调-03 最近24小时：
      • 总用电：89.5 度
      • 平均每小时：3.7 度
      • 状态：正常

用户：照明设备用电情况
助手：照明设备今日总用电 2,350 度：
      • 西北楼照明：580 度
      • 东南楼照明：520 度
      • 243层照明：450 度
      ...
```

### 场景3：异常排查

```
用户：哪些设备用电异常？
助手：当前有 2 台设备异常：
      1. [HIGH] 西南楼-扶梯-01：用电量较平均高出 180%
      2. [WARNING] 243层-照明-03：超过2小时无数据

用户：西南楼的告警有哪些？
助手：西南楼当前有 1 条告警：
      • [HIGH] 扶梯-01 用电量偏高，建议检查设备运行状态

用户：最近有什么严重告警？
助手：最近 24 小时内有 1 条 HIGH 级别告警：
      • 西南楼-扶梯-01：用电量异常偏高
      建议安排人员现场检查。
```

### 场景4：对比分析

```
用户：今天比昨天用电多了多少？
助手：今日总用电 12,450 度，比昨日增加 320 度（+2.6%）。
      增幅最大：东南楼 +15%
      降幅最大：能源中心 -8%

用户：哪个区域用电最多？
助手：今日区域用电排名：
      1. 西北楼：3,200 度（占比 25.7%）
      2. 东南楼：2,890 度（占比 23.2%）
      3. 243层：1,560 度（占比 12.5%）
      ...

用户：本周和上周比怎么样？
助手：本周总用电 85,200 度，比上周减少 2,100 度（-2.4%）。
      主要变化：
      • 空调用电下降 8%（天气转凉）
      • 照明用电上升 3%
```

---

## 第四部分：实现步骤

### Step 1：数据库变更

1. 修改 `DeviceProfile` 模型，增加新字段
2. 更新 `scripts/init_db.sql`
3. 编写数据迁移脚本

### Step 2：数据迁移脚本

1. 解析现有设备名称，提取区域、类型
2. 建立设备与区域的关联关系
3. 生成新的 point_id 和 display_name
4. 迁移现有数据

### Step 3：MCP 工具扩展

1. 新增 `list_areas`、`list_devices`、`compare_usage` 工具
2. 改造现有工具支持 name 参数
3. 添加模糊匹配逻辑
4. 更新返回格式，包含可读名称

### Step 4：更新 Dify 系统提示词

1. 补充新工具的使用说明
2. 添加场景引导示例
3. 优化回复格式模板

### Step 5：测试验证

1. 单元测试：名称解析、模糊匹配
2. 集成测试：MCP 工具调用
3. 端到端测试：Dify 对话场景

---

## 风险与注意事项

1. **数据兼容性**：保留 `original_point_id` 字段，确保历史数据可追溯
2. **命名冲突**：序号生成需确保唯一性
3. **模糊匹配性能**：使用 ILIKE 可能影响大数据量场景，必要时添加索引
