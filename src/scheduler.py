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
