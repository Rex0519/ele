import asyncio

from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.db import get_db
from src.simulator import SimulationGenerator
from src.alert import AlertDetector
from src.alert.sms import DummySmsSender


def run_hourly_tasks():
    """每小时执行的任务"""
    db = next(get_db())
    try:
        generator = SimulationGenerator(db)
        records = generator.generate_hourly_data()
        print(f"Generated {len(records)} records")

        detector = AlertDetector(db)
        alerts = detector.detect_all()
        print(f"Detected {len(alerts)} new alerts")

        # Send SMS for high severity alerts
        if settings.sms_enabled and alerts:
            high_alerts = [a for a in alerts if a.severity in ("HIGH", "CRITICAL")]
            if high_alerts:
                _send_alert_sms(high_alerts)
    finally:
        db.close()


def _send_alert_sms(alerts):
    """Send SMS notification for alerts"""
    if not settings.sms_phones:
        return

    messages = [f"[{a.severity}] {a.message}" for a in alerts[:5]]
    content = f"电力告警 ({len(alerts)}条):\n" + "\n".join(messages)
    if len(alerts) > 5:
        content += f"\n...还有{len(alerts) - 5}条"

    sender = DummySmsSender()
    asyncio.run(sender.send(settings.sms_phones, content))


def start_scheduler() -> BackgroundScheduler:
    """启动调度器"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_hourly_tasks, "cron", minute=0)
    scheduler.start()
    return scheduler
