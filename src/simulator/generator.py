import random
from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models import DeviceProfile, ElectricData
from src.simulator.profiles import get_time_factor


def generate_increment(mean: float, std: float, hour: int) -> float:
    """生成符合时段特征的增量"""
    time_factor = get_time_factor(hour)
    noise = random.gauss(0, std * 0.1) if std > 0 else 0
    incr = max(0, mean * time_factor + noise)
    return round(incr, 2)


class SimulationGenerator:
    def __init__(self, db: Session):
        self.db = db

    def generate_hourly_data(self, target_time: datetime | None = None) -> list[ElectricData]:
        """为所有设备生成一小时的数据"""
        ts = target_time or datetime.now()
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

            record = ElectricData(
                time=ts,
                device_id=hash(profile.point_id) % (10**18),
                point_id=profile.point_id,
                value=round(new_value, 2),
                incr=incr,
            )
            records.append(record)

            profile.last_value = new_value

        self.db.add_all(records)
        self.db.commit()
        return records
