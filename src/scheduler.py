from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.db import get_db
from src.simulator import SimulationGenerator
from src.alert import AlertDetector
from src.alert.feishu import FeishuSender


def run_hourly_tasks():
    db = next(get_db())
    try:
        generator = SimulationGenerator(db)
        records = generator.generate_hourly_data()
        print(f"Generated {len(records)} records")

        detector = AlertDetector(db)
        alerts = detector.detect_all()
        print(f"Detected {len(alerts)} new alerts")

        if settings.feishu_webhook_url and alerts:
            sender = FeishuSender(settings.feishu_webhook_url)
            sender.send(alerts)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_hourly_tasks, "cron", minute=0)
    scheduler.start()
    return scheduler
