# OpenClaw 告警接管 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除系统内置飞书推送，改由 OpenClaw 通过 REST API 获取告警数据、AI 分析后推送飞书。

**Architecture:** 系统侧删除 `FeishuSender` 调用（保留告警检测写入数据库），OpenClaw 侧扩展 `electric-analysis` skill 增加实时告警检查和每日分析日报两个场景，通过 crontab 定时触发。

**Tech Stack:** FastAPI REST API（已有）、OpenClaw Skill（SKILL.md）、curl、飞书 Webhook

---

### Task 1: 移除系统内置飞书推送

**Files:**
- Modify: `src/scheduler.py`

**Step 1: Write the failing test**

无需新测试。现有测试不依赖 FeishuSender 调用逻辑。验证方式为代码审查 + 服务启动。

**Step 2: 修改 src/scheduler.py**

移除 FeishuSender 导入和调用，保留告警检测逻辑：

```python
from apscheduler.schedulers.background import BackgroundScheduler

from src.db import get_db
from src.export import CsvExporter
from src.simulator import SimulationGenerator
from src.alert import AlertDetector


def run_hourly_tasks():
    db = next(get_db())
    try:
        generator = SimulationGenerator(db)
        records = generator.generate_hourly_data()
        print(f"Generated {len(records)} records")

        detector = AlertDetector(db)
        alerts = detector.detect_all()
        print(f"Detected {len(alerts)} new alerts")
    finally:
        db.close()


def run_daily_export():
    db = next(get_db())
    try:
        exporter = CsvExporter(db)
        exporter.export_all()
        print("CSV export completed")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_hourly_tasks, "cron", minute=0)
    scheduler.add_job(run_daily_export, "cron", hour=2)
    scheduler.start()
    return scheduler
```

**Step 3: 清理 src/alert/__init__.py 中的 FeishuSender 导出**

```python
from .detector import AlertDetector
from .rules import AlertType, Severity

__all__ = ["AlertDetector", "AlertType", "Severity"]
```

注意：不删除 `src/alert/feishu.py` 文件本身，保留为可复用模块。`src/config.py` 中的 `feishu_webhook_url` 也保留，OpenClaw skill 可能读取该配置。

**Step 4: 运行现有测试确认无破坏**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/scheduler.py src/alert/__init__.py
git commit -m "refactor: remove built-in Feishu push from scheduler, alerts now consumed via API"
```

---

### Task 2: 扩展 OpenClaw Skill — 增加告警检查和日报场景

**Files:**
- Modify: `~/.openclaw/skills/electric-analysis/SKILL.md`

**Step 1: 在 SKILL.md 中追加场景 6 和场景 7**

在现有「场景 5：时段用电模式」之后、「Fallback」之前，追加以下内容：

```markdown
### 场景 6：实时告警检查

触发词：有异常吗、当前告警、实时告警、alert-check

**注意：此场景通过 REST API 获取实时数据，不依赖 CSV 文件。**

```bash
# 获取当前未解决告警
RESPONSE=$(curl -s http://43.136.40.150:8000/api/alerts/active)
```

如果返回空数组 `[]`，输出「当前没有未解决的告警」，**不要推送飞书**。

如果有告警数据，执行以下分析：

```python
import json

alerts = json.loads('''RESPONSE_HERE''')  # 替换为实际 curl 返回值

# 按严重级别分组
from collections import Counter
by_severity = Counter(a["severity"] for a in alerts)
by_type = Counter(a["alert_type"] for a in alerts)

print(f"当前共 {len(alerts)} 条未解决告警")
print(f"按级别: {dict(by_severity)}")
print(f"按类型: {dict(by_type)}")

for a in alerts:
    print(f"  [{a['severity']}] {a['point_id']}: {a['message']}")
```

然后生成一份简洁的中文分析报告，包含：
1. 告警总数和严重级别分布
2. 每条告警的设备名、区域、异常类型和具体数值
3. 可能的原因分析和建议

最后通过飞书 Webhook 推送报告：

```bash
curl -s -X POST "$FEISHU_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "post",
    "content": {
      "post": {
        "zh_cn": {
          "title": "⚡ 电力告警分析报告",
          "content": [[{"tag": "text", "text": "YOUR_REPORT_HERE"}]]
        }
      }
    }
  }'
```

其中 `FEISHU_WEBHOOK_URL` 从环境变量读取。如果环境变量未设置，提示用户：「飞书 Webhook URL 未配置，请设置 FEISHU_WEBHOOK_URL 环境变量」。

### 场景 7：每日分析日报

触发词：日报、每日报告、daily-report、昨日汇总

此场景结合 REST API 实时告警数据 + CSV 历史数据生成综合日报。

**第一步：获取过去24小时告警**

```bash
RESPONSE=$(curl -s "http://43.136.40.150:8000/api/alerts?limit=500")
```

**第二步：结合 CSV 做趋势分析**

```python
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# 加载告警数据
all_alerts = json.loads('''RESPONSE_HERE''')
yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
recent_alerts = [a for a in all_alerts if a["created_at"][:10] == yesterday]

# 加载 CSV 用电数据
base = Path("data_export")
if (base / "_metadata.json").exists():
    devices = pd.read_csv(base / "devices.csv")
    data = pd.read_csv(base / "electric_data.csv", parse_dates=["time"])
    merged = data.merge(devices[["point_id", "area_name", "device_type"]], on="point_id")

    # 日环比
    daily = merged.groupby(merged["time"].dt.date)["incr"].sum()
    if len(daily) >= 2:
        today_val = daily.iloc[-1]
        yesterday_val = daily.iloc[-2]
        change_pct = ((today_val - yesterday_val) / yesterday_val * 100).round(2)

    # 区域排名
    area_ranking = merged[merged["time"].dt.date == merged["time"].dt.date.max()] \
        .groupby("area_name")["incr"].sum().sort_values(ascending=False).round(2)

    print("日报数据已准备")
else:
    print("CSV 数据不可用，仅使用 API 告警数据")
```

**第三步：生成日报**

生成的日报应包含以下板块：
1. **昨日告警汇总**：告警总数、按区域分组、按类型分组
2. **用电量概况**：总用电量、日环比变化率
3. **区域用电排名**：Top 5 区域及其用电量
4. **异常趋势**：连续告警的设备、反复出现的问题

通过飞书 Webhook 推送，格式同场景 6。
```

**Step 2: 在 SKILL.md 的规则部分追加 API 相关规则**

在现有规则列表末尾追加：

```markdown
6. API 地址为 `http://43.136.40.150:8000`，场景 6 和 7 通过 curl 调用 REST API
7. 飞书推送需要环境变量 `FEISHU_WEBHOOK_URL`，未设置时提示用户而非静默失败
8. 场景 6 在无告警时静默（不推送飞书），避免消息骚扰
```

**Step 3: 验证 SKILL.md 格式正确**

```bash
head -5 ~/.openclaw/skills/electric-analysis/SKILL.md
```

Expected: YAML frontmatter 完整。

**Step 4: Commit**

```bash
cd /Users/qiwu/personal-projects/ele
git add -f ~/.openclaw/skills/electric-analysis/SKILL.md 2>/dev/null || true
# SKILL.md 不在项目仓库中，无需 git commit
# 仅确认文件内容正确
```

注意：`~/.openclaw/skills/` 不在 ele 项目仓库中，无需 git 操作。

---

### Task 3: 配置 OpenClaw Crontab

**Files:**
- OpenClaw crontab 配置（通过 OpenClaw CLI 设置）

**Step 1: 设置每小时告警检查**

```bash
# 通过 OpenClaw CLI 配置 crontab（具体命令取决于 OpenClaw 版本）
# 每小时第 5 分钟执行告警检查
openclaw cron add "5 * * * * /electric-analysis --mode=alert-check"
```

**Step 2: 设置每日日报**

```bash
# 每天 08:00 生成日报
openclaw cron add "0 8 * * * /electric-analysis --mode=daily-report"
```

**Step 3: 验证 crontab 配置**

```bash
openclaw cron list
```

Expected: 显示两条定时任务。

**Step 4: 配置飞书 Webhook 环境变量**

确保 OpenClaw 运行环境中有 `FEISHU_WEBHOOK_URL` 环境变量。可在 `~/.openclaw/config` 或 shell profile 中设置：

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_HOOK_ID"
```

---

### Task 4: 端到端验证

**Step 1: 确认系统侧告警检测仍正常工作**

```bash
# SSH 到服务器，检查 docker 日志
ssh -i /Users/qiwu/GZ.pem root@43.136.40.150 "docker logs ele-app --tail 20"
```

Expected: 看到 `Generated X records` 和 `Detected Y new alerts`，但不再有 `[Feishu]` 相关日志。

**Step 2: 确认 REST API 可用**

```bash
curl -s http://43.136.40.150:8000/api/alerts/active | python3 -m json.tool | head -20
```

Expected: 返回 JSON 告警数组。

**Step 3: 手动触发 OpenClaw 告警检查**

```bash
openclaw /electric-analysis "检查当前有没有异常设备"
```

Expected: OpenClaw 调用 API、分析数据、输出中文报告（如有告警则推送飞书）。

**Step 4: 手动触发日报**

```bash
openclaw /electric-analysis "生成昨日用电日报"
```

Expected: 输出包含告警汇总、用电量概况、区域排名的日报。
