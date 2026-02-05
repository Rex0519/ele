import pytest
from src.simulator.profiles import get_time_factor
from src.simulator.generator import generate_increment, SimulationGenerator


def test_time_factor_night():
    factor = get_time_factor(3)
    assert factor == 0.5


def test_time_factor_morning_peak():
    factor = get_time_factor(8)
    assert factor == 1.3


def test_time_factor_work():
    factor = get_time_factor(14)
    assert factor == 1.0


def test_time_factor_evening_peak():
    factor = get_time_factor(19)
    assert factor == 1.4


def test_generate_increment():
    incr = generate_increment(mean=10.0, std=2.0, hour=12)
    assert incr >= 0


from unittest.mock import MagicMock
from datetime import datetime
from src.db.models import DeviceProfile, ElectricData


def test_generate_hourly_data_with_target_time():
    """generate_hourly_data 使用 target_time 而非 now()"""
    mock_db = MagicMock()
    profile = DeviceProfile(
        point_id="test-device-001",
        mean_value=10.0,
        std_value=2.0,
        last_value=100.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    target = datetime(2026, 1, 15, 14, 0, 0)
    gen = SimulationGenerator(mock_db)
    records = gen.generate_hourly_data(target_time=target)

    assert len(records) == 1
    assert records[0].time == target
    assert records[0].point_id == "test-device-001"
    assert records[0].value > 100.0


def test_generate_hourly_data_default_uses_now():
    """不传 target_time 时行为不变"""
    mock_db = MagicMock()
    profile = DeviceProfile(
        point_id="test-device-002",
        mean_value=5.0,
        std_value=1.0,
        last_value=50.0,
    )
    mock_db.query.return_value.all.return_value = [profile]

    gen = SimulationGenerator(mock_db)
    records = gen.generate_hourly_data()

    assert len(records) == 1
    now = datetime.now()
    assert abs((records[0].time - now).total_seconds()) < 5
