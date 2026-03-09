# OpenClaw Electric Analysis Skill 设计

## 背景

系统已实现 CSV 数据导出（`data_export/` 目录），需要创建 OpenClaw skill 让 agent 能基于这些文件做离线电力数据分析。

## 方案

场景驱动型 Skill + Fallback 自由生成。预定义 5 个常见分析场景，每个场景有完整 pandas 代码模板；不匹配时 agent 基于 schema 描述临时生成脚本。

## Skill 配置

- **位置**：`~/.openclaw/skills/electric-analysis/SKILL.md`（全局 managed skill）
- **名称**：`electric-analysis`
- **触发**：agent 自动识别用电相关意图 + 用户手动 `/electric-analysis`
- **执行**：agent 生成并执行 pandas 脚本，直接返回分析结果

## YAML Frontmatter

```yaml
---
name: electric-analysis
description: 分析电力仿真数据。当用户提到用电量、电力数据、区域能耗、设备用电排名等关键词时自动激活。读取 data_export/ 目录下的 CSV 文件，使用 pandas 执行预定义分析场景并返回结果。
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---
```

## 预定义分析场景

### 场景 1：区域用电排名

- **触发**：哪个区域用电最多、区域排名、区域用电对比
- **逻辑**：按 area_name 聚合 incr 求和，降序排列

### 场景 2：日环比对比

- **触发**：今天和昨天、日环比、用电变化
- **逻辑**：按日期分组求和，计算变化率

### 场景 3：设备类型用电分布

- **触发**：各类型设备、照明/空调/扶梯占比、设备分类
- **逻辑**：按 device_type 聚合 incr 求和

### 场景 4：异常设备检测

- **触发**：哪些设备异常、告警、问题设备
- **逻辑**：读取 alerts.csv，关联 devices.csv 展示未解决告警

### 场景 5：时段用电模式

- **触发**：白天晚上、高峰低谷、时段分析
- **逻辑**：按小时分组，统计各时段平均用电

### Fallback：自定义查询

- **触发**：不匹配以上任何场景时
- **逻辑**：agent 读取 `_metadata.json` 了解 schema，自行生成 pandas 代码

## Guardrails

1. **只读操作** — 禁止修改或删除 data_export/ 下的文件
2. **数据路径** — 先检查 `data_export/_metadata.json` 是否存在
3. **数据缺失** — 文件不存在时告知用户"数据尚未导出"
4. **结果格式** — 中文返回，数值保留 2 位小数，表格展示
5. **不捏造数据** — 结果为空时如实说明

## 改动范围

### 新增

- `~/.openclaw/skills/electric-analysis/SKILL.md` — 完整 skill 文件

### 不改动

- 项目源码、MCP Server、CSV 导出逻辑均不变
