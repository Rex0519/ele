import hashlib
import random
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.models import DeviceProfile, ElectricData
from src.simulator.profiles import get_time_factor


def generate_increment(mean: float, std: float, hour: int, anomaly_rate: float = 0.03) -> float:
    """生成符合时段特征的增量，有小概率产生异常值"""
    time_factor = get_time_factor(hour)
    base = mean * time_factor

    if random.random() < anomaly_rate:
        if random.random() < 0.5:
            incr = base * random.uniform(2.5, 4.0)
        else:
            incr = base * random.uniform(0.02, 0.15)
    else:
        noise = random.gauss(0, std * 0.3) if std > 0 else 0
        incr = max(0, base + noise)

    return round(incr, 2)


class SimulationGenerator:
    def __init__(self, db: Session):
        self.db = db

    def generate_hourly_data(self, target_time: datetime | None = None) -> list[ElectricData]:
        """为所有设备生成一小时的数据"""
        ts = target_time or datetime.now(timezone.utc)
        ts = ts.replace(minute=0, second=0, microsecond=0)
        hour = ts.hour
        records = []

        profiles = self.db.query(DeviceProfile).all()
        for profile in profiles:
            incr = generate_increment(
                mean=profile.mean_value or 0,
                std=profile.std_value or 0,
                hour=hour,
            )
            new_value = (profile.last_value or 0) + incr

            device_id = int(hashlib.sha256(profile.point_id.encode()).hexdigest(), 16) % (10**18)
            record = ElectricData(
                time=ts,
                device_id=device_id,
                point_id=profile.point_id,
                value=round(new_value, 2),
                incr=incr,
            )
            records.append(record)

            profile.last_value = new_value

        if records:
            values = [
                {
                    "time": r.time,
                    "device_id": r.device_id,
                    "point_id": r.point_id,
                    "value": r.value,
                    "incr": r.incr,
                }
                for r in records
            ]
            self.db.execute(
                text(
                    "INSERT INTO electric_data (time, device_id, point_id, value, incr) "
                    "VALUES (:time, :device_id, :point_id, :value, :incr) "
                    "ON CONFLICT (time, point_id) DO NOTHING"
                ),
                values,
            )
            self.db.commit()
        return records
