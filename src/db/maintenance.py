from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.simulator.generator import SimulationGenerator


class DataMaintenance:
    def __init__(self, db: Session):
        self.db = db

    def cleanup_expired_alerts(self, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = self.db.execute(
            text("DELETE FROM alert WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        self.db.commit()
        return result.rowcount

    def backfill_missing_data(self, days: int = 30) -> int:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        start = start.replace(minute=0, second=0, microsecond=0)
        target = now.replace(minute=0, second=0, microsecond=0)

        # 查询已有数据的时间点
        result = self.db.execute(
            text("SELECT DISTINCT time_bucket('1 hour', time) AS hour FROM electric_data WHERE time >= :start"),
            {"start": start},
        )
        existing_hours = {row[0].replace(tzinfo=timezone.utc) if row[0].tzinfo is None else row[0] for row in result}

        # 生成所有应有的时间点，找出缺失的
        current = start
        missing = []
        while current <= target:
            if current not in existing_hours:
                missing.append(current)
            current += timedelta(hours=1)

        if not missing:
            return 0

        generator = SimulationGenerator(self.db)
        for ts in missing:
            generator.generate_hourly_data(target_time=ts)

        return len(missing)
