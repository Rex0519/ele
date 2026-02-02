import pytest
from src.alert.rules import AlertType, Severity, check_threshold, check_trend


def test_check_threshold_exceed_max():
    result = check_threshold(value=150.0, min_val=0.0, max_val=100.0)
    assert result is not None
    assert result["type"] == AlertType.THRESHOLD
    assert "超过上限" in result["message"]


def test_check_threshold_below_min():
    result = check_threshold(value=-5.0, min_val=0.0, max_val=100.0)
    assert result is not None
    assert "低于下限" in result["message"]


def test_check_threshold_normal():
    result = check_threshold(value=50.0, min_val=0.0, max_val=100.0)
    assert result is None


def test_check_trend_spike():
    result = check_trend(current=180.0, previous=100.0)
    assert result is not None
    assert result["type"] == AlertType.TREND_SPIKE


def test_check_trend_drop():
    result = check_trend(current=20.0, previous=100.0)
    assert result is not None
    assert result["type"] == AlertType.TREND_DROP


def test_check_trend_normal():
    result = check_trend(current=110.0, previous=100.0)
    assert result is None
