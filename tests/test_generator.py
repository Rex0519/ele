import pytest
from src.simulator.profiles import get_time_factor
from src.simulator.generator import generate_increment


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
