from apscheduler.schedulers.background import BackgroundScheduler

from src.db import get_db
from src.simulator import SimulationGenerator
from src.alert import AlertDetector


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
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """启动调度器"""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_hourly_tasks, "cron", minute=0)
    scheduler.start()
    return scheduler
