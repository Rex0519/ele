# OpenClaw Electric Analysis Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建 OpenClaw skill，让 agent 能基于 CSV 文件执行 pandas 脚本进行电力数据离线分析。

**Architecture:** 单文件 SKILL.md，包含 YAML frontmatter + 5 个预定义分析场景（含完整 pandas 代码模板）+ fallback 自由生成机制 + guardrails。放置在 `~/.openclaw/skills/electric-analysis/` 目录下。

**Tech Stack:** OpenClaw Skill (SKILL.md)、pandas

---

### Task 1: 创建 SKILL.md 文件

**Files:**
- Create: `~/.openclaw/skills/electric-analysis/SKILL.md`

**Step 1: Create skill directory**

```bash
mkdir -p ~/.openclaw/skills/electric-analysis
```

**Step 2: Write SKILL.md**

创建 `~/.openclaw/skills/electric-analysis/SKILL.md`，完整内容如下：

````markdown
---
name: electric-analysis
description: 分析电力仿真数据。当用户提到用电量、电力数据、区域能耗、设备用电排名、告警、异常设备等关键词时自动激活。读取 data_export/ 目录下的 CSV 文件，使用 pandas 执行分析并返回结果。
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---

# 电力数据分析

## 数据位置

所有数据位于项目根目录的 `data_export/` 下，每天凌晨 2:00 自动从数据库导出更新。

执行任何分析前，先检查 `data_export/_metadata.json` 是否存在。如果不存在，告知用户"数据尚未导出，请先运行导出任务或等待每日自动导出"。

## 数据结构

| 文件 | 说明 | 关键字段 |
|------|------|----------|
| `areas.csv` | 区域配置 | config_id, name |
| `devices.csv` | 设备列表 | device_id, device_name, device_no, device_type, area_name, point_id, rated_power |
| `electric_data.csv` | 逐小时用电数据（近30天） | point_id, time, value(累计kWh), incr(小时增量kWh) |
| `alerts.csv` | 告警记录 | id, point_id, device_id, severity, message, created_at, resolved_at |

表关联：`devices.point_id` ↔ `electric_data.point_id` ↔ `alerts.point_id`

## 通用加载代码

每个分析脚本都以此开头：

```python
import pandas as pd
from pathlib import Path

base = Path("data_export")
devices = pd.read_csv(base / "devices.csv")
data = pd.read_csv(base / "electric_data.csv", parse_dates=["time"])
```

## 分析场景

### 场景 1：区域用电排名

触发词：哪个区域用电最多、区域排名、区域用电对比

```python
merged = data.merge(devices[["point_id", "area_name"]], on="point_id")
ranking = merged.groupby("area_name")["incr"].sum().sort_values(ascending=False).round(2)
print("区域用电排名（kWh）：")
print(ranking.to_string())
```

### 场景 2：日环比对比

触发词：今天和昨天、日环比、用电变化、日对比

```python
merged = data.merge(devices[["point_id", "area_name"]], on="point_id")
daily = merged.groupby(merged["time"].dt.date)["incr"].sum()
if len(daily) >= 2:
    today_val = daily.iloc[-1]
    yesterday_val = daily.iloc[-2]
    change = ((today_val - yesterday_val) / yesterday_val * 100).round(2)
    print(f"最近一天: {today_val:.2f} kWh")
    print(f"前一天: {yesterday_val:.2f} kWh")
    print(f"变化率: {'+' if change > 0 else ''}{change}%")
else:
    print("数据不足两天，无法计算环比")
```

### 场景 3：设备类型用电分布

触发词：各类型设备、照明/空调/扶梯占比、设备分类、类型分布

```python
merged = data.merge(devices[["point_id", "device_type"]], on="point_id")
by_type = merged.groupby("device_type")["incr"].sum().sort_values(ascending=False)
total = by_type.sum()
result = pd.DataFrame({"用电量(kWh)": by_type.round(2), "占比": (by_type / total * 100).round(2).astype(str) + "%"})
print("设备类型用电分布：")
print(result.to_string())
```

### 场景 4：异常设备检测

触发词：哪些设备异常、告警、问题设备、未解决告警

```python
alerts = pd.read_csv(base / "alerts.csv")
active = alerts[alerts["resolved_at"] == ""]
if active.empty:
    print("当前没有未解决的告警")
else:
    merged = active.merge(devices[["point_id", "device_name", "area_name"]], on="point_id", how="left")
    result = merged[["device_name", "area_name", "severity", "message", "created_at"]]
    print(f"当前 {len(result)} 条未解决告警：")
    print(result.to_string(index=False))
```

### 场景 5：时段用电模式

触发词：白天晚上、高峰低谷、时段分析、几点用电最多

```python
merged = data.merge(devices[["point_id", "area_name"]], on="point_id")
merged["hour"] = merged["time"].dt.hour
hourly = merged.groupby("hour")["incr"].mean().round(2)
print("各时段平均用电量（kWh）：")
print(hourly.to_string())
peak = hourly.idxmax()
valley = hourly.idxmin()
print(f"\n高峰时段: {peak}:00（{hourly[peak]:.2f} kWh）")
print(f"低谷时段: {valley}:00（{hourly[valley]:.2f} kWh）")
```

## Fallback：自定义查询

如果用户的问题不匹配以上任何场景，参考上方数据结构部分的 schema 描述，自行编写 pandas 代码来分析。使用通用加载代码作为起点，根据用户需求进行 merge、groupby、filter 等操作。

## 规则

1. 禁止修改或删除 `data_export/` 下的任何文件，只读取
2. 所有输出使用中文，数值保留 2 位小数
3. 如果分析结果为空或无匹配数据，如实告知用户，不要编造数据
4. 优先使用上方预定义场景的代码模板，仅在不匹配时自行生成
5. 执行脚本前先确认 `data_export/_metadata.json` 存在
````

**Step 3: Verify skill is loaded**

```bash
openclaw skills list --eligible 2>/dev/null || echo "OpenClaw not installed locally, skip verification"
```

**Step 4: Commit design doc**

```bash
cd /Users/qiwu/personal-projects/ele
git add docs/plans/2026-03-09-openclaw-skill-design.md
git commit -m "docs: add OpenClaw electric-analysis skill design"
```
