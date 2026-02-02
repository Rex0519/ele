from datetime import datetime

from sqlalchemy import BigInteger, Double, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConfigArea(Base):
    __tablename__ = "config_area"

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str | None] = mapped_column(String(20))
    park_id: Mapped[int | None] = mapped_column(Integer)
    is_delete: Mapped[int] = mapped_column(Integer, default=0)


class ConfigItem(Base):
    __tablename__ = "config_item"

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str | None] = mapped_column(String(20))
    park_id: Mapped[int | None] = mapped_column(Integer)
    is_delete: Mapped[int] = mapped_column(Integer, default=0)


class Device(Base):
    __tablename__ = "device"

    device_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_no: Mapped[str | None] = mapped_column(String(50))
    device_name: Mapped[str | None] = mapped_column(String(200))
    point_type_id: Mapped[int | None] = mapped_column(BigInteger)
    region_id: Mapped[int | None] = mapped_column(BigInteger)
    building_id: Mapped[int | None] = mapped_column(BigInteger)
    floor_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[int] = mapped_column(Integer, default=1)
    remark: Mapped[str | None] = mapped_column(Text)


class ConfigDevice(Base):
    __tablename__ = "config_device"

    config_device_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    config_id: Mapped[int | None] = mapped_column(BigInteger)
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    device_level: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str | None] = mapped_column(String(20))
    config_type: Mapped[str | None] = mapped_column(String(20))


class ElectricData(Base):
    __tablename__ = "electric_data"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    device_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    point_id: Mapped[str | None] = mapped_column(String(50))
    value: Mapped[float | None] = mapped_column(Double)
    incr: Mapped[float | None] = mapped_column(Double)


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    alert_type: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str | None] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Double)
    threshold: Mapped[float | None] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ThresholdConfig(Base):
    __tablename__ = "threshold_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    metric: Mapped[str] = mapped_column(String(20), default="incr")
    min_value: Mapped[float | None] = mapped_column(Double)
    max_value: Mapped[float | None] = mapped_column(Double)
    severity: Mapped[str] = mapped_column(String(10), default="WARNING")


class DeviceProfile(Base):
    __tablename__ = "device_profile"

    point_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    mean_value: Mapped[float | None] = mapped_column(Double)
    std_value: Mapped[float | None] = mapped_column(Double)
    min_value: Mapped[float | None] = mapped_column(Double)
    max_value: Mapped[float | None] = mapped_column(Double)
    last_value: Mapped[float] = mapped_column(Double, default=0)
