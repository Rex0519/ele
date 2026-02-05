from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.simulator.generator import SimulationGenerator


class DataMaintenance:
    def __init__(self, db: Session):
        self.db = db

    def cleanup_expired_alerts(self, days: int = 30) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        result = self.db.execute(
            text("DELETE FROM alert WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        self.db.commit()
        return result.rowcount

    def backfill_missing_data(self, days: int = 30) -> int:
        result = self.db.execute(text("SELECT MAX(time) FROM electric_data"))
        last_time = result.scalar()

        now = datetime.now()
        if last_time is None:
            start = now - timedelta(days=days)
        else:
            start = last_time.replace(tzinfo=None) if last_time.tzinfo else last_time

        start = start.replace(minute=0, second=0, microsecond=0)
        current = start + timedelta(hours=1)
        target = now.replace(minute=0, second=0, microsecond=0)

        if current > target:
            return 0

        generator = SimulationGenerator(self.db)
        count = 0
        while current < target:
            generator.generate_hourly_data(target_time=current)
            count += 1
            current += timedelta(hours=1)

        return count
