# OpenClaw 告警接管设计

## 背景

系统已有每小时告警检测 + 飞书推送能力（`FeishuSender`），但推送内容为原始告警列表，缺乏智能分析。需要将告警监控和推送完全交由 OpenClaw 接管，利用 AI 生成可读性强的中文分析报告。

## 方案

移除系统内置飞书推送，OpenClaw 通过 REST API 获取实时告警数据，AI 分析后推送飞书。

## 架构

```
APScheduler ──每小时──→ 数据生成 + 告警检测 → PostgreSQL
                                                  ↓
OpenClaw crontab ──每小时05分──→ curl /api/alerts/active
                                    ↓ 有告警
                              AI 分析生成报告 → 飞书 Webhook
                 ──每日08:00──→ curl API + 读取 CSV
                                    ↓
                              AI 生成日报 → 飞书 Webhook

APScheduler ──每日02:00──→ CSV 导出 → data_export/
```

## 系统侧改动

### src/scheduler.py

移除 `FeishuSender` 调用。告警检测逻辑保留不变，检测结果写入数据库供 API 查询。

```python
def run_hourly_tasks():
    db = next(get_db())
    try:
        generator = SimulationGenerator(db)
        records = generator.generate_hourly_data()
        detector = AlertDetector(db)
        alerts = detector.detect_all()
    finally:
        db.close()
```

### 不动的部分

- REST API（`/api/alerts/active`、`/api/alerts`）
- MCP Server
- 告警检测逻辑（`AlertDetector`）
- CSV 每日导出

## OpenClaw Skill 扩展

在现有 `electric-analysis` skill 中增加两个场景。

### 场景 6：实时告警检查（每小时触发）

- **触发**：crontab 每小时05分 或 用户问「有异常吗」
- **流程**：
  1. `curl http://43.136.40.150:8000/api/alerts/active` 获取未解决告警
  2. 无告警 → 静默，不推送
  3. 有告警 → AI 分析生成中文报告（设备名、区域、异常类型、建议）
  4. 通过飞书 Webhook 推送报告

### 场景 7：每日分析日报（每日08:00触发）

- **触发**：crontab 每日08:00
- **流程**：
  1. curl API 获取过去24小时告警 + 读取 CSV 做用电趋势分析
  2. AI 生成日报：昨日告警汇总（按区域/类型分组）、用电量异常波动、环比变化趋势
  3. 飞书推送日报

### 飞书推送

Skill 中直接用 `curl` 调用飞书 Webhook，无额外依赖。

### Crontab 配置

```
5 * * * *   openclaw /electric-analysis --mode=alert-check
0 8 * * *   openclaw /electric-analysis --mode=daily-report
```

## 边界条件

| 场景 | 处理 |
|------|------|
| API 不可达 | Skill 输出错误信息，不推送飞书 |
| 无告警 | 静默，不发消息 |
| 飞书 Webhook 未配置 | Skill 提示用户配置环境变量 |
| CSV 文件过旧（日报场景） | 提示「CSV 数据非今日，仅展示 API 实时数据」|

## 改动清单

| 文件 | 操作 |
|------|------|
| `src/scheduler.py` | 删除 FeishuSender 调用 |
| `~/.openclaw/skills/electric-analysis/SKILL.md` | 增加场景6、场景7 + crontab 说明 |
